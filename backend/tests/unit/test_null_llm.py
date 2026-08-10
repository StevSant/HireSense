from __future__ import annotations

import pytest

from hiresense.shared.adapters.llm import NullLLM
from hiresense.shared.kernel.exceptions import UpstreamUnavailableError
from hiresense.shared.ports import LLMNotConfiguredError


@pytest.mark.asyncio
async def test_complete_raises_instead_of_returning_a_stand_in() -> None:
    with pytest.raises(LLMNotConfiguredError):
        await NullLLM().complete("anything")


@pytest.mark.asyncio
async def test_stream_raises_on_first_iteration() -> None:
    """It is an async generator like the real adapter, so callers can keep
    using `async for` and still get the failure."""
    with pytest.raises(LLMNotConfiguredError):
        async for _ in NullLLM().stream("anything"):
            pass


@pytest.mark.asyncio
async def test_message_names_the_feature_that_could_not_run() -> None:
    with pytest.raises(LLMNotConfiguredError, match="cv_translator"):
        await NullLLM(feature="cv_translator").complete("anything")


@pytest.mark.asyncio
async def test_message_without_a_feature_still_states_the_cause() -> None:
    with pytest.raises(LLMNotConfiguredError, match="LLM not configured"):
        await NullLLM().complete("anything")


def test_not_configured_is_a_distinguishable_kind_of_unavailable() -> None:
    """Subclassing inherits the 503 handler registered on the base type, while
    the narrower type still lets retry logic tell a missing API key (never
    resolves itself) from a provider outage (worth retrying)."""
    assert issubclass(LLMNotConfiguredError, UpstreamUnavailableError)
    assert LLMNotConfiguredError is not UpstreamUnavailableError


def test_not_configured_stays_a_runtime_error_not_a_value_error() -> None:
    """Routers with `except ValueError` map to 400. An unconfigured LLM is not
    a bad request, so it must not be catchable there."""
    assert issubclass(LLMNotConfiguredError, RuntimeError)
    assert not issubclass(LLMNotConfiguredError, ValueError)
