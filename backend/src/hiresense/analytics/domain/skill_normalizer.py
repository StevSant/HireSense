from __future__ import annotations

_ALIASES = {
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "node.js": "node",
    "nodejs": "node",
    "postgres": "postgresql",
    "py": "python",
}


class SkillNormalizer:
    """Lowercase/trim + a small alias map so skill variants collapse."""

    def normalize(self, skill: str) -> str:
        base = (skill or "").strip().lower()
        return _ALIASES.get(base, base)
