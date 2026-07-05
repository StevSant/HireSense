from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.ingestion.domain.job_quality import JobQuality
from hiresense.ingestion.domain.job_quality_verdict import JobQualityVerdict
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.matching.domain.scorers.json_extract import extract_json
from hiresense.ports import LLMPort

logger = logging.getLogger(__name__)

# High-precision spam / scam markers. A hit short-circuits straight to SPAM
# without an LLM call. Kept deliberately tight — these phrases essentially never
# appear in a legitimate salaried engineering posting. Matched case-insensitively
# as substrings of "title\ndescription".
_SPAM_MARKERS: tuple[str, ...] = (
    "line of business owner",
    "be your own boss",
    "commission only",
    "commission-only",
    "100% commission",
    "unlimited earning potential",
    "unlimited income",
    "financial freedom",
    "multi-level marketing",
    "multi level marketing",
    "join our downline",
    "pyramid",
    "no experience needed, work from home",
)

_DESC_CHAR_LIMIT = 1200

_SYSTEM_PROMPT = (
    "You are a strict job-board moderator deciding whether each posting is a "
    "legitimate job or junk. Return ONLY a JSON array — one object per job, in "
    'input order: [{"ref": <job number>, "quality": "ok|low_quality|spam", '
    '"reason": "<short phrase, omit for ok>"}].\n\n'
    "Classify as:\n"
    "- \"spam\": MLM / pyramid / franchise / 'be your own boss' / commission-only "
    "/ pay-to-start / get-rich pitches, or anything not actually offering "
    "employment.\n"
    '- "low_quality": real but near-empty/uninformative (no company, no real '
    "description, pure recruiter spam, content-farm repost).\n"
    '- "ok": a normal legitimate job posting. When unsure, choose "ok".\n'
    "Keep each reason under ~10 words."
)


def _deterministic_spam_reason(job: NormalizedJob) -> str | None:
    haystack = f"{job.title}\n{job.description}".lower()
    for marker in _SPAM_MARKERS:
        if marker in haystack:
            return f"Matched spam marker: '{marker}'"
    return None


def _coerce_quality(raw: Any) -> JobQuality:
    if isinstance(raw, str):
        try:
            return JobQuality(raw.strip().lower())
        except ValueError:
            pass
    return JobQuality.OK  # fail-open on anything unexpected


class JobQualityClassifier:
    """Intrinsic job-quality classifier: deterministic spam fast-path + LLM.

    Quality is profile-independent, so this runs once at ingestion (not per
    request). Obvious spam is caught by `_SPAM_MARKERS` with no LLM call; the
    rest is adjudicated by one batched cheap-model call. Every uncertain path
    fails OPEN to OK — we never hide a job because the LLM was unavailable or
    its response was unparseable.
    """

    def __init__(
        self,
        *,
        llm: LLMPort | None,
        batch_size: int = 20,
        desc_char_limit: int = _DESC_CHAR_LIMIT,
        max_concurrency: int = 4,
    ) -> None:
        self._llm = llm
        self._batch_size = max(1, batch_size)
        self._desc_char_limit = desc_char_limit
        # Cap concurrent LLM chunk calls so a large ingestion (or a backfill)
        # can't fan out one request per 20-job chunk all at once and trip the
        # provider's rate limit. Created lazily per classify() so it always
        # binds to the running event loop.
        self._max_concurrency = max(1, max_concurrency)

    async def classify(self, jobs: list[NormalizedJob]) -> dict[str, JobQualityVerdict]:
        """Return a verdict for EVERY input job (default OK)."""
        if not jobs:
            return {}

        results: dict[str, JobQualityVerdict] = {}
        needs_llm: list[NormalizedJob] = []
        for job in jobs:
            reason = _deterministic_spam_reason(job)
            if reason is not None:
                results[job.id] = JobQualityVerdict(
                    job_id=job.id, quality=JobQuality.SPAM, reason=reason
                )
            else:
                needs_llm.append(job)

        # Fail-open: no LLM → everything not already flagged is OK.
        if self._llm is None:
            for job in needs_llm:
                results[job.id] = JobQualityVerdict(job_id=job.id, quality=JobQuality.OK)
            return results

        chunks = [
            needs_llm[i : i + self._batch_size] for i in range(0, len(needs_llm), self._batch_size)
        ]
        sem = asyncio.Semaphore(self._max_concurrency)

        async def _bounded(chunk: list[NormalizedJob]) -> dict[str, JobQualityVerdict]:
            async with sem:
                return await self._classify_chunk(chunk)

        scored_chunks = await asyncio.gather(*(_bounded(c) for c in chunks))
        for chunk_results in scored_chunks:
            results.update(chunk_results)
        return results

    async def _classify_chunk(self, chunk: list[NormalizedJob]) -> dict[str, JobQualityVerdict]:
        # Default every job in the chunk to OK; override with parsed verdicts.
        out = {j.id: JobQualityVerdict(job_id=j.id, quality=JobQuality.OK) for j in chunk}
        prompt = self._build_prompt(chunk)
        try:
            response = await self._llm.complete(prompt, system=_SYSTEM_PROMPT)
        except Exception:
            logger.exception("Job-quality classification batch failed (size=%d)", len(chunk))
            return out  # fail-open
        for ref, item in self._parse(response, chunk):
            quality = _coerce_quality(item.get("quality"))
            reason = item.get("reason")
            out[ref.id] = JobQualityVerdict(
                job_id=ref.id,
                quality=quality,
                reason=(str(reason).strip() if reason and quality is not JobQuality.OK else None),
            )
        return out

    def _build_prompt(self, chunk: list[NormalizedJob]) -> str:
        lines = ["JOBS (classify every one; echo its ref number):"]
        for ref, job in enumerate(chunk, start=1):
            desc = (job.description or "").strip()[: self._desc_char_limit]
            lines.append(f"[{ref}] {job.title} @ {job.company or '(no company)'}")
            lines.append(f"    {desc}")
        return "\n".join(lines)

    @staticmethod
    def _parse(response: str, chunk: list[NormalizedJob]):
        data = extract_json(response)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            logger.warning("Job-quality: unparseable response: %s", str(response)[:200])
            return
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            ref = item.get("ref")
            if isinstance(ref, (int, float)) and 1 <= int(ref) <= len(chunk):
                yield chunk[int(ref) - 1], item
            elif idx < len(chunk):
                yield chunk[idx], item
