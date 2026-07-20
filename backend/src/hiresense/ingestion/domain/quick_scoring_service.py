from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.ingestion.domain.candidate_level import infer_candidate_level
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.profile_hash import score_profile_hash
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict
from hiresense.matching.domain.scorers.json_extract import extract_json
from hiresense.ports import LLMPort

logger = logging.getLogger(__name__)

# Candidate summary truncation inside the batched prompt (module constant,
# mirrors the prompt-truncation style used by the semantic scorer).
_SUMMARY_CHAR_LIMIT = 2500

# Verdict bucket thresholds — intrinsic to the scoring semantics, kept in sync
# with the frontend score-tier thresholds (strong >= 0.7, moderate >= 0.4).
_STRONG_THRESHOLD = 0.7
_MODERATE_THRESHOLD = 0.4

_SYSTEM_PROMPT = (
    "You are a precise technical recruiter scoring how well a CANDIDATE fits "
    "each JOB. Return ONLY a JSON array — one object per job, in input order:\n"
    '[{"ref": <job number>, "score": <0.0-1.0>, '
    '"verdict": "strong|moderate|weak", '
    '"reasons": ["short evidence", ...], '
    '"dealbreakers": ["hard mismatch", ...]}]\n\n'
    "Apply these gating rules STRICTLY — they OVERRIDE topical/keyword overlap:\n"
    "1. SENIORITY GATING. Infer the candidate's level from their experience "
    "(years, scope, titles). If a job's seniority (Senior, Staff, Lead, "
    "Principal, Director, Head) is clearly ABOVE the candidate's level, cap the "
    'score at 0.35 and add a dealbreaker like "Senior role — beyond your level". '
    "NEVER assume the candidate is mid-level; infer it from the CV text.\n"
    "2. CORE-SKILL GATING. Identify the job's PRIMARY language / core discipline "
    "(e.g. Java for a Java Engineer; Go + Linux internals + on-call for an SRE). "
    "If the candidate lacks that primary language or core discipline, cap the "
    'score at 0.30 and add a dealbreaker naming it (e.g. "Requires Java — not in '
    'your stack"). Shared peripheral tools (Docker, AWS, Git, Postgres) must NOT '
    "lift a score on their own.\n"
    "3. DISCIPLINE MATCH. Classify the job: backend, frontend, fullstack, "
    "SRE/infra/devops, data/ML, mobile, QA, or other. If it differs from the "
    "candidate's primary discipline, treat it as a weak fit (<= 0.4) unless the "
    "CV shows direct hands-on experience in that discipline.\n"
    '4. Award "strong" (>= 0.7) ONLY when seniority fits AND the primary skill '
    'and discipline match. Use "weak" (< 0.4) whenever any gate trips.\n'
    "Keep each reason and dealbreaker to a short concrete phrase (~12 words max)."
)


def _verdict_from_score(score: float) -> QuickMatchVerdict:
    if score >= _STRONG_THRESHOLD:
        return QuickMatchVerdict.STRONG
    if score >= _MODERATE_THRESHOLD:
        return QuickMatchVerdict.MODERATE
    return QuickMatchVerdict.WEAK


def _coerce_verdict(raw: Any, score: float) -> QuickMatchVerdict:
    if isinstance(raw, str):
        try:
            return QuickMatchVerdict(raw.strip().lower())
        except ValueError:
            pass
    return _verdict_from_score(score)


def _str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


