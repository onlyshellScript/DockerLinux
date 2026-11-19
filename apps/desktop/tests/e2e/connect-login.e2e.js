// Prueba E2E (manual / CI con pantalla): pantalla de conexion -> login -> cambio de contrasena obligatorio.
// Requiere un API que arranque DESPUES de abrir la app. Uso:
//   SIGOS_API_BASE_URL=http://127.0.0.1:5055 SIGOS_E2E_START_API="<comando que arranca el API>" \
//   SIGOS_E2E_PASSWORD=<pwd admin inicial> node tests/e2e/connect-login.e2e.js
const { _electron: electron } = require('playwright');
const { spawn } = require('node:child_process');
const path = require('node:path');

(async () => {
  const base = process.env.SIGOS_API_BASE_URL;
  const pwd = process.env.SIGOS_E2E_PASSWORD;
  const newPwd = process.env.SIGOS_E2E_NEW_PASSWORD || 'Definitiva-2026-Ab';
  if (!base || !pwd || !process.env.SIGOS_E2E_START_API) throw new Error('faltan variables SIGOS_*');
  const app = await electron.launch({ args: [path.join(__dirname, '..', '..')], env: { ...process.env } });
  const win = await app.firstWindow();
  const results = [];
  const step = (name, okv) => { results.push([name, okv]); console.log(`${okv ? 'PASS' : 'FAIL'} ${name}`); };

  await win.waitForSelector('#title', { timeout: 15000 });
  step('pantalla de conexion visible sin API', (await win.textContent('#title')).includes('Conectando'));
  step('muestra la URL configurada', (await win.textContent('#url')) === new URL(base).origin);

  const api = spawn(process.env.SIGOS_E2E_START_API, { shell: true, stdio: 'ignore' });
  try {
    await win.waitForSelector('#loginForm', { timeout: 90000 });
    step('entra sola al login cuando el API responde', true);
    await win.fill('#username', 'admin');
    await win.fill('#password', pwd);
    await win.click('#loginBtn');
    await win.waitForSelector('#cpForm', { timeout: 20000 });
    step('dialogo de cambio obligatorio tras el primer login', (await win.textContent('#cpTitle')).includes('para continuar'));
    step('el dialogo obligatorio no tiene boton cerrar', (await win.$('[data-cp-close]')) === null);
    await win.keyboard.press('Escape');
    step('Escape no cierra el dialogo obligatorio', (await win.$('#cpForm')) !== null);
    await win.fill('#cpCur', pwd);
    await win.fill('#cpNew', newPwd);
    await win.fill('#cpRep', newPwd);
    await win.click('#cpSave');
    await win.waitForSelector('#cpForm', { state: 'detached', timeout: 20000 });
    step('cambio de contrasena aceptado y dialogo cerrado', true);
    await win.waitForSelector('.app-shell', { timeout: 20000 });
    step('acceso a la aplicacion tras el cambio', true);
  } catch (e) {
    step(`error: ${e.message.split('\n')[0]}`, false);
    await win.screenshot({ path: path.join(require('node:os').tmpdir(), 'sigos-e2e-fail.png') }).catch(() => {});
  } finally {
    await app.close().catch(() => {});
    try { process.kill(-api.pid); } catch { api.kill(); }
  }
  const failed = results.filter(([, v]) => !v).length;
  console.log(`Resultado: ${results.length - failed} PASS, ${failed} FAIL`);
  process.exit(failed ? 1 : 0);
})();
