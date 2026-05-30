from hiresense.matching.domain.scorers.json_extract import extract_json


def test_plain_object():
    assert extract_json('{"score": 0.5}') == {"score": 0.5}


def test_plain_array():
    assert extract_json('[{"ref": 1}, {"ref": 2}]') == [{"ref": 1}, {"ref": 2}]


def test_fenced_json_array():
    raw = "Here you go:\n```json\n[{\"ref\": 1, \"score\": 0.2}]\n```\nthanks"
    assert extract_json(raw) == [{"ref": 1, "score": 0.2}]


def test_array_embedded_in_prose():
    raw = 'Sure! [{"ref": 1, "score": 0.3}] is my answer.'
    assert extract_json(raw) == [{"ref": 1, "score": 0.3}]


def test_garbage_returns_none():
    assert extract_json("no json here at all") is None


def test_empty_returns_none():
    assert extract_json("") is None
