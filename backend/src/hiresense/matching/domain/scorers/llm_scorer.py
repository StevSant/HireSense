from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from hiresense.matching.domain.scorers.base import DimensionResult

logger = logging.getLogger(__name__)


class BaseLLMScorer(ABC):
    def __init__(self, llm: Any, weight: int) -> None:
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
    def _build_system(self) -> str: ...

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if self._llm is None:
            return DimensionResult.default(
                self.dimension_name,
                weight=self._weight,
                rationale="LLM not configured",
            )
        try:
            prompt = self._build_prompt(job, profile)
            system = self._build_system()
            response = await self._llm.complete(prompt, system=system)
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
        # Try direct JSON
        try:
            data = json.loads(response)
            return DimensionResult(
                dimension=self.dimension_name,
                score=float(data["score"]),
                rationale=str(data.get("rationale", "")),
                weight=self._weight,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Try markdown code block
        md_match = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", response, re.DOTALL)
        if md_match:
            try:
                data = json.loads(md_match.group(1))
                return DimensionResult(
                    dimension=self.dimension_name,
                    score=float(data["score"]),
                    rationale=str(data.get("rationale", "")),
                    weight=self._weight,
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        # Try regex float
        float_match = re.search(r"\b(0\.\d+|1\.0|0|1)\b", response)
        if float_match:
            return DimensionResult(
                dimension=self.dimension_name,
                score=float(float_match.group(1)),
                rationale=response[:200],
                weight=self._weight,
            )

        # Fallback
        return DimensionResult(
            dimension=self.dimension_name,
            score=0.5,
            rationale=f"Failed to parse LLM response: {response[:200]}",
            weight=self._weight,
        )
