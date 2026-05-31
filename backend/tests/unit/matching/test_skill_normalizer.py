from hiresense.matching.domain import normalize_skill


def test_lowercases() -> None:
    assert normalize_skill("Python") == "python"


def test_strips_whitespace() -> None:
    assert normalize_skill("  postgresql  ") == "postgresql"


def test_drops_parenthetical_qualifier() -> None:
    assert normalize_skill("Python (primary)") == "python"


def test_collapses_internal_whitespace() -> None:
    assert normalize_skill("distributed   systems") == "distributed systems"


def test_strips_edge_punctuation_but_keeps_internal_dot() -> None:
    assert normalize_skill("Node.js,") == "node.js"


def test_maps_alias_to_canonical() -> None:
    assert normalize_skill("postgres") == "postgresql"
    assert normalize_skill("k8s") == "kubernetes"
    assert normalize_skill("JS") == "javascript"


def test_alias_applied_after_cleaning() -> None:
    # qualifier stripped, then alias resolved
    assert normalize_skill("Golang (primary)") == "go"
