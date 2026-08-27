from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Literal

from hiresense.ingestion.domain.cross_source_deduplicator import consolidate_cross_source_jobs
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.job_filter import (
    JobQueryParams,
    PaginatedResult,
    filter_and_paginate,
)
from hiresense.ingestion.domain.job_query_service import JobQueryService

from hiresense.ingestion.domain.models import NormalizedJob

from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
from hiresense.ingestion.domain.job_scorer import combine_fit_score, score_job_against_skills
from hiresense.ingestion.domain.opportunity import InternationalPathway, OpportunityType
from hiresense.ingestion.domain.score_change_filter import changed_score_updates
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
from hiresense.ingestion.domain.seniority import SeniorityLevel
from hiresense.ingestion.domain.job_sort import sort_jobs
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate
from hiresense.matching.domain.deep_analysis_result import DeepAnalysisResult
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService
from hiresense.network.domain import normalize_company
from hiresense.network.ports import ContactsRepositoryPort
from hiresense.portfolio.domain import PortfolioEnrichmentService
from hiresense.profile.domain import ProfileService

_ALLOWED_SORTS = frozenset(
    f"{field}_{direction}"
    for field in ("match", "posted", "title", "company", "location", "source")
    for direction in ("asc", "desc")
) | {"date_desc", "date_asc"}


async def _gather_profile(
    profile_service: ProfileService,
    portfolio_enrichment: PortfolioEnrichmentService | None = None,
) -> tuple[list[str], str]:
    """Flatten all stored profiles into candidate skills + a summary blob.

    Shared by the list endpoint (quick scoring) and the analysis endpoint
    (deep scoring) so both score against the same profile representation.
    When the portfolio module is configured, its synced projects are appended
    (extra skills + a compact projects block) so scoring sees real projects.
    """
    candidate_skills: list[str] = []
    summary_parts: list[str] = []
    for profile in await profile_service.list_profiles():
        candidate_skills.extend(profile.skills)
        for section in profile.sections:
            summary_parts.append(section.content)
    if portfolio_enrichment is not None:
        extra_skills, extra_text = await portfolio_enrichment.enrichment()
        candidate_skills.extend(extra_skills)
        if extra_text:
            summary_parts.append(extra_text)
    return candidate_skills, "\n".join(summary_parts)


async def _persist_score_updates_by_bucket(
    updates: list[ScoreUpdate],
    bucket_by_job_id: dict[str, Literal["boards", "portals"]],
    job_query: JobQueryService,
    scanner: PortalScanner,
) -> None:
    """Persist score changes through the repository that owns each job."""
    updates_by_bucket: dict[str, list[ScoreUpdate]] = {"boards": [], "portals": []}
    for update in updates:
        bucket = bucket_by_job_id.get(update.job_id)
        if bucket is not None:
            updates_by_bucket[bucket].append(update)

    persist_tasks = []
    if board_updates := updates_by_bucket["boards"]:
        persist_tasks.append(asyncio.to_thread(job_query.persist_scores_batch, board_updates))
    if portal_updates := updates_by_bucket["portals"]:
        persist_tasks.append(asyncio.to_thread(scanner.persist_scores_batch, portal_updates))
    if persist_tasks:
        await asyncio.gather(*persist_tasks)


def _apply_quick(job: NormalizedJob, quick: QuickMatchResult | None) -> NormalizedJob:
    """Overlay an LLM quick result onto a job for the response.

    The displayed `match_score` becomes the LLM score (more accurate than the
    heuristic), and the quick verdict/reasons/dealbreakers ride along for the
    detail panel. Jobs without a quick result keep their heuristic score.
    """
    if quick is None:
        return job
    return job.model_copy(
        update={
            "match_score": quick.score,
            "llm_score": quick.score,
            "verdict": quick.verdict.value,
            "reasons": list(quick.reasons),
            "dealbreakers": list(quick.dealbreakers),
        }
    )


