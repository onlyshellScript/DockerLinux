// index.js: proceso principal de Electron (ventana, IPC, sesion local).
const { app, BrowserWindow, ipcMain, safeStorage, dialog, shell, nativeTheme } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { getHealth } = require('./healthClient');
const { resolveApiBaseUrl } = require('./apiConfig');

const API_BASE_URL = resolveApiBaseUrl({ userDataDir: app.getPath('userData'), isPackaged: app.isPackaged }).url;
const SESSION_FILE = path.join(app.getPath('userData'), 'sigos-session.bin');

// readSession(): lee read session; accede al sistema de archivos; gestiona la sesion cifrada local.
function readSession() {
  try {
    if (!fs.existsSync(SESSION_FILE)) return null;
    const raw = fs.readFileSync(SESSION_FILE);
    const json = safeStorage.isEncryptionAvailable() ? safeStorage.decryptString(raw) : raw.toString('utf8');
    return JSON.parse(json);
  } catch {
    return null;
  }
}

// writeSession(session): escribe write session; accede al sistema de archivos; gestiona la sesion cifrada local.
function writeSession(session) {
  const json = JSON.stringify(session || null);
  const data = safeStorage.isEncryptionAvailable()
    ? safeStorage.encryptString(json)
    : Buffer.from(json, 'utf8');
  fs.writeFileSync(SESSION_FILE, data);
}

// clearSession(): limpia clear session; accede al sistema de archivos.
function clearSession() {
  try { fs.unlinkSync(SESSION_FILE); } catch {}
}

// devuelve api request; realiza peticiones de red.
async function apiRequest({ method, path: reqPath, body, form, token, headers: extraHeaders }) {
  const url = new URL(reqPath, API_BASE_URL);
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (extraHeaders && typeof extraHeaders === 'object') Object.assign(headers, extraHeaders);
  let payload;
  if (form) {
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => { if (v !== undefined && v !== null) fd.append(k, v); });
    payload = fd;
  } else if (body) {
    if (!headers['Content-Type'] && !headers['content-type']) headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  try {
    const response = await fetch(url, {
      method: method || 'GET',
      headers,
      body: payload,
    });
    let parsed = null;
    const text = await response.text();
    try { parsed = text ? JSON.parse(text) : null; } catch { parsed = text; }
    return { ok: response.ok, status: response.status, body: parsed };
  } catch (error) {
    return { ok: false, status: 0, body: null, error: String(error) };
  }
}


