from __future__ import annotations

from typing import Any, AsyncIterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


class LangChainLLMAdapter:
    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        target = self._model.bind(model=model) if model else self._model
        response = await target.ainvoke(messages)
        return response.content

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]:
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        async for chunk in self._model.astream(messages):
            if chunk.content:
                yield chunk.content
