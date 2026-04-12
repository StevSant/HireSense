from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.ports import LLMPort

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a job-matching dimension scorer. Analyze the provided data and return "
    'a JSON object with "score" (float 0.0-1.0) and "rationale" (brief explanation). '
    "Return valid JSON only."
)


class BaseLLMScorer(ABC):
    def __init__(self, llm: LLMPort | None, weight: int) -> None:
        self._llm = llm
        self._weight = weight

    @property
    @abstractmethod
    def dimension_name(self) -> str: ...

    @property
    def weight(self) -> int:
        return self._weight

    @abstractmethod
    def _build_prompt(self, job: Any, profile: Any | None = None) -> str: ...

    @abstractmethod
    def _output_schema(self) -> type[BaseModel]: ...

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if self._llm is None:
            return DimensionResult.default(
                self.dimension_name,
                weight=self._weight,
                rationale="LLM not configured",
            )
        try:
            prompt = self._build_prompt(job, profile)
            response = await self._llm.complete(prompt, system=_SYSTEM_PROMPT)
            return self._parse_response(response)
        except Exception as exc:
            logger.warning("Scorer %s failed: %s", self.dimension_name, exc)
            return DimensionResult(
                dimension=self.dimension_name,
                score=0.5,
                rationale=f"Evaluation failed: {exc}",
                weight=self._weight,
            )

    def _parse_response(self, response: str) -> DimensionResult:
        data = None
        try:
            data = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            md_match = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", response, re.DOTALL)
            if md_match:
                try:
                    data = json.loads(md_match.group(1))
                except (json.JSONDecodeError, TypeError):
                    pass

        if data is not None and "score" in data:
            return DimensionResult(
                dimension=self.dimension_name,
                score=float(data["score"]),
                rationale=str(data.get("rationale", "")),
                weight=self._weight,
            )

        return DimensionResult(
            dimension=self.dimension_name,
            score=0.5,
            rationale=f"Failed to parse LLM response: {response[:200]}",
            weight=self._weight,
        )
