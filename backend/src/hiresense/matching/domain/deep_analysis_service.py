from __future__ import annotations

import logging
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.profile_hash import score_profile_hash
from hiresense.matching.domain.deep_analysis_result import DeepAnalysisResult
from hiresense.matching.domain.deep_dimension import DeepDimension
from hiresense.matching.domain.scorers.json_extract import extract_json
from hiresense.ports import LLMPort

logger = logging.getLogger(__name__)

_STRONG_THRESHOLD = 0.7
_MODERATE_THRESHOLD = 0.4

_DIMENSIONS = ("seniority_fit", "skills_role_fit", "growth", "culture", "compensation")

_SYSTEM_PROMPT = (
    "You are an expert technical recruiter producing an honest, detailed match "
    "analysis between a CANDIDATE and ONE job. Return ONLY a JSON object:\n"
    "{\n"
    '  "overall_score": <0.0-1.0>,\n'
    '  "verdict": "strong|moderate|weak",\n'
    '  "dimensions": [{"dimension": "<name>", "score": <0-1>, "rationale": "..."}],\n'
    '  "matched_skills": ["..."], "missing_skills": ["..."],\n'
    '  "pros": ["..."], "cons": ["..."], "recommendations": ["..."],\n'
    '  "narrative": "2-4 sentence honest summary"\n'
    "}\n"
    f"Use exactly these dimension names: {', '.join(_DIMENSIONS)}.\n\n"
    "Apply these gating rules — overall_score MUST reflect them, not topical "
    "keyword overlap:\n"
    "1. SENIORITY: infer the candidate's level from their experience; if the job "
    "is clearly more senior (Senior/Staff/Lead/Principal/Director), seniority_fit "
    "and overall_score must be low. Never assume mid-level.\n"
    "2. CORE SKILLS: if the candidate lacks the job's primary language or core "
    "discipline, skills_role_fit and overall_score must be low; list it under "
    "missing_skills. Shared peripheral tools do not compensate.\n"
    "3. DISCIPLINE: a different discipline (e.g. SRE/infra vs backend) is a weak "
    "fit unless the CV shows direct hands-on experience in it.\n"
    "Be specific and concrete; recommendations should be actionable next steps."
)


def _str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _verdict_from_score(score: float) -> str:
    if score >= _STRONG_THRESHOLD:
        return "strong"
    if score >= _MODERATE_THRESHOLD:
        return "moderate"
    return "weak"


