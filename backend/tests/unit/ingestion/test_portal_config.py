import pytest
from pathlib import Path
from hiresense.ingestion.domain.portal_config import (
    PortalEntry,
    PortalsConfig,
    load_portals_config,
)


def test_portal_entry_model() -> None:
    entry = PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic")
    assert entry.name == "Anthropic"
    assert entry.platform == "greenhouse"
    assert entry.board_id == "anthropic"
    assert entry.categories == []


def test_portal_entry_with_categories() -> None:
    entry = PortalEntry(
        name="Anthropic",
        platform="greenhouse",
        board_id="anthropic",
        categories=["ai-research"],
    )
    assert entry.categories == ["ai-research"]


def test_portal_entry_rejects_invalid_platform() -> None:
    with pytest.raises(ValueError):
        PortalEntry(name="Foo", platform="invalid", board_id="foo")


def test_portals_config_model() -> None:
    config = PortalsConfig(
        portals=[
            PortalEntry(name="A", platform="greenhouse", board_id="a"),
            PortalEntry(name="B", platform="lever", board_id="b"),
        ]
    )
    assert len(config.portals) == 2


def test_load_portals_config(tmp_path: Path) -> None:
    yml = tmp_path / "portals.yml"
    yml.write_text(
        "portals:\n"
        "  - name: TestCo\n"
        "    platform: ashby\n"
        "    board_id: testco\n"
        "    categories: [ai]\n"
    )
    config = load_portals_config(yml)
    assert len(config.portals) == 1
    assert config.portals[0].name == "TestCo"
    assert config.portals[0].platform == "ashby"
    assert config.portals[0].categories == ["ai"]


def test_load_portals_config_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_portals_config(Path("/nonexistent/portals.yml"))


def test_filter_by_category() -> None:
    config = PortalsConfig(
        portals=[
            PortalEntry(name="A", platform="greenhouse", board_id="a", categories=["ai"]),
            PortalEntry(name="B", platform="lever", board_id="b", categories=["devtools"]),
            PortalEntry(name="C", platform="ashby", board_id="c", categories=["ai", "devtools"]),
        ]
    )
    filtered = [p for p in config.portals if "ai" in p.categories]
    assert len(filtered) == 2
    assert {p.name for p in filtered} == {"A", "C"}


def test_filter_by_company() -> None:
    config = PortalsConfig(
        portals=[
            PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
            PortalEntry(name="Retool", platform="lever", board_id="retool"),
        ]
    )
    filtered = [p for p in config.portals if p.name in ["Anthropic"]]
    assert len(filtered) == 1
    assert filtered[0].board_id == "anthropic"
