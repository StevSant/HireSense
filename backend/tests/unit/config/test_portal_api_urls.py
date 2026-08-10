"""Every portal adapter's base URL must come from config, not from source.

Globant and Thoughtworks used to hardcode their base URLs as constructor
defaults while the other six portal adapters were wired from settings. Workday
is the deliberate exception: each tenant lives on its own host, so there is no
global base URL to configure.
"""

import pytest

from hiresense.shared.config.groups import PortalsSettings


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")


def test_globant_and_thoughtworks_have_default_api_urls() -> None:
    settings = PortalsSettings()

    assert settings.globant_api_url == "https://career.globant.com/api/sap/job-requisition"
    assert settings.thoughtworks_api_url == "https://www.thoughtworks.com/rest/careers/jobs"


def test_globant_and_thoughtworks_urls_are_env_overridable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLOBANT_API_URL", "https://globant.test/api")
    monkeypatch.setenv("THOUGHTWORKS_API_URL", "https://tw.test/jobs")

    settings = PortalsSettings()

    assert settings.globant_api_url == "https://globant.test/api"
    assert settings.thoughtworks_api_url == "https://tw.test/jobs"


def test_no_placeholder_urls_in_portal_settings() -> None:
    """A default nobody can use (example.com) is a config smell, not a default."""
    defaults = [
        value for value in PortalsSettings().model_dump().values() if isinstance(value, str)
    ]

    assert not [url for url in defaults if "example." in url]


def test_workday_has_no_global_base_url_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workday endpoints are derived per tenant from portals.yml careers_url."""
    _set_required(monkeypatch)
    from hiresense.shared.config import Settings

    assert "workday_api_url" not in PortalsSettings.model_fields
    assert "workday_api_url" not in Settings.model_fields
