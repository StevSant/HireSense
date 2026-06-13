# CV Translation & Per-Language PDF Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user upload a CV in one language, translate it to the other language via the LLM (preserving LaTeX), and download the compiled PDF of either language variant from the profile page.

**Architecture:** New `CVTranslator` domain service in the `profile` bounded context calls the existing tracked-LLM port to translate raw `.tex` (commands preserved). `ProfileService.translate_to` runs a one-shot compile sanity-check via the existing `LatexCompilerPort`, then stores the translated variant flagged `machine_translated=True` (replacing the latest variant in that language). Two new endpoints expose translation and per-language PDF compilation. The Angular profile page gains Translate + Download-PDF buttons and a machine-translated badge.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy + Alembic, Pydantic; Angular 21 standalone + signals, Vitest. Backend runs via `uv run python -m ...` (bare `uv run pytest` is broken on this machine).

**Spec:** `docs/superpowers/specs/2026-06-13-cv-translation-and-pdf-download-design.md`

---

## File Structure

**Backend (create):**
- `backend/src/hiresense/profile/domain/cv_translator.py` — `CVTranslator` (LLM-backed LaTeX translation).
- `backend/src/hiresense/profile/domain/translation_outcome.py` — `TranslationOutcome` dataclass.
- `backend/alembic/versions/029_add_profile_machine_translated.py` — migration.
- `backend/tests/unit/profile/test_cv_translator.py`
- `backend/tests/unit/profile/test_translate_to.py`
- `backend/tests/unit/profile/test_machine_translated_mapping.py`

**Backend (modify):**
- `backend/src/hiresense/admin/domain/feature_registry.py` — add `cv_translator` feature.
- `backend/src/hiresense/profile/domain/models.py` — `machine_translated` field.
- `backend/src/hiresense/profile/infrastructure/orm.py` — `machine_translated` column.
- `backend/src/hiresense/profile/infrastructure/repository.py` — map the new field.
- `backend/src/hiresense/profile/domain/services.py` — `translate_to`, `compile_pdf`, new ctor args.
- `backend/src/hiresense/profile/domain/__init__.py` — re-export new symbols.
- `backend/src/hiresense/profile/api/routes.py` — `POST /profile/translate`, `GET /profile/cv.pdf`.
- `backend/src/hiresense/bootstrap/profile.py` — wire translator + compiler.
- `backend/tests/unit/profile/test_routes.py` — endpoint tests.

**Frontend (create):**
- `frontend/src/app/pages/profile/models/translate-response.model.ts`

**Frontend (modify):**
- `frontend/src/app/pages/profile/models/candidate-profile.model.ts` — `machine_translated`.
- `frontend/src/app/core/services/profile.service.ts` — `translate`, `downloadCvPdf`.
- `frontend/src/app/pages/profile/profile.component.ts` — translate/download handlers + signals.
- `frontend/src/app/pages/profile/profile.component.html` — buttons + badge.
- `frontend/src/app/pages/profile/profile.component.spec.ts` — specs.

---

## Task 1: Register the `cv_translator` LLM feature

**Files:**
- Modify: `backend/src/hiresense/admin/domain/feature_registry.py`
- Test: `backend/tests/unit/admin/test_feature_registry.py` (create if absent)

- [ ] **Step 1: Write the failing test**

Create/append `backend/tests/unit/admin/test_feature_registry.py`:

```python
from hiresense.admin.domain.feature_registry import all_feature_keys, get_feature


def test_cv_translator_feature_registered() -> None:
    assert "cv_translator" in all_feature_keys()
    feature = get_feature("cv_translator")
    assert feature is not None
    assert feature.name == "CV Translator"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/admin/test_feature_registry.py -v`
Expected: FAIL — `cv_translator` not in keys.

- [ ] **Step 3: Add the feature descriptor**

In `feature_registry.py`, append inside the `FEATURE_REGISTRY` tuple (after the `cover_letter` entry):

```python
    FeatureDescriptor(
        key="cv_translator",
        name="CV Translator",
        description="Translates a CV's LaTeX into another language, preserving commands.",
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/admin/test_feature_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/admin/domain/feature_registry.py backend/tests/unit/admin/test_feature_registry.py
git commit -m "feat(admin): register cv_translator LLM feature"
```

---

## Task 2: `CVTranslator` domain service

