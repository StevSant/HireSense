# CV Translation & Per-Language PDF Download — Design

**Date:** 2026-06-13
**Status:** Approved (brainstorming)
**Module:** `profile` (backend), `pages/profile` (frontend)

## Problem

Today a user must upload their CV separately for each language (`en` / `es`) via
`POST /profile/upload-file`. There is no way to derive one language from the
other, and no way to download a compiled PDF directly from the profile — PDF
download exists only inside an application (`GET /applications/{id}/cv.pdf`).

We want:

1. **Upload once, translate on demand.** After uploading a CV in one language, an
   explicit **"Translate to {other language}"** action produces the other-language
   variant via the LLM, translating the human-readable text while preserving all
   LaTeX commands and structure.
2. **Download the compiled PDF per language** directly from the profile page.

## Decisions (locked during brainstorming)

- **Trigger:** explicit button after upload (not automatic, not background).
- **Translation scope:** translate the raw `.tex`, preserving all LaTeX
  commands/structure, so the translated variant is itself compilable.
- **PDF download location:** profile page, one button per language variant
  (new profile-level endpoint).
- **Overwrite rule:** translating to a language **replaces** the latest variant
  in that language.
- **Provenance:** translated variants are flagged `machine_translated` and shown
  with a badge.
- **Compile-failure handling:** if the post-translation sanity compile fails, the
  flagged translation is **saved anyway** (nothing is lost); the response signals
  `pdf_ok=false` so the UI warns the user to review.
- **Download button visibility:** shown for **every** variant; compile errors
  surface on click.

## Approach

**Single-shot full-document translation with a compile sanity-check.** The entire
`raw_tex` is sent to the LLM with a strict "translate human-readable text only,
never alter LaTeX commands, environments, or structure" instruction, mirroring the
fence-stripping pattern already used by `CVOptimizer`. The result is compiled once
to confirm it still builds.

Alternatives rejected:
- *Section-aware AST translation* — much more complex for marginal safety gain.
- *Translate cleaned section text only* — loses `raw_tex`, which defeats the
  per-language PDF-download goal.

## Backend changes

### 1. New LLM feature key

Append to `admin/domain/feature_registry.py::FEATURE_REGISTRY`:

```python
FeatureDescriptor(
    key="cv_translator",
    name="CV Translator",
    description="Translates a CV's LaTeX into another language, preserving commands.",
)
```

Model is admin-configurable per feature; absent an override it falls back to
`settings.llm_model`. No `.env` change required.

### 2. `CVTranslator` domain service

New file `profile/domain/cv_translator.py` (one class per file), re-exported from
`profile/domain/__init__.py`:

```python
class CVTranslator:
    def __init__(self, llm: LLMPort | None) -> None: ...
    async def translate(self, raw_tex: str, source_lang: str, target_lang: str) -> str:
        # strict preserve-commands prompt; strip markdown fence; return tex
```

- Raises `RuntimeError` if `llm is None` (LLM unconfigured) — surfaced as 503.
- Prompt instructs: translate only human-readable text in section content,
  headings, and prose; leave every LaTeX command, environment, option, URL, email,
  and structural token unchanged; return only the full `.tex`.

### 3. `profiles.machine_translated` column

- `ProfileOrm`: `machine_translated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=...)`.
- `CandidateProfile`: `machine_translated: bool = False`.
- Repository `_to_domain` / `_to_orm`: map the field; `create(..., machine_translated=...)`.
- New Alembic migration adding the column (default `false`).

### 4. `ProfileService.translate_to(target_language)`

```python
async def translate_to(self, target_language: str) -> TranslationOutcome:
    # 1. source = latest variant in the OTHER language; 400 (ValueError) if none
    # 2. translated_tex = await self._translator.translate(source.raw_tex, source.language, target_language)
    # 3. parse translated_tex (LaTeXParser) to refresh sections/skills for the target
    # 4. compile sanity-check via self._latex_compiler (pdf_ok / compile_error)
    # 5. REPLACE latest target-language variant: create new row, machine_translated=True
    # 6. return TranslationOutcome(profile, pdf_ok, compile_error)
```

