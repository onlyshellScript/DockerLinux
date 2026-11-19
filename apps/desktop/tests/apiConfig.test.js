const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { resolveApiBaseUrl, validUrl } = require('../src/main/apiConfig');

function tmp() { return fs.mkdtempSync(path.join(os.tmpdir(), 'sigos-cfg-')); }

test('apiConfig: entorno manda sobre archivos', () => {
  const d = tmp();
  fs.writeFileSync(path.join(d, 'sigos-config.json'), JSON.stringify({ apiBaseUrl: 'http://user.local' }));
  const r = resolveApiBaseUrl({ env: { SIGOS_API_BASE_URL: 'https://api.example.com/x' }, userDataDir: d, isPackaged: true, systemConfig: '/nope' });
  assert.deepStrictEqual(r, { url: 'https://api.example.com', source: 'env' });
});

test('apiConfig: usuario > sistema > predeterminado', () => {
  const d = tmp();
  const sys = path.join(d, 'desktop.json');
  fs.writeFileSync(sys, JSON.stringify({ apiBaseUrl: 'http://127.0.0.1:8080' }));
  assert.strictEqual(resolveApiBaseUrl({ env: {}, userDataDir: d, isPackaged: true, systemConfig: sys }).source, 'system');
  fs.writeFileSync(path.join(d, 'sigos-config.json'), JSON.stringify({ apiBaseUrl: 'http://10.0.0.5' }));
  assert.strictEqual(resolveApiBaseUrl({ env: {}, userDataDir: d, isPackaged: true, systemConfig: sys }).url, 'http://10.0.0.5');
});

test('apiConfig: predeterminado segun empaquetado', () => {
  assert.strictEqual(resolveApiBaseUrl({ env: {}, isPackaged: true, systemConfig: '/nope' }).url, 'http://127.0.0.1');
  assert.strictEqual(resolveApiBaseUrl({ env: {}, isPackaged: false, systemConfig: '/nope' }).url, 'http://localhost:5000');
});

test('apiConfig: rechaza URLs invalidas o de otro esquema', () => {
  assert.strictEqual(validUrl('file:///etc/passwd'), null);
  assert.strictEqual(validUrl('javascript:alert(1)'), null);
  assert.strictEqual(validUrl('no es url'), null);
  const d = tmp();
  const sys = path.join(d, 'desktop.json');
  fs.writeFileSync(sys, '{ roto');
  assert.strictEqual(resolveApiBaseUrl({ env: {}, isPackaged: true, systemConfig: sys }).source, 'default');
});