**Files:**
- Create: `backend/src/hiresense/profile/domain/cv_translator.py`
- Modify: `backend/src/hiresense/profile/domain/__init__.py`
- Test: `backend/tests/unit/profile/test_cv_translator.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/profile/test_cv_translator.py`:

```python
import pytest

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
    result = await translator.translate(
        "\\section*{SUMMARY}\nBackend engineer.", "en", "es"
    )
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
    translator = CVTranslator(llm=None)
    with pytest.raises(RuntimeError):
        await translator.translate("\\section*{SUMMARY}", "en", "es")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_cv_translator.py -v`
Expected: FAIL — module `cv_translator` does not exist.

- [ ] **Step 3: Implement `CVTranslator`**

Create `backend/src/hiresense/profile/domain/cv_translator.py`:

```python
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_MARKDOWN_FENCE_RE = re.compile(r"```(?:[a-zA-Z]+)?\s*\n?(.*?)\n?```", re.DOTALL)

_LANG_NAMES = {"en": "English", "es": "Spanish"}


class CVTranslator:
    """Translates a CV's LaTeX source into another language via the LLM.

    Only human-readable text is translated; every LaTeX command, environment,
    option, and structural token is preserved so the result still compiles.
    """

    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def translate(self, raw_tex: str, source_lang: str, target_lang: str) -> str:
        if self._llm is None:
            raise RuntimeError("LLM not configured — cannot translate CV")
        prompt = self._build_prompt(raw_tex, source_lang, target_lang)
        response = await self._llm.complete(
            prompt,
            system="You are an expert technical translator for LaTeX résumés.",
        )
        return self._strip_fence(response)

    def _build_prompt(self, raw_tex: str, source_lang: str, target_lang: str) -> str:
        source_name = _LANG_NAMES.get(source_lang, source_lang)
        target_name = _LANG_NAMES.get(target_lang, target_lang)
        return (
            f"Translate the following LaTeX résumé from {source_name} to {target_name}.\n\n"
            "STRICT RULES:\n"
            "- Translate ONLY human-readable text: section bodies, headings, prose, bullet points.\n"
            "- Do NOT alter, remove, or reorder any LaTeX command, environment, option, or "
            "argument structure (e.g. \\section, \\begin{...}, \\textbf{...}, column specs, "
            "braces, backslashes).\n"
            "- Do NOT translate URLs, email addresses, phone numbers, technology names "
            "(e.g. Python, FastAPI, PostgreSQL), company names, or person names.\n"
            "- Keep all whitespace structure and the document preamble intact.\n"
            "- Return ONLY the complete translated .tex document, with no commentary "
            "and no markdown fences.\n\n"
            f"LaTeX source:\n{raw_tex}"
        )

    @staticmethod
    def _strip_fence(text: str) -> str:
        match = _MARKDOWN_FENCE_RE.search(text)
        return (match.group(1) if match else text).strip()
```

- [ ] **Step 4: Re-export from the package**

Edit `backend/src/hiresense/profile/domain/__init__.py` to:

```python
from hiresense.profile.domain.cv_translator import CVTranslator
from hiresense.profile.domain.latex_parser import LaTeXParser
from hiresense.profile.domain.pdf_parser import PDFParser
from hiresense.profile.domain.services import ProfileService
from hiresense.profile.domain.skill_extractor import SkillExtractor
from hiresense.profile.domain.translation_outcome import TranslationOutcome

__all__ = [
    "CVTranslator",
    "LaTeXParser",
    "PDFParser",
    "ProfileService",
    "SkillExtractor",
    "TranslationOutcome",
]
```

> Note: `TranslationOutcome` is created in Task 4 Step 1. To keep imports resolving, create `translation_outcome.py` (Task 4 Step 1) before running anything that imports the package — or temporarily omit the `TranslationOutcome` import/`__all__` entry here and add it back in Task 4.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_cv_translator.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/profile/domain/cv_translator.py backend/src/hiresense/profile/domain/__init__.py backend/tests/unit/profile/test_cv_translator.py
git commit -m "feat(profile): add CVTranslator LaTeX-preserving translation service"
```

---

## Task 3: `machine_translated` field — model, ORM, repository, migration

**Files:**
- Modify: `backend/src/hiresense/profile/domain/models.py`
- Modify: `backend/src/hiresense/profile/infrastructure/orm.py`
- Modify: `backend/src/hiresense/profile/infrastructure/repository.py`
- Create: `backend/alembic/versions/029_add_profile_machine_translated.py`
- Test: `backend/tests/unit/profile/test_machine_translated_mapping.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/profile/test_machine_translated_mapping.py`:

```python
from hiresense.profile.domain.models import CandidateProfile
from hiresense.profile.infrastructure.repository import _to_domain, _to_orm


