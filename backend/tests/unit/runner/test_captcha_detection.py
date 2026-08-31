"""Captcha detection must fire on a real challenge and only on a real challenge.

The regression these guard: an earlier detector substring-searched the whole page
source for "recaptcha"/"turnstile". Greenhouse ships a
GOOGLE_RECAPTCHA_INVISIBLE_KEY inside a JS config blob on every job page, so
every Greenhouse posting escalated immediately and auto-apply was dead on the
most common ATS. Verified against a live Cloudflare/Greenhouse page 2026-08-30.
"""

from hiresense.runner import serialize_dom


def _detect(body: str) -> bool:
    return serialize_dom(f"<html><body>{body}</body></html>", url="https://x.test")[
        "captcha_detected"
    ]


# --- must NOT fire -------------------------------------------------------


def test_greenhouse_invisible_recaptcha_config_blob_is_not_a_challenge():
    body = (
        '<script>window.CONFIG = {"DROPBOX_CHOOSER_API_KEY":"abc",'
        '"GOOGLE_RECAPTCHA_INVISIBLE_KEY":"6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0"};'
        "</script>"
        '<form><input id="first_name" name="first_name" required /></form>'
    )
    assert _detect(body) is False


def test_the_word_recaptcha_in_page_copy_is_not_a_challenge():
    body = "<p>We use reCAPTCHA and Cloudflare Turnstile to protect this site.</p>"
    assert _detect(body) is False


def test_form_fields_survive_a_page_that_merely_mentions_recaptcha():
    obs = serialize_dom(
        '<html><body><script>var k="GOOGLE_RECAPTCHA_INVISIBLE_KEY";</script>'
        '<form><label for="email">Email *</label>'
        '<input id="email" name="email" required /></form></body></html>',
        url="https://x.test",
    )
    assert obs["captcha_detected"] is False
    assert [f["selector"] for f in obs["fields"]] == ["#email"]


def test_invisible_widget_container_does_not_block():
    body = '<div class="g-recaptcha" data-size="invisible" data-sitekey="k"></div>'
    assert _detect(body) is False


def test_greenhouse_enterprise_anchor_frame_does_not_block():
    """The real shape observed on a live Cloudflare/Greenhouse posting.

    Every reCAPTCHA-protected page carries an `anchor` badge frame. It is not a
    challenge, and this exact URL made all four sampled Greenhouse jobs escalate
    before the fix.
    """
    body = (
        '<iframe src="https://www.recaptcha.net/recaptcha/enterprise/anchor?ar=1&k=6Lfmcbcp">'
        "</iframe>"
    )
    assert _detect(body) is False


def test_hidden_recaptcha_response_textarea_does_not_block():
    """reCAPTCHA injects this textarea to hold its token. It is not a widget --
    a substring match on `g-recaptcha` used to flag it on every Greenhouse form."""
    body = '<textarea class="g-recaptcha-response" style="display:none"></textarea>'
    assert _detect(body) is False


def test_invisible_anchor_iframe_does_not_block():
    body = (
        '<iframe src="https://www.google.com/recaptcha/api2/anchor?k=abc&size=invisible"></iframe>'
    )
    assert _detect(body) is False


# --- must fire -----------------------------------------------------------


def test_visible_recaptcha_widget_blocks():
    assert _detect('<div class="g-recaptcha" data-sitekey="k"></div>') is True


def test_hcaptcha_widget_blocks():
    assert _detect('<div class="h-captcha" data-sitekey="k"></div>') is True


def test_turnstile_widget_blocks():
    assert _detect('<div class="cf-turnstile" data-sitekey="k"></div>') is True


def test_interactive_challenge_iframe_blocks():
    body = '<iframe src="https://www.google.com/recaptcha/api2/bframe?k=abc"></iframe>'
    assert _detect(body) is True


def test_arkose_challenge_iframe_blocks():
    body = '<iframe src="https://client-api.arkoselabs.com/fc/gc/challenge?k=x"></iframe>'
    assert _detect(body) is True
