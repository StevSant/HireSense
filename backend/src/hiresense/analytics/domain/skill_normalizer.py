from __future__ import annotations

from hiresense.kernel import normalize_skill


class SkillNormalizer:
    """Injectable wrapper over the kernel's shared skill normalization, so
    analytics canonicalizes skills exactly like matching does (same algorithm
    and alias map — no cross-module drift)."""

    def normalize(self, skill: str) -> str:
        return normalize_skill(skill)
