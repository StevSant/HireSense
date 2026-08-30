from pathlib import Path

from hiresense.runner import serialize_dom

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "greenhouse_apply.html"


def _observation():
    return serialize_dom(
        FIXTURE.read_text(encoding="utf-8"),
        url="https://boards.greenhouse.io/acme/jobs/1",
        title="Apply",
    )


def _by_label():
    return {f["label"]: f for f in _observation()["fields"]}


def test_extracts_labelled_fields():
    labels = set(_by_label())
    assert "First Name *" in labels
    assert "Email *" in labels
    assert "Resume/CV *" in labels


def test_label_resolves_through_a_wrapping_label_element():
    # last_name has no id, so its label can only come from the wrapping <label>.
    fields = _observation()["fields"]
    last_name = next(f for f in fields if f["selector"] == 'input[name="last_name"]')
    assert "Last Name" in last_name["label"]


def test_marks_required_fields():
    fields = _by_label()
    assert fields["First Name *"]["required"] is True
    assert fields["How did you hear about us?"]["required"] is False


def test_scripts_and_styles_are_stripped():
    obs = _observation()
    assert "alert(" not in obs["page_text"]
    assert "dataLayer" not in obs["page_text"]
    assert "font-family" not in obs["page_text"]


def test_page_text_keeps_the_human_readable_content():
    assert "payments infrastructure" in _observation()["page_text"]


def test_hidden_inputs_are_dropped():
    selectors = {f["selector"] for f in _observation()["fields"]}
    assert not any("csrf" in s for s in selectors)


def test_file_input_is_typed_as_file():
    assert _by_label()["Resume/CV *"]["field_type"] == "file"


def test_textarea_is_typed_as_textarea():
    assert _by_label()["Why do you want to work at Acme? *"]["field_type"] == "textarea"


def test_select_carries_its_options_and_current_value():
    field = _by_label()["Will you require visa sponsorship? *"]
    assert field["field_type"] == "select"
    assert "Yes" in field["options"] and "No" in field["options"]
    assert field["current_value"] == "No"


def test_submit_button_is_captured():
    fields = _observation()["fields"]
    submit = next(f for f in fields if f["selector"] == "#submit_app")
    assert submit["field_type"] == "submit"
    assert submit["label"] == "Submit Application"


def test_selector_prefers_id_then_name():
    assert _by_label()["First Name *"]["selector"] == "#first_name"
    selectors = {f["selector"] for f in _observation()["fields"]}
    assert 'input[name="last_name"]' in selectors


def test_captcha_is_detected_from_an_iframe():
    html = (
        '<html><body><iframe src="https://www.google.com/recaptcha/api2/anchor">'
        "</iframe></body></html>"
    )
    assert serialize_dom(html, url="https://x.test")["captcha_detected"] is True


def test_clean_page_reports_no_captcha():
    assert _observation()["captcha_detected"] is False


def test_title_falls_back_to_the_document_title():
    obs = serialize_dom(FIXTURE.read_text(encoding="utf-8"), url="https://x.test", title="")
    assert "Senior Backend Engineer" in obs["title"]


def test_empty_html_is_handled():
    obs = serialize_dom("", url="https://x.test")
    assert obs["fields"] == []
    assert obs["captcha_detected"] is False
