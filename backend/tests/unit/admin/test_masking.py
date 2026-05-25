from __future__ import annotations

from hiresense.admin.domain.masking import mask_api_key


def test_empty_returns_empty() -> None:
    assert mask_api_key(None) == ""
    assert mask_api_key("") == ""


def test_sk_prefix_kept_visible() -> None:
    masked = mask_api_key("sk-ant-abc1234567890xyz9")
    assert masked.startswith("sk-ant-")
    assert masked.endswith("xyz9")
    assert "abc1234567890" not in masked


def test_short_key_fully_masked() -> None:
    assert mask_api_key("abc12345") == "********"


def test_no_sk_prefix_keeps_4_then_4() -> None:
    masked = mask_api_key("xyzwabcdefghijklmnop")
    assert masked.startswith("xyzw")
    assert masked.endswith("mnop")
    assert "abcdefghijkl" not in masked
