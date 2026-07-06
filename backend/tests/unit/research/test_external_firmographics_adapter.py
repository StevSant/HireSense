from __future__ import annotations

import httpx
import pytest

from hiresense.research.infrastructure import ExternalFirmographicsAdapter


class _FakeResponse:
    """Minimal stand-in for httpx.Response: raise_for_status() + json()."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    """Minimal stand-in for httpx.AsyncClient used as an async context manager."""

    def __init__(self, payload: dict, **_kwargs: object) -> None:
        self._payload = payload

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(self._payload)


@pytest.mark.asyncio
async def test_fetch_returns_none_when_provider_url_blank() -> None:
    adapter = ExternalFirmographicsAdapter(provider_url="", api_key="secret")

    result = await adapter.fetch("Acme Corp")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_returns_none_when_api_key_blank() -> None:
    adapter = ExternalFirmographicsAdapter(
        provider_url="https://example.com/firmographics", api_key=""
    )

    result = await adapter.fetch("Acme Corp")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_does_not_make_http_call_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("httpx.AsyncClient should not be constructed when unconfigured")

    monkeypatch.setattr(httpx, "AsyncClient", _fail_if_called)
    adapter = ExternalFirmographicsAdapter(provider_url="", api_key="")

    result = await adapter.fetch("Acme Corp")

    assert result is None
    assert called is False


@pytest.mark.asyncio
async def test_fetch_returns_none_on_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    # company_size as a number fails Firmographics' `str | None` validation.
    malformed_payload = {"industry": "SaaS", "company_size": 250}

    def _fake_client(*_args: object, **kwargs: object) -> _FakeAsyncClient:
        return _FakeAsyncClient(malformed_payload, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _fake_client)
    adapter = ExternalFirmographicsAdapter(
        provider_url="https://example.com/firmographics", api_key="secret"
    )

    result = await adapter.fetch("Acme Corp")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_returns_firmographics_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "industry": "SaaS",
        "company_size": "51-200",
        "headquarters": "Santiago, CL",
        "website": "https://acme.example",
    }

    def _fake_client(*_args: object, **kwargs: object) -> _FakeAsyncClient:
        return _FakeAsyncClient(payload, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _fake_client)
    adapter = ExternalFirmographicsAdapter(
        provider_url="https://example.com/firmographics", api_key="secret"
    )

    result = await adapter.fetch("Acme Corp")

    assert result is not None
    assert result.industry == "SaaS"
    assert result.company_size == "51-200"
    assert result.headquarters == "Santiago, CL"
    assert result.website == "https://acme.example"