def test_candidate_profile_defaults_machine_translated_false() -> None:
    profile = CandidateProfile(id="1", name="x")
    assert profile.machine_translated is False


def test_to_orm_and_back_preserves_machine_translated() -> None:
    profile = CandidateProfile(
        id="123e4567-e89b-12d3-a456-426614174000",
        name="x",
        machine_translated=True,
    )
    orm = _to_orm(profile)
    assert orm.machine_translated is True
    restored = _to_domain(orm)
    assert restored.machine_translated is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_machine_translated_mapping.py -v`
Expected: FAIL — `CandidateProfile` has no `machine_translated`.

- [ ] **Step 3: Add the domain field**

In `backend/src/hiresense/profile/domain/models.py`, add to `CandidateProfile` (after `portfolio_url`):

```python
    machine_translated: bool = False
```

- [ ] **Step 4: Add the ORM column**

In `backend/src/hiresense/profile/infrastructure/orm.py`:

Add `Boolean` to the sqlalchemy import line and import the expression helper:

```python
from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text, Uuid, func
from sqlalchemy.sql import expression
```

Add the column (after `portfolio_url`):

```python
    machine_translated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=expression.false()
    )
```

- [ ] **Step 5: Map the field in the repository**

In `backend/src/hiresense/profile/infrastructure/repository.py`:

In `_to_domain(...)`, add to the `CandidateProfile(...)` constructor:

```python
        machine_translated=row.machine_translated,
```

In `_to_orm(...)`, add to the `ProfileOrm(...)` constructor:

```python
        machine_translated=profile.machine_translated,
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_machine_translated_mapping.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Create the migration**

Create `backend/alembic/versions/029_add_profile_machine_translated.py`:

```python
"""add machine_translated to profiles

Revision ID: 029
Revises: 028
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "machine_translated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "machine_translated")
```

- [ ] **Step 8: Verify the profile unit suite still imports cleanly**

Run: `cd backend && uv run python -m pytest tests/unit/profile -v`
Expected: PASS (existing + new tests).

- [ ] **Step 9: Commit**

```bash
git add backend/src/hiresense/profile/domain/models.py backend/src/hiresense/profile/infrastructure/orm.py backend/src/hiresense/profile/infrastructure/repository.py backend/alembic/versions/029_add_profile_machine_translated.py backend/tests/unit/profile/test_machine_translated_mapping.py
git commit -m "feat(profile): add machine_translated flag (model, orm, repo, migration 029)"
```

---

## Task 4: `TranslationOutcome` + `ProfileService.translate_to` + `compile_pdf`

**Files:**
- Create: `backend/src/hiresense/profile/domain/translation_outcome.py`
- Modify: `backend/src/hiresense/profile/domain/services.py`
- Test: `backend/tests/unit/profile/test_translate_to.py`

- [ ] **Step 1: Create the `TranslationOutcome` dataclass**

Create `backend/src/hiresense/profile/domain/translation_outcome.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from hiresense.profile.domain.models import CandidateProfile


@dataclass(frozen=True)
class TranslationOutcome:
    profile: CandidateProfile
    pdf_ok: bool
    compile_error: str | None = None
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/unit/profile/test_translate_to.py`:

