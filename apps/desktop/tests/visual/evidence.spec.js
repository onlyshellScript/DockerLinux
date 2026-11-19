// evidence.spec.js: prueba visual de la bandeja de evidencias.
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

// devuelve login; sin efectos secundarios.
async function login(page) {
  await page.waitForSelector('.app-sidebar', { timeout: 30000 });
}

// devuelve shot; accede al sistema de archivos.
async function shot(page, name, size) {
  const dir = path.join(__dirname, 'screenshots');
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${name}-${size.width}x${size.height}.png`), fullPage: true });
}

(async () => {
  for (const size of sizes) {
    const app = await electron.launch({ args: ['.'] });
    const page = await app.firstWindow();
    await page.setViewportSize(size);
    await login(page);
    await page.click('[data-view="evidence-inbox"]');
    await page.waitForTimeout(2000);
    await shot(page, 'evidence-inbox', size);
    await page.click('[data-view="evidence"]');
    await page.waitForTimeout(2000);
    await shot(page, 'evidence-technician', size);
    await app.close();
  }
  console.log('done');
})();