class DeepAnalysisUnavailableError(RuntimeError):
    """No deep-analysis service is wired (no LLM configured)."""


class JobFeedService:
    """The job-list use case: ingestion + matching + profile + network + portfolio.

        This was the body of `GET /ingestion/jobs`, a 327-line handler that imported
        five other bounded contexts — mostly into their `domain/` internals rather
        than through ports — and assembled them itself. That made the route a second
        composition root: cross-context wiring living outside `composition/`, where
        the rest of it is declared.

    It lives beside the route it came from rather than in `composition/`: importing
        a composition submodule from `api/` cycles, because `composition/__init__`
        eagerly imports every builder and the builders import each context's api
        package. Extracting the use case and deciding which layer owns it are
        separate changes; this is the first. The composition-layer restructure is
        where it should land.
    """

    def __init__(
        self,
        *,
        job_query: JobQueryService,
        scanner: PortalScanner,
        profile_service: ProfileService,
        portfolio_enrichment: PortfolioEnrichmentService | None,
        semantic_scoring: SemanticScoringService | None,
        quick_scoring: QuickScoringService | None,
        pre_ranker: SemanticPreRanker | None,
        network_repo: ContactsRepositoryPort | None,
        deep_analysis: DeepAnalysisService | None,
        settings: Any | None,
    ) -> None:
        self._job_query = job_query
        self._scanner = scanner
        self._profile_service = profile_service
        self._portfolio_enrichment = portfolio_enrichment
        self._semantic_scoring = semantic_scoring
        self._quick_scoring = quick_scoring
        self._pre_ranker = pre_ranker
        self._network_repo = network_repo
        self._deep_analysis = deep_analysis
        self._settings = settings

    async def list_jobs(
        self,
        *,
        tab: Literal["boards", "portals", "all"],
        page: int = 1,
        page_size: int = 20,
        source: str | None = None,
        company: str | None = None,
        keyword: str | None = None,
        location: str | None = None,
        skills: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        user_location: str | None = None,
        strict_location: bool = False,
        sort: str | None = None,
        min_score: float | None = None,
        seniority: list[SeniorityLevel] | None = None,
        max_years_experience: int | None = None,
        include_closed: bool = False,
        rescore: bool = True,
        max_age_days: int | None = None,
        include_low_quality: bool = False,
        opportunity_type: OpportunityType | None = None,
        international_pathway: InternationalPathway | None = None,
    ) -> PaginatedResult:
        # Default min_score / max_age_days from settings when the client doesn't
        # specify them (pass 0 explicitly to disable either filter). Tests mount the
        # router on a bare FastAPI without app.state.settings — fall back to
        # no-filter in that case.
        settings = self._settings
        if min_score is None and settings is not None:
            min_score = settings.ingestion_min_match_score
        if max_age_days is None and settings is not None:
            max_age_days = settings.ingestion_max_job_age_days
        # Clamp page_size to the configured cap (bounds per-request memory and
        # quick-scoring cost). The cap lives in settings, so it can't be a static
        # Query(le=) bound.
        if settings is not None:
            page_size = min(page_size, settings.ingestion_max_page_size)
        # Push the cheap selective predicates into the repository (SQL WHERE) so
        # closed/filtered rows never reach the scoring pipeline below.
        # filter_and_paginate re-applies them idempotently alongside the
        # Python-only heuristics.
        criteria = JobListCriteria(
            include_closed=include_closed,
            include_low_quality=include_low_quality,
            source=source,
            company=company,
            date_from=date_from,
            date_to=date_to,
        )
        # Corpus load + score persists below run sync SQLAlchemy sessions; offload
        # to worker threads so they don't block the event loop. The combined feed
        # deliberately loads both buckets before consolidation: that is the only
        # path where an aggregator listing and the company's ATS listing can meet.
        if tab == "all":
            board_jobs, portal_jobs = await asyncio.gather(
                asyncio.to_thread(self._job_query.list_jobs, criteria),
                asyncio.to_thread(self._scanner.list_jobs, criteria),
            )
        elif tab == "boards":
            board_jobs = await asyncio.to_thread(self._job_query.list_jobs, criteria)
            portal_jobs = []
        else:
            board_jobs = []
            portal_jobs = await asyncio.to_thread(self._scanner.list_jobs, criteria)
        bucket_by_job_id: dict[str, Literal["boards", "portals"]] = {
            job.id: "boards" for job in board_jobs
        }
        bucket_by_job_id.update({job.id: "portals" for job in portal_jobs})
        all_jobs = board_jobs + portal_jobs
        # Source identities remain separate in persistence for lifecycle tracking.
        # The feed is consolidated before scoring so equivalent cross-source posts
        # do not consume a page slot or duplicate LLM work.
        all_jobs = consolidate_cross_source_jobs(all_jobs)
        # Snapshot the persisted scores so the corpus-wide persist below only writes
        # rows whose score actually changed this request (#132) — otherwise every GET
        # (including plain pagination / sort-only reloads) issues a full-corpus
        # UPDATE, N times over for the several concurrent list calls the UI fires.
        original_scores = {job.id: (job.match_score, job.semantic_score) for job in all_jobs}

        candidate_skills, candidate_summary = await _gather_profile(
            self._profile_service, self._portfolio_enrichment
        )

        # Default to match-descending so the ranking is actually applied when the
        # client omits sort (otherwise the page reflects insertion order — #18).
        effective_sort = sort or "match_desc"
        if effective_sort not in _ALLOWED_SORTS:
            effective_sort = "match_desc"

        # Pre-compute skill-overlap per job (cheap) and fold in any *persisted*
        # semantic score so the sort key matches the displayed value. Keep the
        # raw skill score in a side dict so we can re-combine after page-level
        # semantic scoring without recomputing the overlap.
        skill_by_id: dict[str, float | None] = {}
        if candidate_skills:
            skill_set = {s.lower() for s in candidate_skills if s}
            for job in all_jobs:
                skill_by_id[job.id] = score_job_against_skills(job, skill_set)
            all_jobs = [
                j.model_copy(
                    update={"match_score": combine_fit_score(skill_by_id[j.id], j.semantic_score)}
                )
                for j in all_jobs
            ]

        # GLOBAL pre-rank BEFORE pagination (#18 fix): use the pgvector ANN to set
        # semantic_score + combined match_score across the WHOLE corpus, so a
        # high-semantic / low-keyword job can reach page 1 instead of being scored
        # only after it's already been paginated off. Passthrough (no vector store,
        # empty profile, etc.) leaves the skill-only ordering intact.
        if self._pre_ranker is not None:
            if tab == "all":
                ranked_boards, ranked_portals = await asyncio.gather(
                    self._pre_ranker.rerank(
                        [job for job in all_jobs if bucket_by_job_id[job.id] == "boards"],
                        skill_by_id,
                        candidate_skills,
                        candidate_summary,
                        bucket="boards",
                    ),
                    self._pre_ranker.rerank(
                        [job for job in all_jobs if bucket_by_job_id[job.id] == "portals"],
                        skill_by_id,
                        candidate_skills,
                        candidate_summary,
                        bucket="portals",
                    ),
                )
                all_jobs = ranked_boards + ranked_portals
            else:
                all_jobs = await self._pre_ranker.rerank(
                    all_jobs, skill_by_id, candidate_skills, candidate_summary, bucket=tab
                )

        if candidate_skills:
            score_updates = changed_score_updates(all_jobs, original_scores)
            if score_updates:
                await _persist_score_updates_by_bucket(
                    score_updates, bucket_by_job_id, self._job_query, self._scanner
                )

        # GLOBAL apply of already-cached Tier-1 LLM scores BEFORE pagination. The
        # LLM quick score is the accurate, displayed match value, but it was only
        # ever applied to the visible page — so the global sort ranked by the
        # heuristic blend, which is source-biased (hn_hiring scores via verbose
        # text-mention and saturates; getonboard's structured tags get dilution-
        # capped low). A genuinely strong job from a "weak-heuristic" source was
        # buried off page 1 and never LLM-scored in the all-sources view, even
        # though it ranked highly once its source was filtered.
        #
        # Reading the LLM cache (keyed by job_id+profile_hash, source-agnostic) for
        # the WHOLE corpus and overriding match_score where we have a score makes
        # the global ranking consistent with the displayed value across every
        # filter. This is cache-only (`llm_on_miss=False`) — no LLM calls, one bulk
        # read — so it's safe on the sort-only fast path too. Visible-page cache
        # misses are filled by the page-level pass below and improve later rankings.
        # Applied AFTER persist so the persisted row score stays the heuristic blend
        # (the LLM score lives in its own cache); this override is request-scoped.
        #
        # GATED to match-sort OR an active min_score filter — this pass matters on
        # two independent axes, either one is enough to require it:
        #  (a) RANKING on match-sort: a cached LLM score must be able to pull a
        #      job onto page 1 ahead of the heuristic order.
        #  (b) FILTER MEMBERSHIP on any sort: `filter_and_paginate` below culls
        #      `all_jobs` by `match_score >= min_score` BEFORE the page-level
        #      overlay ever runs. Skipping this pass means that filter reads the
        #      stale heuristic score, so a job whose cached LLM score clears the
        #      threshold but whose heuristic score doesn't gets wrongly excluded
        #      from the result set entirely — not just mis-ranked.
        # With neither condition true (non-match sort, no min_score), order
        # doesn't depend on match_score and nothing gets filtered by it, so
        # reading the LLM cache for the WHOLE corpus on every GET would be pure
        # waste — skipped. Display values stay correct regardless: the page-level
        # pass below (after pagination) overlays quick scores onto `result.jobs`
        # unconditionally, regardless of sort.
        min_score_active = min_score is not None and min_score > 0
        if (
            self._quick_scoring is not None
            and (candidate_skills or candidate_summary)
            and (effective_sort.startswith("match_") or min_score_active)
        ):
            cached_quick = await self._quick_scoring.score_page(
                all_jobs, candidate_skills, candidate_summary, llm_on_miss=False
            )
            if cached_quick:
                all_jobs = [_apply_quick(j, cached_quick.get(j.id)) for j in all_jobs]

            # SOURCE CHAMPIONS (cold-start fairness). The cache-only pass above can
            # only rank what was LLM-scored before, and the page-level pass below
            # only scores the visible page — so with a cold cache the source-biased
            # heuristic decides who ever GETS an accurate score: page 1 fills with
            # the verbose-text sources, those get scored, and a genuinely strong
            # job from a weak-heuristic source (getonboard's structured tags) stays
            # buried until the user happens to filter by that source. Break the
            # loop by LLM-scoring the top-K heuristic champions of EVERY source on
            # a full rescore of the unfiltered match-sorted view. The champion set
            # is the stable heuristic top-K per source (cached members are counted
            # but not re-sent), so once cached this pass costs zero LLM calls.
            # Match-sort only (unlike the outer gate): champions exist to fix
            # RANKING fairness, which is meaningless under a non-match sort even
            # if min_score is what triggered the outer pass.
            # Two cold-start failures, fixed in ONE batched LLM pass:
            #  * DEPTH (window) — the page-level pass below scores only the
            #    visible 20, but page 1 is *selected* before any real score
            #    exists. A job the heuristic ranks 40th never reaches a page, so
            #    it never gets scored, so it never rises: the displayed top-20
            #    stayed wrong until several requests had warmed the cache.
            #  * FAIRNESS (champions) — the heuristic is source-biased, so
            #    without a per-source floor page 1 fills with the verbose-text
            #    sources and a strong getonboard job (structured tags) stays
            #    buried until the user filters by that source.
            # Both select from the same heuristic ranking, so they share one
            # score_page call; already-cached members cost nothing, which drives
            # the steady-state extra LLM cost to zero.
            champions_k = (
                settings.ingestion_source_champions_per_source if settings is not None else 0
            )
            window_n = settings.ingestion_match_scoring_window if settings is not None else 0
            if (
                rescore
                and (champions_k > 0 or window_n > 0)
                and effective_sort.startswith("match_")
            ):
                ranked = sorted(all_jobs, key=lambda j: j.match_score or 0.0, reverse=True)
                selected: dict[str, NormalizedJob] = {}
                if window_n > 0:
                    for job in ranked[:window_n]:
                        selected[job.id] = job
                # Champions stay all-sources-only: a per-source floor is
                # meaningless once the view is already filtered to one source.
                if champions_k > 0 and source is None:
                    taken: dict[str, int] = {}
                    for job in ranked:
                        if taken.get(job.source, 0) >= champions_k:
                            continue
                        taken[job.source] = taken.get(job.source, 0) + 1
                        selected[job.id] = job
                priority = [j for j in selected.values() if j.id not in cached_quick]
                if priority:
                    priority_quick = await self._quick_scoring.score_page(
                        priority, candidate_skills, candidate_summary, llm_on_miss=True
                    )
                    if priority_quick:
                        all_jobs = [_apply_quick(j, priority_quick.get(j.id)) for j in all_jobs]

        params = JobQueryParams(
            page=page,
            page_size=page_size,
            source=source,
            company=company,
            keyword=keyword,
            location=location,
            skills=skills,
            date_from=date_from,
            date_to=date_to,
            user_location=user_location,
            strict_location=strict_location,
            sort=effective_sort,
            min_score=min_score,
            seniority_levels=seniority,
            max_years_experience=max_years_experience,
            include_closed=include_closed,
            max_age_days=max_age_days,
            include_low_quality=include_low_quality,
            opportunity_type=opportunity_type,
            international_pathway=international_pathway,
        )
        result = filter_and_paginate(all_jobs, params)

        # Semantic scoring is bounded to the visible page so the first request
        # after a backend restart doesn't block on 1000+ embeddings. Each request
        # only computes semantic for jobs on this page that don't yet have one;
        # the persisted score feeds back into the sort on subsequent calls.
        needs_semantic = [j for j in result.jobs if j.semantic_score is None]
        if (
            self._semantic_scoring is not None
            and (candidate_skills or candidate_summary)
            and needs_semantic
        ):
            scored = await self._semantic_scoring.score_jobs(
                needs_semantic, candidate_skills, candidate_summary
            )
            scored_by_id = {j.id: j.semantic_score for j in scored}
            result.jobs = [
                j.model_copy(
                    update={
                        "semantic_score": scored_by_id.get(j.id, j.semantic_score),
                    }
                )
                for j in result.jobs
            ]
            # Re-combine match_score using the skill side dict + fresh semantic.
            result.jobs = [
                j.model_copy(
                    update={
                        "match_score": combine_fit_score(skill_by_id.get(j.id), j.semantic_score)
                    }
                )
                for j in result.jobs
            ]
            await _persist_score_updates_by_bucket(
                [ScoreUpdate(j.id, j.match_score, j.semantic_score) for j in result.jobs],
                bucket_by_job_id,
                self._job_query,
                self._scanner,
            )
            # Page-level re-sort so the order reflects the post-semantic match_score
            # that the user actually sees. Phase-1 sort happens pre-pagination on
            # skill-only scores; without this the displayed % column looks unsorted.
            # Only match-field sorts depend on post-pagination scores; every other
            # field's order from filter_and_paginate is already final.
            if effective_sort.startswith("match_"):
                result.jobs = sort_jobs(result.jobs, effective_sort)

        # Tier-1 LLM quick scoring of the visible page (cheap model, one batched
        # call, cached per (job_id, profile_hash)). Runs *after* pagination so the
        # min_score gate never culls a job on a not-yet-computed LLM score. The LLM
        # score replaces the displayed match_score when available; jobs without one
        # keep the heuristic blend. Cache hits make repeat views instant.
        #
        # `rescore=False` is the sort-only / pagination fast path (#76): the result
        # set and order are already determined by the (cheap) skill + ANN + min_score
        # steps above, which still ran. We only DEFER the blocking LLM round-trip —
        # quick scoring runs cache-only (`llm_on_miss=False`), so a reorder reuses
        # already-computed scores instantly and newly-surfaced jobs show their
        # heuristic blend until the next full rescore fills the cache. Clients send
        # rescore=False only for pure reorder/pagination; any filter, tab, feedback
        # or fetch change keeps the default (full LLM scoring of the page).
        if self._quick_scoring is not None and (candidate_skills or candidate_summary):
            quick_results = await self._quick_scoring.score_page(
                result.jobs, candidate_skills, candidate_summary, llm_on_miss=rescore
            )
            if quick_results:
                result.jobs = [_apply_quick(j, quick_results.get(j.id)) for j in result.jobs]
                if effective_sort.startswith("match_"):
                    result.jobs = sort_jobs(result.jobs, effective_sort)

        # Semantic and quick scoring can update a visible job after the first
        # membership gate. Apply the same floor once more so a newly computed
        # low score cannot leak into the response. A missing score remains
        # visible because there is no profile-dependent value to compare.
        if min_score is not None:
            result.jobs = [
                job
                for job in result.jobs
                if job.match_score is None or job.match_score >= min_score
            ]

        # "You know someone here" badge data: one GROUP BY over the visible page's
        # companies. Contacts never enter prompts — this is a display-only count.
        if self._network_repo is not None and result.jobs:
            company_key_by_job = {job.id: normalize_company(job.company) for job in result.jobs}
            counts = await asyncio.to_thread(
                self._network_repo.count_by_companies,
                sorted({key for key in company_key_by_job.values() if key}),
            )
            result.connections_by_job = {
                job_id: counts[key] for job_id, key in company_key_by_job.items() if counts.get(key)
            }

        return result

    async def get_job(self, job_id: str) -> NormalizedJob | None:
        """One job, with the cached Tier-1 quick score overlaid.

        The detail header must open at the SAME value the list showed. Without
        the overlay it returned the raw persisted heuristic blend, so the header
        flashed a lower percentage before deep analysis replaced it. Cache-only
        (`llm_on_miss=False`) — no LLM call.
        """
        job = await self._find_job(job_id)
        if job is None or self._quick_scoring is None:
            return job
        candidate_skills, candidate_summary = await _gather_profile(
            self._profile_service, self._portfolio_enrichment
        )
        if not (candidate_skills or candidate_summary):
            return job
        cached = await self._quick_scoring.score_page(
            [job], candidate_skills, candidate_summary, llm_on_miss=False
        )
        return _apply_quick(job, cached.get(job.id))

    async def analyze_job(self, job_id: str, *, force: bool = False) -> DeepAnalysisResult | None:
        """Deep, single-job match analysis. None when the job is unknown.

        Raises UpstreamUnavailableError-free: the caller maps a missing
        deep-analysis service to 503, mirroring the previous route behaviour.
        """
        job = await self._find_job(job_id)
        if job is None:
            return None
        if self._deep_analysis is None:
            raise DeepAnalysisUnavailableError("Deep analysis is not available")
        candidate_skills, candidate_summary = await _gather_profile(
            self._profile_service, self._portfolio_enrichment
        )
        return await self._deep_analysis.analyze(
            job, candidate_skills, candidate_summary, force=force
        )

    async def _find_job(self, job_id: str) -> NormalizedJob | None:
        # Offload the sync SQLAlchemy lookups to a worker thread so the query
        # duration doesn't block the event loop (matches list_jobs) (#157).
        return await asyncio.to_thread(
            lambda: self._job_query.get_job_by_id(job_id) or self._scanner.get_job_by_id(job_id)
        )
