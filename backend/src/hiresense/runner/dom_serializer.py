from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Comment

# Page text is only context for the model, never the whole document. A cap
# keeps prompt cost bounded on long marketing-heavy job pages.
MAX_PAGE_TEXT = 4000
MAX_LABEL_CHARS = 300

# Hosts that serve captcha frames. Matched against an iframe's src, never
# against the page source at large -- see _detect_captcha.
CAPTCHA_FRAME_HOSTS = (
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "funcaptcha",
    "arkoselabs",
)
_CAPTCHA_FRAME_HOSTS = CAPTCHA_FRAME_HOSTS

# The path segment of the frame that actually presents a challenge to a human
# ("pick every bus"). reCAPTCHA/hCaptcha always embed an `anchor` frame -- the
# badge or checkbox -- but only inject a `bframe` when a challenge is really
# being asked. Blocking on `anchor` would block every Greenhouse posting.
CHALLENGE_FRAME_PATHS = ("/bframe", "/challenge")
_CHALLENGE_FRAME_PATHS = CHALLENGE_FRAME_PATHS

# An `anchor` frame is a passive badge for invisible/v3 reCAPTCHA, but for v2 it
# IS the "I'm not a robot" checkbox a human has to click. The rendered size is
# what distinguishes them, and the live Greenhouse enterprise anchor carries
# neither, so keying on these does not regress it.
INTERACTIVE_FRAME_SIZES = ("size=normal", "size=compact", "frame=checkbox")
_INTERACTIVE_FRAME_SIZES = INTERACTIVE_FRAME_SIZES

# Container elements a captcha library renders a visible widget into. Compared
# by EXACT class name: `g-recaptcha-response` is the hidden textarea holding the
# token, not a widget, and must not match.
CAPTCHA_WIDGET_CLASSES = frozenset({"g-recaptcha", "h-captcha", "cf-turnstile"})
_CAPTCHA_WIDGET_CLASSES = CAPTCHA_WIDGET_CLASSES

# The same rule as a CSS selector, for the driver-side probe. The
# `data-size="invisible"` exclusion mirrors _is_invisible(): an invisible-mode
# container is a config artifact, not a challenge, and it is what stops every
# reCAPTCHA-protected posting from escalating. The two detectors MUST agree.
CAPTCHA_WIDGET_SELECTOR = ", ".join(
    f'.{name}:not([data-size="invisible" i])' for name in sorted(CAPTCHA_WIDGET_CLASSES)
)

_PLAIN_IDENT = re.compile(r"[A-Za-z_-][A-Za-z0-9_-]*")

_VALUE_TYPES = ("text", "email", "tel", "url", "number", "date", "password", "search")
_SKIP_TYPES = ("hidden", "image", "reset")


def _clean(soup: BeautifulSoup) -> None:
    """Strip everything executable or presentational.

    A security boundary, not a size optimisation: this page is attacker-
    controlled content that is about to be put in front of a language model.
    """
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()


def _is_invisible(element: Any) -> bool:
    """True when a captcha container declares itself non-interactive.

    Only `data-size` is consulted -- the correct signal for reCAPTCHA and
    hCaptcha. Turnstile configures this via the dashboard or `data-appearance`,
    so a non-interactive Turnstile widget is still treated as blocking. That is
    the safe direction (over-escalate, never under-escalate), so it is left
    alone deliberately rather than guessed at.
    """
    size = str(element.get("data-size") or "").casefold()
    return size == "invisible"


def _detect_captcha(soup: BeautifulSoup) -> bool:
    """True only when an INTERACTIVE challenge is on the page.

    Deliberately narrow. An earlier version substring-searched the whole page
    source for "recaptcha"/"turnstile", which made every Greenhouse posting
    escalate: Greenhouse ships a `GOOGLE_RECAPTCHA_INVISIBLE_KEY` inside a JS
    config blob on every job page, with no widget anywhere in the DOM. That is
    a configuration value, not a challenge, and treating it as one made
    auto-apply useless on the most common ATS.

    So we look for evidence a human is actually being asked something:
      * a visible widget container, matched by EXACT class name, or
      * a challenge frame (`bframe`), which the library injects only when it
        decides to present a puzzle.

    Everything else about a captcha is ambient and must not block: the config
    key, the badge `anchor` frame that every reCAPTCHA-protected page carries,
    and the hidden `g-recaptcha-response` textarea that holds the token. All
    three are present on a normal, perfectly fillable Greenhouse form.

    If an invisible challenge does reject the submission, that surfaces as a
    failed submit -- the honest place for it, rather than pre-emptively
    escalating every job before a single field is typed.
    """
    for element in soup.find_all(class_=True):
        classes = {str(name).casefold() for name in (element.get("class") or [])}
        if classes & _CAPTCHA_WIDGET_CLASSES and not _is_invisible(element):
            return True

    for frame in soup.find_all("iframe"):
        src = str(frame.get("src") or "").casefold()
        if not any(host in src for host in _CAPTCHA_FRAME_HOSTS):
            continue
        if any(path in src for path in _CHALLENGE_FRAME_PATHS):
            return True
        if any(size in src for size in _INTERACTIVE_FRAME_SIZES):
            return True

    return False


# Deep enough to walk any real form out to <body>. A React-rendered ATS page
# can nest a control dozens of levels below the nearest ancestor id; bailing out
# early would drop the element entirely and reinstate the "filled form with no
# submit control" bug this fallback exists to fix.
MAX_CSS_PATH_DEPTH = 60


