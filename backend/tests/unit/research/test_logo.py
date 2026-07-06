from hiresense.research.domain import logo_url


def test_logo_url_from_website():
    assert logo_url("https://www.bc.cl/careers", "https://logo.x/{domain}") == "https://logo.x/bc.cl"


def test_logo_url_bare_domain():
    assert logo_url("bc.cl", "https://logo.x/{domain}") == "https://logo.x/bc.cl"


def test_logo_url_none_when_no_website():
    assert logo_url(None, "https://logo.x/{domain}") is None


def test_logo_url_none_when_no_service():
    assert logo_url("https://bc.cl", "") is None
