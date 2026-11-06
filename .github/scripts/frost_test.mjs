import { chromium } from 'playwright';
import fs from 'fs';
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1200, height: 2000 } });
await p.goto('https://wetter-badkoenig.de/facebook.html?v=' + Date.now(), { waitUntil: 'networkidle' });
const c = p.locator('.card.frost'); await c.waitFor({ timeout: 60000 });
const src = await c.locator('img').getAttribute('src'); const text = await c.locator('textarea').inputValue();
fs.writeFileSync('/tmp/frost.jpg', Buffer.from(src.split(',')[1], 'base64')); fs.writeFileSync('/tmp/frost.txt', text);
console.log(text); await b.close();
