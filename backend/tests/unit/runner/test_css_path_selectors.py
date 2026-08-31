"""Selector generation for elements with no id and no name.

The agent types a real person's data into real employer forms using these
selectors, so a selector that is syntactically valid but points at the WRONG
element is worse than no selector at all: it fails silently.
"""

from bs4 import BeautifulSoup

from hiresense.runner import serialize_dom
from hiresense.runner.dom_serializer import _css_path


def _paths(html: str, tag: str = "button") -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [_css_path(el) for el in soup.find_all(tag)]


def test_identical_siblings_get_distinct_selectors():
    """BeautifulSoup compares tags by VALUE, so a naive list.index() returns the
    first structurally-equal sibling and every duplicate collapses onto one
    selector. Duplicated submit controls (mobile + desktop variants) are common
    in ATS markup, so this must index by identity."""
    html = (
        '<div id="application-form">'
        '<div><button type="submit">Submit application</button></div>'
        '<div><button type="submit">Submit application</button></div>'
        "</div>"
    )
    paths = _paths(html)
    assert len(paths) == 2
    assert paths[0] != paths[1], f"identical siblings collapsed onto {paths[0]!r}"


def test_each_generated_selector_resolves_to_its_own_element():
    html = '<div id="form"><div><input /></div><div><input /></div><div><input /></div></div>'
    soup = BeautifulSoup(html, "html.parser")
    inputs = soup.find_all("input")
    paths = [_css_path(el) for el in inputs]
    assert len(set(paths)) == 3


def test_path_anchors_on_the_nearest_ancestor_id():
    html = '<div id="anchor"><section><button type="submit">Go</button></section></div>'
    path = _paths(html)[0]
    assert path.startswith("#anchor")


def test_deeply_nested_control_is_not_dropped():
    """A React-rendered ATS page can nest a control far below the nearest id.
    Returning None here reinstates the exact bug this file exists to prevent:
    a filled form with no reachable submit control."""
    inner = '<button type="submit">Submit application</button>'
    html = '<div id="root">' + "<div>" * 30 + inner + "</div>" * 30 + "</div>"
    path = _paths(html)[0]
    assert path is not None
    assert path.endswith("button:nth-of-type(1)")


def test_serializer_keeps_a_submit_button_with_no_id_or_name():
    html = (
        "<html><body><form>"
        '<input id="email" name="email" required />'
        '<button type="submit">Submit application</button>'
        "</form></body></html>"
    )
    obs = serialize_dom(html, url="https://x.test")
    submits = [f for f in obs["fields"] if f["field_type"] == "submit"]
    assert len(submits) == 1
    assert submits[0]["selector"]


# --- selector escaping: ids and names are employer-controlled ---------------


def test_id_with_css_metacharacters_is_not_emitted_raw():
    """HTML5 permits almost any character in an id. `#a:b.c` is a valid id but
    parses as a compound selector, so it must be quoted rather than interpolated."""
    html = '<html><body><input id="a:b.c" required /></body></html>'
    obs = serialize_dom(html, url="https://x.test")
    selector = obs["fields"][0]["selector"]
    assert selector != "#a:b.c"
    assert "a:b.c" in selector


def test_id_starting_with_a_digit_is_quoted():
    html = '<html><body><input id="123abc" required /></body></html>'
    selector = serialize_dom(html, url="https://x.test")["fields"][0]["selector"]
    assert not selector.startswith("#1")


def test_name_that_would_break_out_of_the_attribute_selector_is_escaped():
    """A crafted name must not be able to close the attribute selector and
    append a second compound that redirects the fill elsewhere.

    The property that matters is that every quote inside the value is
    backslash-escaped, so the value stays one CSS string. Metacharacters such
    as `[` are harmless once they cannot escape the quotes.
    """
    html = "<html><body><input name='x\"] , [id=\"other' required /></body></html>"
    selector = serialize_dom(html, url="https://x.test")["fields"][0]["selector"]

    assert selector.startswith('input[name="')
    assert selector.endswith('"]')
    body = selector[len('input[name="') : -len('"]')]
    # No unescaped quote survives inside the value.
    assert '"' not in body.replace('\\"', "")


def test_plain_id_still_uses_the_readable_hash_form():
    html = '<html><body><input id="first_name" required /></body></html>'
    selector = serialize_dom(html, url="https://x.test")["fields"][0]["selector"]
    assert selector == "#first_name"