class DeepAnalysisService:
    """Tier-2 deep match analysis: one rich call to an advanced model, cached.

    Produces a full single-job breakdown (dimensions, matched/missing skills,
    pros/cons, recommendations, narrative) for the detail panel. Cached per
    (job_id, profile_hash). Never raises to the caller: when the LLM is
    unconfigured or the response can't be parsed it returns a heuristic-backed
    result built from the job's existing match_score.

    `cache_repo` is a JobMatchCacheRepository (typed Any to keep the domain
    layer free of an infrastructure import).
    """

    def __init__(
        self,
        *,
        llm: LLMPort | None,
        cache_repo: Any,
        job_char_limit: int = 6000,
    ) -> None:
        self._llm = llm
        self._cache_repo = cache_repo
        self._job_char_limit = job_char_limit

    async def analyze(
        self,
        job: NormalizedJob,
        candidate_skills: list[str],
        candidate_summary: str,
        *,
        force: bool = False,
    ) -> DeepAnalysisResult:
        profile_hash = score_profile_hash(candidate_skills, candidate_summary)

        if not force:
            cached = self._safe_get_cached(job.id, profile_hash)
            if cached is not None:
                return cached

        if self._llm is None:
            return self._heuristic(job, "Deep analysis unavailable — no LLM configured.")
        if not candidate_skills and not candidate_summary:
            return self._heuristic(job, "Add a profile/CV to get a deep match analysis.")

        prompt = self._build_prompt(job, candidate_skills, candidate_summary)
        try:
            response = await self._llm.complete(prompt, system=_SYSTEM_PROMPT)
        except Exception:
            logger.exception("Deep analysis LLM call failed for job %s", job.id)
            return self._heuristic(job, "Deep analysis failed — showing heuristic score.")

        result = self._parse(response, job.id)
        if result is None:
            logger.warning("Deep analysis: unparseable response for job %s", job.id)
            return self._heuristic(job, "Deep analysis failed — showing heuristic score.")

        self._safe_upsert(result, profile_hash)
        return result

    # ---- Internals ----------------------------------------------------

    def _build_prompt(
        self, job: NormalizedJob, candidate_skills: list[str], candidate_summary: str
    ) -> str:
        skills = ", ".join(s for s in candidate_skills if s) or "(none listed)"
        summary = (candidate_summary or "").strip() or "(no summary)"
        job_skills = ", ".join(s for s in job.skills if s) or "(none listed)"
        desc = (job.description or "").strip()[: self._job_char_limit]
        return (
            "CANDIDATE\n"
            f"Skills: {skills}\n"
            f"Experience / summary:\n{summary}\n\n"
            "JOB\n"
            f"Title: {job.title}\n"
            f"Company: {job.company or 'Unknown'}\n"
            f"Location: {job.location or 'Unknown'}\n"
            f"Compensation: {job.salary_range or 'Not stated'}\n"
            f"Listed skills: {job_skills}\n"
            f"Description:\n{desc}"
        )

    def _parse(self, response: str, job_id: str) -> DeepAnalysisResult | None:
        data = extract_json(response)
        if not isinstance(data, dict):
            return None
        try:
            overall = float(data.get("overall_score"))
        except (TypeError, ValueError):
            return None

        dimensions: list[DeepDimension] = []
        for entry in data.get("dimensions", []) or []:
            if not isinstance(entry, dict) or "dimension" not in entry or "score" not in entry:
                continue
            try:
                dimensions.append(
                    DeepDimension(
                        dimension=str(entry["dimension"]),
                        score=float(entry["score"]),
                        rationale=str(entry.get("rationale", "")),
                    )
                )
            except (TypeError, ValueError):
                continue

        verdict = data.get("verdict")
        verdict = str(verdict) if isinstance(verdict, str) else _verdict_from_score(overall)
        return DeepAnalysisResult(
            job_id=job_id,
            overall_score=overall,
            verdict=verdict,
            dimensions=dimensions,
            matched_skills=_str_list(data.get("matched_skills")),
            missing_skills=_str_list(data.get("missing_skills")),
            pros=_str_list(data.get("pros")),
            cons=_str_list(data.get("cons")),
            recommendations=_str_list(data.get("recommendations")),
            narrative=str(data.get("narrative", "")),
        )

    def _heuristic(self, job: NormalizedJob, narrative: str) -> DeepAnalysisResult:
        score = job.match_score if job.match_score is not None else 0.0
        return DeepAnalysisResult(
            job_id=job.id,
            overall_score=score,
            verdict=_verdict_from_score(score),
            narrative=narrative,
        )

    def _safe_get_cached(self, job_id: str, profile_hash: str) -> DeepAnalysisResult | None:
        try:
            payload = self._cache_repo.get_deep(job_id, profile_hash)
        except Exception:
            logger.exception("Deep analysis cache read failed for job %s", job_id)
            return None
        if not payload:
            return None
        try:
            return DeepAnalysisResult.model_validate(payload)
        except Exception:
            logger.warning("Deep analysis cached payload invalid for job %s", job_id)
            return None

    def _safe_upsert(self, result: DeepAnalysisResult, profile_hash: str) -> None:
        try:
            self._cache_repo.upsert_deep(result.job_id, profile_hash, result.model_dump())
        except Exception:
            logger.exception("Deep analysis cache upsert failed for job %s", result.job_id)