```python
import pytest

from hiresense.ports import LatexCompileError
from hiresense.profile.domain.latex_parser import LaTeXParser
from hiresense.profile.domain.services import ProfileService
from hiresense.profile.domain.skill_extractor import SkillExtractor

SAMPLE_TEX = r"""
\documentclass{article}
\begin{document}
\begin{center}{\LARGE \textbf{JOHN DOE}}\end{center}
\section*{SUMMARY}
Backend engineer with Python and FastAPI expertise.
\end{document}
"""


class FakeTranslator:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple[str, str, str]] = []

    async def translate(self, raw_tex: str, source_lang: str, target_lang: str) -> str:
        self.calls.append((raw_tex, source_lang, target_lang))
        return self.output


class FakeCompiler:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def compile_to_pdf(self, tex: str) -> bytes:
        if self.fail:
            raise LatexCompileError("boom")
        return b"%PDF-1.4 fake"


def _service(translator: FakeTranslator, compiler: FakeCompiler) -> ProfileService:
    return ProfileService(
        parser=LaTeXParser(),
        skill_extractor=SkillExtractor(),
        translator=translator,
        latex_compiler=compiler,
    )


@pytest.mark.asyncio
async def test_translate_to_creates_flagged_target_variant() -> None:
    translator = FakeTranslator(SAMPLE_TEX)
    service = _service(translator, FakeCompiler())
    await service.parse_and_create(SAMPLE_TEX, language="en")

    outcome = await service.translate_to("es")

    assert outcome.pdf_ok is True
    assert outcome.compile_error is None
    assert outcome.profile.language == "es"
    assert outcome.profile.machine_translated is True
    assert translator.calls == [(SAMPLE_TEX, "en", "es")]


@pytest.mark.asyncio
async def test_translate_to_saves_even_when_compile_fails() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler(fail=True))
    await service.parse_and_create(SAMPLE_TEX, language="en")

    outcome = await service.translate_to("es")

    assert outcome.pdf_ok is False
    assert outcome.compile_error is not None
    assert outcome.profile.machine_translated is True
    saved = await service.get_current_profile(language="es")
    assert saved is not None


@pytest.mark.asyncio
async def test_translate_to_without_source_raises() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler())
    with pytest.raises(ValueError):
        await service.translate_to("es")


@pytest.mark.asyncio
async def test_compile_pdf_returns_bytes() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler())
    await service.parse_and_create(SAMPLE_TEX, language="en")
    pdf = await service.compile_pdf("en")
    assert pdf.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_compile_pdf_missing_language_raises() -> None:
    service = _service(FakeTranslator(SAMPLE_TEX), FakeCompiler())
    with pytest.raises(ValueError):
        await service.compile_pdf("es")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_translate_to.py -v`
Expected: FAIL — `translate_to` / `compile_pdf` not defined and ctor rejects `translator`.

- [ ] **Step 4: Extend `ProfileService`**

In `backend/src/hiresense/profile/domain/services.py`:

Change the typing import line from `from typing import TYPE_CHECKING` to:

```python
from typing import TYPE_CHECKING, Any
```

Add these imports after the existing `from hiresense.profile.domain...` imports:

```python
from hiresense.ports import LatexCompileError
from hiresense.profile.domain.translation_outcome import TranslationOutcome
```

Replace the `__init__` with (adds `translator` and `latex_compiler`):

```python
    def __init__(
        self,
        parser: LaTeXParser,
        skill_extractor: SkillExtractor,
        repository: ProfileRepositoryPort | None = None,
        pdf_parser: PDFParser | None = None,
        cv_directory: str = "./cvs",
        translator: Any | None = None,
        latex_compiler: Any | None = None,
    ) -> None:
        self._parser = parser
        self._skill_extractor = skill_extractor
        self._repository = repository
        self._pdf_parser = pdf_parser
        self._cv_directory = Path(cv_directory)
        self._translator = translator
        self._latex_compiler = latex_compiler
        self._profiles: dict[str, CandidateProfile] = {}
```

Add these three methods after `parse_file_and_create`:

