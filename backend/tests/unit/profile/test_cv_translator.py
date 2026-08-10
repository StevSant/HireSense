import pytest

from hiresense.shared.adapters.llm import NullLLM
from hiresense.shared.ports import LLMNotConfiguredError
from hiresense.profile.domain.cv_translator import CVTranslator


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    async def complete(self, prompt: str, system: str | None = None) -> str:
        self.last_prompt = prompt
        self.last_system = system
        return self.response


@pytest.mark.asyncio
async def test_translate_returns_tex_and_strips_markdown_fence() -> None:
    llm = FakeLLM("```latex\n\\section*{RESUMEN}\nIngeniero backend.\n```")
    translator = CVTranslator(llm=llm)
    result = await translator.translate("\\section*{SUMMARY}\nBackend engineer.", "en", "es")
    assert result == "\\section*{RESUMEN}\nIngeniero backend."


@pytest.mark.asyncio
async def test_translate_prompt_preserves_commands_and_names_languages() -> None:
    llm = FakeLLM("\\section*{RESUMEN}")
    translator = CVTranslator(llm=llm)
    await translator.translate("\\section*{SUMMARY}", "en", "es")
    assert "do not alter" in llm.last_prompt.lower()
    assert "English" in llm.last_prompt
    assert "Spanish" in llm.last_prompt


@pytest.mark.asyncio
async def test_translate_raises_when_llm_unconfigured() -> None:
    # The composition layer injects a NullLLM when no provider is configured,
    # so the not-configured failure comes from the LLM, not a guard here. Still
    # a RuntimeError, so the route keeps mapping it to a 503.
    translator = CVTranslator(llm=NullLLM(feature="cv_translator"))
    with pytest.raises(LLMNotConfiguredError):
        await translator.translate("\\section*{SUMMARY}", "en", "es")
    assert issubclass(LLMNotConfiguredError, RuntimeError)
