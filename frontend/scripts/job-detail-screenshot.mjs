// Open the ingestion table and click the first hn_hiring row so we can
// screenshot the redesigned detail panel against structured-section data.
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outArg = process.argv[2] ?? 'job-detail.png';
const outPath = path.isAbsolute(outArg) ? outArg : path.join(__dirname, '..', '.screenshots', outArg);
const sourceFilter = process.argv[3] ?? 'hn_hiring';
const jobId = process.argv.find((a) => a.startsWith('--job-id='))?.split('=')[1];

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await context.newPage();

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
await page.waitForSelector('table tbody tr', { timeout: 15000 }).catch(() => {});
await page.waitForTimeout(800);

const keyword = process.argv.find((a) => a.startsWith('--keyword='))?.split('=')[1];
if (keyword) {
  await page.fill('input[placeholder^="Search title"]', keyword);
  await page.waitForTimeout(900);
}

// Find the first row whose source cell matches the filter.
const rowClicked = await page.evaluate((src) => {
  const rows = Array.from(document.querySelectorAll('tbody tr'));
  for (const row of rows) {
    const cells = row.querySelectorAll('td');
    if (cells.length < 5) continue;
    if (cells[4].textContent?.trim() === src) {
      row.click();
      return cells[1].textContent?.trim() ?? '';
    }
  }
  return null;
}, sourceFilter);

console.log('Clicked row title:', rowClicked);
await page.waitForSelector('.panel', { timeout: 5000 }).catch(() => {});
await page.waitForTimeout(500);

await page.screenshot({ path: outPath, fullPage: false });
console.log(`Saved: ${outPath}`);
await browser.close();
