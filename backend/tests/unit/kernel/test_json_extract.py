from hiresense.shared.kernel import extract_json


def test_plain_object():
    assert extract_json('{"score": 0.5}') == {"score": 0.5}


def test_plain_array():
    assert extract_json('[{"ref": 1}, {"ref": 2}]') == [{"ref": 1}, {"ref": 2}]


def test_fenced_json_array():
    raw = 'Here you go:\n```json\n[{"ref": 1, "score": 0.2}]\n```\nthanks'
    assert extract_json(raw) == [{"ref": 1, "score": 0.2}]


def test_array_embedded_in_prose():
    raw = 'Sure! [{"ref": 1, "score": 0.3}] is my answer.'
    assert extract_json(raw) == [{"ref": 1, "score": 0.3}]


def test_garbage_returns_none():
    assert extract_json("no json here at all") is None


def test_empty_returns_none():
    assert extract_json("") is None


def test_fenced_object_without_json_tag():
    raw = 'Result:\n```\n{"name": "acme", "size": 20}\n```'
    assert extract_json(raw) == {"name": "acme", "size": 20}


def test_object_embedded_in_prose():
    raw = 'Here is the answer: {"score": 0.9, "rationale": "strong"} — hope it helps.'
    assert extract_json(raw) == {"score": 0.9, "rationale": "strong"}


def test_malformed_json_inside_fence_returns_none():
    raw = '```json\n{"score": 0.5,,}\n```'
    assert extract_json(raw) is None
