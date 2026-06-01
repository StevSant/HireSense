from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STYLE_GUIDE = (
    "Write a short, professional outreach message. Be concise and specific: "
    "name the role, mention one genuine, concrete reason you're a fit, and close "
    "with a light call to connect. No fluff."
)


def load_style_guide(path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
        return text or DEFAULT_STYLE_GUIDE
    except OSError:
        logger.warning("outreach: style guide not readable at %s — using default", path)
        return DEFAULT_STYLE_GUIDE
