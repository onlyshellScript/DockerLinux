// apiConfig.js: resuelve la URL base del API.
// Orden: SIGOS_API_BASE_URL (entorno) > config del usuario (userData/sigos-config.json) > config del sistema
// (/etc/sigos/desktop.json, la escribe el instalador de Linux) > predeterminado.
// Predeterminado: empaquetada -> http://127.0.0.1 (proxy Caddy local en :80); en desarrollo -> http://localhost:5000.
const fs = require('node:fs');
const path = require('node:path');

const SYSTEM_CONFIG = '/etc/sigos/desktop.json';

function validUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const u = new URL(value.trim());
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    return u.origin;
  } catch {
    return null;
  }
}

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return null; }
}

function resolveApiBaseUrl({ env = process.env, userDataDir, isPackaged, systemConfig = SYSTEM_CONFIG } = {}) {
  const fromEnv = validUrl(env.SIGOS_API_BASE_URL);
  if (fromEnv) return { url: fromEnv, source: 'env' };
  if (userDataDir) {
    const user = readJson(path.join(userDataDir, 'sigos-config.json'));
    const u = user && validUrl(user.apiBaseUrl);
    if (u) return { url: u, source: 'user' };
  }
  const sys = readJson(systemConfig);
  const s = sys && validUrl(sys.apiBaseUrl);
  if (s) return { url: s, source: 'system' };
  return { url: isPackaged ? 'http://127.0.0.1' : 'http://localhost:5000', source: 'default' };
}

module.exports = { resolveApiBaseUrl, validUrl, SYSTEM_CONFIG };
