from __future__ import annotations

# Maps common skill spellings/abbreviations to a single canonical form so that
# "postgres", "Postgres", and "PostgreSQL" all compare equal across modules
# (matching, analytics). Keys must already be normalized (lowercase, no
# parentheticals, trimmed) — see normalize_skill, which applies this map as
# its final step.
#
# This is curated domain reference data (like a stopword list), not a tunable
# configuration value, so it lives in code rather than the settings layer.
SKILL_ALIASES: dict[str, str] = {
    "postgres": "postgresql",
    "postgre": "postgresql",
    "psql": "postgresql",
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "k8s": "kubernetes",
    "k8": "kubernetes",
    "gha": "github actions",
    "gcp": "google cloud",
    "node": "node.js",
    "nodejs": "node.js",
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    "dl": "deep learning",
    "ml": "machine learning",
}
