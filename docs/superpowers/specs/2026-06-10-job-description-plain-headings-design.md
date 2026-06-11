# Job Description Plain-Heading Parsing & Sectioned Rendering — Design

**Date:** 2026-06-10
**Status:** Approved
**Area:** frontend (`pages/ingestion/lib`, `pages/ingestion/components/job-description`)

## Problem

The job detail page (`/dashboard/job/:id`) renders many descriptions as a single
flat `<p>` wall of text. `parseJobDescription` only recognizes HN-style
`*Heading*:` asterisk headings; postings that use plain-text headings (e.g.
Spanish ATS postings with `Formación:`, `Experiencia:`, `Conocimientos
Específicos / Requisitos Técnicos:`) yield zero sections, so the component
falls back to the raw dump. The result is a huge unstructured column with no
visual hierarchy (see the GetOnBoard-style posting on job
`507c94b9-f778-4a8e-95f0-5fe4f0b9ca0c`).

## Goals

- Parse plain `Heading:` lines into sections so these descriptions render as
  the existing color-coded section cards.
- Render line-oriented section bodies as bullet lists instead of pre-wrapped
  prose.
- Recognize Spanish heading keywords in the emphasis map.

## Non-goals

- No page-layout restructure (tabs, collapsible sections, sticky aside).
- No backend/LLM normalization of descriptions.
- Raw fallback for truly structureless text stays unchanged.

## Design

### 1. Plain-heading detection (`parse-job-description.ts`)

In addition to the existing HN `*Heading*:` pattern, a trimmed line is a
heading when **all** hold:

- it ends with `:` (colon is the last character — rejects prose with
  mid-line colons like `Bases de Datos: SQL y noSQL, como MongoDB.`),
- the text before the colon is 1–60 chars,
- it contains no sentence punctuation (`.`, `;`) before the colon,
- it does not start with a bullet marker (`-`, `•`, `*`, `·`).

Existing HN parsing, intro handling, and section flushing are reused; plain
headings simply become a second way to open a section.

### 2. List-aware section bodies

`JobDescriptionSection` gains an optional `items?: string[]` (additive —
`body` stays populated because `job-detail-panel` reads it for the
compensation highlight):

- Lines starting with a bullet marker are items (marker stripped).
- A section whose body is 2+ plain lines with no blank-line-separated
  paragraphs is treated as a line-list: each non-empty line becomes an item.
- Single-line or paragraph-style bodies keep prose rendering (no `items`).

`JobDescriptionComponent` renders `items` as `<ul class="jd-list">`, else the
existing `<p class="jd-prose">`.

### 3. Spanish emphasis keywords (`EMPHASIS_MAP`)

- compensation: `compensación|salario|sueldo|beneficios`
- apply: `postula|aplicar|contacto`
- stack: `requisitos|conocimientos|tecnología|herramientas`
- role: `experiencia|funciones|responsabilidades|rol|formación`

### 4. Styling

Small SCSS addition only: `.jd-list` — compact bullet list, secondary text
color, same typography as `.jd-prose`. Existing `.jd-section` cards provide
the boxed, color-coded look.

## Testing

- New `parse-job-description.spec.ts`: plain-heading detection, mid-line-colon
  rejection, line-list extraction, bullet-marker stripping, paragraph bodies
  staying prose, HN-format regression, intro preservation.
- `job-description.component.spec.ts`: plain-heading description renders
  `.jd-section` cards with `.jd-list` items; raw fallback regression.
