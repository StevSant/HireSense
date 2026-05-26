// Headless screenshot helper for iterating on the profile page styling.
// Run with: node scripts/profile-screenshot.mjs [outfile]
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outArg = process.argv[2] ?? 'profile.png';
const outPath = path.isAbsolute(outArg) ? outArg : path.join(__dirname, '..', '.screenshots', outArg);

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await context.newPage();

const consoleErrors = [];
page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
page.on('console', (m) => {
  if (m.type() === 'error') consoleErrors.push(`console.error: ${m.text()}`);
});

await page.goto('http://localhost:4200/login', { waitUntil: 'networkidle' });

if (await page.locator('#username').count()) {
  await page.fill('#username', 'admin');
  await page.fill('#password', 'changeme');
  await Promise.all([
    page.waitForURL('**/dashboard/**', { timeout: 15000 }).catch(() => {}),
    page.click('button[type="submit"]'),
  ]);
}

const tab = process.argv[3] ?? 'cv';
const scrollSection = process.argv[4]; // optional: section name substring to scroll to
await page.goto('http://localhost:4200/dashboard/profile', { waitUntil: 'networkidle' });
await page.waitForSelector('.profile-view, .upload-card, .details-card, .per-job-card', { timeout: 15000 }).catch(() => {});
if (tab !== 'cv') {
  const label = tab === 'personal' ? 'Personal details' : tab === 'cover-letters' ? 'Cover letters' : 'CV';
  await page.getByRole('tab', { name: label }).click().catch(() => {});
}
await page.waitForTimeout(500);
const clickButton = process.env.CLICK_BUTTON_TEXT;
if (clickButton) {
  await page.getByRole('button', { name: clickButton }).first().click().catch(() => {});
  await page.waitForTimeout(300);
}
if (scrollSection) {
  await page.evaluate((needle) => {
    const headings = Array.from(document.querySelectorAll('.section h3'));
    const match = headings.find((h) => h.textContent?.toLowerCase().includes(needle.toLowerCase()));
    match?.scrollIntoView({ behavior: 'instant', block: 'start' });
  }, scrollSection);
  await page.waitForTimeout(300);
}

const checkHtml = await page.evaluate(() => {
  return {
    coverTabExists: !!document.querySelector('app-cover-letter-library, app-cover-letter-templates'),
    comingSoonCount: document.querySelectorAll('.coming-soon-card').length,
    tabPanelInner: document.querySelector('.tab-panel')?.outerHTML?.slice(0, 200) ?? null,
  };
});
console.log('--- HTML probe ---');
console.log(JSON.stringify(checkHtml, null, 2));

const dumpContents = process.argv.includes('--dump');
if (dumpContents) {
  const sectionsDump = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.section')).map((s) => ({
      heading: s.querySelector('h3')?.textContent?.trim(),
      raw: s.querySelector('.section-content')?.textContent ?? '',
    }));
  });
  console.log('--- section contents ---');
  for (const s of sectionsDump) {
    console.log(`\n## ${s.heading}`);
    console.log(s.raw);
  }
}

const metrics = await page.evaluate(() => {
  const pageEl = document.querySelector('.page');
  const view = document.querySelector('.profile-view');
  const infoGrid = document.querySelector('.info-grid');
  const r = (el) => (el ? el.getBoundingClientRect() : null);
  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    page: r(pageEl) && { width: r(pageEl).width, left: r(pageEl).left, right: r(pageEl).right },
    profileView: r(view) && { width: r(view).width, left: r(view).left, right: r(view).right },
    infoGrid: r(infoGrid) && { width: r(infoGrid).width, left: r(infoGrid).left, right: r(infoGrid).right },
    contentMaxWidth: getComputedStyle(document.querySelector('.content') ?? document.body).maxWidth,
  };
});

const focusSelector = process.env.FOCUS_SELECTOR;
if (focusSelector) {
  const element = await page.$(focusSelector);
  if (element) {
    await element.screenshot({ path: outPath });
  } else {
    await page.screenshot({ path: outPath, fullPage: true });
  }
} else {
  await page.screenshot({ path: outPath, fullPage: true });
}

console.log('--- metrics ---');
console.log(JSON.stringify(metrics, null, 2));
if (consoleErrors.length) {
  console.log('--- page console errors ---');
  for (const e of consoleErrors) console.log(e);
}
console.log(`Saved: ${outPath}`);

await browser.close();
