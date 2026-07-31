"""Lightweight profile-skill relevance for opportunities (no ANN required)."""

from __future__ import annotations

import re
from datetime import date

from hiresense.opportunities.domain.models import Opportunity

_TEXT_MENTION_WEIGHT = 0.25
_TOPIC_HIT_WEIGHT = 0.45
_SCORE_CAP = 1.0

_NOT_FUNDED = frozenset({"none", "n/a", "na", "no", "-", "unfunded", "self-funded"})
_STOP = frozenset({"and", "or", "the", "of", "for", "with", "primary", "principal", "sdk"})

# Broad buckets we keep even without an exact skill hit.
_GENERAL_TOPICS = frozenset(
    {
        "general",
        "latam",
        "tech",
    }
)

# Topic ↔ skill aliases for deterministic matching.
_TOPIC_ALIASES: dict[str, set[str]] = {
    "javascript": {"javascript", "js", "typescript", "ts", "node", "nodejs"},
    "python": {"python", "django", "fastapi", "flask"},
    "ai": {"ai", "ml", "machine-learning", "machine learning", "llm", "genai"},
    "data": {"data", "data-science", "analytics", "sql", "spark"},
    "devops": {"devops", "sre", "kubernetes", "k8s", "docker", "terraform"},
    "security": {"security", "cybersecurity", "infosec", "appsec"},
    "golang": {"go", "golang"},
    "cpp": {"c++", "cpp"},
    "dotnet": {"dotnet", ".net", "csharp", "c#"},
    "php": {"php", "laravel"},
    "ruby": {"ruby", "rails"},
    "ios": {"ios", "swift", "swiftui"},
    "android": {"android", "kotlin"},
    "rust": {"rust"},
    "ux": {"ux", "ui", "design", "figma"},
}

_TOKEN_SPLIT = re.compile(r"[^\w+#.+]+", re.UNICODE)


def opportunity_text(opp: Opportunity) -> str:
    parts = [
        opp.title or "",
        opp.organization or "",
        opp.description or "",
        " ".join(opp.topics or []),
        opp.funding or "",
        opp.country or "",
        opp.city or "",
    ]
    return "\n".join(parts)


def actionable_deadline(opp: Opportunity) -> date | None:
    return opp.application_deadline or opp.cfp_deadline


def is_stale(opp: Opportunity, *, today: date | None = None) -> bool:
    """True when the CFP/application window or the event itself is already over."""
    today = today or date.today()
    deadline = actionable_deadline(opp)
    if deadline is not None and deadline < today:
        return True
    end = opp.end_date or opp.start_date
    if end is not None and end < today:
        return True
    return False


def expand_skill_tokens(candidate_skills: set[str]) -> set[str]:
    """Flatten profile skills into searchable tokens.

    ``Python (principal)`` → ``{python (principal), python}``
    ``Django REST Framework`` → ``{django rest framework, django, rest, framework}``
    """
    tokens: set[str] = set()
    for skill in candidate_skills:
        if not skill or not skill.strip():
            continue
        raw = skill.strip().lower()
        tokens.add(raw)
        cleaned = re.sub(r"\([^)]*\)", " ", raw)
        for part in _TOKEN_SPLIT.split(cleaned):
            part = part.strip(".-_")
            if len(part) >= 2 and part not in _STOP:
                tokens.add(part)
    return tokens


def score_opportunity_relevance(
    opp: Opportunity,
    candidate_skills: set[str],
) -> float | None:
    """Deterministic relevance in [0, 1] from topic overlap + skill-token hits."""
    if not candidate_skills:
        return None
    skills = {s for s in candidate_skills if s}
    tokens = expand_skill_tokens(skills)
    if not tokens:
        return None

    score = 0.0
    topic_hits = 0
    for topic in opp.topics or []:
        if _skills_cover_topic(topic, skills):
            topic_hits += 1
    if topic_hits:
        score += min(topic_hits, 2) * _TOPIC_HIT_WEIGHT

    text = opportunity_text(opp)
    text_l = text.lower()
    title_compact = re.sub(r"[^a-z0-9+#]+", "", (opp.title or "").lower())
    matched: set[str] = set()
    for token in sorted(tokens, key=len, reverse=True):
        if token in matched:
            continue
        if re.search(rf"\b{re.escape(token)}\b", text_l, flags=re.IGNORECASE):
            matched.add(token)
            continue
        # Compound titles: "django" inside "DjangoCon".
        if len(token) >= 4 and token in title_compact:
            matched.add(token)
    if matched:
        score += min(len(matched), 4) * _TEXT_MENTION_WEIGHT

    if score <= 0:
        return None
    return min(score, _SCORE_CAP)


def _normalize_token(value: str) -> str:
    return re.sub(r"[\s_]+", "-", value.strip().lower())


def _skills_cover_topic(topic: str, skills: set[str]) -> bool:
    topic_n = _normalize_token(topic)
    if not topic_n:
        return False
    if topic_n in _GENERAL_TOPICS:
        return True
    skill_tokens = expand_skill_tokens(skills)
    if topic_n in skill_tokens:
        return True
    if any(topic_n in s or s in topic_n for s in skill_tokens if len(s) >= 3):
        return True
    aliases = _TOPIC_ALIASES.get(topic_n, {topic_n})
    return any(alias in skill_tokens or any(alias in s for s in skill_tokens) for alias in aliases)


def matches_profile(opp: Opportunity, candidate_skills: set[str]) -> bool:
    """Deterministic keep/drop against profile skills (no LLM).

    Keeps funded/general/untagged items, and anything whose topics or text
    overlap the candidate skill set. Drops siloed stacks the profile lacks
    (e.g. a pure ``php`` CFP when skills are Python/AI).
    """
    if not candidate_skills:
        return True
    skills = {s for s in candidate_skills if s}
    if is_funded(opp):
        return True
    topics = [t for t in (opp.topics or []) if t]
    if not topics:
        return True
    if any(_skills_cover_topic(t, skills) for t in topics):
        return True
    if score_opportunity_relevance(opp, skills) is not None:
        return True
    if all(_normalize_token(t) in _GENERAL_TOPICS for t in topics):
        return True
    return False


def is_funded(opp: Opportunity) -> bool:
    """Treat explicit funding text or grant/fellowship kinds as funded."""
    if opp.kind.value in {"grant", "fellowship"}:
        return True
    funding = (opp.funding or "").strip().lower()
    if not funding or funding in _NOT_FUNDED:
        return False
    return True
