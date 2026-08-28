from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hiresense
from hiresense.ingestion.adapters import (
    AdzunaAdapter,
    ArbeitnowAdapter,
    AshbyAdapter,
    AutoPortalAdapter,
    CrunchBoardAdapter,
    CSVImportAdapter,
    DiceAdapter,
    GenericScraperAdapter,
    GetOnBoardAdapter,
    GlassdoorAdapter,
    GlobantAdapter,
    GreenhouseAdapter,
    HimalayasAdapter,
    HNHiringAdapter,
    IndeedAdapter,
    JobicyAdapter,
    LeverAdapter,
    LinkedInAdapter,
    MonsterAdapter,
    RecruiteeAdapter,
    RemotiveAdapter,
    SmartRecruitersAdapter,
    TheMuseAdapter,
    ThoughtworksAdapter,
    WellfoundAdapter,
    WeWorkRemotelyAdapter,
    WorkdayAdapter,
    WorkableAdapter,
    YCJobsAdapter,
    ZipRecruiterAdapter,
)
from hiresense.ingestion.api.provider import IngestionProvider
from hiresense.ingestion.domain import (
    IngestionOrchestrator,
    JobEmbeddingIndexer,
    JobHistoryRecorder,
    JobQualityClassifier,
    JobQueryService,
    JobRevalidationService,
    PortalScanner,
    load_portals_config,
)
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.embedding_backfill_service import EmbeddingBackfillService
from hiresense.ingestion.domain.normalizers import (
    AdzunaNormalizer,
    ArbeitnowNormalizer,
    AshbyNormalizer,
    CrunchBoardNormalizer,
    CSVNormalizer,
    DiceNormalizer,
    GenericScraperNormalizer,
    GetOnBoardNormalizer,
    GlassdoorNormalizer,
    GlobantNormalizer,
    GreenhouseNormalizer,
    HimalayasNormalizer,
    HNHiringNormalizer,
    IndeedNormalizer,
    JobicyNormalizer,
    LeverNormalizer,
    LinkedInNormalizer,
    MonsterNormalizer,
    RecruiteeNormalizer,
    RemotiveNormalizer,
    SmartRecruitersNormalizer,
    TheMuseNormalizer,
    ThoughtworksNormalizer,
    WellfoundNormalizer,
    WeWorkRemotelyNormalizer,
    WorkdayNormalizer,
    WorkableNormalizer,
    YCJobsNormalizer,
    ZipRecruiterNormalizer,
)
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
from hiresense.ingestion.domain.source_health import SourceHealthTracker
from hiresense.ingestion.infrastructure import (
    JobHistoryRepository,
    JobMatchCacheRepository,
    JobsRepository,
)
from hiresense.ingestion.infrastructure import PlaywrightPageRenderer
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService
from hiresense.composition.shared_infra import SharedInfra


@dataclass(frozen=True)
class IngestionBuild:
    provider: IngestionProvider
    orchestrator: IngestionOrchestrator
    job_query: JobQueryService
    boards_jobs_repo: Any
    pre_ranker: Any
    revalidation_service: Any


