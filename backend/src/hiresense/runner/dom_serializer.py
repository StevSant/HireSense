from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, Comment

# Page text is only context for the model, never the whole document. A cap
# keeps prompt cost bounded on long marketing-heavy job pages.
MAX_PAGE_TEXT = 4000
MAX_LABEL_CHARS = 300

# Widgets whose presence means a human has to take over. Never "solved".
_CAPTCHA_MARKERS = ("recaptcha", "hcaptcha", "turnstile", "funcaptcha", "arkoselabs")

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


def _detect_captcha(soup: BeautifulSoup, raw: str) -> bool:
    haystack = raw.casefold()
    if any(marker in haystack for marker in _CAPTCHA_MARKERS):
        return True
    for frame in soup.find_all("iframe"):
        src = (frame.get("src") or "").casefold()
        if any(marker in src for marker in _CAPTCHA_MARKERS):
            return True
    return False


def _selector_for(element: Any) -> str | None:
    """A stable CSS selector, preferring id then name. None when neither exists."""
    element_id = element.get("id")
    if element_id:
        return f"#{element_id}"
    name = element.get("name")
    if name:
        tag = element.name
        return f'{tag}[name="{name}"]'
    return None


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
    captcha = _detect_captcha(soup, html or "")
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
                or (element.get("aria-required") or "").casefold() == "true",
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
