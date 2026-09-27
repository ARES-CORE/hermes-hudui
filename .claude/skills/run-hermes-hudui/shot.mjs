// Captura de la UI con Playwright + Chromium preinstalado. Uso: node shot.mjs <base> <png> [tab]
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const pwPath = process.env.PLAYWRIGHT_MODULE || '/opt/node22/lib/node_modules/playwright';
const { chromium } = require(pwPath);
const [base, out, tab = 'dashboard'] = process.argv.slice(2);
const keys = { dashboard: '1', memory: '2', skills: '3', profiles: '0' };
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(base + '/', { waitUntil: 'networkidle' });
if (tab !== 'dashboard') { await page.keyboard.press(keys[tab] ?? '1'); await page.waitForTimeout(1500); }
await page.waitForTimeout(1500);
await page.screenshot({ path: out });
console.log('screenshot:', out);
await browser.close();
