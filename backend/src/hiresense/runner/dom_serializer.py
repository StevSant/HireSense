from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, Comment

# Page text is only context for the model, never the whole document. A cap
# keeps prompt cost bounded on long marketing-heavy job pages.
MAX_PAGE_TEXT = 4000
MAX_LABEL_CHARS = 300

# Hosts that serve captcha frames. Matched against an iframe's src, never
# against the page source at large -- see _detect_captcha.
_CAPTCHA_FRAME_HOSTS = (
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "funcaptcha",
    "arkoselabs",
)

# The path segment of the frame that actually presents a challenge to a human
# ("pick every bus"). reCAPTCHA/hCaptcha always embed an `anchor` frame -- the
# badge or checkbox -- but only inject a `bframe` when a challenge is really
# being asked. Blocking on `anchor` would block every Greenhouse posting.
_CHALLENGE_FRAME_PATHS = ("/bframe", "/challenge")

# Container elements a captcha library renders a visible widget into. Compared
# by EXACT class name: `g-recaptcha-response` is the hidden textarea holding the
# token, not a widget, and must not match.
_CAPTCHA_WIDGET_CLASSES = frozenset({"g-recaptcha", "h-captcha", "cf-turnstile"})

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
    """True when a captcha container is configured not to need interaction."""
    size = str(element.get("data-size") or "").casefold()
    return size in ("invisible",)


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

    return False


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
    for _ in range(12):  # depth guard; ATS forms are nowhere near this deep
        parent = current.parent
        if parent is None or getattr(parent, "name", None) is None:
            return None

        siblings = [s for s in parent.find_all(current.name, recursive=False)]
        index = siblings.index(current) + 1 if current in siblings else 1
        segments.append(f"{current.name}:nth-of-type({index})")

        parent_id = parent.get("id") if hasattr(parent, "get") else None
        if parent_id:
            segments.append(f"#{parent_id}")
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
        return f"#{element_id}"
    name = element.get("name")
    if name:
        tag = element.name
        return f'{tag}[name="{name}"]'
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
