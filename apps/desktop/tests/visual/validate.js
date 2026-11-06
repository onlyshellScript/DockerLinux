const { _electron: electron } = require('playwright');
const fs = require('fs');
const path = require('path');

const sizes = [
  { width: 1024, height: 768 },
  { width: 1280, height: 800 },
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];

async function check(page, label) {
  const result = await page.evaluate(() => {
    const doc = document.documentElement;
    const overflowX = doc.scrollWidth > window.innerWidth + 2;
    const buttons = Array.from(document.querySelectorAll('button'));
    const rects = buttons.map(b => {
      const r = b.getBoundingClientRect();
      return { el: b, r };
    });
    let overlaps = 0;
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        const a = rects[i].r, b = rects[j].r;
        const inter = !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
        if (inter) overlaps++;
      }
    }
    const outOfView = buttons.filter(b => {
      const r = b.getBoundingClientRect();
      return r.right > window.innerWidth + 2 || r.bottom > window.innerHeight + 2 || r.left < -2 || r.top < -2;
    }).length;
    return { overflowX, overlaps, outOfView, buttonCount: buttons.length };
  });
  console.log(label, JSON.stringify(result));
}

(async () => {
  for (const size of sizes) {
    const app = await electron.launch({ args: ['.'] });
    const page = await app.firstWindow();
    await page.setViewportSize(size);
    await page.waitForSelector('.sidebar', { timeout: 30000 });
    await page.click('[data-view="evidence-inbox"]');
    await page.waitForTimeout(2500);
    await check(page, `inbox ${size.width}x${size.height}`);
    const openBtn = await page.$('.ev-open-btn');
    if (openBtn) { await openBtn.click(); await page.waitForTimeout(2500); await check(page, `detail ${size.width}x${size.height}`); }
    await page.click('[data-view="evidence"]');
    await page.waitForTimeout(2500);
    await check(page, `technician ${size.width}x${size.height}`);
    await app.close();
  }
  console.log('done');
})();