```python
    async def translate_to(self, target_language: str) -> TranslationOutcome:
        """Translate the latest other-language CV into `target_language`.

        Stores the result as a new variant flagged machine_translated=True
        (the repository's latest-per-language behavior makes it current).
        Runs a one-shot compile sanity-check; on failure the variant is still
        saved and the outcome carries pdf_ok=False + the error.
        """
        if self._translator is None:
            raise RuntimeError("LLM not configured — cannot translate CV")
        source = self._find_source_for_translation(target_language)
        if source is None or not source.raw_tex:
            raise ValueError("No CV found to translate — upload one first")

        translated_tex = await self._translator.translate(
            source.raw_tex, source.language, target_language
        )

        pdf_ok = True
        compile_error: str | None = None
        if self._latex_compiler is not None:
            try:
                await self._latex_compiler.compile_to_pdf(translated_tex)
            except LatexCompileError as exc:
                pdf_ok = False
                compile_error = str(exc)

        parsed = self._parser.parse(translated_tex)
        skills = self._extract_skills_from_parsed(parsed)
        cleaned_sections = self._parser.strip_section_content(parsed.sections)
        sections = [CVSection(name=s.name, content=s.content) for s in cleaned_sections]

        shared_links = self._inherit_shared_links()
        profile = CandidateProfile(
            id=str(uuid.uuid4()),
            name=parsed.name or source.name,
            email=parsed.email or source.email,
            phone=parsed.phone or source.phone,
            location=parsed.location or source.location,
            sections=sections,
            raw_tex=translated_tex,
            language=target_language,
            skills=skills,
            machine_translated=True,
            **shared_links,
        )

        if self._repository is not None:
            self._repository.create(profile)
        else:
            self._profiles[profile.id] = profile

        return TranslationOutcome(
            profile=profile, pdf_ok=pdf_ok, compile_error=compile_error
        )

    async def compile_pdf(self, language: str) -> bytes:
        """Compile the latest CV variant for `language` to PDF bytes."""
        if self._latex_compiler is None:
            raise ValueError("PDF compilation not available")
        profile = self._get_latest_for_language_sync(language)
        if profile is None or not profile.raw_tex:
            raise ValueError(
                f"No CV found for language '{language}' — upload one first"
            )
        return await self._latex_compiler.compile_to_pdf(profile.raw_tex)

    def _find_source_for_translation(
        self, target_language: str
    ) -> CandidateProfile | None:
        """Latest profile whose language differs from the target."""
        if self._repository is not None:
            candidates = self._repository.list_all()  # newest-first
        else:
            candidates = list(reversed(list(self._profiles.values())))
        for profile in candidates:
            if profile.language != target_language:
                return profile
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_translate_to.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Verify package import + existing profile tests**

Run: `cd backend && uv run python -m pytest tests/unit/profile -v`
Expected: PASS (confirms the `TranslationOutcome` re-export from Task 2 Step 4 resolves).

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/profile/domain/translation_outcome.py backend/src/hiresense/profile/domain/services.py backend/src/hiresense/profile/domain/__init__.py backend/tests/unit/profile/test_translate_to.py
git commit -m "feat(profile): add translate_to + compile_pdf to ProfileService"
```

---

## Task 5: API endpoints — `POST /profile/translate` and `GET /profile/cv.pdf`

**Files:**
- Modify: `backend/src/hiresense/profile/api/routes.py`
- Test: `backend/tests/unit/profile/test_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/profile/test_routes.py`:

```python
from hiresense.profile.domain.translation_outcome import TranslationOutcome


class TranslateFakeService:
    async def translate_to(self, target_language: str) -> TranslationOutcome:
        return TranslationOutcome(
            profile=CandidateProfile(
                id="p-translated",
                name="Test User",
                language=target_language,
                raw_tex="\\documentclass{article}",
                machine_translated=True,
            ),
            pdf_ok=True,
            compile_error=None,
        )

    async def compile_pdf(self, language: str) -> bytes:
        return b"%PDF-1.4 fake-bytes"


def _translate_app(service: object) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_profile_service] = lambda: service
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_translate_endpoint_ok() -> None:
    app = _translate_app(TranslateFakeService())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/profile/translate", json={"target_language": "es"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"]["language"] == "es"
    assert data["profile"]["machine_translated"] is True
    assert data["pdf_ok"] is True


@pytest.mark.asyncio
async def test_translate_endpoint_no_source_returns_400() -> None:
    class NoSource:
        async def translate_to(self, target_language: str):
            raise ValueError("No CV found to translate — upload one first")

    app = _translate_app(NoSource())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/profile/translate", json={"target_language": "es"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_translate_endpoint_no_llm_returns_503() -> None:
    class NoLLM:
        async def translate_to(self, target_language: str):
            raise RuntimeError("LLM not configured — cannot translate CV")

    app = _translate_app(NoLLM())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/profile/translate", json={"target_language": "es"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_download_cv_pdf_ok() -> None:
    app = _translate_app(TranslateFakeService())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/profile/cv.pdf", params={"language": "es"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_download_cv_pdf_missing_returns_400() -> None:
    class NoCv:
        async def compile_pdf(self, language: str) -> bytes:
            raise ValueError("No CV found for language 'es' — upload one first")

    app = _translate_app(NoCv())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/profile/cv.pdf", params={"language": "es"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_routes.py -v -k "translate or download_cv_pdf"`
Expected: FAIL — endpoints return 404 (not yet defined).

- [ ] **Step 3: Add imports + endpoints**

In `backend/src/hiresense/profile/api/routes.py`:

Add to the imports (the file already imports `StreamingResponse`? it does not — add it; and add the LaTeX error):