def build_ingestion(
    infra: SharedInfra, tracked: Callable[[str], Any], *, preference_query: Any = None
) -> IngestionBuild:
    s = infra.settings
    http_client = infra.http_client

    sources = []
    normalizers = {}
    for source_name in s.enabled_job_sources:
        if source_name == "remotive":
            sources.append(RemotiveAdapter(http_client=http_client, base_url=s.remotive_api_url))
            normalizers["remotive"] = RemotiveNormalizer()
        elif source_name == "csv":
            sources.append(CSVImportAdapter(import_dir=s.csv_import_dir))
            normalizers["csv"] = CSVNormalizer()
        elif source_name == "jobicy":
            sources.append(JobicyAdapter(http_client=http_client, base_url=s.jobicy_api_url))
            normalizers["jobicy"] = JobicyNormalizer()
        elif source_name == "himalayas":
            sources.append(HimalayasAdapter(http_client=http_client, base_url=s.himalayas_api_url))
            normalizers["himalayas"] = HimalayasNormalizer()
        elif source_name == "hn_hiring":
            sources.append(HNHiringAdapter(http_client=http_client, base_url=s.hn_algolia_api_url))
            normalizers["hn_hiring"] = HNHiringNormalizer()
        elif source_name == "weworkremotely":
            sources.append(
                WeWorkRemotelyAdapter(http_client=http_client, rss_url=s.weworkremotely_rss_url)
            )
            normalizers["weworkremotely"] = WeWorkRemotelyNormalizer()
        elif source_name == "getonboard":
            sources.append(
                GetOnBoardAdapter(
                    http_client=http_client,
                    base_url=s.getonboard_api_url,
                    categories=s.getonboard_categories,
                    company_concurrency=s.getonboard_company_concurrency,
                    profile_sink=infra.company_profile_store,
                    profile_char_limit=s.company_profile_char_limit,
                )
            )
            normalizers["getonboard"] = GetOnBoardNormalizer()
        elif source_name == "linkedin":
            sources.append(
                LinkedInAdapter(
                    http_client=http_client,
                    base_url=s.linkedin_jobs_url,
                    detail_concurrency=s.linkedin_detail_concurrency,
                    detail_delay=s.linkedin_detail_delay,
                )
            )
            normalizers["linkedin"] = LinkedInNormalizer()
        elif source_name == "arbeitnow":
            sources.append(ArbeitnowAdapter(http_client=http_client, base_url=s.arbeitnow_api_url))
            normalizers["arbeitnow"] = ArbeitnowNormalizer()
        elif source_name == "themuse":
            sources.append(
                TheMuseAdapter(
                    http_client=http_client,
                    base_url=s.themuse_api_url,
                    categories=s.themuse_categories,
                    api_key=s.themuse_api_key,
                )
            )
            normalizers["themuse"] = TheMuseNormalizer()
        elif source_name == "adzuna":
            # Key-gated: skip silently when credentials are absent so a
            # misconfigured opt-in never breaks the whole fetch.
            if s.adzuna_app_id and s.adzuna_app_key:
                sources.append(
                    AdzunaAdapter(
                        http_client=http_client,
                        base_url=s.adzuna_api_url,
                        app_id=s.adzuna_app_id,
                        app_key=s.adzuna_app_key,
                        countries=s.adzuna_countries,
                        query=s.adzuna_query,
                    )
                )
                normalizers["adzuna"] = AdzunaNormalizer()
        elif source_name == "dice":
            sources.append(
                DiceAdapter(
                    http_client=http_client,
                    mcp_url=s.dice_mcp_url,
                    query=s.dice_query,
                    location=s.dice_location,
                    remote_only=s.dice_remote_only,
                    page_limit=s.dice_page_limit,
                    jobs_per_page=s.dice_jobs_per_page,
                    posted_date=s.dice_posted_date,
                    employment_types=s.dice_employment_types,
                )
            )
            normalizers["dice"] = DiceNormalizer()
        elif source_name == "crunchboard":
            sources.append(
                CrunchBoardAdapter(
                    http_client=http_client,
                    rss_url=s.crunchboard_rss_url,
                    result_limit=s.crunchboard_result_limit,
                )
            )
            normalizers["crunchboard"] = CrunchBoardNormalizer()
        elif source_name == "yc_jobs":
            sources.append(
                YCJobsAdapter(
                    http_client=http_client,
                    base_url=s.yc_jobs_base_url,
                    roles=s.yc_jobs_roles,
                    remote_only=s.yc_jobs_remote_only,
                    enrich_companies=s.yc_jobs_enrich_companies,
                    company_enrich_limit=s.yc_jobs_company_enrich_limit,
                    result_limit=s.yc_jobs_result_limit,
                )
            )
            normalizers["yc_jobs"] = YCJobsNormalizer()
        elif source_name == "ziprecruiter":
            sources.append(
                ZipRecruiterAdapter(
                    http_client=http_client,
                    mcp_url=s.ziprecruiter_mcp_url,
                    query=s.ziprecruiter_query,
                    location=s.ziprecruiter_location,
                    country=s.ziprecruiter_country,
                    remote_only=s.ziprecruiter_remote_only,
                    page_limit=s.ziprecruiter_page_limit,
                )
            )
            normalizers["ziprecruiter"] = ZipRecruiterNormalizer()
        elif source_name == "indeed":
            sources.append(
                IndeedAdapter(
                    import_dir=s.csv_import_dir,
                    default_filename=s.indeed_import_filename,
                )
            )
            normalizers["indeed"] = IndeedNormalizer()
        elif source_name == "wellfound":
            sources.append(
                WellfoundAdapter(
                    import_dir=s.csv_import_dir,
                    default_filename=s.wellfound_import_filename,
                )
            )
            normalizers["wellfound"] = WellfoundNormalizer()
        elif source_name == "glassdoor":
            sources.append(
                GlassdoorAdapter(
                    import_dir=s.csv_import_dir,
                    default_filename=s.glassdoor_import_filename,
                )
            )
            normalizers["glassdoor"] = GlassdoorNormalizer()
        elif source_name == "monster":
            sources.append(
                MonsterAdapter(
                    import_dir=s.csv_import_dir,
                    default_filename=s.monster_import_filename,
                )
            )
            normalizers["monster"] = MonsterNormalizer()

    boards_jobs_repo = JobsRepository(session_factory=infra.sync_session_factory, bucket="boards")
    portals_jobs_repo = JobsRepository(session_factory=infra.sync_session_factory, bucket="portals")

    # One history store shared by the orchestrator and the sweep: the audit
    # trail spans both, and a job's timeline interleaves their events.
    job_history_repo = JobHistoryRepository(session_factory=infra.sync_session_factory)
    job_history_recorder = JobHistoryRecorder(store=job_history_repo)

    # Persist embeddings of newly ingested jobs into the vector store (when one is
    # configured) so semantic search survives restarts. Per-bucket so search can
    # filter by tab. None when no vector store is wired (e.g. tests) → no-op.
    boards_indexer = (
        JobEmbeddingIndexer(infra.embedding, infra.vector_store, bucket="boards")
        if infra.vector_store is not None
        else None
    )
    portals_indexer = (
        JobEmbeddingIndexer(infra.embedding, infra.vector_store, bucket="portals")
        if infra.vector_store is not None
        else None
    )

    # Intrinsic quality / spam classifier (cheap model, deterministic spam
    # fast-path + LLM); fails open to "ok" when no LLM is configured.
    quality_classifier = JobQualityClassifier(llm=tracked("job_quality_classifier"))
    health_tracker = SourceHealthTracker()

    ingestion_orchestrator = IngestionOrchestrator(
        sources=sources,
        normalizers=normalizers,
        event_bus=infra.event_bus,
        cooldown_seconds=s.ingestion_cooldown_seconds,
        repository=boards_jobs_repo,
        retention_days=s.ingestion_job_retention_days,
        indexer=boards_indexer,
        closure_miss_threshold=s.job_closure_miss_threshold,
        quality_classifier=quality_classifier,
        health_tracker=health_tracker,
        source_concurrency=s.ingestion_source_concurrency,
        history=job_history_recorder,
        history_retention_days=s.job_history_retention_days,
    )

    # Job lookups / score persistence for the boards bucket. Shares the very
    # same repository instance as the orchestrator, so every other context can
    # read the corpus without holding the orchestrator itself.
    job_query = JobQueryService(repository=boards_jobs_repo)

    # URL-probe revalidation sweep for the boards bucket. Snapshot sources
    # (portals) get disappearance-based closure during ingestion, so the sweep
    # only targets feed/search sources whose listings stay live after closing.
    # Which sources are skipped, and why, is declared in config
    # (job_revalidation_excluded_sources) so it is tunable per deployment rather
    # than frozen in the wiring. Sources that stay in the list but fail a probe
    # remain UNKNOWN and are never closed on that basis.
    _revalidation_excluded = set(s.job_revalidation_excluded_sources)
    revalidation_sources = [
        name for name in s.enabled_job_sources if name not in _revalidation_excluded
    ]

    # LinkedIn closure lives on its guest API, not the public /jobs/view URL the
    # user clicks (that returns a login wall server-side). Probe the same guest
    # endpoint the adapter scrapes; it returns 200 + "No longer accepting
    # applications" (a global marker) when closed, or 404 when removed.
    def _linkedin_probe_url(job: NormalizedJob) -> str:
        if job.source_id:
            return f"{s.linkedin_jobs_url}/jobPosting/{job.source_id}"
        return job.url

    revalidation_service = JobRevalidationService(
        http_client=http_client,
        repository=boards_jobs_repo,
        indexer=boards_indexer,
        sources=revalidation_sources,
        markers=s.job_closed_markers,
        batch=s.job_revalidation_batch,
        concurrency=s.job_revalidation_concurrency,
        delay=s.job_revalidation_delay,
        host_concurrency=s.job_revalidation_host_concurrency,
        max_probe_bytes=s.job_revalidation_max_probe_bytes,
        max_redirects=s.job_revalidation_max_redirects,
        probe_url_builders={"linkedin": _linkedin_probe_url},
        user_agent=s.job_revalidation_user_agent,
        expired_redirect_markers=s.job_revalidation_expired_redirect_markers,
        history=job_history_recorder,
    )

    # Resolve the portals config relative to the hiresense package root (not
    # this module), preserving the original create_app() behaviour.
    portals_config_path = Path(hiresense.__file__).parent / s.portals_config_path
    portals_config = load_portals_config(portals_config_path)

    page_renderer = PlaywrightPageRenderer(timeout_ms=int(s.portal_scan_timeout * 1000))
    scraper_adapter = GenericScraperAdapter(
        http_client=http_client,
        renderer=page_renderer,
        timeout=s.portal_scan_timeout,
    )

    portal_adapters = {
        "greenhouse": GreenhouseAdapter(
            http_client=http_client,
            base_url=s.greenhouse_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "lever": LeverAdapter(
            http_client=http_client,
            base_url=s.lever_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "ashby": AshbyAdapter(
            http_client=http_client,
            base_url=s.ashby_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "workable": WorkableAdapter(
            http_client=http_client,
            base_url=s.workable_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "smartrecruiters": SmartRecruitersAdapter(
            http_client=http_client,
            base_url=s.smartrecruiters_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "recruitee": RecruiteeAdapter(
            http_client=http_client,
            base_url=s.recruitee_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "workday": WorkdayAdapter(
            http_client=http_client,
            timeout=s.portal_scan_timeout,
        ),
        "thoughtworks": ThoughtworksAdapter(
            http_client=http_client,
            base_url=s.thoughtworks_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "globant": GlobantAdapter(
            http_client=http_client,
            base_url=s.globant_api_url,
            timeout=s.portal_scan_timeout,
        ),
        "scraper": scraper_adapter,
    }
    portal_adapters["auto"] = AutoPortalAdapter(portal_adapters, scraper_adapter)

    portal_normalizers = {
        "greenhouse": GreenhouseNormalizer(),
        "lever": LeverNormalizer(),
        "ashby": AshbyNormalizer(),
        "workable": WorkableNormalizer(),
        "smartrecruiters": SmartRecruitersNormalizer(),
        "recruitee": RecruiteeNormalizer(),
        "workday": WorkdayNormalizer(),
        "thoughtworks": ThoughtworksNormalizer(),
        "globant": GlobantNormalizer(),
        "scraper": GenericScraperNormalizer(),
        "auto": GenericScraperNormalizer(),
    }

    portal_scanner = PortalScanner(
        config=portals_config,
        adapters=portal_adapters,
        normalizers=portal_normalizers,
        event_bus=infra.event_bus,
        repository=portals_jobs_repo,
        retention_days=s.ingestion_job_retention_days,
        indexer=portals_indexer,
        closure_miss_threshold=s.job_closure_miss_threshold,
        history=job_history_recorder,
        history_retention_days=s.job_history_retention_days,
        source_concurrency=s.ingestion_source_concurrency,
    )

    from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
    from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService

    semantic_scoring = SemanticScoringService(
        embedding_port=infra.embedding,
        job_cache_size=s.semantic_job_cache_size,
        profile_cache_size=s.semantic_profile_cache_size,
    )

    # SemanticPreRanker wires vector store + embedding for global ANN pre-ranking.
    # When vector store is None (no pgvector configured), pre_ranker is still
    # constructed — its own passthrough logic handles the None vector_store case.
    pre_ranker = SemanticPreRanker(
        infra.vector_store,
        infra.embedding,
        top_k_cap=s.prerank_top_k_cap,
        skill_weight=s.prerank_weight_skill,
        semantic_weight=s.prerank_weight_semantic,
        preference=preference_query,
        profile_cache_size=s.semantic_profile_cache_size,
    )

    match_cache_repo = JobMatchCacheRepository(session_factory=infra.sync_session_factory)
    quick_scoring = QuickScoringService(
        llm=tracked("match_quick_scorer"),
        cache_repo=match_cache_repo,
        batch_size=s.match_quick_batch_size,
        job_char_limit=s.match_quick_job_char_limit,
        concurrency=s.match_quick_concurrency,
    )
    deep_analysis = DeepAnalysisService(
        llm=tracked("match_deep_analyzer"),
        cache_repo=match_cache_repo,
        job_char_limit=s.match_deep_job_char_limit,
    )

    # Backfill service: re-embeds all pre-existing jobs into pgvector on demand.
    # Uses the same embedding + vector_store as the per-bucket indexers.
    # None when no vector store is configured (graceful no-op at runtime).
    backfill_service = EmbeddingBackfillService(
        boards_repo=boards_jobs_repo,
        portals_repo=portals_jobs_repo,
        embedding=infra.embedding,
        vector_store=infra.vector_store,
        chunk_size=s.embedding_backfill_chunk_size,
    )

    provider = IngestionProvider(
        orchestrator=ingestion_orchestrator,
        job_query=job_query,
        portal_scanner=portal_scanner,
        portals_config=portals_config,
        semantic_scoring=semantic_scoring,
        quick_scoring=quick_scoring,
        deep_analysis=deep_analysis,
        pre_ranker=pre_ranker,
        revalidation_service=revalidation_service,
        backfill_service=backfill_service,
        job_history=job_history_repo,
    )
    return IngestionBuild(
        provider=provider,
        orchestrator=ingestion_orchestrator,
        job_query=job_query,
        boards_jobs_repo=boards_jobs_repo,
        pre_ranker=pre_ranker,
        revalidation_service=revalidation_service,
    )