class QuickScoringService:
    """Tier-1 quick match scoring: a cheap model, batched per page, cached.

    For each job on the visible page it produces a seniority/role/core-skill
    gated 0-1 score + short reasons + dealbreakers. The whole page is scored in
    one batched LLM call; results are cached per (job_id, profile_hash) so a
    page is only scored once per profile. Degrades to "no LLM result" (caller
    keeps the heuristic score) when the LLM is unconfigured or a batch fails.

    `cache_repo` is a JobMatchCacheRepository (typed Any to keep the domain
    layer free of an infrastructure import, matching SemanticScoringService).
    """

    def __init__(
        self,
        *,
        llm: LLMPort | None,
        cache_repo: Any,
        batch_size: int = 20,
        job_char_limit: int = 1500,
        concurrency: int = 4,
    ) -> None:
        self._llm = llm
        self._cache_repo = cache_repo
        self._batch_size = max(1, batch_size)
        self._job_char_limit = job_char_limit
        # Cap concurrent LLM chunk calls so a large rescore (many cache misses
        # fanned out over several batch-sized chunks) can't fire one request per
        # chunk all at once and trip the provider's rate limit. Mirrors
        # JobQualityClassifier's max_concurrency.
        self._concurrency = max(1, concurrency)

    async def score_page(
        self,
        jobs: list[NormalizedJob],
        candidate_skills: list[str],
        candidate_summary: str,
        *,
        llm_on_miss: bool = True,
    ) -> dict[str, QuickMatchResult]:
        """Return quick results keyed by job_id for the jobs we could score.

        Jobs absent from the returned dict have no LLM score (cache miss + no
        LLM, or a failed batch) — the caller falls back to the heuristic score.

        When ``llm_on_miss`` is False, cache misses are NOT sent to the LLM:
        only already-cached scores are returned. This is the #76 sort-only fast
        path — a pure reorder reuses cached scores instantly and never pays the
        blocking LLM round-trip; newly-surfaced jobs keep their heuristic score
        until a full rescore fills the cache.
        """
        if not jobs:
            return {}
        profile_hash = score_profile_hash(candidate_skills, candidate_summary)
        hits = await asyncio.to_thread(
            self._cache_repo.get_quick_bulk, [j.id for j in jobs], profile_hash
        )

        if not llm_on_miss or self._llm is None or (not candidate_skills and not candidate_summary):
            return hits

        misses = [j for j in jobs if j.id not in hits]
        if not misses:
            return hits

        level = infer_candidate_level(candidate_summary)
        chunks = [misses[i : i + self._batch_size] for i in range(0, len(misses), self._batch_size)]
        sem = asyncio.Semaphore(self._concurrency)

        async def _bounded(chunk: list[NormalizedJob]) -> list[QuickMatchResult]:
            async with sem:
                return await self._score_chunk(
                    chunk, candidate_skills, candidate_summary, level.value
                )

        scored_chunks = await asyncio.gather(*(_bounded(chunk) for chunk in chunks))

        results = dict(hits)
        new_results: list[QuickMatchResult] = []
        for chunk_results in scored_chunks:
            for result in chunk_results:
                new_results.append(result)
                results[result.job_id] = result
        if new_results:
            await self._safe_upsert_bulk(new_results, profile_hash)
        return results

    async def _score_chunk(
        self,
        chunk: list[NormalizedJob],
        candidate_skills: list[str],
        candidate_summary: str,
        level: str,
    ) -> list[QuickMatchResult]:
        system_prompt = self._build_system_prompt(candidate_skills, candidate_summary, level)
        prompt = self._build_prompt(chunk)
        try:
            response = await self._llm.complete(prompt, system=system_prompt)
        except Exception:
            logger.exception("Quick scoring batch failed (size=%d)", len(chunk))
            return []
        return self._parse(response, chunk)

    @staticmethod
    def _build_system_prompt(
        candidate_skills: list[str],
        candidate_summary: str,
        level: str,
    ) -> str:
        """Static instructions + the CANDIDATE block, as the cached prefix.

        The CANDIDATE block is byte-stable across chunks within one
        `score_page` call (same candidate_skills/candidate_summary/level are
        passed to every chunk) and across runs for the same profile_hash, so
        placing it in the system prompt lets Anthropic prompt caching (see
        LangChainLLMAdapter) reuse the cached prefix across chunks and calls
        instead of re-processing it every time. JOBS — which vary per chunk —
        stay in the user prompt (`_build_prompt`).
        """
        skills = ", ".join(s for s in candidate_skills if s) or "(none listed)"
        summary = (candidate_summary or "").strip()[:_SUMMARY_CHAR_LIMIT] or "(no summary)"
        candidate_block = "\n".join(
            [
                "CANDIDATE",
                f"Inferred level: {level}",
                f"Skills: {skills}",
                "Experience / summary:",
                summary,
            ]
        )
        return f"{_SYSTEM_PROMPT}\n\n{candidate_block}"

    def _build_prompt(self, chunk: list[NormalizedJob]) -> str:
        lines = ["JOBS (score every one; echo its ref number):"]
        for ref, job in enumerate(chunk, start=1):
            job_skills = ", ".join(s for s in job.skills if s) or "(none listed)"
            desc = (job.description or "").strip()[: self._job_char_limit]
            lines.append(f"[{ref}] {job.title} @ {job.company or 'Unknown'}")
            lines.append(f"    Listed skills: {job_skills}")
            lines.append(f"    Description: {desc}")
        return "\n".join(lines)

    def _parse(self, response: str, chunk: list[NormalizedJob]) -> list[QuickMatchResult]:
        data = extract_json(response)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            logger.warning("Quick scoring: unparseable response: %s", str(response)[:200])
            return []

        results: list[QuickMatchResult] = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            job = self._resolve_job(item, idx, chunk)
            if job is None or "score" not in item:
                continue
            try:
                score = float(item["score"])
            except (TypeError, ValueError):
                continue
            verdict = _coerce_verdict(item.get("verdict"), score)
            results.append(
                QuickMatchResult(
                    job_id=job.id,
                    score=score,
                    verdict=verdict,
                    reasons=_str_list(item.get("reasons")),
                    dealbreakers=_str_list(item.get("dealbreakers")),
                )
            )
        return results

    @staticmethod
    def _resolve_job(item: dict, idx: int, chunk: list[NormalizedJob]) -> NormalizedJob | None:
        ref = item.get("ref")
        if isinstance(ref, (int, float)) and 1 <= int(ref) <= len(chunk):
            return chunk[int(ref) - 1]
        # Positional fallback when the model omits/garbles the ref.
        if idx < len(chunk):
            return chunk[idx]
        return None

    async def _safe_upsert_bulk(self, results: list[QuickMatchResult], profile_hash: str) -> None:
        try:
            await asyncio.to_thread(self._cache_repo.upsert_quick_bulk, results, profile_hash)
        except Exception:
            # Cache write failure must never fail scoring — the caller already
            # has the results in hand; only the next request's cache hit is lost.
            logger.exception("Quick score cache bulk upsert failed for %d results", len(results))