```python
from fastapi.responses import StreamingResponse
from hiresense.ports import LatexCompileError
```

Add the request/response models after `UploadCVRequest`:

```python
class TranslateRequest(BaseModel):
    target_language: Literal["en", "es"]


class TranslateResponse(BaseModel):
    profile: CandidateProfile
    pdf_ok: bool
    compile_error: str | None = None
```

Add the endpoints **immediately after the `upload_file` endpoint and BEFORE the `/{profile_id}` route** (route ordering matters — `cv.pdf` must not be captured by `/{profile_id}`):

```python
@router.post("/translate", response_model=TranslateResponse)
async def translate_cv(
    body: TranslateRequest,
    service: Annotated[object, Depends(get_profile_service)],
) -> TranslateResponse:
    try:
        outcome = await service.translate_to(body.target_language)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return TranslateResponse(
        profile=outcome.profile,
        pdf_ok=outcome.pdf_ok,
        compile_error=outcome.compile_error,
    )


@router.get("/cv.pdf")
async def download_cv_pdf(
    service: Annotated[object, Depends(get_profile_service)],
    language: Literal["en", "es"] = "en",
) -> StreamingResponse:
    try:
        pdf = await service.compile_pdf(language)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except LatexCompileError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LaTeX compile failed: {exc}",
        ) from exc
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cv_{language}.pdf"'},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/profile/test_routes.py -v`
Expected: PASS (existing + 5 new tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/profile/api/routes.py backend/tests/unit/profile/test_routes.py
git commit -m "feat(profile): add /profile/translate and /profile/cv.pdf endpoints"
```

---

## Task 6: Bootstrap wiring

**Files:**
- Modify: `backend/src/hiresense/bootstrap/profile.py`

- [ ] **Step 1: Wire translator + compiler into `build_profile`**

Replace the contents of `backend/src/hiresense/bootstrap/profile.py` with:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.adapters.latex import LatexCompiler
from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.profile.api.provider import ProfileProvider
from hiresense.profile.domain import (
    CVTranslator,
    LaTeXParser,
    PDFParser,
    ProfileService,
    SkillExtractor,
)
from hiresense.profile.infrastructure import ProfileRepository


@dataclass(frozen=True)
class ProfileBuild:
    provider: ProfileProvider
    service: ProfileService


def build_profile(infra: SharedInfra, tracked: Callable[[str], Any]) -> ProfileBuild:
    profile_repo = ProfileRepository(session_factory=infra.sync_session_factory)
    latex_parser = LaTeXParser()
    pdf_parser = PDFParser(llm=tracked("cv_parser"))
    skill_extractor = SkillExtractor()
    translator = CVTranslator(llm=tracked("cv_translator"))
    latex_compiler = LatexCompiler(
        compiler=infra.settings.latex_compiler,
        timeout_seconds=infra.settings.latex_timeout_seconds,
    )
    profile_service = ProfileService(
        parser=latex_parser,
        skill_extractor=skill_extractor,
        repository=profile_repo,
        pdf_parser=pdf_parser,
        cv_directory=infra.settings.cv_directory,
        translator=translator,
        latex_compiler=latex_compiler,
    )
    provider = ProfileProvider(profile_service=profile_service)
    return ProfileBuild(provider=provider, service=profile_service)
```

> `main.py` already calls `build_profile(infra, tracked)` — no caller change needed. `infra.settings.latex_compiler` / `latex_timeout_seconds` are the same settings used by `bootstrap/applications.py`.

- [ ] **Step 2: Verify the app builds and the full backend suite passes**

Run: `cd backend && uv run python -m pytest -q`
Expected: PASS (whole suite; integration tests build the app, exercising this wiring).

- [ ] **Step 3: Lint**

Run: `cd backend && uv run ruff check .`
Expected: no new errors in the files touched.

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/bootstrap/profile.py
git commit -m "feat(profile): wire CVTranslator + LatexCompiler into build_profile"
```

---

## Task 7: Frontend models + ProfileService methods

**Files:**
- Modify: `frontend/src/app/pages/profile/models/candidate-profile.model.ts`
- Create: `frontend/src/app/pages/profile/models/translate-response.model.ts`
- Modify: `frontend/src/app/core/services/profile.service.ts`

- [ ] **Step 1: Add `machine_translated` to the CandidateProfile interface**

In `frontend/src/app/pages/profile/models/candidate-profile.model.ts`, add to the interface:

```typescript
  machine_translated: boolean;
```

> If existing test/object literals fail the build, make it optional (`machine_translated?: boolean;`); otherwise prefer required to match the backend response.

- [ ] **Step 2: Create the TranslateResponse model**

Create `frontend/src/app/pages/profile/models/translate-response.model.ts`:

```typescript
import { CandidateProfile } from './candidate-profile.model';

export interface TranslateResponse {
  profile: CandidateProfile;
  pdf_ok: boolean;
  compile_error: string | null;
}
```

- [ ] **Step 3: Add service methods**

In `frontend/src/app/core/services/profile.service.ts`:

Add the import:

```typescript
import { TranslateResponse } from '../../pages/profile/models/translate-response.model';
```

Add the two methods inside the class (after `updateManualFields`):

```typescript
  translate(targetLanguage: string): Observable<TranslateResponse> {
    return this.http
      .post<TranslateResponse>(`${environment.apiUrl}/profile/translate`, {
        target_language: targetLanguage,
      })
      .pipe(
        tap((res) => {
          this.profiles.update((all) => ({ ...all, [res.profile.language]: res.profile }));
          this.activeLanguage.set(res.profile.language);
        }),
      );
  }

  downloadCvPdf(language: string): Observable<Blob> {
    return this.http.get(`${environment.apiUrl}/profile/cv.pdf`, {
      params: { language },
      responseType: 'blob',
    });
  }
```

- [ ] **Step 4: Verify build + lint**

Run: `cd frontend && npm run build && npx ng lint`
Expected: build succeeds; lint clean. (CI runs `ng lint`, which `npm test`/`build` skip — run it.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/profile/models/candidate-profile.model.ts frontend/src/app/pages/profile/models/translate-response.model.ts frontend/src/app/core/services/profile.service.ts
git commit -m "feat(profile): add translate + downloadCvPdf to frontend ProfileService"
```

---

## Task 8: Profile page — Translate button, Download PDF button, badge

**Files:**
- Modify: `frontend/src/app/pages/profile/profile.component.ts`
- Modify: `frontend/src/app/pages/profile/profile.component.html`
- Modify: `frontend/src/app/pages/profile/profile.component.spec.ts`

- [ ] **Step 1: Add component handlers + signals**

In `frontend/src/app/pages/profile/profile.component.ts`, add signals (near the other `signal(...)` declarations):

```typescript
  translating = signal(false);
  translateWarning = signal('');
```

Add a computed for the other language (after `uploadedLanguages`):

```typescript
  otherLanguage = computed(() => (this.activeLanguage() === 'es' ? 'en' : 'es'));
```

Add the methods (after `uploadLatex`):

```typescript
  translateToOther(): void {
    const target = this.otherLanguage();
    this.translating.set(true);
    this.translateWarning.set('');
    this.profileService
      .translate(target)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.translating.set(false);
          if (!res.pdf_ok) {
            this.translateWarning.set(
              'Translated, but the PDF did not compile — review the LaTeX.',
            );
          }
        },
        error: (err) => {
          this.translateWarning.set(err.error?.detail || 'Translation failed');
          this.translating.set(false);
        },
      });
  }

  downloadPdf(language: string): void {
    this.profileService
      .downloadCvPdf(language)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement('a');
          anchor.href = url;
          anchor.download = `cv_${language}.pdf`;
          anchor.click();
          URL.revokeObjectURL(url);
        },
        error: (err) => this.error.set(err.error?.detail || 'Failed to download PDF'),
      });
  }
```

- [ ] **Step 2: Add UI to the template**

Open `frontend/src/app/pages/profile/profile.component.html` and locate the CV-tab block that renders the active `profile()` and the language switcher (search for `switchLanguage` / `uploadedLanguages`). Add this action row near the CV header (adapt class names to the surrounding markup):

```html
@if (profile(); as p) {
  <div class="cv-actions">
    <button type="button" class="btn" (click)="downloadPdf(p.language)">
      Download PDF ({{ p.language }})
    </button>
    <button
      type="button"
      class="btn"
      [disabled]="translating()"
      (click)="translateToOther()"
    >
      {{ translating() ? 'Translating…' : 'Translate to ' + otherLanguage() }}
    </button>
    @if (p.machine_translated) {
      <span class="badge badge-translated">Machine-translated</span>
    }
  </div>
  @if (translateWarning()) {
    <p class="warning">{{ translateWarning() }}</p>
  }
}
```

> Place it inside the existing CV tab (`@if (pageTab() === 'cv')` region). Keep the existing language switcher; this row supplements it. Match the project's button/badge classes if they differ.

- [ ] **Step 3: Write component specs**

In `frontend/src/app/pages/profile/profile.component.spec.ts`, add a focused describe block. Reuse the file's existing import style; override `ProfileService` with a stub:

```typescript
import { of } from 'rxjs';
import { signal } from '@angular/core';

describe('ProfileComponent translation + download', () => {
  function makeStub() {
    return {
      profile: signal({ id: '1', name: 'X', language: 'en', machine_translated: false }),
      profiles: signal({ en: { id: '1', name: 'X', language: 'en', machine_translated: false } }),
      activeLanguage: signal('en'),
      listProfiles: () => of([]),
      getCurrentProfile: () => of(null),
      translate: vi.fn(() =>
        of({
          profile: { id: '2', name: 'X', language: 'es', machine_translated: true },
          pdf_ok: true,
          compile_error: null,
        }),
      ),
      downloadCvPdf: vi.fn(() => of(new Blob(['%PDF'], { type: 'application/pdf' }))),
    };
  }

  it('calls translate with the other language', () => {
    const stub = makeStub();
    TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [{ provide: ProfileService, useValue: stub }],
    });
    const fixture = TestBed.createComponent(ProfileComponent);
    fixture.detectChanges();
    fixture.componentInstance.translateToOther();
    expect(stub.translate).toHaveBeenCalledWith('es');
  });

  it('downloads the PDF blob for a language', () => {
    const stub = makeStub();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    TestBed.configureTestingModule({
      imports: [ProfileComponent],
      providers: [{ provide: ProfileService, useValue: stub }],
    });
    const fixture = TestBed.createComponent(ProfileComponent);
    fixture.detectChanges();
    fixture.componentInstance.downloadPdf('en');
    expect(stub.downloadCvPdf).toHaveBeenCalledWith('en');
    clickSpy.mockRestore();
  });
});
```

> Adjust imports (`ProfileService`, `ProfileComponent`, `TestBed`, `vi`) to match the existing spec file. If the existing spec provides `ProfileService` via `HttpClientTestingModule`, prefer the `useValue` stub override shown here for these two tests.

- [ ] **Step 4: Run the specs**

Run: `cd frontend && npm test -- --include "**/profile.component.spec.ts"`
Expected: PASS (existing + 2 new tests).

- [ ] **Step 5: Build + lint**

Run: `cd frontend && npm run build && npx ng lint`
Expected: build succeeds; lint clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/profile/profile.component.ts frontend/src/app/pages/profile/profile.component.html frontend/src/app/pages/profile/profile.component.spec.ts
git commit -m "feat(profile): translate-to-other + per-language PDF download UI"
```

---

## Final verification

- [ ] **Backend full suite**

Run: `cd backend && uv run python -m pytest -q`
Expected: all green (DB-free).

- [ ] **Backend lint**

Run: `cd backend && uv run ruff check .`
Expected: no new errors in touched files.

- [ ] **Frontend test + build + lint**

Run: `cd frontend && npm test && npm run build && npx ng lint`
Expected: all green.

- [ ] **Manual smoke (optional, needs running app + xelatex + LLM key)**

  1. `docker compose up db` then `cd backend && uv run python -m alembic upgrade head` (applies migration 029).
  2. `uv run app`; in another shell `cd frontend && npm start`.
  3. Upload a `.tex` CV in English on the profile page.
  4. Click **Translate to es** → a Spanish variant appears with a **Machine-translated** badge.
  5. Click **Download PDF (es)** → a compiled PDF downloads.

---

## Notes for the implementer

- **uv quirk:** always `uv run python -m pytest` / `-m alembic`; bare `uv run pytest`/`alembic` fail on this machine.
- **ruff:** the repo is not `ruff format`-clean and CI only runs `ruff check` — never run `ruff format .` repo-wide.
- **ng lint:** CI runs `ng lint`; `npm test`/`npm run build` skip it. Run `npx ng lint` before pushing frontend.
- **Route ordering:** `/profile/cv.pdf` and `/profile/translate` must be declared before `/{profile_id}` or the path param swallows them.
- **One-class-per-file:** `CVTranslator` and `TranslationOutcome` each live in their own file and are re-exported from `profile/domain/__init__.py`.
```