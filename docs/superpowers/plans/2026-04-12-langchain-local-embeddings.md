# LangChain Migration & Local Embeddings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the direct Anthropic SDK adapter with a LangChain-based adapter and add local sentence-transformers embeddings via a new EmbeddingPort, making the system provider-agnostic with zero external embedding API cost.

**Architecture:** Hexagonal ports/adapters. `LLMPort` loses `embed()`, new `EmbeddingPort` created. `LangChainLLMAdapter` wraps `BaseChatModel` (ChatAnthropic). `SentenceTransformerAdapter` wraps local sentence-transformers model. Domain layer stays untouched except the orchestrator accepting `EmbeddingPort`.

**Tech Stack:** LangChain (`langchain-anthropic`, `langchain-core`), sentence-transformers, FastAPI, Pydantic

---

### Task 1: Update Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add sentence-transformers and move langchain-anthropic to required**

In `backend/pyproject.toml`, update the `dependencies` list to add `sentence-transformers>=3.0.0` and `langchain-anthropic>=0.3.0`. Remove the `anthropic` and `openai` optional dependency groups:

```toml
[project]
name = "hiresense"
version = "0.1.0"
description = "AI-powered job matching and CV optimization system"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "sqlalchemy[asyncio]>=2.0.35",
    "asyncpg>=0.30.0",
    "pgvector>=0.3.5",
    "alembic>=1.14.0",
    "httpx>=0.27.0",
    "apscheduler>=3.10.0",
    "python-multipart>=0.0.12",
    "passlib[bcrypt]>=1.7.4",
    "python-jose[cryptography]>=3.3.0",
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "sentence-transformers>=3.0.0",
    "feedparser>=6.0.0",
    "beautifulsoup4>=4.12.0",
    "pyyaml>=6.0",
    "psycopg2-binary>=2.9.11",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.7.0",
]
groq = ["langchain-groq>=0.2.0"]
ollama = ["langchain-ollama>=0.2.0"]
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && uv sync`
Expected: All dependencies install successfully, including `sentence-transformers` and `langchain-anthropic`.

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "build: add sentence-transformers and langchain-anthropic as core dependencies"
```

---

### Task 2: Create EmbeddingPort Protocol

**Files:**
- Test: `backend/tests/unit/test_embedding_port.py`
- Create: `backend/src/hiresense/ports/embedding.py`
- Modify: `backend/src/hiresense/ports/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_embedding_port.py`:

```python
import pytest

from hiresense.ports import EmbeddingPort


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


