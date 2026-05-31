from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from hiresense.admin.domain.resolved_config import ResolvedConfig


class LLMFactoryPort(Protocol):
    """Port that builds and caches LangChain chat-model instances."""

    def build_chat_model(self, config: "ResolvedConfig") -> Any: ...

    def invalidate(self) -> None: ...