def _quote(value: str) -> str:
    """Quote a value for use inside a CSS attribute selector."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _id_selector(value: str) -> str:
    """`#id` when the id is a plain CSS identifier, else a quoted attribute.

    Ids and names come from the employer's page, and HTML5 permits almost any
    character in them. Interpolating one straight into `#...` produces a
    selector that either fails to parse (`#123abc`) or silently means something
    else (`#a:b.c` is a compound, not an id), and a crafted value could close
    the selector and redirect a fill to an element of the page's choosing.
    """
    if _PLAIN_IDENT.fullmatch(value):
        return f"#{value}"
    return f"[id={_quote(value)}]"


def _css_path(element: Any) -> str | None:
    """Build a positional CSS path for an element with no id or name.

    Walks up to the nearest ancestor carrying an id (or to <body>), emitting
    `tag:nth-of-type(k)` segments. Plain CSS, so it stays browser-agnostic and
    works with any driver.

    Needed because real ATS controls often have neither id nor name -- notably
    Greenhouse's `<button type="submit">Submit application</button>`, which
    carries no attributes at all. Dropping such elements meant the agent could
    see a fully filled form but no way to submit it.
    """
    segments: list[str] = []
    current = element
    for _ in range(MAX_CSS_PATH_DEPTH):
        parent = current.parent
        if parent is None or getattr(parent, "name", None) is None:
            return None

        # Index by identity. BeautifulSoup's Tag.__eq__ compares by value, so
        # list.index()/`in` match the FIRST structurally-equal sibling -- two
        # identical buttons would collapse onto one selector that silently
        # drives the wrong control.
        siblings = parent.find_all(current.name, recursive=False)
        index = next((i for i, s in enumerate(siblings) if s is current), 0) + 1
        segments.append(f"{current.name}:nth-of-type({index})")

        parent_id = parent.get("id") if hasattr(parent, "get") else None
        if parent_id:
            segments.append(_id_selector(str(parent_id)))
            break
        if parent.name in ("body", "html"):
            segments.append(parent.name)
            break
        current = parent
    else:
        return None

    return " > ".join(reversed(segments))


def _selector_for(element: Any) -> str | None:
    """A stable CSS selector: id, then name, then a positional path."""
    element_id = element.get("id")
    if element_id:
        return _id_selector(str(element_id))
    name = element.get("name")
    if name:
        return f"{element.name}[name={_quote(str(name))}]"
    return _css_path(element)


def _label_for(soup: BeautifulSoup, element: Any) -> str:
    """Resolve a field's visible label the way a human reads the form."""
    element_id = element.get("id")
    if element_id:
        label = soup.find("label", attrs={"for": element_id})
        if label is not None:
            return label.get_text(" ", strip=True)[:MAX_LABEL_CHARS]

    parent = element.parent
    while parent is not None and getattr(parent, "name", None) is not None:
        if parent.name == "label":
            return parent.get_text(" ", strip=True)[:MAX_LABEL_CHARS]
        parent = parent.parent

    for attr in ("aria-label", "placeholder", "title", "name"):
        value = element.get(attr)
        if value:
            return str(value)[:MAX_LABEL_CHARS]
    return ""


def _field_type(element: Any) -> str:
    if element.name == "textarea":
        return "textarea"
    if element.name == "select":
        return "select"
    if element.name == "button":
        return (element.get("type") or "submit").casefold()
    return (element.get("type") or "text").casefold()


def _options(element: Any) -> list[str]:
    if element.name != "select":
        return []
    return [o.get_text(" ", strip=True) for o in element.find_all("option")]


def _current_value(element: Any) -> str | None:
    if element.name == "textarea":
        return element.get_text() or None
    if element.name == "select":
        selected = element.find("option", selected=True)
        return selected.get_text(" ", strip=True) if selected is not None else None
    return element.get("value") or None


def serialize_dom(html: str, *, url: str, title: str = "") -> dict:
    """Turn raw page HTML into a PageObservation-shaped dict.

    Pure and browser-free, so the whole extraction path is testable against
    saved HTML fixtures without ever touching a live employer site.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    captcha = _detect_captcha(soup)
    _clean(soup)

    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag is not None else ""

    fields: list[dict] = []
    for element in soup.find_all(["input", "textarea", "select", "button"]):
        field_type = _field_type(element)
        if field_type in _SKIP_TYPES:
            continue
        selector = _selector_for(element)
        if selector is None:
            continue
        label = _label_for(soup, element)
        if element.name == "button" or field_type == "submit":
            label = label or element.get_text(" ", strip=True)[:MAX_LABEL_CHARS]
        fields.append(
            {
                "selector": selector,
                "label": label,
                "field_type": field_type
                if field_type in _VALUE_TYPES
                or field_type
                in ("textarea", "select", "file", "checkbox", "radio", "submit", "button")
                else "text",
                "required": element.has_attr("required")
                or str(element.get("aria-required") or "").casefold() == "true",
                "options": _options(element),
                "current_value": _current_value(element),
            }
        )

    return {
        "url": url,
        "title": title,
        "fields": fields,
        "captcha_detected": captcha,
        "page_text": soup.get_text(" ", strip=True)[:MAX_PAGE_TEXT],
    }