@pytest.mark.asyncio
async def test_fake_embedder_satisfies_embedding_port() -> None:
    embedder: EmbeddingPort = FakeEmbedder()
    result = await embedder.embed(["hello", "world"])
    assert len(result) == 2
    assert result[0] == [0.1, 0.2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_embedding_port.py -v`
Expected: FAIL with `ImportError: cannot import name 'EmbeddingPort'`

- [ ] **Step 3: Create EmbeddingPort protocol**

Create `backend/src/hiresense/ports/embedding.py`:

```python
from __future__ import annotations

from typing import Protocol


class EmbeddingPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- [ ] **Step 4: Update ports __init__.py to re-export EmbeddingPort**

In `backend/src/hiresense/ports/__init__.py`, add the import and export:

```python
from hiresense.ports.embedding import EmbeddingPort
from hiresense.ports.event_bus import EventBus
from hiresense.ports.latex_compiler import CompilationError, LaTeXCompilerPort
from hiresense.ports.llm import LLMPort
from hiresense.ports.vector_store import ScoredResult, VectorStorePort

__all__ = [
    "CompilationError",
    "EmbeddingPort",
    "EventBus",
    "LaTeXCompilerPort",
    "LLMPort",
    "ScoredResult",
    "VectorStorePort",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_embedding_port.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ports/embedding.py backend/src/hiresense/ports/__init__.py backend/tests/unit/test_embedding_port.py
git commit -m "feat(ports): add EmbeddingPort protocol"
```

---

### Task 3: Create SentenceTransformerAdapter

**Files:**
- Test: `backend/tests/unit/test_sentence_transformer_adapter.py`
- Create: `backend/src/hiresense/adapters/embedding/__init__.py`
- Create: `backend/src/hiresense/adapters/embedding/sentence_transformer_adapter.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_sentence_transformer_adapter.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from hiresense.adapters.embedding import SentenceTransformerAdapter
from hiresense.ports import EmbeddingPort


def test_adapter_satisfies_embedding_port() -> None:
    adapter: EmbeddingPort = SentenceTransformerAdapter(model_name="all-mpnet-base-v2")
    assert hasattr(adapter, "embed")


@pytest.mark.asyncio
async def test_embed_delegates_to_sentence_transformer() -> None:
    adapter = SentenceTransformerAdapter(model_name="all-mpnet-base-v2")

    fake_model = MagicMock()
    fake_model.encode.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    adapter._model = fake_model

    result = await adapter.embed(["hello", "world"])

    fake_model.encode.assert_called_once_with(["hello", "world"])
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


@pytest.mark.asyncio
async def test_embed_lazy_loads_model() -> None:
    with patch("hiresense.adapters.embedding.sentence_transformer_adapter.SentenceTransformer") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.encode.return_value = [[0.1]]
        mock_cls.return_value = mock_instance

        adapter = SentenceTransformerAdapter(model_name="all-mpnet-base-v2", device="cpu")
        assert adapter._model is None

        await adapter.embed(["test"])

        mock_cls.assert_called_once_with("all-mpnet-base-v2", device="cpu")
        assert adapter._model is mock_instance


@pytest.mark.asyncio
async def test_embed_converts_numpy_to_list() -> None:
    adapter = SentenceTransformerAdapter(model_name="all-mpnet-base-v2")

    fake_model = MagicMock()
    # sentence-transformers returns numpy arrays; simulate with objects that have .tolist()
    import numpy as np
    fake_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
    adapter._model = fake_model

    result = await adapter.embed(["a", "b"])

    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert result[0] == pytest.approx([0.1, 0.2])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_sentence_transformer_adapter.py -v`
Expected: FAIL with `ImportError: cannot import name 'SentenceTransformerAdapter'`

- [ ] **Step 3: Create the adapter**

Create `backend/src/hiresense/adapters/embedding/sentence_transformer_adapter.py`:

```python
from __future__ import annotations

import asyncio
from typing import Any


class SentenceTransformerAdapter:
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model: Any = None

    def _load_model(self) -> Any:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self._model_name, device=self._device)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = await asyncio.to_thread(self._load_model)

        embeddings = await asyncio.to_thread(self._model.encode, texts)

        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return [list(e) for e in embeddings]
```

- [ ] **Step 4: Create the package __init__.py**

Create `backend/src/hiresense/adapters/embedding/__init__.py`:

```python
from hiresense.adapters.embedding.sentence_transformer_adapter import SentenceTransformerAdapter

__all__ = ["SentenceTransformerAdapter"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_sentence_transformer_adapter.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/adapters/embedding/ backend/tests/unit/test_sentence_transformer_adapter.py
git commit -m "feat(adapters): add SentenceTransformerAdapter for local embeddings"
```

---

### Task 4: Create LangChainLLMAdapter

**Files:**
- Test: `backend/tests/unit/test_langchain_adapter.py`
- Create: `backend/src/hiresense/adapters/llm/langchain_adapter.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_langchain_adapter.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from hiresense.adapters.llm import LangChainLLMAdapter
from hiresense.ports import LLMPort


def test_adapter_satisfies_llm_port() -> None:
    mock_model = MagicMock()
    adapter: LLMPort = LangChainLLMAdapter(model=mock_model)
    assert hasattr(adapter, "complete")
    assert hasattr(adapter, "stream")


@pytest.mark.asyncio
async def test_complete_invokes_model() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="Hello from LangChain")

    adapter = LangChainLLMAdapter(model=mock_model)
    result = await adapter.complete("Say hello", system="Be friendly")

    assert result == "Hello from LangChain"
    mock_model.ainvoke.assert_called_once()
    call_args = mock_model.ainvoke.call_args[0][0]
    assert len(call_args) == 2  # system + human messages


@pytest.mark.asyncio
async def test_complete_with_model_override() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="response")

    adapter = LangChainLLMAdapter(model=mock_model)
    await adapter.complete("prompt", model="claude-opus-4-6")

    call_kwargs = mock_model.ainvoke.call_args
    # model override should be passed via bind
    mock_model.bind.assert_called_once_with(model="claude-opus-4-6")


@pytest.mark.asyncio
async def test_complete_without_system_prompt() -> None:
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = AIMessage(content="response")

    adapter = LangChainLLMAdapter(model=mock_model)
    await adapter.complete("prompt")

    call_args = mock_model.ainvoke.call_args[0][0]
    assert len(call_args) == 1  # only human message, no system


@pytest.mark.asyncio
async def test_stream_yields_chunks() -> None:
    mock_model = AsyncMock()

    async def fake_stream(messages):
        for chunk in [
            MagicMock(content="Hello"),
            MagicMock(content=" world"),
        ]:
            yield chunk

    mock_model.astream = fake_stream

    adapter = LangChainLLMAdapter(model=mock_model)
    chunks = []
    async for chunk in adapter.stream("Say hello"):
        chunks.append(chunk)

    assert chunks == ["Hello", " world"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_langchain_adapter.py -v`
Expected: FAIL with `ImportError: cannot import name 'LangChainLLMAdapter'`

- [ ] **Step 3: Create the adapter**

Create `backend/src/hiresense/adapters/llm/langchain_adapter.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_langchain_adapter.py -v`
Expected: All 5 tests PASS. If `test_complete_with_model_override` fails because `bind` returns a new mock that also needs `ainvoke`, adjust the test to chain properly:

```python
@pytest.mark.asyncio
async def test_complete_with_model_override() -> None:
    mock_model = MagicMock()
    bound_model = AsyncMock()
    bound_model.ainvoke.return_value = AIMessage(content="response")
    mock_model.bind.return_value = bound_model

    adapter = LangChainLLMAdapter(model=mock_model)
    result = await adapter.complete("prompt", model="claude-opus-4-6")

    mock_model.bind.assert_called_once_with(model="claude-opus-4-6")
    assert result == "response"
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/adapters/llm/langchain_adapter.py backend/tests/unit/test_langchain_adapter.py
git commit -m "feat(adapters): add LangChainLLMAdapter wrapping BaseChatModel"
```

---

### Task 5: Update LLMPort and Adapter Re-exports

**Files:**
- Modify: `backend/src/hiresense/ports/llm.py`
- Modify: `backend/src/hiresense/adapters/llm/__init__.py`

- [ ] **Step 1: Remove embed() from LLMPort**

Update `backend/src/hiresense/ports/llm.py` to:

```python
from __future__ import annotations

from typing import AsyncIterator, Protocol


class LLMPort(Protocol):
    async def complete(
        self, prompt: str, *, system: str = "", model: str = ""
    ) -> str: ...

    async def stream(
        self, prompt: str, *, system: str = ""
    ) -> AsyncIterator[str]: ...
```

- [ ] **Step 2: Update adapters/llm/__init__.py to export LangChainLLMAdapter**

Update `backend/src/hiresense/adapters/llm/__init__.py` to:

```python
from hiresense.adapters.llm.langchain_adapter import LangChainLLMAdapter

__all__ = ["LangChainLLMAdapter"]
```

- [ ] **Step 3: Run full test suite to check for breakages**

Run: `cd backend && uv run pytest tests/unit/ -v --ignore=tests/unit/test_llm_adapters.py --ignore=tests/unit/test_app.py --ignore=tests/unit/test_config.py -x`
Expected: PASS (we ignore old adapter tests and app/config tests that reference old settings — those get fixed in later tasks)

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/ports/llm.py backend/src/hiresense/adapters/llm/__init__.py
git commit -m "refactor(ports): remove embed() from LLMPort, update adapter re-exports"
```

---

### Task 6: Update Configuration

**Files:**
- Test: `backend/tests/unit/test_config.py`
- Modify: `backend/src/hiresense/config.py`

- [ ] **Step 1: Update the test to reflect new config shape**

Replace `backend/tests/unit/test_config.py` with:

```python
import pytest


def test_settings_loads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.app_name == "HireSense"
    assert settings.app_port == 8000
    assert settings.llm_provider == "anthropic"
    assert settings.embedding_model == "all-mpnet-base-v2"
    assert settings.embedding_device == "cpu"
    assert settings.vector_store_provider == "pgvector"
    assert settings.weight_semantic == 15
    assert settings.weight_skill_match == 20


def test_settings_enabled_sources_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLED_JOB_SOURCES", "remotive,remoteok")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.enabled_job_sources == ["remotive", "remoteok"]


def test_embedding_device_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_DEVICE", "cuda")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.embedding_device == "cuda"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_config.py -v`
Expected: FAIL because `embedding_api_key` is still required and `embedding_device` doesn't exist yet.

- [ ] **Step 3: Update config.py**

In `backend/src/hiresense/config.py`, replace the embedding-related settings. Remove `embedding_provider` and `embedding_api_key`. Change `embedding_model` default. Add `embedding_device`:

Replace:
```python
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str
```

With:
```python
    embedding_model: str = "all-mpnet-base-v2"
    embedding_device: str = "cpu"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_config.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/config.py backend/tests/unit/test_config.py
git commit -m "refactor(config): remove external embedding settings, add local embedding config"
```

---

### Task 7: Update MatchingOrchestrator to Accept EmbeddingPort

**Files:**
- Modify: `backend/tests/unit/matching/test_orchestrator.py`
- Modify: `backend/src/hiresense/matching/domain/services.py`

- [ ] **Step 1: Update the orchestrator test**

Update `backend/tests/unit/matching/test_orchestrator.py`. The `FakeLLM` no longer needs `embed()`. Add a `FakeEmbedder` and pass it to the orchestrator. Update the `analyze()` call to not pass pre-computed embeddings (the orchestrator generates them now):

```python
import asyncio

import pytest

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.kernel.events import DomainEvent
from hiresense.matching.domain.services import MatchingOrchestrator


class FakeLLM:
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        return """{
            "experience_score": 0.7,
            "language_score": 1.0,
            "pros": ["Strong Python background"],
            "cons": ["No Kubernetes experience"],
            "recommendations": ["Learn container orchestration"]
        }"""


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.8, 0.6] for _ in texts]


@pytest.mark.asyncio
async def test_orchestrator_produces_match_result() -> None:
    bus = InMemoryEventBus()
    events: list[DomainEvent] = []

    async def capture(event: DomainEvent) -> None:
        events.append(event)

    bus.subscribe("match.completed", capture)

    orchestrator = MatchingOrchestrator(llm=FakeLLM(), event_bus=bus, embedding=FakeEmbedder())
    result = await orchestrator.analyze(
        job_id="job-1",
        cv_id="cv-1",
        job_description="Backend engineer with Python, FastAPI, and Kubernetes experience",
        job_skills=["python", "fastapi", "kubernetes"],
        cv_summary="Experienced Python developer with FastAPI projects",
        cv_skills=["python", "fastapi", "django"],
    )
    assert result.job_id == "job-1"
    assert result.cv_id == "cv-1"
    assert 0.0 <= result.overall_score <= 1.0
    assert result.breakdown.semantic_score > 0
    assert result.breakdown.skill_score > 0
    assert "python" in result.matched_skills
    assert "kubernetes" in result.missing_skills
    assert len(result.pros) > 0

    await asyncio.sleep(0.05)
    assert len(events) == 1
    assert events[0].event_type == "match.completed"


@pytest.mark.asyncio
async def test_orchestrator_without_embedding_port() -> None:
    bus = InMemoryEventBus()
    orchestrator = MatchingOrchestrator(llm=FakeLLM(), event_bus=bus)
    result = await orchestrator.analyze(
        job_id="job-2",
        cv_id="cv-2",
        job_description="Frontend developer",
        job_skills=["react", "typescript"],
        cv_summary="Backend developer",
        cv_skills=["python", "django"],
    )
    assert result.breakdown.semantic_score == 0.0
    assert result.breakdown.skill_score == 0.0
    assert 0.0 <= result.overall_score <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/matching/test_orchestrator.py -v`
Expected: FAIL because `MatchingOrchestrator` doesn't accept `embedding` parameter yet.

- [ ] **Step 3: Update MatchingOrchestrator**

In `backend/src/hiresense/matching/domain/services.py`, update the constructor to accept an optional `embedding` parameter. Update `analyze()` to generate embeddings when no pre-computed ones are provided:

Replace the constructor:
```python
class MatchingOrchestrator:
    def __init__(self, llm: Any, event_bus: Any, dimension_scorers: list[Any] | None = None) -> None:
        self._llm = llm
        self._event_bus = event_bus
        self._dimension_scorers = dimension_scorers or []
        self._semantic_scorer = SemanticScorer()
        self._skill_matcher = SkillMatcher()
```

With:
```python
class MatchingOrchestrator:
    def __init__(
        self,
        llm: Any,
        event_bus: Any,
        dimension_scorers: list[Any] | None = None,
        embedding: Any | None = None,
    ) -> None:
        self._llm = llm
        self._event_bus = event_bus
        self._dimension_scorers = dimension_scorers or []
        self._embedding = embedding
        self._semantic_scorer = SemanticScorer()
        self._skill_matcher = SkillMatcher()
```

Replace the semantic score block in `analyze()`:

```python
        # 1. Semantic score
        if cv_embedding and job_embedding:
            semantic_score = self._semantic_scorer.score(cv_embedding, job_embedding)
        else:
            semantic_score = 0.0
```

With:
```python
        # 1. Semantic score
        if cv_embedding and job_embedding:
            semantic_score = self._semantic_scorer.score(cv_embedding, job_embedding)
        elif self._embedding and cv_summary and job_description:
            embeddings = await self._embedding.embed([cv_summary, job_description])
            semantic_score = self._semantic_scorer.score(embeddings[0], embeddings[1])
        else:
            semantic_score = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/matching/test_orchestrator.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/services.py backend/tests/unit/matching/test_orchestrator.py
git commit -m "feat(matching): accept EmbeddingPort in orchestrator for auto-embedding"
```

---

### Task 8: Update DI Wiring (main.py)

**Files:**
- Modify: `backend/src/hiresense/main.py`
- Modify: `backend/tests/unit/test_app.py`

- [ ] **Step 1: Update main.py**

In `backend/src/hiresense/main.py`, replace the LLM initialization block.

Replace:
```python
    llm = None
    if settings.llm_api_key:
        try:
            from anthropic import AsyncAnthropic
            from hiresense.adapters.llm.anthropic_adapter import AnthropicLLMAdapter
            anthropic_client = AsyncAnthropic(api_key=settings.llm_api_key)
            llm = AnthropicLLMAdapter(client=anthropic_client, model=settings.llm_model)
        except ImportError:
            pass
```

With:
```python
    llm = None
    if settings.llm_api_key:
        try:
            from langchain_anthropic import ChatAnthropic

            from hiresense.adapters.llm import LangChainLLMAdapter

            chat_model = ChatAnthropic(model=settings.llm_model, api_key=settings.llm_api_key)
            llm = LangChainLLMAdapter(model=chat_model)
        except ImportError:
            pass

    from hiresense.adapters.embedding import SentenceTransformerAdapter

    embedding = SentenceTransformerAdapter(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
    )
```

Update the orchestrator construction to pass the embedding adapter:

Replace:
```python
    matching_orchestrator = MatchingOrchestrator(llm=llm, event_bus=event_bus, dimension_scorers=dimension_scorers)
```

With:
```python
    matching_orchestrator = MatchingOrchestrator(
        llm=llm,
        event_bus=event_bus,
        dimension_scorers=dimension_scorers,
        embedding=embedding,
    )
```

Also remove the old import `from hiresense.adapters.llm.anthropic_adapter import AnthropicLLMAdapter` if it's at the top level (it's currently inside the try block, so just make sure the new code replaces it cleanly).