// saveFile(payload): guarda save file; accede al sistema de archivos; muestra dialogos nativos del sistema.
async function saveFile(payload) {
  try {
    const { defaultName, filters, data } = payload || {};
    const allowedExt = ['csv', 'xlsx', 'pdf'];
    const ext = (defaultName || '').split('.').pop().toLowerCase();
    if (!allowedExt.includes(ext)) return { ok: false, error: 'invalid extension' };
    const result = await dialog.showSaveDialog({
      title: 'Guardar como',
      defaultPath: defaultName,
      filters: [{ name: ext.toUpperCase(), extensions: [ext] }],
    });
    if (result.canceled || !result.filePath) return { ok: true, canceled: true };
    const chosenExt = result.filePath.split('.').pop().toLowerCase();
    if (chosenExt !== ext) return { ok: false, error: 'invalid extension' };
    const buf = Buffer.from(data);
    require('node:fs').writeFileSync(result.filePath, buf);
    return { ok: true, canceled: false, path: result.filePath };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}


// exportDownload(payload): exporta export download; realiza peticiones de red; accede al sistema de archivos; muestra dialogos nativos del sistema.
async function exportDownload(payload) {
  try {
    const { query, defaultName } = payload || {};
    const token = payload && payload.token;
    const url = API_BASE_URL + '/api/v1/materials/export/download?' + (query || '');
    const res = await fetch(url, { headers: token ? { Authorization: 'Bearer ' + token } : {} });
    if (!res.ok) {
      let msg = 'Error';
      try { const j = await res.json(); msg = j.message || j.error || msg; } catch {}
      return { ok: false, error: msg };
    }
    const buf = Buffer.from(await res.arrayBuffer());
    const ext = (defaultName || 'inventario.csv').split('.').pop().toLowerCase();
    const allowed = ['csv', 'xlsx', 'pdf'];
    if (!allowed.includes(ext)) return { ok: false, error: 'invalid extension' };
    const result = await dialog.showSaveDialog({
      title: 'Guardar como',
      defaultPath: defaultName,
      filters: [{ name: ext.toUpperCase(), extensions: [ext] }],
    });
    if (result.canceled || !result.filePath) return { ok: true, canceled: true };
    const chosenExt = result.filePath.split('.').pop().toLowerCase();
    if (chosenExt !== ext) return { ok: false, error: 'invalid extension' };
    require('node:fs').writeFileSync(result.filePath, buf);
    return { ok: true, canceled: false, path: result.filePath };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

// windowBackground(): color de fondo de la ventana antes de que cargue el CSS (evita el destello blanco en tema oscuro).
function windowBackground() {
  let theme = 'system';
  try { theme = JSON.parse(fs.readFileSync(path.join(app.getPath('userData'), 'sigos-ui-prefs.json'), 'utf8')).theme || 'system'; } catch { /* sin preferencias */ }
  const dark = theme === 'dark' || (theme === 'system' && nativeTheme.shouldUseDarkColors);
  return dark ? '#0F1513' : '#F7F6F3';
}

// createWindow(): crea create window; sin efectos secundarios.
function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    backgroundColor: windowBackground(),
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.webContents.on('will-navigate', (event) => event.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  // Primero la pantalla de conexion: espera a que el API (proxy local) responda y entonces abre la app.
  win.loadFile(path.join(__dirname, '../renderer/connecting.html'));
}

app.whenReady().then(() => {
  ipcMain.handle('sigos:get-health', async () => getHealth(API_BASE_URL));
  ipcMain.handle('sigos:get-api-base-url', async () => API_BASE_URL);
  ipcMain.handle('sigos:open-app', async (event) => {
    await event.sender.loadFile(path.join(__dirname, '../renderer/index.html'));
    return true;
  });
  ipcMain.handle('sigos:api-request', async (_event, payload) => apiRequest(payload || {}));
  ipcMain.handle('sigos:download-file', async (_event, payload) => {
    const { path: reqPath, token } = payload || {};
    const url = new URL(reqPath, API_BASE_URL);
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    try {
      const response = await fetch(url, { headers });
      if (!response.ok) return { ok: false, status: response.status, data: null };
      const buf = Buffer.from(await response.arrayBuffer());
      const ct = response.headers.get('content-type') || 'application/octet-stream';
      return { ok: true, status: response.status, data: buf.toString('base64'), contentType: ct };
    } catch (error) {
      return { ok: false, status: 0, data: null, error: String(error) };
    }
  });
  ipcMain.handle('sigos:upload-file', async (_event, payload) => {
    const { method, path: reqPath, fields, file, token } = payload || {};
    const url = new URL(reqPath, API_BASE_URL);
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const fd = new FormData();
    Object.entries(fields || {}).forEach(([k, v]) => { if (v !== undefined && v !== null) fd.append(k, v); });
    if (file && file.data) {
      const bytes = Buffer.from(file.data, 'base64');
      const blob = new Blob([bytes], { type: file.type || 'application/octet-stream' });
      fd.append(file.field || 'file', blob, file.name || 'upload.bin');
    }
    try {
      const response = await fetch(url, { method: method || 'POST', headers, body: fd });
      const text = await response.text();
      let parsed = null;
      try { parsed = text ? JSON.parse(text) : null; } catch { parsed = text; }
      return { ok: response.ok, status: response.status, body: parsed };
    } catch (error) {
      return { ok: false, status: 0, body: null, error: String(error) };
    }
  });  ipcMain.handle('sigos:session:load', async () => readSession());
  ipcMain.handle('sigos:session:save', async (_event, session) => { writeSession(session); return true; });
  ipcMain.handle('sigos:session:clear', async () => { clearSession(); return true; });
  // Fin de sesion (logout o expiracion): ademas del archivo de sesion se descartan la cache HTTP, el almacenamiento
  // de sesion/IndexedDB/caches y el historial de navegacion, y se recarga el renderer desde cero (sin la ruta
  // anterior). Asi ningun estado en memoria, vista o dato de la cuenta anterior sobrevive para la siguiente.
  // localStorage se conserva solo para preferencias de interfaz (tema, sidebar); el renderer borra antes sus claves de datos.
  ipcMain.handle('sigos:session:end', async (event, payload) => {
    clearSession();
    const wc = event.sender;
    try { await wc.session.clearCache(); } catch { /* sin cache */ }
    try {
      await wc.session.clearStorageData({ storages: ['sessionstorage', 'indexdb', 'cachestorage', 'serviceworkers', 'websql', 'shadercache', 'cookies'] });
    } catch { /* almacenamiento no disponible */ }
    const reason = payload && payload.reason === 'expired' ? 'expired' : 'logout';
    const clearHistory = () => {
      try {
        if (wc.navigationHistory && typeof wc.navigationHistory.clear === 'function') wc.navigationHistory.clear();
        else if (typeof wc.clearHistory === 'function') wc.clearHistory();
      } catch { /* sin historial */ }
    };
    wc.once('did-finish-load', clearHistory);
    await wc.loadFile(path.join(__dirname, '../renderer/index.html'), { query: { ended: reason } });
    return true;
  });
  // Peticion que puede devolver un archivo binario (exportaciones). Solo rutas /api/v1/exports/ del API configurado.
  ipcMain.handle('sigos:api-binary', async (_event, payload) => {
    const { method, path: reqPath, body, token } = payload || {};
    // Se valida la ruta YA normalizada (evita "/api/v1/exports/../../otra-ruta") y el mismo origen del API.
    let target;
    try { target = new URL(reqPath, API_BASE_URL); } catch { return { ok: false, status: 0, error: 'ruta no permitida' }; }
    if (typeof reqPath !== 'string' || target.origin !== new URL(API_BASE_URL).origin || !target.pathname.startsWith('/api/v1/exports/')) {
      return { ok: false, status: 0, error: 'ruta no permitida' };
    }
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    try {
      const res = await fetch(target, { method: method || 'POST', headers, body: body ? JSON.stringify(body) : undefined });
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) return { ok: res.ok, status: res.status, json: await res.json() };
      const buf = Buffer.from(await res.arrayBuffer());
      return {
        ok: res.ok, status: res.status, data: buf.toString('base64'), contentType: ct, size: buf.length,
        filename: res.headers.get('x-export-filename'), rows: Number(res.headers.get('x-export-rows') || 0), document: res.headers.get('x-export-document'),
      };
    } catch (error) {
      return { ok: false, status: 0, error: String(error) };
    }
  });
  // Preferencias de interfaz (no sensibles): JSON en userData; solo claves conocidas.
  const PREFS_FILE = path.join(app.getPath('userData'), 'sigos-ui-prefs.json');
  // Cada clave conocida valida su tipo: sidebarCollapsed (boolean), theme ('light' | 'dark' | 'system').
  const PREF_VALIDATORS = {
    sidebarCollapsed: (v) => typeof v === 'boolean',
    theme: (v) => v === 'light' || v === 'dark' || v === 'system',
  };
  const readPrefs = () => { try { return JSON.parse(fs.readFileSync(PREFS_FILE, 'utf8')) || {}; } catch { return {}; } };
  ipcMain.handle('sigos:prefs:get', async () => readPrefs());
  ipcMain.handle('sigos:prefs:set', async (_event, patch) => {
    const next = readPrefs();
    Object.entries(patch || {}).forEach(([k, v]) => { if (Object.prototype.hasOwnProperty.call(PREF_VALIDATORS, k) && PREF_VALIDATORS[k](v)) next[k] = v; });
    try { fs.writeFileSync(PREFS_FILE, JSON.stringify(next)); return true; } catch { return false; }
  });
  ipcMain.handle('sigos:save-file', async (_event, payload) => saveFile(payload || {}));
  ipcMain.handle('sigos:open-folder', async (_event, folderPath) => { try { await shell.openPath(require('node:path').dirname(folderPath)); return { ok: true }; } catch (e) { return { ok: false, error: String(e) }; } });
  ipcMain.handle('sigos:export-download', async (_event, payload) => exportDownload(payload || {}));

  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
