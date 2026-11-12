import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.join(root, 'previews');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true });
try {
  for (const [name, width, height] of [['desktop',1440,1000], ['notebook',1366,768], ['mobile',390,844]]) {
    const page = await browser.newPage({ viewport: { width, height }, reducedMotion: 'reduce' });
    const errors = [];
    const external = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) external.push(request.url()); });
    await page.goto(pathToFileURL(path.join(root, 'index.html')).href);
    await page.locator('#clock').filter({ hasText: /\d{1,2}:\d{2}/ }).waitFor({ state: 'attached' });
    assert.equal(await page.locator('#home-view').isVisible(), true);
    assert.equal(await page.locator('#finance-demo').isVisible(), false);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, name);
    if (name === 'notebook') assert.equal(await page.evaluate(() => document.documentElement.scrollHeight > innerHeight), false, 'Notebook overview should fit vertically');
    await page.screenshot({ path: path.join(output, `home-${name}.png`), fullPage: true });
    await page.locator('[data-dialog="bob"]').click();
    assert.equal(await page.locator('dialog').isVisible(), true);
    await page.keyboard.press('Escape');
    await page.locator('[data-view="finance"]').click();
    await page.locator('#finance-view').waitFor();
    assert.equal(await page.locator('.finance-empty').isVisible(), true);
    await page.locator('#show-demo').click();
    assert.equal(await page.locator('#finance-demo').isVisible(), true);
    assert.match(await page.locator('#finance-demo').innerText(), /16 569,50/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `finance-${name}`);
    await page.screenshot({ path: path.join(output, `finance-${name}.png`), fullPage: true });
    await page.locator('.back-link').click();
    await page.locator('#home-view').waitFor();
    await page.locator('[data-view="finance"]').click();
    await page.locator('#finance-view').waitFor();
    assert.equal(await page.locator('#finance-demo').isVisible(), false, 'Financial demo must not reopen automatically');
    await page.locator('#show-demo').click();
    await page.locator('#hide-demo').click();
    assert.equal(await page.locator('#finance-demo').isVisible(), false);
    assert.deepEqual(errors, []);
    assert.deepEqual(external, [], 'Prototype must not call external services');
    await page.close();
    console.log(`PASS ${name}: home, privacy default, demo, dialogs, viewport, no external requests`);
  }
} finally {
  await browser.close();
}