- [ ] **Step 2: Update test_app.py**

In `backend/tests/unit/test_app.py`, remove all `monkeypatch.setenv("EMBEDDING_API_KEY", ...)` lines from all three tests. The `EMBEDDING_API_KEY` setting no longer exists.

Remove this line from each test:
```python
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
```

- [ ] **Step 3: Run the app test**

Run: `cd backend && uv run pytest tests/unit/test_app.py -v`
Expected: All 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/main.py backend/tests/unit/test_app.py
git commit -m "refactor(main): wire LangChain and SentenceTransformer adapters"
```

---

### Task 9: Delete Old Adapters and Update Their Tests

**Files:**
- Delete: `backend/src/hiresense/adapters/llm/anthropic_adapter.py`
- Delete: `backend/src/hiresense/adapters/llm/openai_embeddings.py`
- Modify: `backend/tests/unit/test_llm_adapters.py`

- [ ] **Step 1: Delete old adapter files**

```bash
rm backend/src/hiresense/adapters/llm/anthropic_adapter.py
rm backend/src/hiresense/adapters/llm/openai_embeddings.py
```

- [ ] **Step 2: Replace test_llm_adapters.py**

Replace `backend/tests/unit/test_llm_adapters.py` with tests for the new adapters (the individual adapter tests already exist in `test_langchain_adapter.py` and `test_sentence_transformer_adapter.py`, so this file becomes a thin integration-style check):

```python
from hiresense.adapters.embedding import SentenceTransformerAdapter
from hiresense.adapters.llm import LangChainLLMAdapter
from hiresense.ports import EmbeddingPort, LLMPort


