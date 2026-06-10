import pytest

from hiresense.network.domain import normalize_company


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme Inc.", "acme"),
        ("ACME, LLC", "acme"),
        ("Globant S.A.", "globant"),
        ("Mercado Libre S.A. de C.V.", "mercado libre"),
        ("Stripe", "stripe"),
        ("  Banco   Guayaquil  ", "banco guayaquil"),
        ("Thoughtworks Ltd", "thoughtworks"),
        ("Siemens GmbH", "siemens"),
        ("MixRank (YC S11)", "mixrank"),
        ("Studio C", "studio c"),
        ("Plan A", "plan a"),
        ("Tesla Model S", "tesla model s"),
        ("", ""),
    ],
)
def test_normalize_company(raw: str, expected: str) -> None:
    assert normalize_company(raw) == expected
