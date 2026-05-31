from __future__ import annotations

import hashlib
import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hiresense.admin.domain.resolved_config import ResolvedConfig

logger = logging.getLogger(__name__)


class UnsupportedProviderError(RuntimeError):
    """The requested provider is not wired into the factory."""


class LLMFactory:
    """Builds LangChain BaseChatModel instances from a ResolvedConfig.

    Instances are cached by a key derived from (provider, model, api_key, extra_params)
    so we don't reconstruct the client on every call. Cache size is bounded by the
    number of distinct configurations the admin uses across features, which in
    practice is small (one global + a handful of overrides).
    """

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def build_chat_model(self, config: ResolvedConfig) -> Any:
        cache_key = self._cache_key(config)
        with self._lock:
            existing = self._cache.get(cache_key)
            if existing is not None:
                return existing
        model = self._construct(config)
        with self._lock:
            self._cache[cache_key] = model
        return model

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()

    @staticmethod
    def _cache_key(config: ResolvedConfig) -> str:
        # Hash the API key so it never sits in a Python dict in plaintext form
        # for longer than necessary. provider/model/extra_params are short.
        key_digest = hashlib.sha256(config.api_key.encode("utf-8")).hexdigest()[:16]
        extras = "&".join(f"{k}={v}" for k, v in sorted(config.extra_params.items()))
        return f"{config.provider}|{config.model}|{key_digest}|{extras}"

    def _construct(self, config: ResolvedConfig) -> Any:
        provider = config.provider.lower()
        if provider == "anthropic":
            try:
                from langchain_anthropic import ChatAnthropic
            except ImportError as exc:
                raise UnsupportedProviderError("langchain_anthropic not installed") from exc
            kwargs: dict[str, Any] = {"model": config.model, "api_key": config.api_key}
            kwargs.update(self._filter_extras(config.extra_params, allowed={"temperature", "max_tokens", "base_url"}))
            return ChatAnthropic(**kwargs)
        if provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise UnsupportedProviderError(
                    "langchain_openai not installed (install hiresense[openai] or add the package)"
                ) from exc
            kwargs = {"model": config.model, "api_key": config.api_key}
            kwargs.update(self._filter_extras(config.extra_params, allowed={"temperature", "max_tokens", "base_url"}))
            return ChatOpenAI(**kwargs)
        if provider == "groq":
            try:
                from langchain_groq import ChatGroq
            except ImportError as exc:
                raise UnsupportedProviderError(
                    "langchain_groq not installed (install hiresense[groq])"
                ) from exc
            kwargs = {"model": config.model, "api_key": config.api_key}
            kwargs.update(self._filter_extras(config.extra_params, allowed={"temperature", "max_tokens"}))
            return ChatGroq(**kwargs)
        if provider == "ollama":
            try:
                from langchain_ollama import ChatOllama
            except ImportError as exc:
                raise UnsupportedProviderError(
                    "langchain_ollama not installed (install hiresense[ollama])"
                ) from exc
            kwargs = {"model": config.model}
            kwargs.update(self._filter_extras(config.extra_params, allowed={"temperature", "base_url"}))
            return ChatOllama(**kwargs)
        raise UnsupportedProviderError(f"unknown provider: {config.provider}")

    @staticmethod
    def _filter_extras(extras: dict, *, allowed: set[str]) -> dict:
        return {k: v for k, v in (extras or {}).items() if k in allowed}
