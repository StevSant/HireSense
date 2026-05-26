// Drive the /dashboard/ingestion page to capture the jobs table state.
// Usage: node scripts/ingestion-screenshot.mjs <outfile> [--sort=match_desc]
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outArg = process.argv[2] ?? 'ingestion.png';
const outPath = path.isAbsolute(outArg) ? outArg : path.join(__dirname, '..', '.screenshots', outArg);
const sort = process.argv.find((a) => a.startsWith('--sort='))?.split('=')[1];
const minScoreZero = process.argv.includes('--no-min-score');

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await context.newPage();
const consoleErrors = [];
page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`console.error: ${m.text()}`); });

await page.goto('http://localhost:4200/login', { waitUntil: 'networkidle' });
if (await page.locator('#username').count()) {
  await page.fill('#username', 'admin');
  await page.fill('#password', 'changeme');
  await Promise.all([
    page.waitForURL('**/dashboard/**', { timeout: 15000 }).catch(() => {}),
    page.click('button[type="submit"]'),
  ]);
}

await page.goto('http://localhost:4200/dashboard/ingestion', { waitUntil: 'networkidle' });
await page.waitForSelector('table, .empty-state', { timeout: 15000 }).catch(() => {});
await page.waitForTimeout(800);

if (sort) {
  await page.selectOption('#sort-select', sort).catch(() => {});
  await page.waitForTimeout(800);
}

const rows = await page.evaluate(() => {
  const result = [];
  for (const tr of document.querySelectorAll('tbody tr')) {
    const cells = tr.querySelectorAll('td');
    if (cells.length < 5) continue;
    result.push({
      match: cells[0]?.innerText?.trim() ?? '',
      title: cells[1]?.innerText?.trim() ?? '',
      company: cells[2]?.innerText?.trim() ?? '',
      location: cells[3]?.innerText?.trim() ?? '',
      source: cells[4]?.innerText?.trim() ?? '',
    });
  }
  return result;
});

await page.screenshot({ path: outPath, fullPage: false });
console.log(`Saved: ${outPath}`);
console.log('--- first 12 rows ---');
console.log(JSON.stringify(rows.slice(0, 12), null, 2));
if (consoleErrors.length) {
  console.log('--- page errors ---');
  for (const e of consoleErrors) console.log(e);
}
await browser.close();
