/**
 * Render the launch carousels to print-accurate PDFs.
 *
 *   node export-pdf.mjs            # both languages
 *   node export-pdf.mjs es         # one language
 *
 * Chrome's print dialog is unreliable for this deck: the "Microsoft Print to PDF"
 * destination ignores `@page { size: 1080px 1350px }` and falls back to Letter, and
 * "Background graphics" is off by default, which flattens the dark slides to white.
 * Headless Chromium takes both as explicit arguments instead.
 *
 * Requires Playwright (local, or global via `npm i -g @playwright/test`) and its
 * Chromium build (`npx playwright install chromium`).
 */

import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import process from 'node:process';

const HERE = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));

/** Slide box in CSS pixels — must match `.slide` / `@page` in carousel.css. */
const PAGE = { width: '1080px', height: '1350px' };
const LANGUAGES = ['en', 'es'];

/** Playwright may live in this folder, in a parent, or in the global npm root. */
async function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [];
  try {
    candidates.push(require.resolve('playwright'));
  } catch {
    /* not installed locally — fall through to the global root */
  }
  try {
    const globalRoot = execSync('npm root -g', { encoding: 'utf8' }).trim();
    candidates.push(
      path.join(globalRoot, 'playwright', 'index.js'),
      path.join(globalRoot, '@playwright', 'test', 'node_modules', 'playwright', 'index.js'),
    );
  } catch {
    /* npm not on PATH — the local resolution above is the only chance */
  }

  for (const entry of candidates) {
    try {
      // Playwright ships as CommonJS, so the named export may only exist on `default`.
      const mod = await import(pathToFileURL(entry).href);
      const chromium = mod.chromium ?? mod.default?.chromium;
      if (chromium) return chromium;
    } catch {
      /* try the next candidate */
    }
  }
  throw new Error(
    'Playwright not found. Install it with `npm i -g @playwright/test` and then ' +
      '`npx playwright install chromium`.',
  );
}

async function exportLanguage(browser, lang) {
  const source = path.join(HERE, `carousel-${lang}.html`);
  const target = path.join(HERE, `carousel-${lang}.pdf`);

  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  await page.goto(pathToFileURL(source).href, { waitUntil: 'networkidle' });
  // Webfonts arrive from Google Fonts; printing before they land silently swaps in
  // the fallback stack and every headline reflows.
  await page.evaluate(() => document.fonts.ready);

  await page.pdf({
    path: target,
    ...PAGE,
    printBackground: true,
    preferCSSPageSize: false,
    margin: { top: '0', right: '0', bottom: '0', left: '0' },
  });

  const slides = await page.locator('.slide').count();
  await page.close();
  return { target, slides };
}

const requested = process.argv.slice(2).filter((arg) => LANGUAGES.includes(arg));
const languages = requested.length ? requested : LANGUAGES;

const chromium = await loadPlaywright();
const browser = await chromium.launch();
try {
  for (const lang of languages) {
    const { target, slides } = await exportLanguage(browser, lang);
    console.log(`${path.basename(target)} — ${slides} slides at 1080x1350`);
  }
} finally {
  await browser.close();
}
