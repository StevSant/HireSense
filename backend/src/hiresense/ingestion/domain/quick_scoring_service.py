from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.ingestion.domain.candidate_level import infer_candidate_level
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.profile_hash import score_profile_hash
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict
from hiresense.ingestion.prompts import render_quick_scoring_system_prompt
from hiresense.shared.kernel import extract_json
from hiresense.shared.kernel.prompts import MODERATE_THRESHOLD, STRONG_THRESHOLD, prompt_fingerprint
from hiresense.shared.ports import LLMPort

logger = logging.getLogger(__name__)

# Candidate summary truncation inside the batched prompt (module constant,
# mirrors the prompt-truncation style used by the semantic scorer).
_SUMMARY_CHAR_LIMIT = 2500


def _quick_prompt_fingerprint() -> str:
    """Identity of the static rubric half of the prompt.

    The CANDIDATE block is deliberately excluded: it already varies per
    profile and is covered by profile_hash. Only the rubric needs to
    invalidate cached scores when it changes.
    """
    return prompt_fingerprint(render_quick_scoring_system_prompt())


def _verdict_from_score(score: float) -> QuickMatchVerdict:
    if score >= STRONG_THRESHOLD:
        return QuickMatchVerdict.STRONG
    if score >= MODERATE_THRESHOLD:
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
            self._cache_repo.get_quick_bulk,
            [j.id for j in jobs],
            profile_hash,
            _quick_prompt_fingerprint(),
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
        return f"{render_quick_scoring_system_prompt()}\n\n{candidate_block}"

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

        # Positional fallback is only sound when the model returned exactly one
        # object per job — a shorter/longer array means the Nth object no longer
        # lines up with the Nth job, so binding by position would attribute a
        # score to the wrong job (#143). When the count differs we trust the
        # per-item `ref` alone and drop any item without a usable one.
        positional_ok = len(data) == len(chunk)

        results: list[QuickMatchResult] = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            job = self._resolve_job(item, idx, chunk, positional_ok=positional_ok)
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
    def _resolve_job(
        item: dict,
        idx: int,
        chunk: list[NormalizedJob],
        *,
        positional_ok: bool,
    ) -> NormalizedJob | None:
        ref = item.get("ref")
        if isinstance(ref, (int, float)) and 1 <= int(ref) <= len(chunk):
            return chunk[int(ref) - 1]
        # Positional fallback when the model omits/garbles the ref — but ONLY
        # when the returned array is 1:1 with the chunk, so position N reliably
        # maps to job N. Otherwise drop the item rather than guess (#143).
        if positional_ok and idx < len(chunk):
            return chunk[idx]
        return None

    async def _safe_upsert_bulk(self, results: list[QuickMatchResult], profile_hash: str) -> None:
        try:
            await asyncio.to_thread(
                self._cache_repo.upsert_quick_bulk,
                results,
                profile_hash,
                _quick_prompt_fingerprint(),
            )
        except Exception:
            # Cache write failure must never fail scoring — the caller already
            # has the results in hand; only the next request's cache hit is lost.
            logger.exception("Quick score cache bulk upsert failed for %d results", len(results))