def test_langchain_adapter_exported_from_package() -> None:
    assert LangChainLLMAdapter is not None


def test_sentence_transformer_adapter_exported_from_package() -> None:
    assert SentenceTransformerAdapter is not None
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/unit/test_llm_adapters.py -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `cd backend && uv run pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(adapters): remove AnthropicLLMAdapter and OpenAIEmbeddingAdapter"
```

---

### Task 10: Update .env and .env.example

**Files:**
- Modify: `backend/.env`
- Modify: `backend/.env.example`

- [ ] **Step 1: Update .env.example**

In `backend/.env.example`, replace the embedding section:

Replace:
```env
EMBEDDING_PROVIDER=openai
# Options: openai | ollama
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=your-openai-key-here
```

With:
```env
EMBEDDING_MODEL=all-mpnet-base-v2
# Options: all-mpnet-base-v2 | all-MiniLM-L6-v2 | any sentence-transformers model
EMBEDDING_DEVICE=cpu
# Options: cpu | cuda
```

- [ ] **Step 2: Update .env**

In `backend/.env`, replace the embedding section:

Replace:
```env
EMBEDDING_PROVIDER=openai
# Options: openai | ollama
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=your-openai-key-here
```

With:
```env
EMBEDDING_MODEL=all-mpnet-base-v2
# Options: all-mpnet-base-v2 | all-MiniLM-L6-v2 | any sentence-transformers model
EMBEDDING_DEVICE=cpu
# Options: cpu | cuda
```

- [ ] **Step 3: Run full test suite one final time**

Run: `cd backend && uv run pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/.env.example backend/.env
git commit -m "chore(config): update env files for local embeddings"
```

---

### Task 11: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `cd backend && uv run pytest tests/unit/ -v`
Expected: All tests PASS with no failures

- [ ] **Step 2: Verify no imports of old adapters remain**

Run: `cd backend && grep -r "AnthropicLLMAdapter\|OpenAIEmbeddingAdapter\|anthropic_adapter\|openai_embeddings" src/ tests/`
Expected: No matches found

- [ ] **Step 3: Verify no references to removed config fields**

Run: `cd backend && grep -r "embedding_api_key\|embedding_provider\|EMBEDDING_API_KEY\|EMBEDDING_PROVIDER" src/ tests/`
Expected: No matches found

- [ ] **Step 4: Commit any remaining cleanups (if any)**

Only if previous steps revealed issues. Otherwise, skip.