- New collaborators on `ProfileService.__init__`: `translator: CVTranslator | None`,
  `latex_compiler: LatexCompilerPort | None`. Both optional so existing
  in-memory/test construction stays valid.
- "Replace the latest target-language variant" reuses the existing
  `create` + "latest-per-language" repository behavior (insert wins as current);
  no new repository method strictly required.
- Shared links (`linkedin_url` / `github_url` / `portfolio_url`) inherited via the
  existing `_inherit_shared_links()` path.
- `TranslationOutcome` is a small frozen dataclass in the domain.

### 5. Endpoints (`profile/api/routes.py`)

```python
class TranslateRequest(BaseModel):
    target_language: Literal["en", "es"]

class TranslateResponse(BaseModel):
    profile: CandidateProfile
    pdf_ok: bool
    compile_error: str | None = None

@router.post("/translate", response_model=TranslateResponse)
async def translate_cv(body, service): ...
    # 503 if LLM unconfigured (RuntimeError), 400 if no source CV (ValueError)

@router.get("/cv.pdf")
async def download_cv_pdf(language: Literal["en","es"], service): ...
    # compile latest raw_tex for `language`; 400 if none, 500 (LaTeX log) on compile failure
    # StreamingResponse(media_type="application/pdf", Content-Disposition attachment)
```

### 6. Bootstrap wiring (`bootstrap/profile.py`)

`build_profile(infra, tracked, latex_compiler)` — pass `tracked("cv_translator")`
into `CVTranslator` and the shared `LatexCompilerPort` into `ProfileService`.
Update the caller in `bootstrap/__init__.py` (the compiler instance already exists
for the applications build — reuse it).

## Frontend changes (`pages/profile`)

### `core/services/profile.service.ts`
- `translate(targetLanguage: string): Observable<TranslateResponse>` → POST
  `/profile/translate`; on success update `profiles` signal and `activeLanguage`.
- `downloadCvPdf(language: string): Observable<Blob>` → GET `/profile/cv.pdf?language=`
  with `responseType: 'blob'`; component triggers browser save.

### `profile.component`
- **"Translate to {other language}"** button: visible when at least one variant
  exists; derives the target as the language that is *not* currently active.
  Shows a loading state; on `pdf_ok=false` shows a warning notice.
- **"Download PDF"** button per language variant → blob → anchor download
  (`cv_{language}.pdf`).
- **"Machine-translated"** badge on variants where `machine_translated` is true.
- `CandidateProfile` model gains `machine_translated: boolean`.

## Error handling

| Condition | Behavior |
|---|---|
| LLM unconfigured (`tracked` → None) | `POST /translate` → 503 |
| No source CV in the other language | `POST /translate` → 400 |
| Translation compiles | saved, `machine_translated=true`, `pdf_ok=true` |
| Translation fails sanity compile | **saved anyway**, `machine_translated=true`, `pdf_ok=false`, `compile_error` set; UI warns |
| `GET /cv.pdf` no CV for language | 400 |
| `GET /cv.pdf` compile failure | 500 with tail of LaTeX log |

## Testing

**Backend unit**
- `CVTranslator`: fake LLM returns translated tex; assert the prompt carries the
  preserve-commands instruction and that markdown fences are stripped; `RuntimeError`
  when `llm is None`.
- `ProfileService.translate_to`: fake repo + fake translator + fake compiler;
  asserts it reads the other-language source, replaces the target variant, sets
  `machine_translated=True`, and propagates `pdf_ok` / `compile_error`; 400 when no
  source.

**Backend integration** (StaticPool SQLite, `require_auth` override, fake
`LatexCompilerPort` returning bytes — per the audit conventions)
- `POST /profile/translate` happy path + 503 (no LLM) + 400 (no source).
- `GET /profile/cv.pdf` returns `application/pdf`; 400 when missing; 500 on compile
  error (fake compiler raising `LatexCompileError`).

**Frontend**
- `profile.component` spec: translate button calls service and refreshes; download
  triggers blob save; badge renders when `machine_translated`.

## Out of scope (YAGNI)

- Automatic/background translation.
- LLM auto-repair loop on compile failure (the flagged + `pdf_ok=false` path is
  sufficient; user can re-upload/replace manually).
- Version history UI for prior variants.
- Languages beyond `en` / `es`.
