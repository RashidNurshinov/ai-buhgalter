// node render.js preview t1,t2,...   |   node render.js full
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const mode = process.argv[2];
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.join(__dirname, 'ad.html'));
  await page.evaluate(() => window.ready);
  await page.waitForTimeout(300);
  if (mode === 'preview') {
    const ts = process.argv[3].split(',').map(Number);
    for (const t of ts) {
      await page.evaluate(t => render(t), t);
      await page.screenshot({ path: path.join(__dirname, `prev_${t}.jpg`), type: 'jpeg', quality: 80 });
    }
  } else {
    const FPS = 30, DUR = 40, dir = path.join(__dirname, 'frames');
    fs.mkdirSync(dir, { recursive: true });
    for (let i = 0; i < FPS * DUR; i++) {
      await page.evaluate(t => render(t), i / FPS);
      await page.screenshot({ path: path.join(dir, String(i).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 92 });
      if (i % 150 === 0) console.log('frame', i);
    }
  }
  await browser.close();
})();
