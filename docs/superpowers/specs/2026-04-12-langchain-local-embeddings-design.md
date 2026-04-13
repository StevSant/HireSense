# LangChain Migration & Local Embeddings

**Date:** 2026-04-12
**Status:** Approved

## Summary

Replace the direct Anthropic SDK adapter with a LangChain-based adapter (`ChatAnthropic` via `langchain-anthropic`) and introduce local sentence-transformers embeddings via a new `EmbeddingPort`. This decouples the system from any single LLM vendor and removes the need for an external embeddings API key.

## Goals

- **Provider-agnostic LLM layer** — Swap Anthropic SDK for LangChain's `BaseChatModel`, making future provider switches trivial.
- **Free local embeddings** — Use `sentence-transformers` (`all-mpnet-base-v2` default) so no external API key is needed for embeddings.
- **Clean port separation** — Split the current `LLMPort` (which bundles `complete`, `stream`, `embed`) into `LLMPort` (complete/stream) and `EmbeddingPort` (embed).
- **Minimal domain disruption** — The matching orchestrator, dimension scorers, skill matcher, and semantic scorer remain unchanged or receive only constructor-level changes.

## Architecture

### Port Changes

**`LLMPort`** (modify):
- Keep: `complete(prompt, *, system, model) -> str`, `stream(prompt, *, system) -> AsyncIterator[str]`
- Remove: `embed(texts) -> list[list[float]]`

**`EmbeddingPort`** (new):
- `async def embed(texts: list[str]) -> list[list[float]]`

### Adapter Changes

**`LangChainLLMAdapter`** (new):
- Wraps LangChain's `BaseChatModel` (initialized as `ChatAnthropic`)
- Implements `LLMPort.complete()` via `model.ainvoke()`
- Implements `LLMPort.stream()` via `model.astream()`

**`SentenceTransformerAdapter`** (new):
- Wraps `sentence_transformers.SentenceTransformer`
- Implements `EmbeddingPort.embed()`
- Model loaded lazily on first call
- Configurable model name (`EMBEDDING_MODEL`) and device (`EMBEDDING_DEVICE`)

**Delete:**
- `AnthropicLLMAdapter` — replaced by `LangChainLLMAdapter`
- `OpenAIEmbeddingAdapter` — replaced by `SentenceTransformerAdapter`

### Configuration Changes

**Remove:**
- `EMBEDDING_PROVIDER` — always local now
- `EMBEDDING_API_KEY` — no external API needed

**Modify:**
- `EMBEDDING_MODEL` — default changes to `all-mpnet-base-v2`

**Add:**
- `EMBEDDING_DEVICE` — `cpu` (default) or `cuda`

**Dependencies (`pyproject.toml`):**
- Add: `sentence-transformers>=3.0.0`
- Move `langchain-anthropic>=0.3.0` from optional to required
- Remove: `openai` optional dependency group

### DI Wiring (main.py)

1. `ChatAnthropic(model=..., api_key=...)` → `LangChainLLMAdapter` → registered as `LLMPort`
2. `SentenceTransformerAdapter(model_name=..., device=...)` → registered as `EmbeddingPort`
3. Both injected into `MatchingOrchestrator` and resolved via FastAPI `Depends()`

### Domain Layer Impact

- **`MatchingOrchestrator`** — constructor accepts `EmbeddingPort` as new dependency. `analyze()` can generate embeddings internally instead of requiring pre-computed ones.
- **`SemanticScorer`** — no changes (pure cosine similarity on vectors).
- **Dimension scorers (all 6)** — no changes (depend on `LLMPort.complete()`).
- **`SkillMatcher`** — no changes (pure logic).

## Files

### Create
| File | Purpose |
|------|---------|
| `ports/embedding.py` | `EmbeddingPort` protocol |
| `adapters/embedding/__init__.py` | Package re-exports |
| `adapters/embedding/sentence_transformer_adapter.py` | Local embedding adapter |
| `adapters/llm/langchain_adapter.py` | LangChain-based LLM adapter |

### Modify
| File | Change |
|------|--------|
| `ports/llm.py` | Remove `embed()` |
| `ports/__init__.py` | Re-export `EmbeddingPort` |
| `adapters/llm/__init__.py` | Update re-exports |
| `config.py` | Remove `EMBEDDING_PROVIDER`/`EMBEDDING_API_KEY`, add `EMBEDDING_DEVICE`, change `EMBEDDING_MODEL` default |
| `main.py` | New DI wiring with LangChain + sentence-transformers |
| `matching/domain/services.py` | Accept `EmbeddingPort` in constructor |
| `matching/api/dependencies.py` | Resolve `EmbeddingPort` |
| `pyproject.toml` | Dependency changes |
| `.env.example` | Update template |
| `.env` | Update active config |

### Delete
| File | Reason |
|------|--------|
| `adapters/llm/anthropic_adapter.py` | Replaced by `LangChainLLMAdapter` |
| `adapters/llm/openai_embeddings.py` | Replaced by `SentenceTransformerAdapter` |
