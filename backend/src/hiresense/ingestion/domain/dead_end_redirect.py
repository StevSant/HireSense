from __future__ import annotations

from urllib.parse import urlsplit

# Paths a board sends a dead listing to when it has nothing specific left to
# show. Matched exactly (after stripping a trailing slash) so a real listing
# path is never mistaken for one of them.
_GENERIC_PATHS = frozenset({"", "/"})


def is_dead_end_redirect(original_url: str, final_url: str, markers: list[str]) -> bool:
    """True when a probe was bounced from a specific listing to a generic page.

    Boards rarely 404 a removed listing. WeWorkRemotely 301s it to the site
    root; LinkedIn 301s it to a generic role search carrying
    `trk=expired_jd_redirect`. Following those hops costs a second request and
    then classifies a *homepage* body, which matches no closure marker — so the
    job stayed open and was re-probed on every sweep, forever.

    Recognising the redirect target itself lets the probe close the job without
    fetching the landing page. Deliberately conservative: only an exactly-generic
    final path or an explicit configured marker counts, because a false positive
    closes a live job. A board rewriting a listing URL to its canonical form
    (getonbrd's `/jobs/<slug>` -> `/jobs/<category>/<slug>`) is NOT a dead end.
    """
    if not original_url or not final_url or original_url == final_url:
        return False
    original = urlsplit(original_url)
    final = urlsplit(final_url)
    # A probe that started at a root URL has no specific listing to lose.
    if original.path.rstrip("/") in _GENERIC_PATHS:
        return False
    if any(marker and marker in final_url for marker in markers):
        return True
    return final.path.rstrip("/") in _GENERIC_PATHS
