from __future__ import annotations

import math


class SemanticScorer:
    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def score(self, a: list[float], b: list[float]) -> float:
        """Return cosine similarity clamped to [0, 1] for use as a match score."""
        raw = self.cosine_similarity(a, b)
        return max(0.0, min(1.0, raw))
