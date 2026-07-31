# Launch carousel

An 8-slide LinkedIn document post, in English and Spanish, built as printable HTML.

| File | What it is |
|---|---|
| `carousel-en.html` | English slides |
| `carousel-es.html` | Spanish slides |
| `carousel.css` | Shared styling for both — edit here to change the design once |
| `export-pdf.mjs` | Renders both HTML files to `carousel-<lang>.pdf` at exactly 1080×1350 |

The copy on the slides mirrors the primary launch post in
[`../copy-en.md`](../copy-en.md) / [`../copy-es.md`](../copy-es.md). If you rewrite a hook
there, rewrite it here too.

## Export to PDF

```bash
cd docs/open-source-launch/carousel
node export-pdf.mjs          # both languages
node export-pdf.mjs es       # just one
```

You get `carousel-en.pdf` and `carousel-es.pdf`: 8 pages, exactly 1080×1350 px (4:5), the
LinkedIn document-post ratio, backgrounds intact. Upload with "Add a document". The grey
instruction bar at the top of the HTML page is screen-only and never reaches the PDF.

The script needs Playwright and its Chromium build; it resolves Playwright from the folder
or from the global npm root:

```bash
npm i -g @playwright/test && npx playwright install chromium
```

### Printing by hand instead

Only if you can't run the script — Chrome's dialog gets this wrong in two ways:

1. Destination must be **Save as PDF**, *not* "Microsoft Print to PDF". The Windows printer
   driver ignores `@page { size: 1080px 1350px }` and forces Letter, so the slides get
   letterboxed and the ratio stops being 4:5.
2. Open **More settings** and tick **Background graphics**. Chrome strips backgrounds by
   default, which turns the dark slides (1, 3, 8) into white pages with grey headlines.

Also set Margins: **None** and Scale: **Default**.

## The slides

| # | Purpose | Note |
|---|---|---|
| 1 | Hook — the question | Cover. No product, no logo lockup. This is what stops the scroll. |
| 2 | The before — tabs, spreadsheet, four CV versions | The identification slide |
| 3 | The insight — "it's on page 40" | The idea people quote back at you. Don't cut this one. |
| 4 | How — the five-step pipeline | The credibility slide |
| 5 | The result — ranked shortlist | |
| 6 | After the match — the rest of the workflow | So it doesn't read as "just a search box" |
| 7 | New — conferences, CFPs, funded programs | The freshness hook |
| 8 | Close — open source, self-hosted, links | One call to action only |

Slides 3 and 4 do the persuading. If you need to shorten the deck, cut 6 before either.

## The product views are mocks, not screenshots

Slides 5 and 7 are hand-built HTML mocks of the Discover and Opportunities views, using
**synthetic** companies, roles, and deadlines. They are sharper than a downscaled screenshot
and carry no risk of leaking real listings or personal data.

That is a deliberate trade-off: they are *representative*, not literal captures. Keep real
screenshots in the repository README so nobody can claim the carousel oversells the product,
and never swap real company names or live listings into these slides.

## Before you post

- [ ] Pages 1, 3 and 8 are actually dark in the PDF — if they're white, the export lost the
      backgrounds (see "Printing by hand" above).
- [ ] Both links on slide 8 resolve — repository and `hiresense-demo.vercel.app`. The demo
      went live on 2026-07-31; re-check it right before posting, since a push to `main` that
      drops the root `vercel.json` would break it again.
- [ ] The post's first line matches slide 1 — LinkedIn truncates after ~2–3 lines, so the
      hook has to work alone.
- [ ] Only the demo and repository links are in the post body; anything else goes in the
      first comment.
- [ ] One call to action, not five.
