const { app, BrowserWindow, ipcMain, safeStorage, dialog, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { getHealth } = require('./healthClient');

const API_BASE_URL = process.env.SIGOS_API_BASE_URL || 'http://localhost:5000';
const SESSION_FILE = path.join(app.getPath('userData'), 'sigos-session.bin');

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

function writeSession(session) {
  const json = JSON.stringify(session || null);
  const data = safeStorage.isEncryptionAvailable()
    ? safeStorage.encryptString(json)
    : Buffer.from(json, 'utf8');
  fs.writeFileSync(SESSION_FILE, data);
}

function clearSession() {
  try { fs.unlinkSync(SESSION_FILE); } catch {}
}

async function apiRequest({ method, path: reqPath, body, form, token }) {
  const url = new URL(reqPath, API_BASE_URL);
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => { if (v !== undefined && v !== null) fd.append(k, v); });
    payload = fd;
  } else if (body) {
    headers['Content-Type'] = 'application/json';
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

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  win.webContents.on('will-navigate', (event) => event.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.loadFile(path.join(__dirname, '../renderer/index.html'));
}

app.whenReady().then(() => {
  ipcMain.handle('sigos:get-health', async () => getHealth(API_BASE_URL));
  ipcMain.handle('sigos:api-request', async (_event, payload) => apiRequest(payload || {}));
  ipcMain.handle('sigos:session:load', async () => readSession());
  ipcMain.handle('sigos:session:save', async (_event, session) => { writeSession(session); return true; });
  ipcMain.handle('sigos:session:clear', async () => { clearSession(); return true; });
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
