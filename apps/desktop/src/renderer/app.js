// app.js: logica de la vista del cliente de escritorio y comunicacion con Electron.
const state = {

}
// Devuelve el primer elemento del DOM que coincide con el selector CSS dado, buscando desde root. Sin efectos secundarios.
const $ = (sel, root = document) => root.querySelector(sel);
// devuelve safe html; actualiza el DOM.
function safeHtml(el, html) { if (el) el.innerHTML = html; }
// Devuelve la lista de elementos del DOM que coinciden con el selector CSS dado, buscando desde root. Sin efectos secundarios.
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
// devuelve search field; sin efectos secundarios.
function searchField({ placeholder = '', id = '', value = '', upper = false } = {}) {
  return `<label class="search-field"><svg class="search-field__icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z"/><path d="M21 21l-4.35-4.35"/></svg><input type="search" class="search-field__input" id="${escapeHtml(id)}" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(value)}" aria-label="Buscar"${upper ? ' data-upper' : ''}></label>`;
}

// normalizeText(value): normaliza normalize text; sin efectos secundarios.
function normalizeText(value) {
  if (value === null || value === undefined) return '';
  let text = String(value).trim().toLowerCase();
  text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  text = text.replace(/\s+/g, ' ').trim();
  return text;
}
// devuelve escape html; sin efectos secundarios.
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
// devuelve needs review; sin efectos secundarios.
function needsReview(e, pub) {
  if (!e) return false;
  const ws = (pub && pub.work_start) || '07:00';
  const we = (pub && pub.work_end) || '18:00';
  const s = String(e.start || '').slice(11,16);
  const en = String(e.end || '').slice(11,16);
  if (s && s < ws) return true;
  if (en && en > we) return true;
  return false;
}
// devuelve order code; sin efectos secundarios.
function orderCode(o) {
  if (!o) return '';
  if (o.order_code) return o.order_code;
  if (o.code) return o.code;
  const id = o.order_id || o.id;
  return id != null ? 'OS-' + String(id).padStart(4, '0') : '';
}

// api(method, path, body, form, headers, canRetry, opts): petición a la API por IPC.
//   Indicador de carga (SigosLoading): las mutaciones (POST/PUT/PATCH/DELETE) se muestran solas, en el botón que
//   originó la acción o, si no hay botón, como aviso global. opts.loading = false lo omite (consultas en segundo
//   plano); opts.loading = { mode, message, target, block } lo fija. Las cargas de vistas las gestiona trackView().
//   Una respuesta que llega después de un cambio de sesión se descarta: no actualiza la interfaz del usuario nuevo.
async function api(method, path, body = null, form = null, headers = null, canRetry = true, opts = {}) {
  const L = window.SigosLoading;
  const m = String(method || 'GET').toUpperCase();
  const spec = opts.loading === false || !L ? null : (opts.loading || (m !== 'GET' ? {} : null));
  let loadingId = 0;
  if (spec) {
    const btn = spec.mode ? spec.target : (spec.button || L.actionButton());
    loadingId = L.start({
      message: spec.message || L.describe(m, path),
      mode: spec.mode || (btn ? 'button' : 'global'),
      target: spec.mode ? spec.target : btn,
      // Sin botón de origen (p. ej. arrastrar en el calendario) el aviso global no bloquea la aplicación.
      block: spec.block ?? (spec.mode || btn ? undefined : false),
      delay: spec.delay,
    });
  }
  const startEpoch = L ? L.epoch : 0;
  const startSession = state.session;
  try {
    const res = await window.sigos.apiRequest({ method, path, body, form, token: state.session?.access_token, headers });
    if ((L && L.epoch !== startEpoch) || state.session !== startSession) return { ok: false, status: 0, body: null, aborted: true };
    if (res && typeof classifyError === 'function') res.errorInfo = classifyError(res);
    if (res.status !== 401 || !canRetry || !state.session?.refresh_token) return res;
    if (await refreshAccess()) return api(method, path, body, form, headers, false, { loading: false });
    await endSession('expired');
    return res;
  } finally {
    if (loadingId) L.end(loadingId);
  }
}

// ipcTracked(name, payload, loading): llamada IPC de archivos (subida, descarga, exportación) con indicador de carga.
//   loading: { message, mode?, target? }; sin mode se usa el botón que originó la acción o, si no hay, el modo global.
async function ipcTracked(name, payload, loading = {}) {
  const L = window.SigosLoading;
  const btn = loading.mode ? loading.target : L.actionButton();
  return L.run({ message: loading.message, mode: loading.mode || (btn ? 'button' : 'global'), target: btn || loading.target, block: loading.block }, () => window.sigos[name](payload));
}

// loaderBlock(message, height): placeholder de carga (MetaballLoader + mensaje) para un contenedor sin contenido.
function loaderBlock(message, height = 200) {
  return window.SigosLoading ? window.SigosLoading.block(message, { height }) : `<div style="min-height:${height}px"></div>`;
}

// refreshAccess(): renueva el access token con el refresh token de la sesion actual. Devuelve true si lo logro.
async function refreshAccess() {
  if (!state.session?.refresh_token) return false;
  const refreshed = await window.sigos.apiRequest({
    method: 'POST',
    path: '/api/v1/auth/refresh',
    body: { refresh_token: state.session.refresh_token },
  });
  if (!refreshed.ok || !refreshed.body?.access_token) return false;
  state.session.access_token = refreshed.body.access_token;
  if (refreshed.body.user) state.session.user = refreshed.body.user;
  await saveSession();
  return true;
}

// downloadAuthed(path): descarga un archivo de la API (imagen de evidencia o firma) con la sesion actual,
// renovando el token una vez si vencio. Devuelve { ok, status, data (base64), contentType }.
async function downloadAuthed(path) {
  const startEpoch = window.SigosLoading?.epoch;
  let res = await window.sigos.downloadFile({ path, token: state.session?.access_token });
  if (window.SigosLoading && window.SigosLoading.epoch !== startEpoch) return { ok: false, status: 0, aborted: true };
  if (res.status === 401) {
    if (await refreshAccess()) res = await window.sigos.downloadFile({ path, token: state.session?.access_token });
    else { await endSession('expired'); return res; }
  }
  return res;
}

// devuelve notify; actualiza el DOM.
function notify(message, type = 'info') {
  const colors = { error: ['var(--c-danger-bg)', 'var(--c-danger)'], success: ['var(--c-success-bg)', 'var(--c-success)'], info: ['var(--c-neutral-bg)', 'var(--c-text-2)'] };
  const [bg, fg] = colors[type] || colors.info;
  const el = document.createElement('div');
  el.style.cssText = `background:${bg};color:${fg};border-radius:4px;padding:8px 12px;font-size:13px;margin-bottom:8px;`;
  el.textContent = message;
  const container = $('#alerts') || $('#content');
  container.prepend(el);
  setTimeout(() => el.remove(), 4000);
}

// decodeJwtPayload(token): decodifica decode jwt payload; sin efectos secundarios.
function decodeJwtPayload(token) {
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(part));
  } catch { return {}; }
}

// loadSession(): carga load session; comunica con Electron por IPC.
async function loadSession() {
  const s = await window.sigos.loadSession();
  if (s && s.access_token) { state.session = s; return true; }
  return false;
}

// saveSession(): guarda save session; comunica con Electron por IPC.
async function saveSession() {
  if (state.session) await window.sigos.saveSession(state.session);
}

// clearSession(): limpia clear session; comunica con Electron por IPC.
async function clearSession() {
  state.session = null;
  await window.sigos.clearSession();
}

// Claves de localStorage con datos o filtros de un usuario; se borran al cerrar sesion. Las preferencias de
// interfaz del equipo (tema, sidebar) se conservan.
const USER_SCOPED_STORAGE_KEYS = ['sigos.calendar'];

// endSession(reason): cierra la sesion de forma completa ('logout' | 'expired').
//   1) revoca la sesion en el servidor (el token anterior deja de servir aunque alguien lo reutilice);
//   2) borra el archivo de sesion, la cache y el almacenamiento del navegador, y el historial;
//   3) recarga la aplicacion desde cero: no queda estado en memoria, vista, filtros ni datos de la cuenta anterior.
let _endingSession = false;
async function endSession(reason = 'logout') {
  if (_endingSession) return;
  _endingSession = true;
  const s = state.session;
  // Ninguna carga de la sesión que termina sigue activa ni puede actualizar la interfaz siguiente.
  window.SigosLoading?.reset();
  window.SigosLoading?.start({ mode: 'global', message: 'Cerrando sesión…', delay: 0 });
  if (s?.access_token || s?.refresh_token) {
    try {
      await window.sigos.apiRequest({ method: 'POST', path: '/api/v1/auth/logout', token: s.access_token, body: { refresh_token: s.refresh_token } });
    } catch { /* sin red: igual se limpia el equipo; el token vence solo */ }
  }
  USER_SCOPED_STORAGE_KEYS.forEach((k) => { try { localStorage.removeItem(k); } catch { /* sin almacenamiento */ } });
  try { sessionStorage.clear(); } catch { /* sin almacenamiento */ }
  clearTimeout(state.calendarRefreshTimer);
  state.session = null;
  if (window.sigos.endSession) { await window.sigos.endSession({ reason }); return; }
  await window.sigos.clearSession();
  location.replace(location.pathname + '?ended=' + encodeURIComponent(reason));
}

// viewAllowed(view): la vista esta permitida para los roles de la sesion. La navegacion la define NAV_GROUPS;
// esto solo evita mostrar pantallas ajenas al rol (los permisos reales los valida la API en cada peticion).
function viewAllowed(view) {
  const item = NAV.find((it) => it.key === view);
  if (item) return navAllowed(item);
  if (view === 'order-detail') return true;
  return Object.prototype.hasOwnProperty.call(VIEW_META, view);
}

// hasRole(role): verifica has role; sin efectos secundarios.
function hasRole(role) {
  return (state.session?.user?.roles || []).includes(role);
}

const ICON_SVG = {
  dashboard: `<rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />`,
  orders: `<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
    <rect x="9" y="3" width="6" height="4" rx="1" />
    <path d="M9 12h6M9 16h4" />`,
  tech: `<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />`,
  calendar: `<rect x="3" y="4" width="18" height="18" rx="2" />
    <path d="M16 2v4M8 2v4M3 10h18" />`,
  materials: `<path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
    <line x1="12" y1="22.08" x2="12" y2="12" />`,
  evidence: `<rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <polyline points="21 15 16 10 5 21" />`,
  reports: `<line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />`,
  users: `<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
    <circle cx="12" cy="7" r="4" />`,
  bell: `<path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" />`,
  settings: `<circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />`,
  mobile: `<rect x="5" y="2" width="14" height="20" rx="2" />
    <line x1="12" y1="18" x2="12.01" y2="18" />`,
  search: `<circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />`,
  plus: `<line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />`,
  filter: `<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />`,
  eye: `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />`,
  edit: `<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />`,
  logout: `<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />`,
  close: `<circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />`,
  hourglass: `<circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />`,
  schedule: `<circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />`,
  event: `<rect x="3" y="4" width="18" height="18" rx="2" />
    <path d="M16 2v4M8 2v4M3 10h18" />`,
  sync: `<polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />`,
  check_circle: `<polyline points="20 6 9 17 4 12" />`,
  engineering: `<path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />`,
  warning: `<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />`,
  lock: `<rect x="3" y="11" width="18" height="11" rx="2" />
    <path d="M7 11V7a5 5 0 0110 0v4" />`,
  cancel: `<circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />`,
};

// devuelve icon; sin efectos secundarios.
function icon(name, size = 18) {
  const inner = ICON_SVG[name] || '';
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

ICON_SVG.sun = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>';
ICON_SVG.moon = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
ICON_SVG.menu = '<path d="M4 6h16M4 12h16M4 18h16"/>';
ICON_SVG.chevronsLeft = '<path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/>';
ICON_SVG.chevronDown = '<path d="M6 9l6 6 6-6"/>';
ICON_SVG.key = '<circle cx="8" cy="15" r="4"/><path d="M10.8 12.2L20 3M16 7l3 3M14 9l2 2"/>';
ICON_SVG.inbox = '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/>';
ICON_SVG.requests = '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6M9 16h4"/>';

// Navegacion agrupada por categorias. roles=null => cualquier usuario autenticado.
const NAV_GROUPS = [
  { label: 'Operación', items: [
    { key: 'dashboard', label: 'Dashboard', icon: 'dashboard', roles: null },
    { key: 'orders', label: 'Órdenes', icon: 'orders', roles: null },
    { key: 'calendar', label: 'Calendario', icon: 'calendar', roles: null },
    { key: 'technicians', label: 'Técnicos', icon: 'tech', roles: ['admin', 'dispatcher'] },
  ] },
  { label: 'Inventario', items: [
    { key: 'materials', label: 'Materiales', icon: 'materials', roles: ['admin', 'dispatcher'] },
    { key: 'requests', label: 'Solicitudes', icon: 'requests', roles: null },
  ] },
  { label: 'Evidencias', items: [
    { key: 'evidence', label: 'Evidencias', icon: 'evidence', roles: null },
    { key: 'evidence-inbox', label: 'Bandeja de evidencias', icon: 'inbox', roles: ['admin', 'dispatcher'] },
  ] },
  { label: 'Análisis', items: [
    { key: 'reports', label: 'Reportes', icon: 'reports', roles: ['admin', 'dispatcher'] },
  ] },
  { label: 'Sistema', items: [
    { key: 'users', label: 'Usuarios', icon: 'users', roles: ['admin'] },
    { key: 'notifications', label: 'Notificaciones', icon: 'bell', roles: null },
    { key: 'settings', label: 'Configuración', icon: 'settings', roles: ['admin', 'dispatcher'] },
  ] },
];
const NAV = NAV_GROUPS.flatMap((g) => g.items);

// devuelve nav allowed; sin efectos secundarios.
function navAllowed(item) {
  return !item.roles || item.roles.some((r) => hasRole(r));
}

// devuelve status class; sin efectos secundarios.
function statusClass(s) {
  return s === 'in_progress' ? 'inprogress' : (s || '');
}

// Preferencia del sidebar (expandido/minimizado) persistida por equipo; tolera almacenamiento no disponible.
const SIDEBAR_KEY = 'sigos.sidebar.collapsed';
// Fuente principal: archivo de preferencias del proceso principal (state.uiPrefs, cargado en init); respaldo: localStorage.
function sidebarCollapsedPref() {
  if (typeof state.uiPrefs?.sidebarCollapsed === 'boolean') return state.uiPrefs.sidebarCollapsed;
  try { return localStorage.getItem(SIDEBAR_KEY) === '1'; } catch { return false; }
}
function setSidebarCollapsedPref(v) {
  state.uiPrefs = { ...(state.uiPrefs || {}), sidebarCollapsed: v };
  try { window.sigos?.setPrefs?.({ sidebarCollapsed: v }); } catch { /* sin IPC */ }
  try { localStorage.setItem(SIDEBAR_KEY, v ? '1' : '0'); } catch { /* sin persistencia */ }
}
const isMobileLayout = () => window.matchMedia('(max-width: 767px)').matches;

// render(opts): renderiza la vista; actualiza el DOM.
//   opts.transition: tipo de View Transition ('nav' | 'detail'); solo se usa si el shell ya existe.
//   opts.maxWait: ms que la transición espera a que la vista cargue datos antes de capturar el estado nuevo.
// Sin opts (o sin soporte del navegador) renderiza de forma síncrona, como siempre.
function render(opts = {}) {
  const vt = window.sigosVT;
  if (opts.transition && vt && state.session && $('.app-shell')) {
    return vt.run(renderNow, { types: [opts.transition], maxWait: opts.maxWait ?? 220 }).updated;
  }
  return renderNow();
}

function renderNow() {
  const app = $('#app');
  if (!state.view) state.view = 'dashboard';
  if (!state.session) { app.innerHTML = loginTemplate(); bindLogin(); return; }
  if (!viewAllowed(state.view)) { state.view = 'dashboard'; state.selectedOrderId = null; }
  app.innerHTML = shellTemplate();
  bindShell();
  const pending = renderView();
  syncHash();
  const meta = VIEW_META[state.view];
  const announcer = $('#viewAnnouncer');
  if (announcer && meta) setTimeout(() => { announcer.textContent = `Página: ${meta[0]}`; }, 50);
  if (state._focusNav) {
    const target = state._focusNav;
    state._focusNav = null;
    // En movil el drawer se cierra al navegar: el foco va al contenido nuevo.
    if (isMobileLayout()) $('#content')?.focus();
    else $(`.app-sidebar [data-view="${target}"]`)?.focus();
  }
  return pending;
}

// bindOrderCards(root): tarjetas [data-wo] ("Mi día") abren su orden con clic o Enter/Espacio.
function bindOrderCards(root) {
  $$('[data-wo]', root).forEach((c) => {
    c.addEventListener('click', () => openOrderDetail(c.dataset.wo, c));
    c.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openOrderDetail(c.dataset.wo, c); } });
  });
}

// Campos [data-upper] (módulo de materiales): el valor real pasa a MAYÚSCULAS al escribir y al pegar, conservando
// el cursor. No es solo presentación (text-transform): lo enviado ya va normalizado; la API lo normaliza igualmente.
document.addEventListener('input', (e) => {
  const el = e.target;
  if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) || !el.hasAttribute('data-upper') || e.isComposing) return;
  const up = el.value.toLocaleUpperCase('es');
  if (up === el.value) return;
  const start = el.selectionStart;
  const end = el.selectionEnd;
  el.value = up;
  try { el.setSelectionRange(start, end); } catch { /* tipo de campo sin selección */ }
}, true);
document.addEventListener('compositionend', (e) => {
  if (e.target instanceof HTMLElement && e.target.hasAttribute('data-upper')) e.target.dispatchEvent(new Event('input', { bubbles: true }));
}, true);

// Acciones delegadas para HTML generado como texto (la CSP script-src 'self' bloquea los onclick inline):
//   [data-open-order] abre el detalle (cerrando el modal que lo contenga); [data-order-modal] abre la ficha rápida.
document.addEventListener('click', (e) => {
  const t = e.target instanceof Element ? e.target : null;
  const open = t && t.closest('[data-open-order]');
  if (open) {
    e.preventDefault();
    open.closest('.modal-overlay')?.remove();
    openOrderDetail(open.dataset.openOrder);
    return;
  }
  const quick = t && t.closest('[data-order-modal]');
  if (quick) { e.preventDefault(); openOrderModal(Number(quick.dataset.orderModal)); }
});
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const quick = e.target instanceof Element && e.target.closest('[data-order-modal]');
  if (quick) { e.preventDefault(); openOrderModal(Number(quick.dataset.orderModal)); }
});

// canCancelOrders(): administrador o coordinador (la API lo valida en cada petición).
const canCancelOrders = () => hasRole('admin') || hasRole('dispatcher');
const CANCELLABLE_STATUSES = new Set(['pending', 'assigned', 'in_progress']);

// openCancelOrder(orderId, onDone): cancelación lógica con confirmación discreta y motivo opcional.
//   Consulta antes si la orden puede cancelarse y qué registros asociados se conservan; si una regla lo impide,
//   lo explica. Nada se elimina: orden, evidencias, historial, técnico y materiales se conservan.
async function openCancelOrder(orderId, onDone) {
  const chk = await api('GET', `/api/v1/work-orders/${orderId}/cancellation`);
  if (!chk.ok) { if (!chk.aborted) notify(chk.body?.error || 'No se pudo consultar la orden', 'error'); return; }
  const c = chk.body || {};
  const code = c.code_order || orderCode({ id: orderId });
  if (!c.can_cancel) {
    const m = sigosModal({ title: `No se puede cancelar ${code}`, size: 'sm', body: `<p class="cx-text">${escapeHtml(c.blocked_reason || 'La orden no admite cancelación.')}</p>`, footer: '<button type="button" class="sigos-btn-primary" data-modal-close>Entendido</button>' });
    return m;
  }
  const im = c.impacts || {};
  const keep = [];
  if (im.approved_evidences) keep.push(`${im.approved_evidences} evidencia${im.approved_evidences === 1 ? '' : 's'} aprobada${im.approved_evidences === 1 ? '' : 's'}`);
  else if (im.evidences) keep.push(`${im.evidences} evidencia${im.evidences === 1 ? '' : 's'}`);
  if (im.material_consumptions) keep.push(`${im.material_consumptions} consumo${im.material_consumptions === 1 ? '' : 's'} de material registrado${im.material_consumptions === 1 ? '' : 's'}`);
  const m = sigosModal({
    title: `¿Deseas cancelar la orden ${code}?`,
    size: 'sm',
    body: `
      <p class="cx-text">La orden quedará cancelada. No se elimina: se conservan su historial, técnico${keep.length ? ', ' + escapeHtml(keep.join(', ')) : ' y evidencias'}.</p>
      ${im.open_material_requests ? `<div class="ds-alert ds-alert--warning cx-note">Tiene ${im.open_material_requests} solicitud${im.open_material_requests === 1 ? '' : 'es'} de material abierta${im.open_material_requests === 1 ? '' : 's'}; no se cancela${im.open_material_requests === 1 ? '' : 'n'} automáticamente.</div>` : ''}
      <div class="fld" style="margin:12px 0 0"><label for="cxReason">Motivo de cancelación <span class="ev-muted">(opcional)</span></label>
        <textarea id="cxReason" class="sigos-input" rows="3" maxlength="1000" style="width:100%;resize:vertical"></textarea></div>
      <div class="fld-error" id="cxErr" role="alert"></div>`,
    footer: '<button type="button" class="sigos-btn-secondary" data-modal-close>Volver</button><button type="button" class="sigos-btn-danger" id="cxConfirm">Confirmar cancelación</button>',
  });
  m.q('#cxConfirm').addEventListener('click', async () => {
    const reason = m.q('#cxReason').value.trim();
    const res = await api('POST', `/api/v1/work-orders/${orderId}/cancel`, { reason: reason || null }, null, null, true, { loading: { mode: 'button', target: m.q('#cxConfirm'), message: 'Cancelando orden…' } });
    if (res.aborted) return;
    if (!res.ok) { m.q('#cxErr').textContent = res.body?.error || 'No se pudo cancelar la orden'; return; }
    m.close();
    notify(`Orden ${code} cancelada`, 'success');
    if (typeof onDone === 'function') onDone(res.body);
  });
  return m;
}

// openOrderDetail(id, sourceEl): abre el detalle de una orden. Si viene de una fila o tarjeta marcada con
// [data-vt-card], su código, título y estado se transforman en los del encabezado del detalle.
function openOrderDetail(id, sourceEl = null) {
  state.selectedOrderId = Number(id);
  state.view = 'order-detail';
  const card = sourceEl && sourceEl.closest ? sourceEl.closest('[data-vt-card]') : null;
  if (card && window.sigosVT) window.sigosVT.tagShared(card);
  return render({ transition: card ? 'detail' : 'nav', maxWait: 320 });
}

// devuelve login template; comunica con Electron por IPC.
function loginTemplate() {
  return `
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--c-bg);padding:16px">
    <div class="sigos-card" style="width:400px;max-width:100%;padding:32px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:28px">
        <div class="app-sidebar__mark">S</div>
        <div><div style="font:700 19px/1 var(--font-display);color:var(--c-nav)">SIGOS</div><div style="font-size:12px;color:var(--c-text-3);margin-top:3px">Gestión de órdenes de servicio</div></div>
      </div>
      <h2 style="margin-bottom:4px">Iniciar sesión</h2>
      <p style="font-size:13px;color:var(--c-text-3);margin-bottom:20px">Ingrese con su usuario corporativo.</p>
      <div id="alerts"></div>
      <form id="loginForm" novalidate>
        <div class="fld"><label for="username">Usuario</label><input id="username" class="sigos-input" autocomplete="username" autofocus></div>
        <div class="fld"><label for="password">Contraseña</label><input id="password" type="password" class="sigos-input" autocomplete="current-password"></div>
        <button type="submit" id="loginBtn" class="sigos-btn-primary" style="width:100%;height:40px;margin-top:4px">Ingresar</button>
      </form>
    </div>
  </div>`;
}

// bindLogin(): vincula eventos para bind login; realiza peticiones de red.
function bindLogin() {
  const btn = $('#loginBtn');
  $('#loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = $('#username').value.trim();
    const password = $('#password').value;
    if (!username || !password) { notify('Usuario y contraseña requeridos', 'error'); return; }
    const res = await api('POST', '/api/v1/auth/login', { username, password }, null, null, true, { loading: { mode: 'global', message: 'Iniciando sesión…' } });
    if (!res.ok) { notify(res.status === 429 ? 'Demasiados intentos. Espere unos minutos.' : (res.body?.error || 'Credenciales inválidas'), 'error'); return; }
    state.session = res.body;
    await saveSession();
    // La vista inicial se decide para ESTE usuario: nunca se hereda la de una sesion anterior.
    state.view = 'dashboard';
    state.selectedOrderId = null;
    if (state.pendingRoute) {
      const r = hashToView(state.pendingRoute);
      state.view = r.view;
      if (r.orderId) state.selectedOrderId = r.orderId;
      state.pendingRoute = null;
    }
    notify('Sesión iniciada', 'success');
    render();
  });
}

const ROLE_NAMES = { admin: 'Administrador', dispatcher: 'Coordinador', technician: 'Técnico' };

// devuelve shell template; sin efectos secundarios.
function shellTemplate() {
  const user = state.session.user;
  const roles = (user.roles || []).map((r) => ROLE_NAMES[r] || r).join(', ');
  const initials = escapeHtml(user.initials || (user.username || '').slice(0, 2).toUpperCase());
  const collapsed = !isMobileLayout() && sidebarCollapsedPref();
  const activeKey = state.view === 'order-detail' ? 'orders' : state.view;
  const item = (it) => `
    <a href="#" class="sidebar-nav-item${activeKey === it.key ? ' active' : ''}" data-view="${it.key}" data-tip="${escapeHtml(it.label)}" ${activeKey === it.key ? 'aria-current="page"' : ''}>
      ${activeKey === it.key ? '<span class="nav-indicator" aria-hidden="true"></span>' : ''}${icon(it.icon, 18)}<span class="app-sidebar__label">${escapeHtml(it.label)}</span>${it.key === 'materials' ? '<span class="app-sidebar__count" data-menu-badge="materials" style="display:none"></span>' : ''}
    </a>`;
  const groups = NAV_GROUPS.map((g) => {
    const visible = g.items.filter(navAllowed);
    return visible.length ? `<div class="app-sidebar__section" role="presentation">${escapeHtml(g.label)}</div>${visible.map(item).join('')}` : '';
  }).join('');
  return `
  <a class="skip-link" href="#content" id="skipLink">Saltar al contenido</a>
  <div class="sr-only" aria-live="polite" id="viewAnnouncer"></div>
  <div class="app-shell">
    <aside class="app-sidebar${collapsed ? ' is-collapsed' : ''}" id="appSidebar" aria-label="Navegación principal">
      <div class="app-sidebar__brand">
        <div class="app-sidebar__mark" aria-hidden="true">S</div>
        <div class="app-sidebar__brand-text"><div class="app-sidebar__name">SIGOS</div><div class="app-sidebar__sub">Gestión de órdenes</div></div>
      </div>
      <nav class="app-sidebar__nav">${groups}</nav>
      <div class="app-sidebar__foot">
        <button type="button" class="app-sidebar__toggle" id="sidebarToggle" aria-controls="appSidebar" aria-expanded="${!collapsed}" data-tip="Expandir menú">
          ${icon('chevronsLeft', 18)}<span class="app-sidebar__toggle-text">Minimizar menú</span>
        </button>
      </div>
    </aside>
    <div class="app-scrim" id="appScrim" hidden></div>
    <div class="app-main">
      <header class="app-topbar">
        <button type="button" class="icon-btn app-topbar__menu" id="drawerBtn" aria-label="Abrir menú" aria-controls="appSidebar" aria-expanded="false">${icon('menu', 20)}</button>
        <div class="app-topbar__title"><h1 id="viewTitle">SIGOS</h1><div class="app-topbar__sub" id="viewSub"></div></div>
        <div class="app-topbar__search" id="topbarSearch" hidden>${searchField({ placeholder: 'Buscar...', id: 'globalSearch', upper: true })}</div>
        <div id="topbarExport" style="display:flex"></div>
        <div id="topbarActions" style="display:flex;gap:8px;align-items:center"></div>
        <button type="button" class="icon-btn theme-toggle" id="themeBtn" aria-label="${themeLabel()}" data-tip="${themeLabel()}" data-tip-pos="below">${icon('moon', 18).replace('<svg ', '<svg class="ic-moon" aria-hidden="true" ')}${icon('sun', 18).replace('<svg ', '<svg class="ic-sun" aria-hidden="true" ')}</button>
        <a class="icon-btn" href="#" id="bellBtn" aria-label="Notificaciones" data-tip="Notificaciones" data-tip-pos="below">${icon('bell', 18)}<span class="dot-count" id="bellBadge" style="display:none">0</span></a>
        <div class="user-menu">
          <button type="button" class="user-menu__btn" id="userMenuBtn" aria-haspopup="menu" aria-expanded="false" aria-controls="userMenu">
            <span class="user-menu__avatar" aria-hidden="true">${initials}</span>
            <span class="user-menu__name">${escapeHtml(user.username || '')}</span>${icon('chevronDown', 14)}
          </button>
          <div class="user-menu__panel" id="userMenu" role="menu" hidden>
            <div class="user-menu__head"><strong>${escapeHtml(user.username || '')}</strong><span>${escapeHtml(roles)}${user.email ? ' · ' + escapeHtml(user.email) : ''}</span></div>
            ${hasRole('technician') ? `<button type="button" class="user-menu__item" role="menuitem" id="mySigBtn">${icon('edit', 16)} Mi firma</button>` : ''}
            <button type="button" class="user-menu__item" role="menuitem" id="changePwBtn">${icon('key', 16)} Cambiar contraseña</button>
            <button type="button" class="user-menu__item user-menu__item--danger" role="menuitem" id="logoutBtn">${icon('logout', 16)} Cerrar sesión</button>
          </div>
        </div>
      </header>
      <div id="alerts" style="padding:0 24px"></div>
      <main class="app-content content" id="content" aria-busy="false" tabindex="-1"></main>
    </div>
  </div>`;
}

// Tooltip unico para iconos del sidebar minimizado y botones de icono (hover y foco de teclado).
let _tipEl = null;
function showTip(target) {
  const sidebar = $('#appSidebar');
  const inSidebar = sidebar && sidebar.contains(target);
  if (inSidebar && !sidebar.classList.contains('is-collapsed')) return;
  const text = target.id === 'sidebarToggle' ? 'Expandir menú' : target.dataset.tip;
  if (!text) return;
  if (!_tipEl) { _tipEl = document.createElement('div'); _tipEl.className = 'ds-tooltip'; _tipEl.setAttribute('role', 'tooltip'); _tipEl.id = 'dsTooltip'; document.body.appendChild(_tipEl); }
  _tipEl.textContent = text;
  const r = target.getBoundingClientRect();
  _tipEl.style.visibility = 'hidden';
  _tipEl.classList.add('is-visible');
  if (target.dataset.tipPos === 'below') {
    _tipEl.style.left = Math.max(8, Math.min(window.innerWidth - _tipEl.offsetWidth - 8, r.left + r.width / 2 - _tipEl.offsetWidth / 2)) + 'px';
    _tipEl.style.top = (r.bottom + 8) + 'px';
  } else {
    _tipEl.style.left = (r.right + 10) + 'px';
    _tipEl.style.top = (r.top + r.height / 2 - _tipEl.offsetHeight / 2) + 'px';
  }
  _tipEl.style.visibility = '';
  target.setAttribute('aria-describedby', 'dsTooltip');
}
function hideTip(target) {
  if (_tipEl) _tipEl.classList.remove('is-visible');
  if (target) target.removeAttribute('aria-describedby');
}

// bindShell(): navegacion, sidebar colapsable, drawer movil, menu de usuario y tooltips.
function bindShell() {
  const sidebar = $('#appSidebar');
  const scrim = $('#appScrim');
  const drawerBtn = $('#drawerBtn');
  const closeDrawer = () => { sidebar.classList.remove('is-drawer-open'); scrim.hidden = true; drawerBtn.setAttribute('aria-expanded', 'false'); };
  const openDrawer = () => { sidebar.classList.add('is-drawer-open'); scrim.hidden = false; drawerBtn.setAttribute('aria-expanded', 'true'); sidebar.querySelector('.sidebar-nav-item')?.focus(); };

  $$('[data-view]').forEach((b) => b.addEventListener('click', (e) => {
    e.preventDefault(); hideTip();
    // Si se navego con teclado, devolver el foco al mismo item tras reconstruir el shell.
    state._focusNav = b.matches(':focus-visible') || e.detail === 0 ? b.dataset.view : null;
    state.view = b.dataset.view; state.selectedOrderId = null;
    // Volver a un módulo desde el menú abre su listado, no el último detalle consultado.
    if (state.view === 'evidence') state.evidenceWoId = null;
    state.evidenceReturn = null;
    render({ transition: 'nav' });
  }));
  $('#skipLink').addEventListener('click', (e) => { e.preventDefault(); $('#content').focus(); });
  $('#sidebarToggle').addEventListener('click', () => {
    const collapsed = sidebar.classList.toggle('is-collapsed');
    setSidebarCollapsedPref(collapsed);
    $('#sidebarToggle').setAttribute('aria-expanded', String(!collapsed));
    hideTip();
  });
  // Al terminar de animar el ancho, los graficos recalculan su tamaño con el nuevo espacio disponible.
  sidebar.addEventListener('transitionend', (e) => { if (e.target === sidebar && e.propertyName === 'width') window.dispatchEvent(new Event('resize')); });
  drawerBtn.addEventListener('click', openDrawer);
  scrim.addEventListener('click', closeDrawer);
  // Listeners globales: una sola vez (render() reconstruye el shell en cada navegacion).
  if (!window.__sigosShellDocBound) {
    window.__sigosShellDocBound = true;
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const sb = $('#appSidebar');
      if (sb && sb.classList.contains('is-drawer-open')) { sb.classList.remove('is-drawer-open'); $('#appScrim').hidden = true; $('#drawerBtn').setAttribute('aria-expanded', 'false'); $('#drawerBtn').focus(); }
      const um = $('#userMenu');
      if (um && !um.hidden) { um.hidden = true; $('#userMenuBtn').setAttribute('aria-expanded', 'false'); $('#userMenuBtn').focus(); }
    });
    document.addEventListener('click', () => {
      const um = $('#userMenu');
      if (um && !um.hidden) { um.hidden = true; $('#userMenuBtn')?.setAttribute('aria-expanded', 'false'); }
    });
  }

  $$('[data-tip]').forEach((el) => {
    el.addEventListener('mouseenter', () => showTip(el));
    el.addEventListener('mouseleave', () => hideTip(el));
    el.addEventListener('focus', () => showTip(el));
    el.addEventListener('blur', () => hideTip(el));
  });

  const menuBtn = $('#userMenuBtn');
  const menu = $('#userMenu');
  const toggleMenu = (open) => { menu.hidden = !open; menuBtn.setAttribute('aria-expanded', String(open)); if (open) menu.querySelector('.user-menu__item')?.focus(); };
  menuBtn.addEventListener('click', (e) => { e.stopPropagation(); toggleMenu(menu.hidden); });
  menu.addEventListener('click', (e) => e.stopPropagation());
  menu.addEventListener('keydown', (e) => {
    const items = $$('.user-menu__item', menu);
    const i = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
  });
  $('#logoutBtn').addEventListener('click', async (e) => { e.currentTarget.disabled = true; await endSession('logout'); });
  $('#changePwBtn').addEventListener('click', () => { toggleMenu(false); openChangePassword(); });
  $('#mySigBtn')?.addEventListener('click', () => { toggleMenu(false); openMySignature(() => { if (state.view === 'evidence') render(); }); });
  $('#bellBtn').addEventListener('click', (e) => { e.preventDefault(); state.view = 'notifications'; render({ transition: 'nav' }); });
  $('#themeBtn').addEventListener('click', (e) => {
    hideTip(e.currentTarget);
    const vt = window.sigosVT;
    if (!vt) return;
    const next = vt.theme.toggle(e.currentTarget);
    try { window.sigos?.setPrefs?.({ theme: next }); } catch { /* sin IPC: queda en localStorage */ }
  });
}

// Tema: etiqueta del botón (anuncia la acción) y recoloreado de lo que no se pinta con CSS (gráficos).
function themeLabel() {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'Activar tema claro' : 'Activar tema oscuro';
}
window.addEventListener('sigos:themechange', () => {
  const btn = $('#themeBtn');
  if (btn) { btn.setAttribute('aria-label', themeLabel()); btn.dataset.tip = themeLabel(); }
  recolorCharts();
});

// openChangePassword(): cambio de contrasena propio (POST /auth/change-password, ya existente).
function openChangePassword() {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="sigos-card modal-card" role="dialog" aria-modal="true" aria-labelledby="cpTitle" style="width:420px">
      <div class="modal-head"><h3 id="cpTitle">Cambiar contraseña</h3><button type="button" class="icon-btn" data-cp-close aria-label="Cerrar">${icon('close', 18)}</button></div>
      <form class="modal-body" id="cpForm" novalidate>
        <div class="fld"><label for="cpCur">Contraseña actual</label><input id="cpCur" type="password" class="sigos-input" autocomplete="current-password"></div>
        <div class="fld"><label for="cpNew">Nueva contraseña</label><input id="cpNew" type="password" class="sigos-input" autocomplete="new-password"><div class="fld-hint">Mínimo 10 caracteres, con mayúscula, minúscula y número.</div></div>
        <div class="fld"><label for="cpRep">Repetir nueva contraseña</label><input id="cpRep" type="password" class="sigos-input" autocomplete="new-password"></div>
        <div class="fld-error" id="cpErr" role="alert"></div>
      </form>
      <div class="modal-foot"><button type="button" class="sigos-btn-secondary" data-cp-close>Cancelar</button><button type="submit" form="cpForm" class="sigos-btn-primary" id="cpSave">Guardar</button></div>
    </div>`;
  document.body.appendChild(modal);
  const close = () => modal.remove();
  modal.querySelectorAll('[data-cp-close]').forEach((b) => b.addEventListener('click', close));
  modal.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
  modal.querySelector('#cpCur').focus();
  modal.querySelector('#cpForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = modal.querySelector('#cpErr');
    const cur = modal.querySelector('#cpCur').value;
    const nw = modal.querySelector('#cpNew').value;
    if (!cur || !nw) { err.textContent = 'Complete todos los campos'; return; }
    if (nw !== modal.querySelector('#cpRep').value) { err.textContent = 'Las contraseñas nuevas no coinciden'; return; }
    const btn = modal.querySelector('#cpSave');
    btn.disabled = true;
    const res = await api('POST', '/api/v1/auth/change-password', { current_password: cur, new_password: nw });
    btn.disabled = false;
    if (!res.ok) { err.textContent = res.body?.error === 'current password incorrect' ? 'La contraseña actual no es correcta' : (res.body?.error || 'No se pudo cambiar la contraseña'); return; }
    close();
    notify('Contraseña actualizada', 'success');
  });
}


const VIEW_META = {
  dashboard: ['Dashboard', 'Resumen general del sistema'],
  orders: ['Órdenes de servicio', 'Gestión de órdenes'],
  'order-detail': ['Detalle de orden', ''],
  technicians: ['Técnicos', 'Perfiles y disponibilidad'],
  calendar: ['Calendario', 'Visitas programadas'],
  materials: ['Materiales', 'Inventario y stock'],
  requests: ['Solicitudes de materiales', 'Gestion de solicitudes'],
  evidence: ['Evidencias', 'Archivos y observaciones'],
  'evidence-inbox': ['Bandeja de evidencias', 'Revisión y aprobación de expedientes'],
  reports: ['Reportes', 'Indicadores y exportación'],
  users: ['Usuarios', 'Gestión de accesos'],
  notifications: ['Notificaciones', 'Avisos del sistema'],
  settings: ['Configuración', 'Preferencias'],
  mobile: ['Vista Técnico', 'Modo campo'],
};

// Vista -> modulo de exportacion (plantillas del backend). El backend valida el rol en cada endpoint.
const EXPORT_MODULES = {
  dashboard: 'reports', reports: 'reports', orders: 'orders', technicians: 'technicians', materials: 'materials',
  requests: 'requests', evidence: 'evidence', 'evidence-inbox': 'evidence', users: 'users',
};

// renderExportButton(): boton unico "Exportar" en el header para los modulos con plantillas.
function renderExportButton() {
  const box = $('#topbarExport');
  if (!box) return;
  const module = EXPORT_MODULES[state.view];
  const allowed = module && (hasRole('admin') || (hasRole('dispatcher') && module !== 'users'));
  box.innerHTML = allowed ? `<button type="button" class="sigos-btn-secondary" id="exportBtn">${icon('reports', 16)} Exportar</button>` : '';
  $('#exportBtn')?.addEventListener('click', () => {
    let initial = {};
    if (state.view === 'reports' && typeof reportState === 'object') {
      initial = { status: reportState.estado, technician_id: reportState.tecnico_id, zone: reportState.zona, date_from: reportState.desde, date_to: reportState.hasta, date_field: reportState.campo_fecha };
    } else if (state.view === 'users' && state.usersFilters) {
      initial = { role: state.usersFilters.role, status: state.usersFilters.status };
    }
    openExportWizard(module, Object.fromEntries(Object.entries(initial).filter(([, v]) => v)));
  });
}

// renderiza la vista view; actualiza el DOM.
function renderView() {
  const content = $('#content');
  const meta = VIEW_META[state.view] || [state.view, ''];
  $('#viewTitle').textContent = meta[0];
  const longDate = new Date().toLocaleDateString('es-ES', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  $('#viewSub').textContent = longDate.charAt(0).toUpperCase() + longDate.slice(1);
  $('#topbarActions').innerHTML = '';
  // La busqueda del header solo se muestra donde esta conectada (hoy: Materiales).
  const ts = $('#topbarSearch'); if (ts) ts.hidden = state.view !== 'materials';
  renderExportButton();
  if (state.view === 'dashboard') return renderDashboard(content);
  else if (state.view === 'orders') return renderOrders(content);
  else if (state.view === 'order-detail') return renderOrderDetail(content);
  else if (state.view === 'technicians') return renderTechnicians(content);
  else if (state.view === 'calendar') return renderCalendar(content);
  else if (state.view === 'settings') return renderSettings(content);
  else if (state.view === 'materials') return renderMaterials(content);
  else if (state.view === 'requests') return renderRequests(content);
  else if (state.view === 'evidence') return renderEvidence(content);
  else if (state.view === 'evidence-inbox') return renderEvidenceInbox(content);
  else if (state.view === 'users') return renderUsers(content);
  else if (state.view === 'notifications') return renderNotifications(content);
  else if (state.view === 'reports') return renderReports(content);
  else if (state.view === 'mobile') return renderMobile(content);
  else pendingView(content, meta[0]);
}

// renderEvidence(content): módulo de evidencias. Sin orden seleccionada muestra el listado de órdenes con el
// resumen de sus evidencias (sin imágenes); con una orden, sus registros. Las imágenes se piden al abrir cada registro.
async function renderEvidence(content) {
  if (state.evidenceWoId) return renderEvidenceOrder(content, state.evidenceWoId);
  return renderEvidenceList(content);
}

const EV_PAGE_SIZE = 20;

// renderEvidenceList(content): listado paginado de órdenes con búsqueda, filtros y orden por fecha de registro.
async function renderEvidenceList(content) {
  if (!state.evidenceList) state.evidenceList = { q: '', technician_id: '', date_from: '', date_to: '', order: 'desc', page: 1 };
  const f = state.evidenceList;
  const canPickTech = hasRole('admin') || hasRole('dispatcher');
  content.setAttribute('aria-busy', 'true');
  if (!content.querySelector('.ev-orders')) content.innerHTML = loaderBlock('Consultando evidencias…', 320);

  const params = new URLSearchParams({ page: String(f.page || 1), page_size: String(EV_PAGE_SIZE), order: f.order });
  ['q', 'date_from', 'date_to'].forEach((k) => { if (f[k]) params.set(k, f[k]); });
  if (canPickTech && f.technician_id) params.set('technician_id', f.technician_id);
  const [res, profilesRes] = await Promise.all([
    api('GET', '/api/v1/evidences/orders?' + params.toString()),
    canPickTech && !state.evidenceTechs ? api('GET', '/api/v1/technician-profiles') : Promise.resolve(null),
  ]);
  if (!content.isConnected) return;
  content.removeAttribute('aria-busy');
  if (profilesRes) state.evidenceTechs = profilesRes.ok ? (profilesRes.body || []).filter((p) => p.user?.id) : [];
  if (!res.ok) {
    content.innerHTML = `<div class="sigos-card"><div class="empty-state"><div class="empty-state__title">No se pudo cargar el listado de evidencias</div><div class="empty-state__text">${escapeHtml(res.body?.error || 'Revise la conexión con el servidor e inténtelo de nuevo.')}</div><button type="button" class="sigos-btn-secondary" id="evRetry">Reintentar</button></div></div>`;
    $('#evRetry')?.addEventListener('click', () => renderEvidenceList(content));
    return;
  }
  const data = res.body || {};
  const items = data.items || [];
  const total = data.total || 0;
  const pages = Math.max(1, Math.ceil(total / EV_PAGE_SIZE));
  const filtered = !!(f.q || f.technician_id || f.date_from || f.date_to);
  const sortLabel = f.order === 'asc' ? 'más antiguas primero' : 'más recientes primero';

  content.innerHTML = `
    <div class="ev-orders">
      <form class="sigos-card filters ev-filters" id="evFilters" role="search" aria-label="Filtrar evidencias">
        <div class="fld"><label for="evQ">Número de orden</label><input id="evQ" class="sigos-input" placeholder="OS-0012, 12 o cliente" value="${escapeHtml(f.q)}" autocomplete="off"></div>
        ${canPickTech ? `<div class="fld"><label for="evTech">Técnico</label><select id="evTech" class="sigos-select"><option value="">Todos</option>${(state.evidenceTechs || []).map((p) => `<option value="${p.user.id}" ${String(f.technician_id) === String(p.user.id) ? 'selected' : ''}>${escapeHtml(p.user.username || '')}</option>`).join('')}</select></div>` : ''}
        <div class="fld"><label for="evFrom">Registradas desde</label><input id="evFrom" type="date" class="sigos-input" value="${escapeHtml(f.date_from)}"></div>
        <div class="fld"><label for="evTo">Hasta</label><input id="evTo" type="date" class="sigos-input" value="${escapeHtml(f.date_to)}"></div>
        <div class="ev-filters__actions">
          <button type="submit" class="sigos-btn-primary">Buscar</button>
          ${filtered ? '<button type="button" class="sigos-btn-ghost" id="evClear">Limpiar</button>' : ''}
        </div>
      </form>
      <div class="sigos-card ev-table-card">
        <div class="ev-table-head"><span>${total} ${total === 1 ? 'orden' : 'órdenes'}</span><span class="ev-muted">Ordenadas por fecha de registro, ${sortLabel}</span></div>
        ${items.length ? `<div class="ev-table-wrap"><table class="tbl">
          <thead><tr>
            <th scope="col">Orden</th><th scope="col">Descripción</th><th scope="col">Técnico</th>
            <th scope="col" aria-sort="${f.order === 'asc' ? 'ascending' : 'descending'}"><button type="button" class="ev-sort" id="evSort" aria-label="Ordenar por fecha de registro, ahora ${sortLabel}">Último registro ${evIcon('sort', 14)}</button></th>
            <th scope="col" class="ev-num">Evidencias</th><th scope="col">Estado de la orden</th><th scope="col">Validación</th><th scope="col"><span class="sr-only">Acción</span></th>
          </tr></thead>
          <tbody>${items.map((it) => {
            const wo = it.work_order || {};
            const st = typeof statusOf === 'function' ? statusOf(wo.status) : { label: wo.status, badge: '' };
            return `<tr class="tbl-row" data-ev-wo="${wo.id}">
              <td><span class="mono ev-code">${escapeHtml(wo.code || orderCode(wo))}</span></td>
              <td class="ev-desc"><strong>${escapeHtml(wo.title || '—')}</strong>${wo.customer_name ? `<span>${escapeHtml(wo.customer_name)}</span>` : ''}</td>
              <td>${escapeHtml(it.technician?.username || 'Sin asignar')}</td>
              <td class="ev-num">${it.last_evidence_at ? escapeHtml(evFmtDate(it.last_evidence_at)) : '<span class="ev-muted">—</span>'}</td>
              <td class="ev-num">${Number(it.evidence_count || 0)}</td>
              <td><span class="${st.badge}">${escapeHtml(st.label || '—')}</span></td>
              <td>${it.validation_status ? evidenceStatusBadge(it.validation_status) : '<span class="ev-muted">Sin evidencias</span>'}</td>
              <td style="text-align:right"><button type="button" class="sigos-btn-secondary sigos-btn-sm" data-ev-open-wo="${wo.id}">Ver evidencias</button></td>
            </tr>`;
          }).join('')}</tbody></table></div>`
        : `<div class="empty-state"><div class="empty-state__title">${filtered ? 'Ninguna orden coincide con los filtros' : 'No hay órdenes para mostrar'}</div><div class="empty-state__text">${filtered ? 'Revise el número de orden, el técnico o el rango de fechas.' : (hasRole('technician') ? 'Aquí aparecerán las órdenes que tenga asignadas.' : 'Las órdenes aparecerán aquí cuando se creen.')}</div></div>`}
        ${pages > 1 ? `<div class="pager"><span class="ev-muted">Página ${f.page} de ${pages}</span><span style="display:flex;gap:6px"><button type="button" class="sigos-btn-secondary sigos-btn-sm ev-pager" id="evPrev" ${f.page <= 1 ? 'disabled' : ''}>Anterior</button><button type="button" class="sigos-btn-secondary sigos-btn-sm ev-pager" id="evNext" ${f.page >= pages ? 'disabled' : ''}>Siguiente</button></span></div>` : ''}
      </div>
    </div>`;

  const reload = () => renderEvidenceList(content);
  $('#evFilters').addEventListener('submit', (e) => {
    e.preventDefault();
    const from = $('#evFrom').value, to = $('#evTo').value;
    if (from && to && from > to) { notify('La fecha inicial no puede ser posterior a la final', 'error'); return; }
    f.q = $('#evQ').value.trim();
    f.technician_id = $('#evTech')?.value || '';
    f.date_from = from; f.date_to = to; f.page = 1;
    reload();
  });
  $('#evTech')?.addEventListener('change', () => $('#evFilters').requestSubmit());
  $('#evClear')?.addEventListener('click', () => { Object.assign(f, { q: '', technician_id: '', date_from: '', date_to: '', page: 1 }); reload(); });
  $('#evSort')?.addEventListener('click', () => { f.order = f.order === 'asc' ? 'desc' : 'asc'; f.page = 1; reload(); });
  $('#evPrev')?.addEventListener('click', () => { if (f.page > 1) { f.page--; reload(); } });
  $('#evNext')?.addEventListener('click', () => { if (f.page < pages) { f.page++; reload(); } });
  $$('[data-ev-wo]', content).forEach((row) => row.addEventListener('click', () => { state.evidenceWoId = Number(row.dataset.evWo); render(); }));
}

// renderEvidenceOrder(content, woId): evidencias de una orden, según el rol.
//   Técnico: registra evidencias (con su firma), firma o negativa del cliente, checklist, y envía o reenvía a revisión.
//   Administrador / coordinador: verificación. Consulta registros, fotografías y firmas, ve el estado y el historial de
//   revisión y, según su permiso, inicia la revisión, aprueba, solicita corrección o rechaza. Sin acciones de envío.
//   Los permisos reales los valida la API en cada petición.
async function renderEvidenceOrder(content, woId) {
  content.innerHTML = loaderBlock('Cargando evidencias de la orden…', 360);
  const reviewer = hasRole('admin') || hasRole('dispatcher');
  const isAdmin = hasRole('admin');
  const isTech = hasRole('technician') && !reviewer;
  const [woRes, detailRes, sigRes] = await Promise.all([
    api('GET', `/api/v1/work-orders/${woId}`),
    api('GET', `/api/v1/work-orders/${woId}/${reviewer ? 'evidence-detail' : 'evidence-status'}`),
    isTech ? api('GET', '/api/v1/me/signature') : Promise.resolve(null),
  ]);
  if (!content.isConnected || state.evidenceWoId !== woId) return;
  const back = () => { state.evidenceWoId = null; if (state.evidenceReturn) { state.view = state.evidenceReturn; state.evidenceReturn = null; } render(); };
  const backLabel = state.evidenceReturn === 'evidence-inbox' ? 'Bandeja' : 'Evidencias';
  if (!woRes.ok || !detailRes.ok) {
    const msg = woRes.status === 403 || detailRes.status === 403 ? 'No tiene acceso a las evidencias de esta orden.' : woRes.status === 404 ? 'La orden no existe.' : 'No se pudieron cargar las evidencias.';
    content.innerHTML = `<div class="sigos-card"><div class="empty-state"><div class="empty-state__title">${msg}</div><button type="button" class="sigos-btn-secondary" id="evBack">Volver</button></div></div>`;
    $('#evBack').addEventListener('click', back);
    return;
  }
  const wo = woRes.body || {};
  const detail = detailRes.body || {};
  const evidences = detail.evidences || [];
  const signatures = detail.signatures || [];
  const checklist = detail.checklist || [];
  const events = detail.events || [];
  const reviews = detail.reviews || [];
  const status = detail.status || 'DRAFT';
  const st = typeof statusOf === 'function' ? statusOf(wo.status) : { label: wo.status, badge: '' };
  const count = (s) => evidences.filter((e) => e.status === s).length;
  const drafts = count('DRAFT');
  const inReview = evidences.filter((e) => ['SUBMITTED', 'UNDER_REVIEW', 'RESUBMITTED'].includes(e.status)).length;
  const toCorrect = count('CORRECTION_REQUIRED');
  const me = state.session?.user?.id;
  const ownEvidence = evidences.some((e) => e.uploaded_by_id === me);
  const lastApproval = [...reviews].reverse().find((r) => r.decision === 'APPROVED');

  // ---- acciones según rol y estado ----
  let actions = '';
  let reviewNote = '';
  if (isTech) {
    if (toCorrect) actions += '<button type="button" id="evResubmitBtn" class="sigos-btn-primary">Reenviar</button>';
    else if (drafts) actions += `<button type="button" id="evSubmitBtn" class="sigos-btn-primary">${status === 'DRAFT' ? 'Enviar a revisión' : `Enviar ${drafts} nueva${drafts === 1 ? '' : 's'} a revisión`}</button>`;
  } else if (reviewer && evidences.length) {
    const finished = status === 'APPROVED' || status === 'REJECTED';
    if (!finished && ownEvidence) reviewNote = 'Este expediente tiene evidencias registradas por usted: debe revisarlo otro administrador.';
    else if (!finished && toCorrect) reviewNote = 'Esperando las correcciones del técnico.';
    else if (!finished && drafts) reviewNote = `Hay ${drafts} evidencia${drafts === 1 ? '' : 's'} que el técnico todavía no envió a revisión.`;
    else if (!finished && !inReview) reviewNote = 'El técnico aún no ha enviado el expediente a revisión.';
    if (!finished && !ownEvidence) {
      if (isAdmin) {
        if (inReview) actions += '<button type="button" id="evCorrectBtn" class="sigos-btn-secondary">Solicitar corrección</button>';
        if (inReview || toCorrect) actions += '<button type="button" id="evRejectBtn" class="sigos-btn-danger">Rechazar</button>';
        if (inReview && !drafts && !toCorrect) actions += '<button type="button" id="evApproveBtn" class="sigos-btn-primary">Aprobar</button>';
      } else if (count('SUBMITTED') || count('RESUBMITTED')) {
        actions += '<button type="button" id="evStartReviewBtn" class="sigos-btn-primary">Iniciar revisión</button>';
      }
    }
  }

  const reviewsHtml = reviews.length
    ? `<ul class="ev-timeline">${dedupeReviews(reviews).map((r) => `<li><strong>${escapeHtml(EVIDENCE_STATUS[r.decision]?.label || evLabel({}, r.decision))}</strong><small>${escapeHtml(r.reviewer_username || 'Revisor')} · ${escapeHtml(evFmtDate(r.created_at))}</small>${r.notes ? `<span>${escapeHtml(r.notes)}</span>` : ''}</li>`).join('')}</ul>`
    : '<div class="ev-text">Sin revisiones todavía.</div>';
  const eventsHtml = events.length
    ? `<ul class="ev-timeline">${events.slice(-8).reverse().map((e) => `<li><strong>${escapeHtml(evLabel(EVIDENCE_ACTIONS, e.action))}</strong><small>${escapeHtml(evFmtDate(e.created_at))}</small>${e.to_status && e.to_status !== e.from_status && e.from_status ? `<span>${escapeHtml(EVIDENCE_STATUS[e.from_status]?.label || e.from_status)} → ${escapeHtml(EVIDENCE_STATUS[e.to_status]?.label || e.to_status)}</span>` : ''}</li>`).join('')}</ul>`
    : '<div class="ev-text">Sin actividad.</div>';
  const clientSig = signatures.length
    ? signatures.map((s) => (s.refused ? `<span class="badge-cancelled">Negativa</span> ${escapeHtml(s.refusal_reason || '')}` : `<span class="badge-completed">Firma registrada</span> ${escapeHtml(s.signer_name || '')}`)).join('<br>')
    : 'Sin firma del cliente registrada.';

  content.innerHTML = `
    <div class="ev-head">
      <button type="button" id="evBack" class="sigos-btn-ghost">${evIcon('back')} ${backLabel}</button>
      <h2><span class="mono">${escapeHtml(orderCode(wo))}</span> · ${escapeHtml(wo.title || '')}</h2>
      ${evidenceStatusBadge(status)}
      <div class="ev-head__actions">${actions}</div>
    </div>
    ${lastApproval && status === 'APPROVED' ? `<div class="ds-alert ds-alert--success ev-banner">Aprobado por ${escapeHtml(lastApproval.reviewer_username || 'administrador')} el <span class="ev-num">${escapeHtml(evFmtDate(lastApproval.created_at))}</span></div>` : ''}
    ${reviewNote ? `<div class="ds-alert ds-alert--info ev-banner">${escapeHtml(reviewNote)}</div>` : ''}
    ${isTech && status === 'CORRECTION_REQUIRED' ? '<div class="ds-alert ds-alert--warning ev-banner">El revisor solicitó correcciones. Agregue las evidencias necesarias y use «Reenviar».</div>' : ''}
    <div class="ev-layout">
      <div class="sigos-card ev-main">
        <section class="ev-section" aria-labelledby="evRecTitle">
          <h3 id="evRecTitle">Evidencias registradas <span class="ev-muted">${evidences.length}</span></h3>
          ${evidenceRecordsTable(evidences)}
        </section>
        ${isTech ? evidenceUploadSection(sigRes) : ''}
        <section class="ev-section" aria-labelledby="evCliTitle">
          <h3 id="evCliTitle">Firma del cliente</h3>
          <div class="ev-text" style="margin-bottom:8px">${clientSig}</div>
          ${isTech ? `<canvas id="evSigCanvas" width="420" height="140" class="ev-sign" aria-label="Recuadro de firma del cliente"></canvas>
          <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
            <button type="button" id="evSigSaveBtn" class="sigos-btn-primary">Guardar firma del cliente</button>
            <button type="button" id="evSigClearBtn" class="sigos-btn-ghost">Limpiar</button>
            <button type="button" id="evRefuseBtn" class="sigos-btn-secondary" style="margin-left:auto">Registrar negativa</button>
          </div>` : ''}
        </section>
      </div>
      <aside class="ev-side">
        <div class="sigos-card ev-section">
          <h3>Orden</h3>
          <dl class="ev-dl"><dt>Cliente</dt><dd>${escapeHtml(wo.customer_name || '—')}</dd><dt>Técnico</dt><dd>${escapeHtml(wo.assigned_to?.username || 'Sin asignar')}</dd><dt>Estado</dt><dd><span class="${st.badge}">${escapeHtml(st.label || '—')}</span></dd>${wo.description ? `<dt>Descripción</dt><dd>${escapeHtml(wo.description)}</dd>` : ''}</dl>
        </div>
        ${reviewer || reviews.length ? `<div class="sigos-card ev-section"><h3>Historial de revisión</h3>${reviewsHtml}</div>` : ''}
        <div class="sigos-card ev-section">
          <h3>Checklist de la visita</h3>
          <div id="evChecklist">${checklist.length ? `<ul class="ev-list">${checklist.map((i) => `<li><span>${escapeHtml(i.label)}</span><span class="${i.result === 'COMPLETED' ? 'badge-completed' : i.result === 'NOT_COMPLETED' ? 'badge-cancelled' : 'badge-low'}">${i.result === 'COMPLETED' ? 'Hecho' : i.result === 'NOT_COMPLETED' ? 'No realizado' : 'Pendiente'}</span></li>`).join('')}</ul>` : '<div class="ev-text">Sin actividades registradas.</div>'}</div>
          ${isTech ? `<div style="display:flex;gap:8px;margin-top:10px">
            <input id="evCheckLabel" class="sigos-input" placeholder="Nueva actividad realizada" aria-label="Nueva actividad">
            <button type="button" id="evCheckAdd" class="sigos-btn-secondary" style="flex-shrink:0">Agregar</button>
          </div>` : ''}
        </div>
        <div class="sigos-card ev-section">
          <h3>Actividad</h3>
          <div id="evEvents">${eventsHtml}</div>
        </div>
      </aside>
    </div>`;

  const reload = () => renderEvidenceOrder(content, woId);
  $('#evBack').addEventListener('click', back);
  bindEvidenceRecords(content, evidences);

  // ---- revisión (administrador / coordinador) ----
  const review = async (path, body, okMsg) => {
    const r = await api('POST', `/api/v1/work-orders/${woId}/evidences/${path}`, body || {});
    if (r.ok) { notify(okMsg, 'success'); reload(); }
    else if (!r.aborted) notify(r.body?.error || 'No se pudo completar la operación', 'error');
  };
  $('#evStartReviewBtn')?.addEventListener('click', () => review('start-review', {}, 'Revisión iniciada'));
  $('#evApproveBtn')?.addEventListener('click', async () => {
    if (await confirmDialog(`Se aprobarán ${inReview} evidencia${inReview === 1 ? '' : 's'} de ${orderCode(wo)}. Quedará registrado quién aprobó y cuándo.`, { title: '¿Aprobar expediente?', confirmLabel: 'Aprobar', cancelLabel: 'Volver' })) review('approve', {}, 'Expediente aprobado');
  });
  $('#evCorrectBtn')?.addEventListener('click', async () => {
    const notes = await askText('Indique qué debe corregir el técnico.', { title: 'Solicitar corrección', multiline: true, confirmLabel: 'Solicitar' });
    if (notes) review('request-correction', { notes }, 'Corrección solicitada');
  });
  $('#evRejectBtn')?.addEventListener('click', async () => {
    const reason = await askText('Indique el motivo del rechazo.', { title: 'Rechazar expediente', multiline: true, confirmLabel: 'Rechazar' });
    if (reason) review('reject', { reason }, 'Expediente rechazado');
  });
  if (!isTech) return;

  // ---- registro (técnico) ----
  $('#evMySig')?.addEventListener('click', () => openMySignature(() => reload()));
  $('#evUploadForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('#evFile');
    const file = input.files && input.files[0];
    const description = $('#evDesc').value.trim();
    if (!file && !description) { notify('Seleccione un archivo o escriba una descripción', 'error'); return; }
    const btn = $('#evUploadBtn');
    btn.disabled = true;
    const send = async (fileData) => {
      const res = await ipcTracked('uploadFile', {
        method: 'POST',
        path: `/api/v1/work-orders/${woId}/evidences`,
        fields: { category: $('#evCategory').value, description, evidence_type: !fileData ? 'observation' : fileData.type === 'application/pdf' ? 'document' : 'photo' },
        file: fileData,
        token: state.session?.access_token,
      }, { mode: 'button', target: btn, message: fileData ? 'Procesando evidencia…' : 'Registrando observación…' });
      if (res.status === 401 && await refreshAccess()) return send(fileData);
      btn.disabled = false;
      if (res.ok) { notify('Evidencia registrada', 'success'); reload(); return; }
      if (res.status === 401) { await endSession('expired'); return; }
      const code = res.body?.code;
      notify(code === 'technician_signature_required' ? 'Registre su firma antes de adjuntar evidencias.' : (res.body?.error === 'file type not allowed' ? 'Tipo de archivo no permitido. Use una imagen o un PDF.' : res.body?.error === 'file too large' ? 'El archivo supera el tamaño permitido.' : (res.body?.error || 'No se pudo registrar la evidencia')), 'error');
    };
    if (!file) { send(null); return; }
    const reader = new FileReader();
    reader.onload = () => send({ name: file.name, type: file.type, data: String(reader.result).split(',')[1] });
    reader.onerror = () => { btn.disabled = false; notify('No se pudo leer el archivo', 'error'); };
    reader.readAsDataURL(file);
  });

  $('#evRefuseBtn').addEventListener('click', async () => {
    const reason = await askText('Indique por qué el cliente no firma.', { title: 'Registrar negativa de firma', multiline: true, confirmLabel: 'Registrar' });
    if (!reason) return;
    const res = await api('POST', `/api/v1/work-orders/${woId}/signatures`, { refused: true, reason });
    if (res.ok) { notify('Negativa registrada', 'success'); reload(); }
    else notify(res.body?.error || 'No se pudo registrar la negativa', 'error');
  });

  const pad = bindSignaturePad($('#evSigCanvas'));
  $('#evSigClearBtn').addEventListener('click', () => pad.clear());
  $('#evSigSaveBtn').addEventListener('click', async () => {
    if (pad.isEmpty()) { notify('El cliente debe firmar en el recuadro', 'error'); return; }
    const signer = await askText('Nombre de quien firma', { title: 'Firma del cliente', placeholder: 'Nombre completo', confirmLabel: 'Guardar' });
    if (!signer) return;
    const res = await ipcTracked('uploadFile', {
      method: 'POST',
      path: `/api/v1/work-orders/${woId}/signatures`,
      fields: { signer_name: signer, acceptance_text: 'Acepto el trabajo realizado', consent_version: 'v1' },
      file: { name: 'signature.png', type: 'image/png', data: pad.toDataURL().split(',')[1], field: 'file' },
      token: state.session?.access_token,
    }, { message: 'Guardando firma del cliente…' });
    if (res.ok) { notify('Firma del cliente registrada', 'success'); reload(); }
    else notify(res.body?.error || 'No se pudo registrar la firma', 'error');
  });

  $('#evCheckAdd').addEventListener('click', async () => {
    const label = $('#evCheckLabel').value.trim();
    if (!label) return;
    const res = await api('POST', `/api/v1/work-orders/${woId}/checklist`, { label, result: 'COMPLETED' });
    if (res.ok) reload();
    else notify(res.body?.error || 'No se pudo agregar la actividad', 'error');
  });

  $('#evSubmitBtn')?.addEventListener('click', async () => {
    const res = await api('POST', `/api/v1/work-orders/${woId}/evidences/submit`, {});
    if (res.ok) { notify('Evidencias enviadas a revisión', 'success'); reload(); }
    else notify(res.body?.details?.includes('signature_or_refusal_required') ? 'Registre la firma o la negativa del cliente antes de enviar.' : (res.body?.details?.join(', ') || res.body?.error || 'No se pudo enviar el expediente'), 'error');
  });
  $('#evResubmitBtn')?.addEventListener('click', async () => {
    const res = await api('POST', `/api/v1/work-orders/${woId}/evidences/resubmit`, {});
    if (res.ok) { notify('Expediente reenviado', 'success'); reload(); }
    else notify(res.body?.error || 'No se pudo reenviar el expediente', 'error');
  });
}

// dedupeReviews(reviews): una decisión por expediente en el historial (la API guarda una fila por evidencia).
function dedupeReviews(reviews) {
  const seen = new Set();
  return [...reviews].reverse().filter((r) => {
    const key = `${r.decision}|${r.reviewer_id}|${String(r.created_at).slice(0, 19)}|${r.notes || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// evidenceUploadSection(sigRes): formulario del técnico para adjuntar evidencia con su firma registrada.
function evidenceUploadSection(sigRes) {
  const mySig = sigRes && sigRes.ok ? sigRes.body?.signature : null;
  const dis = mySig ? '' : 'disabled';
  return `<section class="ev-section" aria-labelledby="evUpTitle">
    <h3 id="evUpTitle">Adjuntar evidencia</h3>
    ${mySig
      ? `<p class="ev-sign-note">${evIcon('check', 14)} Se adjuntará su firma registrada (versión ${Number(mySig.version)}). <button type="button" class="sigos-btn-ghost sigos-btn-sm" id="evMySig">Ver o cambiar mi firma</button></p>`
      : '<div class="ds-alert ds-alert--warning ev-sign-missing"><span>Registre su firma antes de adjuntar evidencias. Se agregará automáticamente a cada registro.</span><button type="button" class="sigos-btn-primary sigos-btn-sm" id="evMySig">Registrar mi firma</button></div>'}
    <form class="ev-upload" id="evUploadForm">
      <div class="fld"><label for="evCategory">Momento</label>
        <select id="evCategory" class="sigos-select" ${dis}>${Object.entries(EVIDENCE_CATEGORIES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></div>
      <div class="fld ev-upload__grow"><label for="evDesc">Descripción</label><input id="evDesc" class="sigos-input" maxlength="500" placeholder="Qué muestra la evidencia" ${dis}></div>
      <div class="fld ev-upload__grow"><label for="evFile">Archivo (imagen o PDF)</label><input type="file" id="evFile" accept="image/*,application/pdf" class="sigos-input" ${dis}></div>
      <button type="submit" id="evUploadBtn" class="sigos-btn-primary" ${dis}>Adjuntar</button>
    </form>
  </section>`;
}

const CAL_TZ = (state.calendarTz) || 'America/Bogota';
// devuelve cal today str; sin efectos secundarios.
function calTodayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: CAL_TZ });
}
// isoWeekNumber(d): verifica iso week number; sin efectos secundarios.
function isoWeekNumber(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(),0,1));
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}
// devuelve cal start of week; sin efectos secundarios.
function calStartOfWeek(d) {
  const x = new Date(d);
  const day = x.getDay();
  const diff = (day === 0 ? -6 : 1 - day);
  x.setDate(x.getDate() + diff);
  x.setHours(0,0,0,0);
  return x;
}
// devuelve cal add days; sin efectos secundarios.
function calAddDays(d, n) { const x = new Date(d); x.setDate(x.getDate()+n); return x; }
// devuelve cal fmt date; sin efectos secundarios.
function calFmtDate(d, opts) { return d.toLocaleDateString('es-CO', opts); }
// devuelve cal short day; sin efectos secundarios.
function calShortDay(d) { return d.toLocaleDateString('es-CO', { weekday: 'short' }).replace('.',''); }

// renderiza la vista calendar; actualiza el DOM; realiza peticiones de red.
async function renderCalendar(content) {
   if (!state.calendarState) {
     let restored = null;
     try { restored = JSON.parse(localStorage.getItem('sigos.calendar') || 'null'); } catch (e) {}
     // devuelve valid date; sin efectos secundarios.
     const validDate = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v || '');
     if (restored && !validDate(restored.anchor)) restored = null;
     state.calendarState = restored || { view: 'month', anchor: calTodayStr(), selectedDay: calTodayStr(), filters: { technician_id: '', status: '', type: '', priority: '', city_id: '', zone_id: '', include_cancelled: false } };
     state.calendarState.view = 'month';
     if (!state.calendarState.filters) state.calendarState.filters = { technician_id: '', status: '', type: '', priority: '', city_id: '', zone_id: '', include_cancelled: false };
     if (!validDate(state.calendarState.selectedDay)) state.calendarState.selectedDay = state.calendarState.anchor || calTodayStr();
     if (!validDate(state.calendarState.anchor)) state.calendarState.anchor = calTodayStr();
   }
   const cs = state.calendarState;
   cs.view = 'month';
   if (!cs.collapsed) cs.collapsed = { pending: false, detail: false };
  // load tz from settings public
   try {
     const s = await api('GET', '/api/v1/settings/public');
     if (s.body) { state.calendarTz = s.body.timezone || state.calendarTz; state._calPublic = s.body; }
   } catch (e) {}
   const tz = state.calendarTz || CAL_TZ;
   const pub = state._calPublic || {};
   const anchorStr = (cs.view === 'day' && cs.selectedDay) ? cs.selectedDay : cs.anchor;
   let anchor = new Date(anchorStr + 'T00:00:00');
    if (isNaN(anchor.getTime())) { cs.anchor = calTodayStr(); cs.selectedDay = calTodayStr(); anchor = new Date(cs.anchor + 'T00:00:00'); }
  let from, to, days = [];
  if (cs.view === 'day') {
    from = new Date(anchor); from.setHours(0,0,0,0);
    to = calAddDays(from, 1);
    days = [from];
  } else if (cs.view === 'month') {
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const start = calStartOfWeek(first);
    from = start;
    to = calAddDays(start, 42);
    for (let i=0;i<42;i++) days.push(calAddDays(start, i));
  } else {
    const start = calStartOfWeek(anchor);
    from = start;
    to = calAddDays(start, 7);
    for (let i=0;i<7;i++) days.push(calAddDays(start, i));
  }
  const fromIso = from.toISOString();
  const toIso = to.toISOString();
  content.innerHTML = loaderBlock('Cargando agenda…', 320);
  const params = new URLSearchParams();
  params.set('from', fromIso);
  params.set('to', toIso);
  Object.entries(cs.filters).forEach(([k,v]) => { if (v) params.set(k, v); });
  if (cs.filters.include_cancelled) params.set('include_cancelled', 'true');
   let items = [], unassigned = [], error = null, offline = false, eventsErrorDetail = null, unassignedError = null;
   let techOpts = [], cityOpts = [], zoneOpts = [], typeOpts = [];
   try {
    const res = await api('GET', '/api/v1/calendar/events?' + params.toString());
    if (res.ok) items = (res.body && res.body.items) || [];
    else { error = (res.body && (res.body.message || res.body.error)) || 'Error del servidor'; eventsErrorDetail = { status: res.status, code: (res.body && res.body.code) || null, url: '/api/v1/calendar/events', body: res.body, transportError: res.error || null }; console.error('calendar events error', eventsErrorDetail); }
    const ures = await api('GET', '/api/v1/calendar/unassigned?page_size=50');
    if (ures.ok) unassigned = (ures.body && ures.body.items) || [];
    else { unassignedError = (ures.body && (ures.body.message || ures.body.error)) || 'Error del servidor'; console.error('calendar unassigned error', ures); }
    state._calItems = items;
    state._calUnassigned = unassigned;
    if (!error) cs.lastUpdated = Date.now();
    techOpts = []; cityOpts = []; zoneOpts = []; typeOpts = [];
    if (hasRole('dispatcher')) {
      try { const tr = await api('GET', '/api/v1/technicians?page_size=200&active=true'); if (tr.ok) techOpts = (tr.body && tr.body.items) || []; } catch(e) {}
    }
    try { const cr = await api('GET', '/api/v1/catalogs/cities'); if (cr.ok) cityOpts = cr.body || []; } catch(e) {}
    try { const zr = await api('GET', '/api/v1/catalogs/zones'); if (zr.ok) zoneOpts = zr.body || []; } catch(e) {}
    try { const itr = await api('GET', '/api/v1/catalogs/installation-types'); if (itr.ok) typeOpts = itr.body || []; } catch(e) {}
  } catch (e) { offline = true; error = String(e); }
  let label = '';
  if (cs.view === 'day') label = anchor.toLocaleDateString('es-CO', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
  else if (cs.view === 'month') label = anchor.toLocaleDateString('es-CO', { month:'long', year:'numeric' });
  else label = 'Semana ' + isoWeekNumber(anchor) + ' · ' + calFmtDate(days[0], { day:'numeric', month:'short' }) + ' – ' + calFmtDate(days[6], { day:'numeric', month:'short', year:'numeric' });
  const hasEventsError = !!error;
  const programmed = hasEventsError ? '—' : items.length;
  const unassignedCount = hasEventsError ? '—' : unassigned.length;
  const inProgress = hasEventsError ? '—' : items.filter(e => e.status === 'in_progress').length;
  const byDay = {};
  items.forEach(e => { const d = e.start.slice(0,10); (byDay[d]=byDay[d]||[]).push(e); });
  const todayStr = calTodayStr();
  let html = '';
  // topbar actions area handled by view title; add period nav
   const canSchedule = hasRole('dispatcher');
   html += '<div class="cal-root" style="display:flex;flex-direction:column;height:100%;min-height:0;gap:8px;overflow:hidden">';
   const lu = cs.lastUpdated ? new Date(cs.lastUpdated).toLocaleTimeString('es-CO') : '';
   html += '<div class="cal-toolbar" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">';
   html += '<button type="button" class="sigos-btn-secondary" style="width:36px;height:36px;padding:0;display:inline-flex;align-items:center;justify-content:center" id="calPrev" aria-label="Anterior"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg></button>';
   html += '<button type="button" class="sigos-btn-secondary" style="height:36px" id="calToday">Hoy</button>';
   html += '<button type="button" class="sigos-btn-secondary" style="width:36px;height:36px;padding:0;display:inline-flex;align-items:center;justify-content:center" id="calNext" aria-label="Siguiente"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></button>';
   html += '<span style="font-family:Outfit;font-weight:600;font-size:16px;color:var(--c-nav);margin-left:8px">' + escapeHtml(label) + '</span>';
   // view selector removed: only month view
   html += '<span style="margin-left:auto;font-size:11px;color:var(--c-text-3)">Actualizado ' + escapeHtml(lu) + '</span>';
   html += '<button type="button" class="sigos-btn-secondary" style="width:32px;height:32px;padding:0;display:inline-flex;align-items:center;justify-content:center" id="calRefresh" title="Refrescar" aria-label="Refrescar"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>';
   html += '<button type="button" class="sigos-btn-primary" ' + (canSchedule?'':'disabled title="Sin permisos"') + ' style="height:36px" id="calSchedule">+ Programar visita</button>';
   html += '<button type="button" class="sigos-btn-secondary" style="height:36px" id="calPendingBtn">Pendientes (' + unassigned.length + ')</button>';
   html += '</div>';
   // row 2: chips + filters
   const hasActiveFilters = !!(cs.filters.technician_id || cs.filters.status || cs.filters.type || cs.filters.priority || cs.filters.city_id || cs.filters.zone_id || cs.filters.include_cancelled);
   const activeFilterCount = [cs.filters.technician_id, cs.filters.status, cs.filters.type, cs.filters.priority, cs.filters.city_id, cs.filters.zone_id, cs.filters.include_cancelled].filter(Boolean).length;
   html += '<div class="cal-toolbar" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">';
   html += '<span class="cal-chip" style="display:inline-flex;align-items:center;gap:6px;padding:2px 8px;border:1px solid var(--c-border);border-radius:999px;font-size:12px;height:28px;cursor:pointer" id="chipProg">Programadas <span style="font-family:Outfit;font-weight:800;font-size:15px;color:var(--c-ev-done)">' + programmed + '</span></span>';
   html += '<span class="cal-chip" style="display:inline-flex;align-items:center;gap:6px;padding:2px 8px;border:1px solid var(--c-border);border-radius:999px;font-size:12px;height:28px;cursor:pointer" id="chipUnas">Sin asignar <span style="font-family:Outfit;font-weight:800;font-size:15px;color:var(--c-warning)">' + unassignedCount + '</span></span>';
   html += '<span class="cal-chip" style="display:inline-flex;align-items:center;gap:6px;padding:2px 8px;border:1px solid var(--c-border);border-radius:999px;font-size:12px;height:28px;cursor:pointer" id="chipProg2">En ejecución <span style="font-family:Outfit;font-weight:800;font-size:15px;color:var(--c-ev-done)">' + inProgress + '</span></span>';
   const techOptions = techOpts.map(t => '<option value="' + (t.user_id||t.id) + '"' + (String(cs.filters.technician_id)===String(t.user_id||t.id)?' selected':'') + '>' + escapeHtml(t.full_name||t.username||('Técnico '+(t.user_id||t.id))) + '</option>').join('');
   const statusOpts = ['pending','assigned','in_progress','completed','cancelled'].map(s => '<option value="' + s + '"' + (cs.filters.status===s?' selected':'') + '>' + escapeHtml((typeof statusOf==='function'?statusOf(s).label:s)) + '</option>').join('');
   html += '<select class="sigos-input" id="calFiltTech" aria-label="Filtrar calendario por técnico"><option value="">Todos los técnicos</option>' + techOptions + '</select>';
   html += '<select class="sigos-input" id="calFiltStatus" aria-label="Filtrar calendario por estado"><option value="">Todos los estados</option>' + statusOpts + '</select>';
   html += '<button type="button" class="sigos-btn-secondary" style="height:36px" id="calFiltersBtn">Filtros' + (activeFilterCount ? ' ' + activeFilterCount : '') + '</button>';
   if (hasActiveFilters) html += '<button type="button" class="sigos-btn-secondary" style="height:36px;font-size:12px" id="calClear">Limpiar</button>';
   if (!error) html += '<span style="font-size:11px;color:var(--c-text-3);margin-left:auto">' + items.length + ' resultado' + (items.length===1?'':'s') + '</span>';
   html += '</div>';
   if (cs.filtersPopoverOpen) {
     html += '<div id="calFiltersPopover" style="position:fixed;top:120px;left:50%;transform:translateX(-50%);background:var(--c-surface);border:1px solid var(--c-border);border-radius:6px;box-shadow:0 8px 24px rgba(0,0,0,.15);padding:12px;z-index:9999;min-width:280px">';
     const typeOptions = typeOpts.map(t => '<option value="' + escapeHtml(t.code) + '"' + (cs.filters.type===t.code?' selected':'') + '>' + escapeHtml(t.label) + '</option>').join('');
     const prioOptions = ['low','medium','high','urgent'].map(p => '<option value="' + p + '"' + (cs.filters.priority===p?' selected':'') + '>' + escapeHtml((typeof priorityOf==='function'?priorityOf(p).label:p)) + '</option>').join('');
     const cityOptions = cityOpts.map(c => '<option value="' + c.id + '"' + (String(cs.filters.city_id)===String(c.id)?' selected':'') + '>' + escapeHtml(c.name||c.label) + '</option>').join('');
     const zoneOptions = zoneOpts.map(z => '<option value="' + z.id + '"' + (String(cs.filters.zone_id)===String(z.id)?' selected':'') + '>' + escapeHtml(z.name) + '</option>').join('');
     html += '<div style="display:grid;gap:8px">';
     html += '<label style="font-size:12px">Tipo <select class="sigos-input" id="popType"><option value="">Todos</option>' + typeOptions + '</select></label>';
     html += '<label style="font-size:12px">Prioridad <select class="sigos-input" id="popPrio"><option value="">Todas</option>' + prioOptions + '</select></label>';
     html += '<label style="font-size:12px">Ciudad <select class="sigos-input" id="popCity"><option value="">Todas</option>' + cityOptions + '</select></label>';
     html += '<label style="font-size:12px">Zona <select class="sigos-input" id="popZone"><option value="">Todas</option>' + zoneOptions + '</select></label>';
     html += '<label style="font-size:12px;display:flex;align-items:center;gap:6px"><input type="checkbox" id="popCancel" ' + (cs.filters.include_cancelled?'checked':'') + '> Incluir canceladas</label>';
     html += '<div style="display:flex;gap:8px;justify-content:flex-end"><button type="button" class="sigos-btn-secondary" style="height:32px" id="popReset">Restablecer</button><button type="button" class="sigos-btn-primary" style="height:32px" id="popApply">Aplicar</button></div>';
     html += '</div></div>';
   }
  if (offline) {
    html += '<div style="background:var(--c-danger-bg);color:var(--c-danger);padding:8px;border-radius:6px;font-size:12px">Sin conexión · datos de las ' + new Date().toLocaleTimeString('es-CO') + '</div>';
  } else if (error) {
    const d = eventsErrorDetail || {};
    html += '<div class="sigos-card" style="margin:12px"><div class="empty-state"><div class="empty-state__title">No se pudo cargar la agenda</div><div class="empty-state__text">' + escapeHtml(error) + '</div><button type="button" class="sigos-btn-secondary" id="calRetry">Reintentar</button><details style="margin-top:8px;font-size:11px;color:var(--c-text-3)"><summary>Detalle técnico</summary><div>status: ' + escapeHtml(d.status||'') + '</div><div>code: ' + escapeHtml(d.code||'') + '</div><div>url: ' + escapeHtml(d.url||'') + '</div><div>request_id: ' + escapeHtml((d.body && d.body.request_id)||'') + '</div></details></div></div>';
  } else if (!error && !items.length && !unassigned.length) {
    html += '<div class="sigos-card"><div class="empty-state"><div class="empty-state__title">Sin visitas programadas</div><div class="empty-state__text">No hay visitas en este rango. Programa una nueva desde Órdenes.</div><button type="button" class="sigos-btn-secondary" id="calGoOrders">Ir a Órdenes</button></div></div>';
  }
   // main layout: full width grid
   html += '<div style="flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr);gap:16px">';
   html += '<div class="cal-grid-scroll" style="min-height:0;overflow:auto;border:1px solid var(--c-border);border-radius:8px;background:var(--c-surface)">';
  if (cs.view === 'month') {
    html += '<div style="display:grid;grid-template-columns:repeat(7,1fr)">';
    ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'].forEach(d => { html += '<div style="padding:6px;font-size:11px;font-weight:600;color:var(--c-text-3);border-bottom:1px solid var(--c-border);text-align:center">' + d + '</div>'; });
     days.forEach(d => {
       const key = d.toISOString().slice(0,10);
       const evs = byDay[key] || [];
       const isToday = key === todayStr;
       html += '<div style="min-height:70px;border:1px solid var(--c-border);padding:4px;cursor:pointer" data-day="' + key + '">';
       html += '<div style="font-size:11px;font-weight:600;' + (isToday?'color:#fff;background:#2A5C45;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center':'color:var(--c-text-2)') + '">' + d.getDate() + '</div>';
       if (evs.length) {
         html += '<div style="margin-top:2px;display:flex;flex-direction:column;gap:2px">';
         evs.slice(0,2).forEach(e => {
           const color = e.status==='in_progress'?'var(--c-ev-progress)':e.status==='completed'?'var(--c-ev-done)':e.schedule_status==='unassigned'?'var(--c-ev-progress)':'var(--c-ev-idle)';
           html += '<div class="cal-month-badge" data-order-id="' + e.order_id + '" style="font-size:9px;padding:1px 3px;border-radius:3px;background:color-mix(in srgb, ' + color + ' 14%, transparent);color:' + color + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer">' + escapeHtml(orderCode(e)) + ' ' + escapeHtml((e.title||'').slice(0,12)) + '</div>';
         });
         if (evs.length > 2) html += '<div style="font-size:9px;color:var(--c-text-3)">+' + (evs.length-2) + '</div>';
         html += '</div>';
       }
       html += '</div>';
     });
     html += '</div>';
   } else {
    const viewDays = cs.view === 'day' ? 1 : 7;
    const gDays = days.slice(0, viewDays);
    html += '<div style="display:grid;grid-template-columns:60px repeat(' + viewDays + ',1fr);position:relative">';
    html += '<div style="position:sticky;top:0;background:var(--c-surface);z-index:2;border-bottom:1px solid var(--c-border)"></div>';
    gDays.forEach(d => {
      const key = d.toISOString().slice(0,10);
       const isToday = key === todayStr;
       const isSelected = key === cs.selectedDay;
       const isWeekend = d.getDay()===0 || d.getDay()===6;
       let bg = isSelected ? 'var(--c-cal-selected)' : isToday ? 'var(--c-cal-today)' : (isWeekend ? 'var(--c-cal-muted)' : 'var(--c-surface)');
       const border = isSelected ? 'border-bottom:2px solid var(--c-primary);' : 'border-bottom:1px solid var(--c-border);';
       html += '<div data-day="' + key + '" style="position:sticky;top:0;background:' + bg + ';z-index:2;' + border + 'padding:6px;text-align:center;font-size:12px;font-weight:600;color:' + (isSelected?'var(--c-primary)':isToday?'var(--c-ev-done)':'var(--c-text-2)') + ';cursor:pointer">' + calShortDay(d) + ' ' + d.getDate() + (isToday?' <span style="background:#2A5C45;color:#fff;border-radius:50%;padding:1px 5px;font-size:10px">HOY</span>':'') + '</div>';
    });
     const startHour = parseInt((pub.work_start || '07:00').split(':')[0], 10);
     const endHour = parseInt((pub.work_end || '18:00').split(':')[0], 10);
     for (let h=7; h<=17; h++) {
       const out = (h < startHour || h >= endHour);
       const rowBg = out ? 'background:var(--c-cal-muted);' : '';
       html += '<div style="border-top:1px solid var(--c-border);padding:2px 4px;font-size:10px;color:var(--c-text-3);font-family:JetBrains Mono,monospace;' + rowBg + '">' + String(h).padStart(2,'0') + ':00</div>';
       for (let di=0; di<viewDays; di++) {
         const dkey = gDays[di].toISOString().slice(0,10);
         const weekend = gDays[di].getDay() === 0 || gDays[di].getDay() === 6;
         const dayBg = weekend ? 'background:var(--c-cal-weekend);' : (out ? 'background:var(--c-cal-muted);' : '');
         html += '<div data-slot-date="' + dkey + '" data-slot-hour="' + h + '" style="border-left:1px solid var(--c-border);border-top:1px solid var(--c-border);position:relative;min-height:48px;cursor:pointer;' + dayBg + '"></div>';
       }
     }
    html += '</div>';
    // overlay events positioned absolutely
    // We'll render events in a separate layer per day using top offsets
    html += '<div style="position:relative;margin-top:-' + (11*48+24) + 'px;padding-left:60px;display:grid;grid-template-columns:repeat(' + viewDays + ',1fr);gap:0;pointer-events:none">';
    gDays.forEach((d, di) => {
      const key = d.toISOString().slice(0,10);
      const evs = byDay[key] || [];
      const cols = layoutOverlaps(evs);
      html += '<div style="position:relative;height:' + (11*48) + 'px">';
      cols.forEach(col => {
        col.forEach(e => {
          const s = new Date(e.start); const en = new Date(e.end);
          const startMin = (s.getHours()-7)*60 + s.getMinutes();
          const durMin = Math.max(20, (en - s)/60000);
          const top = (startMin/60)*48;
          const height = (durMin/60)*48;
          const width = (100/cols.length) + '%';
          const left = (col.index/cols.length*100) + '%';
           const color = e.status==='in_progress'?'var(--c-ev-progress)':e.status==='completed'?'var(--c-ev-done)':'var(--c-ev-idle)';
           const dash = e.schedule_status === 'unassigned' ? 'border-style:dashed' : '';
           const selected = cs.selectedEventId === e.order_id;
           const highlighted = cs.highlightId === e.order_id;
           const selStyle = highlighted ? 'border:2px solid var(--c-primary);box-shadow:0 0 0 4px var(--c-primary-ring);background:var(--c-cal-selected);' : selected ? 'border:2px solid var(--c-primary);box-shadow:0 4px 12px rgba(46,122,80,.25);' : ('border:1px solid ' + color + ';');
           html += '<div class="cal-event" data-event-id="' + e.order_id + '" tabindex="0" title="' + escapeHtml(orderCode(e) + ' ' + e.title) + '" style="position:absolute;top:' + top + 'px;left:' + left + ';width:' + width + ';height:' + height + 'px;background:var(--c-primary-soft);' + selStyle + dash + ';border-radius:4px;padding:2px 4px;font-size:11px;overflow:hidden;pointer-events:auto;cursor:pointer">';
           const review = needsReview(e, pub);
           html += '<div style="font-family:JetBrains Mono,monospace;font-size:10px">' + escapeHtml(orderCode(e)) + (review ? ' <span class="cal-review" title="Fuera del horario laboral: revisar" aria-label="Fuera del horario laboral">' + icon('warning', 11) + '</span>' : '') + '</div>';
           html += '<div style="font-weight:600;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">' + escapeHtml(e.title) + '</div>';
           html += '<div style="color:var(--c-text-3)">' + escapeHtml((e.technicians||[]).map(t=>t.name).join(', ') || 'Por asignar') + '</div>';
           html += '<div class="cal-resize-handle" data-event-id="' + e.order_id + '" style="position:absolute;bottom:0;left:0;right:0;height:6px;cursor:ns-resize"></div>';
           html += '</div>';
        });
       });
       if (key === todayStr) {
         const now = new Date();
         const mins = (now.getHours()-7)*60 + now.getMinutes();
         const top = (mins/60)*48;
         html += '<div style="position:absolute;left:0;right:0;top:' + top + 'px;height:2px;background:var(--c-danger);z-index:5;pointer-events:none"></div>';
       }
       html += '</div>';
     });
     html += '</div>';
   }
  html += '</div>';
   const selDay = cs.selectedDay;
   html += '<div class="sigos-card" style="padding:10px;flex:1;overflow:auto"><div style="font-family:Outfit;font-weight:600;font-size:13px;color:var(--c-nav);margin-bottom:6px">Órdenes del día seleccionado</div>';
   const selEvs = byDay[selDay] || [];
   if (!selEvs.length) html += '<div style="font-size:12px;color:var(--c-text-3)">Selecciona un día para ver sus visitas.</div>';
   selEvs.forEach(e => {
     html += '<div style="padding:8px;border:1px solid var(--c-border);border-radius:6px;margin-bottom:6px">';
     html += '<div style="font-family:JetBrains Mono,monospace;font-size:11px">' + escapeHtml(orderCode(e)) + '</div>';
     html += '<div style="font-weight:600;font-size:12px">' + escapeHtml(e.title) + '</div>';
     const parts = [e.city, e.zone].filter(Boolean);
     html += '<div style="font-size:11px;color:var(--c-text-3)">' + escapeHtml(parts.join(' · ') || '—') + '</div>';
     html += '<div style="font-size:11px;color:var(--c-text-3)">' + escapeHtml(e.start.slice(11,16)) + '–' + escapeHtml(e.end.slice(11,16)) + ' · ' + escapeHtml((e.technicians||[]).map(t=>t.name).join(', ')||'Por asignar') + '</div>';
     html += '<div style="display:flex;gap:4px;margin-top:6px"><button type="button" class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" data-open-order="\' + e.order_id + \'">Abrir orden</button></div>';
     html += '</div>';
   });
   html += '</div>';
  html += '</div>';
  html += '</div>';
   content.innerHTML = html;
  const prev = document.getElementById('calPrev');
  const next = document.getElementById('calNext');
  const todayBtn = document.getElementById('calToday');
   if (prev) prev.addEventListener('click', () => { const n = calAddDays(anchor, cs.view==='month'?-30:cs.view==='day'?-1:-7).toISOString().slice(0,10); cs.anchor = n; if (cs.view === 'day') cs.selectedDay = n; if (cs.view === 'month') cs.expanded = false; render(); });
   if (next) next.addEventListener('click', () => { const n = calAddDays(anchor, cs.view==='month'?30:cs.view==='day'?1:7).toISOString().slice(0,10); cs.anchor = n; if (cs.view === 'day') cs.selectedDay = n; if (cs.view === 'month') cs.expanded = false; render(); });
   if (todayBtn) todayBtn.addEventListener('click', () => { cs.view = 'month'; cs.anchor = calTodayStr(); cs.selectedDay = calTodayStr(); render(); });
  document.querySelectorAll('[data-calview]').forEach(b => b.addEventListener('click', () => { cs.view = b.dataset.calview; render(); }));
   content.querySelectorAll('.cal-event').forEach(el => {
     const eid = Number(el.dataset.eventId);
     el.addEventListener('click', (ev) => { ev.stopPropagation(); cs.selectedEventId = eid; render(); });
     el.addEventListener('dblclick', (ev) => { ev.stopPropagation(); cs.selectedEventId = eid; state.selectedOrderId = eid; state.view = 'order-detail'; render(); });
     el.addEventListener('contextmenu', (ev) => { ev.preventDefault(); ev.stopPropagation(); cs.selectedEventId = eid; showContextMenu(ev.clientX, ev.clientY, eid); });
     el.addEventListener('keydown', (ev) => {
       if (ev.key === 'Enter') { ev.preventDefault(); state.selectedOrderId = eid; state.view = 'order-detail'; render(); }
       if (ev.key === 'm' || ev.key === 'M') { ev.preventDefault(); openScheduleModal({ orderId: eid }); }
     });
   });
   content.querySelectorAll('.cal-event').forEach(el => {
     el.addEventListener('pointerdown', (ev) => { if (ev.button !== 0) return; beginDragEvent(ev, Number(el.dataset.eventId)); });
   });
   content.querySelectorAll('.cal-resize-handle').forEach(el => {
     el.addEventListener('pointerdown', (ev) => { ev.stopPropagation(); if (ev.button !== 0) return; beginResize(ev, Number(el.dataset.eventId)); });
   });
   content.querySelectorAll('.cal-tray-item').forEach(el => {
     el.addEventListener('pointerdown', (ev) => { if (ev.button !== 0) return; beginDragTray(ev, Number(el.dataset.orderId)); });
   });
   // day header selection already via data-day
   content.querySelectorAll('[data-cal-action]').forEach(btn => {
     btn.addEventListener('click', async (ev) => {
       ev.stopPropagation();
       const action = btn.dataset.calAction;
       const next = btn.dataset.next;
       const eid = cs.selectedEventId;
       if (!eid) return;
       if (action === 'open') { state.selectedOrderId = eid; state.view = 'order-detail'; render(); return; }
       if (action === 'schedule') { notify('Programación disponible en la Fase 2.', 'info'); return; }
       if (action === 'assign') { notify('Asignación disponible en la Fase 2.', 'info'); return; }
       if (action === 'history') { openHistoryDrawer(eid); return; }
       if (action === 'transition') {
         let reason = null;
         if (next === 'cancelled') {
           reason = window.prompt('Motivo de cancelación (obligatorio):');
           if (!reason) { notify('Motivo obligatorio.', 'error'); return; }
         }
         const actionName = next === 'assigned' ? 'assign' : next === 'in_progress' ? 'start' : next === 'completed' ? 'complete' : next === 'cancelled' ? 'cancel' : next;
         const res = await api('POST', '/api/v1/work-orders/' + eid + '/transitions', { action: actionName, reason });
         if (res.ok) { notify('Estado actualizado.', 'success'); cs.selectedEventId = eid; render(); }
         else { notify((res.body && (res.body.message || res.body.error)) || 'Error', 'error'); }
       }
     });
   });
   // bindFilter(id, key): vincula eventos para bind filter; actualiza el DOM.
   const bindFilter = (id, key) => {
     const el = document.getElementById(id);
     if (el) el.addEventListener('change', () => { cs.filters[key] = el.value; render(); });
   };
   bindFilter('calFiltTech', 'technician_id');
   bindFilter('calFiltStatus', 'status');
   bindFilter('calFiltType', 'type');
   bindFilter('calFiltPrio', 'priority');
   bindFilter('calFiltCity', 'city_id');
   bindFilter('calFiltZone', 'zone_id');
   const cancelCb = document.getElementById('calFiltCancel');
   if (cancelCb) cancelCb.addEventListener('change', () => { cs.filters.include_cancelled = cancelCb.checked; render(); });
   const clear = document.getElementById('calClear');
   if (clear) clear.addEventListener('click', () => { cs.filters = { technician_id: '', status: '', type: '', priority: '', city_id: '', zone_id: '', include_cancelled: false }; render(); });
   const refreshBtn = document.getElementById('calRefresh');
   if (refreshBtn) refreshBtn.addEventListener('click', () => render());
   const pendingBtn = document.getElementById('calPendingBtn');
   if (pendingBtn) pendingBtn.addEventListener('click', () => openPendingModal());
   const filtersBtn = document.getElementById('calFiltersBtn');
   if (filtersBtn) filtersBtn.addEventListener('click', () => { cs.filtersPopoverOpen = !cs.filtersPopoverOpen; render(); });
   const popApply = document.getElementById('popApply');
   if (popApply) popApply.addEventListener('click', () => {
     cs.filters.type = document.getElementById('popType').value;
     cs.filters.priority = document.getElementById('popPrio').value;
     cs.filters.city_id = document.getElementById('popCity').value;
     cs.filters.zone_id = document.getElementById('popZone').value;
     cs.filters.include_cancelled = document.getElementById('popCancel').checked;
     cs.filtersPopoverOpen = false;
     render();
   });
   const popReset = document.getElementById('popReset');
   if (popReset) popReset.addEventListener('click', () => {
     cs.filters.type = ''; cs.filters.priority = ''; cs.filters.city_id = ''; cs.filters.zone_id = ''; cs.filters.include_cancelled = false;
     cs.filtersPopoverOpen = false;
     render();
   });
   const chipProg = document.getElementById('chipProg');
   if (chipProg) chipProg.addEventListener('click', () => { cs.filters.status = (cs.filters.status === 'assigned' ? '' : 'assigned'); render(); });
   const chipUnas = document.getElementById('chipUnas');
   if (chipUnas) chipUnas.addEventListener('click', () => { cs.filters.status = (cs.filters.status === 'pending' ? '' : 'pending'); render(); });
   const chipProg2 = document.getElementById('chipProg2');
   if (chipProg2) chipProg2.addEventListener('click', () => { cs.filters.status = (cs.filters.status === 'in_progress' ? '' : 'in_progress'); render(); });
  const retry = document.getElementById('calRetry');
  if (retry) retry.addEventListener('click', () => render());
   document.querySelectorAll('[data-day]').forEach(el => el.addEventListener('click', () => { openDayModal(el.dataset.day); }));
   document.querySelectorAll('.cal-month-badge').forEach(el => el.addEventListener('click', (ev) => { ev.stopPropagation(); openOrderModal(Number(el.dataset.orderId)); }));
   document.querySelectorAll('[data-righttab]').forEach(b => b.addEventListener('click', () => { cs.rightTab = b.dataset.righttab; render(); }));
   const collapseBtn = document.getElementById('calCollapseMonth');
   if (collapseBtn) collapseBtn.addEventListener('click', () => { cs.expanded = false; render(); });
   document.querySelectorAll('.cal-collapse-header').forEach(h => h.addEventListener('click', () => { cs.collapsed[h.dataset.panel] = !cs.collapsed[h.dataset.panel]; render(); }));
   if (cs.filtersPopoverOpen) {
     setTimeout(() => {
       // close(ev): cierra close; actualiza el DOM.
       const close = (ev) => {
         const pop = document.getElementById('calFiltersPopover');
         const btn = document.getElementById('calFiltersBtn');
         if (pop && !pop.contains(ev.target) && btn && !btn.contains(ev.target)) {
           cs.filtersPopoverOpen = false; render();
           document.removeEventListener('click', close);
         }
       };
       document.addEventListener('click', close);
     }, 0);
   }
   const schBtn = document.getElementById('calSchedule');
   if (schBtn) schBtn.addEventListener('click', () => openScheduleModal({}));
   document.querySelectorAll('[data-slot-date]').forEach(el => {
     el.addEventListener('click', () => {
       if (!hasRole('admin') && !hasRole('dispatcher')) return;
       openScheduleModal({ date: el.dataset.slotDate, hour: Number(el.dataset.slotHour), minute: 0 });
     });
   });
    const goOrders = document.getElementById('calGoOrders');
    if (goOrders) goOrders.addEventListener('click', () => { state.view='orders'; render(); });
    try { localStorage.setItem('sigos.calendar', JSON.stringify({ view: cs.view, anchor: cs.anchor, selectedDay: cs.selectedDay, filters: cs.filters })); } catch (e) {}
    if (state.calendarRefreshTimer) clearTimeout(state.calendarRefreshTimer);
    state.calendarRefreshTimer = setTimeout(() => { if (state.view === 'calendar') quietRender(); }, 45000);
    state._calPublic = pub;
    setTimeout(() => {
      const scroller = document.querySelector('.cal-grid-scroll');
      if (scroller) {
        const ws = (pub.work_start || '07:00').split(':')[0];
        const now = new Date();
        let targetHour = parseInt(ws, 10) || 7;
        if (cs.anchor === calTodayStr()) targetHour = Math.max(targetHour, now.getHours() - 1);
        scroller.scrollTop = Math.max(0, (targetHour - 7) * 48);
      }
    }, 50);
}

// devuelve layout overlaps; sin efectos secundarios.
function layoutOverlaps(evs) {
  // returns array of columns, each column is array of events with .index
  if (!evs.length) return [];
  const sorted = evs.slice().sort((a,b) => new Date(a.start)-new Date(b.start));
  const columns = [];
  sorted.forEach(e => {
    let placed = false;
    for (const col of columns) {
      const last = col[col.length-1];
      if (new Date(e.start) >= new Date(last.end)) { col.push(e); placed = true; break; }
    }
    if (!placed) columns.push([e]);
  });
  columns.forEach((col, i) => col.forEach(e => e._col = i));
  // regroup by column index for rendering
  const out = columns.map((col, i) => col.map(e => Object.assign({}, e, { index: i })));
  return out.length ? out : [[]];
}

// renderiza la vista settings; actualiza el DOM; realiza peticiones de red.
// ---------- Configuracion ----------
let settingsTab = 'organization';
// Cada seccion se organiza en grupos con descripcion. Solo se exponen campos que existen en la API.
// Campo: [nombre, etiqueta, tipo, { hint, min, max, step, unit, placeholder }]
const SETTINGS_SECTIONS = {
  organization: {
    label: 'Organización', path: '/api/v1/settings/organization',
    description: 'Datos de la empresa que aparecen en reportes y comunicaciones.',
    groups: [
      { title: 'Identidad', description: 'Nombre legal e identificación tributaria.', fields: [
        ['company_name', 'Nombre de la empresa', 'text', { placeholder: 'Ej. Gas Natural S.A.' }],
        ['nit', 'NIT', 'text', { placeholder: '900123456-7' }],
      ] },
      { title: 'Contacto', description: 'Canales de contacto administrativo.', fields: [
        ['admin_email', 'Correo del administrador', 'email', { placeholder: 'admin@empresa.com' }],
        ['contact_phone', 'Teléfono de contacto', 'text'],
        ['address', 'Dirección', 'text', { wide: true }],
      ] },
      { title: 'Región', description: 'Zona horaria usada para agendas, horarios laborales y reportes.', fields: [
        ['timezone', 'Zona horaria', 'text', { hint: 'Formato IANA, por ejemplo America/Bogota.' }],
      ] },
    ],
  },
  operations: {
    label: 'Operación', path: '/api/v1/settings/operations',
    description: 'Reglas que usa el calendario para programar visitas.',
    groups: [
      { title: 'Jornada laboral', description: 'Días y horario en que se pueden programar visitas.', fields: [
        ['work_days', 'Días laborales', 'days', { wide: true }],
        ['work_start', 'Hora de inicio', 'time'],
        ['work_end', 'Hora de finalización', 'time', { hint: 'Debe ser posterior a la hora de inicio.' }],
      ] },
      { title: 'Visitas', description: 'Duración de las visitas programadas.', fields: [
        ['default_visit_duration', 'Duración predeterminada', 'number', { unit: 'min', min: 15, max: 480, step: 5, hint: 'Entre 15 y 480 minutos, en múltiplos de 5.' }],
        ['max_visit_duration', 'Duración máxima', 'number', { unit: 'min', min: 15, max: 480, step: 5, hint: 'Límite para cualquier visita programada.' }],
      ] },
      { title: 'Programación', description: 'Restricciones al agendar y vista del calendario.', fields: [
        ['min_advance_hours', 'Antelación mínima', 'number', { unit: 'h', min: 0, max: 720, hint: 'Tiempo mínimo entre la programación y la visita.' }],
        ['travel_margin_minutes', 'Margen de traslado', 'number', { unit: 'min', min: 0, max: 120, hint: 'Separación mínima entre visitas del mismo técnico.' }],
        ['calendar_interval', 'Intervalo del calendario', 'interval', { hint: 'Tamaño de cada franja en la vista de calendario.' }],
      ] },
    ],
  },
  security: {
    label: 'Seguridad', path: '/api/v1/settings/security',
    description: 'Políticas de sesión, contraseñas y bloqueo de cuentas.',
    groups: [
      { title: 'Sesiones', description: 'Cuándo se cierra automáticamente una sesión.', fields: [
        ['session_inactivity_minutes', 'Cierre por inactividad', 'number', { unit: 'min', min: 1 }],
        ['session_max_hours', 'Duración máxima de sesión', 'number', { unit: 'h', min: 1 }],
      ] },
      { title: 'Contraseñas', description: 'Requisitos para contraseñas nuevas y temporales.', fields: [
        ['password_min_length', 'Longitud mínima', 'number', { unit: 'caracteres', min: 8 }],
        ['password_history_count', 'Historial no reutilizable', 'number', { unit: 'contraseñas', min: 0, hint: 'Cuántas contraseñas anteriores no se pueden repetir.' }],
        ['temp_password_validity_days', 'Vigencia de contraseña temporal', 'number', { unit: 'días', min: 1 }],
      ] },
      { title: 'Bloqueo de cuenta', description: 'Protección contra intentos de acceso repetidos.', fields: [
        ['lock_attempts', 'Intentos fallidos permitidos', 'number', { min: 1 }],
        ['lock_minutes', 'Duración del bloqueo', 'number', { unit: 'min', min: 1 }],
      ] },
    ],
  },
  audit: { label: 'Auditoría', description: 'Historial de cambios de configuración.' },
};
const WEEK_DAYS = [[1, 'Lun'], [2, 'Mar'], [3, 'Mié'], [4, 'Jue'], [5, 'Vie'], [6, 'Sáb'], [7, 'Dom']];
const toMin = (hhmm) => { const [h, m] = String(hhmm || '').split(':').map(Number); return Number.isFinite(h) ? h * 60 + (m || 0) : NaN; };

// renderSettings(content): pestañas de configuracion; el admin edita, el resto solo consulta.
async function renderSettings(content) {
  const isAdmin = hasRole('admin');
  const tabs = Object.entries(SETTINGS_SECTIONS).filter(([k]) => isAdmin || k === 'organization' || k === 'operations');
  if (!tabs.some(([k]) => k === settingsTab)) settingsTab = tabs[0][0];
  content.innerHTML = `
    <div style="max-width:960px">
      <div class="ds-tabs" role="tablist" aria-label="Secciones de configuración">
        ${tabs.map(([k, s]) => `<button type="button" role="tab" class="ds-tab" id="stab-${k}" data-stab="${k}" aria-selected="${k === settingsTab}" aria-controls="settingsBody" tabindex="${k === settingsTab ? 0 : -1}">${escapeHtml(s.label)}</button>`).join('')}
      </div>
      <div id="settingsBody" role="tabpanel" aria-labelledby="stab-${settingsTab}">${loaderBlock('Cargando configuración…', 280)}</div>
    </div>`;
  const tabEls = $$('[data-stab]');
  tabEls.forEach((b, i) => {
    b.addEventListener('click', () => { settingsTab = b.dataset.stab; renderSettings(content); });
    b.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      const next = tabEls[(i + d + tabEls.length) % tabEls.length];
      settingsTab = next.dataset.stab; renderSettings(content).then(() => $(`#stab-${settingsTab}`)?.focus());
    });
  });
  if (settingsTab === 'audit') return loadAuditLog(1);
  return loadSettingsSection(settingsTab, isAdmin);
}

// validateOperations(v): reglas del backend + coherencia entre campos. Devuelve { campo: mensaje }.
function validateOperations(v) {
  const e = {};
  if (!v.work_days.length) e.work_days = 'Seleccione al menos un día laboral';
  const ws = toMin(v.work_start), we = toMin(v.work_end);
  if (Number.isNaN(ws)) e.work_start = 'Hora inválida';
  if (Number.isNaN(we)) e.work_end = 'Hora inválida';
  if (!e.work_start && !e.work_end && ws >= we) e.work_end = 'Debe ser posterior a la hora de inicio';
  const dd = v.default_visit_duration, md = v.max_visit_duration;
  if (!(dd >= 15 && dd <= 480) || dd % 5) e.default_visit_duration = 'Entre 15 y 480 min, múltiplo de 5';
  if (!(md >= 15 && md <= 480)) e.max_visit_duration = 'Entre 15 y 480 min';
  if (!e.default_visit_duration && !e.max_visit_duration && dd > md) e.max_visit_duration = 'No puede ser menor que la duración predeterminada';
  if (!e.work_end && !e.max_visit_duration && md > we - ws) e.max_visit_duration = `Supera la jornada laboral (${we - ws} min)`;
  if (!(v.min_advance_hours >= 0 && v.min_advance_hours <= 720)) e.min_advance_hours = 'Entre 0 y 720 horas';
  if (!(v.travel_margin_minutes >= 0 && v.travel_margin_minutes <= 120)) e.travel_margin_minutes = 'Entre 0 y 120 min';
  if (![15, 30, 60].includes(v.calendar_interval)) e.calendar_interval = 'Seleccione 15, 30 o 60 min';
  return e;
}

// loadSettingsSection(key, editable): formulario agrupado con validacion, deteccion de cambios y control de version.
async function loadSettingsSection(key, editable) {
  const sec = SETTINGS_SECTIONS[key];
  const body = $('#settingsBody');
  const res = await api('GET', sec.path);
  if (!$('#settingsBody')) return;
  if (!res.ok) { body.innerHTML = `<div class="ds-alert ds-alert--danger">${escapeHtml(res.body?.error || 'No se pudo cargar la configuración')}</div>`; return; }
  const data = res.body || {};
  const dis = editable ? '' : 'disabled';
  const fieldHtml = ([name, label, type, o = {}]) => {
    const v = data[name];
    const id = `st-${name}`;
    let input;
    if (type === 'days') {
      const cur = Array.isArray(v) ? v.map(Number) : [];
      input = `<div role="group" aria-labelledby="${id}-l" class="st-days">${WEEK_DAYS.map(([n, l]) => `<label class="st-day"><input type="checkbox" data-day="${n}" ${cur.includes(n) ? 'checked' : ''} ${dis}><span>${l}</span></label>`).join('')}</div>`;
    } else if (type === 'interval') {
      input = `<div class="st-seg" role="radiogroup" aria-labelledby="${id}-l">${[15, 30, 60].map((n) => `<label class="st-seg__opt"><input type="radio" name="st-interval" value="${n}" ${Number(v) === n ? 'checked' : ''} ${dis}><span>${n} min</span></label>`).join('')}</div>`;
    } else {
      const attrs = `${o.min !== undefined ? `min="${o.min}"` : ''} ${o.max !== undefined ? `max="${o.max}"` : ''} ${o.step ? `step="${o.step}"` : ''}`;
      const inp = `<input id="${id}" data-f="${name}" type="${type}" class="sigos-input" value="${escapeHtml(v ?? '')}" placeholder="${escapeHtml(o.placeholder || '')}" ${attrs} ${dis} aria-describedby="${id}-h ${id}-e">`;
      input = o.unit ? `<div class="st-unit">${inp}<span>${escapeHtml(o.unit)}</span></div>` : inp;
    }
    return `<div class="fld${o.wide ? ' st-wide' : ''}" data-field="${name}">
      <label id="${id}-l" for="${id}">${escapeHtml(label)}</label>${input}
      ${o.hint ? `<div class="fld-hint" id="${id}-h">${escapeHtml(o.hint)}</div>` : ''}<div class="fld-error" id="${id}-e"></div></div>`;
  };
  body.innerHTML = `
    <p class="st-intro">${escapeHtml(sec.description)}</p>
    ${editable ? '' : '<div class="ds-alert ds-alert--info" style="margin-bottom:16px">Solo el administrador puede modificar esta sección.</div>'}
    <form id="stForm" novalidate>
      ${sec.groups.map((g) => `
        <section class="st-group">
          <div class="st-group__head"><h3>${escapeHtml(g.title)}</h3><p>${escapeHtml(g.description)}</p></div>
          <div class="st-group__fields">${g.fields.map(fieldHtml).join('')}</div>
        </section>`).join('')}
      ${editable ? `<div class="st-actions">
        <span class="st-actions__status" id="stStatus" aria-live="polite">Sin cambios</span>
        <button type="button" class="sigos-btn-secondary" id="stReset" disabled>Descartar</button>
        <button type="submit" class="sigos-btn-primary" id="stSave" disabled>Guardar cambios</button>
      </div>` : ''}
    </form>`;
  if (!editable) return;

  const fields = sec.groups.flatMap((g) => g.fields);
  const read = () => {
    const out = {};
    for (const [name, , type] of fields) {
      if (type === 'days') out[name] = $$('[data-day]').filter((c) => c.checked).map((c) => Number(c.dataset.day));
      else if (type === 'interval') out[name] = Number($('input[name="st-interval"]:checked')?.value);
      else {
        const raw = $(`[data-f="${name}"]`).value.trim();
        out[name] = type === 'number' ? (raw === '' ? NaN : Number(raw)) : (raw === '' ? null : raw);
      }
    }
    return out;
  };
  const changed = () => {
    const cur = read();
    return Object.fromEntries(Object.entries(cur).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(data[k] ?? null)));
  };
  const showErrors = (errs) => {
    fields.forEach(([name]) => {
      const box = $(`[data-field="${name}"]`);
      const msg = errs[name] || '';
      box.querySelector('.fld-error').textContent = msg;
      box.querySelectorAll('input').forEach((i) => (msg ? i.setAttribute('aria-invalid', 'true') : i.removeAttribute('aria-invalid')));
    });
  };
  const validate = () => {
    const v = read();
    let errs = {};
    if (key === 'operations') errs = validateOperations(v);
    else {
      fields.forEach(([name, , type, o = {}]) => {
        if (type === 'number' && (!Number.isInteger(v[name]) || (o.min !== undefined && v[name] < o.min))) errs[name] = `Ingrese un número entero${o.min !== undefined ? ` mayor o igual a ${o.min}` : ''}`;
        if (type === 'email' && v[name] && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v[name])) errs[name] = 'Correo inválido';
      });
      if (key === 'organization' && !v.company_name) errs.company_name = 'Obligatorio';
    }
    return errs;
  };
  const refresh = () => {
    const n = Object.keys(changed()).length;
    $('#stStatus').textContent = n ? `${n} cambio${n > 1 ? 's' : ''} sin guardar` : 'Sin cambios';
    $('#stSave').disabled = !n;
    $('#stReset').disabled = !n;
    showErrors(n ? validate() : {});
  };
  $('#stForm').addEventListener('input', refresh);
  $('#stForm').addEventListener('change', refresh);
  $('#stReset').addEventListener('click', () => loadSettingsSection(key, editable));
  $('#stForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errs = validate();
    showErrors(errs);
    if (Object.keys(errs).length) { $(`[data-field="${Object.keys(errs)[0]}"] input`)?.focus(); return; }
    const diff = changed();
    if (!Object.keys(diff).length) return;
    if (key === 'operations') {
      const imp = await api('POST', '/api/v1/settings/operations/impact', { ...read() });
      if (imp.ok && imp.body?.count > 0) {
        const list = (imp.body.items || []).slice(0, 5).map((i) => `• ${i.order_code}: ${i.violations.join(', ')}`).join('\n');
        const more = imp.body.count > 5 ? `\n… y ${imp.body.count - 5} más` : '';
        if (!(await confirmDialog(`${imp.body.count} visita(s) programada(s) quedarían fuera de las nuevas reglas. No se modifican automáticamente.\n\n${list}${more}`, { title: '¿Guardar de todos modos?', confirmLabel: 'Guardar' }))) return;
      }
    }
    const btn = $('#stSave');
    btn.disabled = true;
    const r = await api('PATCH', sec.path, { version: Number(data.version || 0), ...diff });
    btn.textContent = 'Guardar cambios';
    if (r.status === 409) { notify('Otro usuario modificó esta sección. Se recargaron los valores actuales.', 'error'); loadSettingsSection(key, editable); return; }
    if (!r.ok) {
      btn.disabled = false;
      const msgs = { invalid_timezone: 'Zona horaria no válida', invalid_city: 'Ciudad no válida' };
      if (r.body?.field) showErrors({ [r.body.field]: msgs[r.body.error?.replace(' ', '_')] || r.body.error });
      notify(r.body?.error === 'invalid timezone' ? 'Zona horaria no válida' : (r.body?.error || 'No se pudo guardar'), 'error');
      return;
    }
    notify(r.body?.message || 'Cambios guardados', 'success');
    loadSettingsSection(key, editable);
  });
}

// loadAuditLog(page): historial de cambios de configuracion (solo admin).
async function loadAuditLog(page) {
  const body = $('#settingsBody');
  const res = await api('GET', `/api/v1/audit-log?page=${page}&page_size=20`);
  if (!$('#settingsBody')) return;
  if (!res.ok) { body.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(res.body?.error || 'No se pudo cargar la auditoría')}</div>`; return; }
  const d = res.body || {};
  const items = Array.isArray(d.items) ? d.items : [];
  const pages = Math.max(1, Math.ceil(Number(d.total || 0) / (d.page_size || 20)));
  const fmt = (v) => (v ? new Date(v).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '');
  body.innerHTML = `<p class="st-intro">Historial de cambios de configuración: quién cambió qué y cuándo.</p>` + (items.length ? `
    <table class="tbl" style="width:100%"><thead><tr><th>Fecha</th><th>Usuario</th><th>Sección</th><th>Campo</th><th>Anterior</th><th>Nuevo</th><th>Resultado</th></tr></thead>
    <tbody>${items.map((a) => `<tr class="tbl-row"><td>${escapeHtml(fmt(a.created_at))}</td><td>${escapeHtml(a.username || '')}</td><td>${escapeHtml(a.section || '')}</td><td>${escapeHtml(a.field || '')}</td><td>${escapeHtml(a.old_value ?? '')}</td><td>${escapeHtml(a.new_value ?? '')}</td><td>${escapeHtml(a.result || '')}</td></tr>`).join('')}</tbody></table>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;font-size:12px">
      <span style="color:var(--c-text-3)">${Number(d.total || 0)} registros · página ${page} de ${pages}</span>
      <span style="display:flex;gap:6px"><button type="button" class="sigos-btn-secondary" id="auPrev" ${page <= 1 ? 'disabled' : ''}>Anterior</button><button type="button" class="sigos-btn-secondary" id="auNext" ${page >= pages ? 'disabled' : ''}>Siguiente</button></span>
    </div>` : '<div class="empty-state__text">Sin cambios registrados todavía</div>');
  $('#auPrev')?.addEventListener('click', () => loadAuditLog(page - 1));
  $('#auNext')?.addEventListener('click', () => loadAuditLog(page + 1));
}

// devuelve pending view; actualiza el DOM.
function pendingView(content, title) {
  content.innerHTML = `
    <div class="sigos-card"><div class="empty-state">
      <div class="empty-state__icon">${icon("hourglass", 24)}</div>
      <div class="empty-state__title">${escapeHtml(title)}</div>
      <div class="empty-state__text">Vista pendiente de migrar desde React.</div>
    </div></div>`;
}

if (!state.charts) state.charts = {};
// destroyCharts(): destruye destroy charts; sin efectos secundarios.
// chartTheme(): colores de Chart.js leídos de los tokens CSS del tema activo (el canvas no entiende var()).
function chartTheme() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n).trim();
  const ink = v('--c-chart-ink') || '#163028';
  const h = ink.replace('#', '');
  const inkSoft = h.length === 6 ? `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},0.12)` : 'rgba(22,48,40,0.1)';
  return { ink, inkSoft, text: v('--c-chart-text') || '#64748B', grid: v('--c-chart-grid') || '#F1EEE8', surface: v('--c-surface') || '#FFFFFF' };
}
let _chartTheme = null;
// recolorCharts(): al cambiar de tema, sustituye en los gráficos vivos los colores del tema anterior por los del nuevo.
function recolorCharts() {
  if (typeof Chart === 'undefined') return;
  const prev = _chartTheme;
  const next = chartTheme();
  _chartTheme = next;
  Chart.defaults.color = next.text;
  if (!prev) return;
  const map = new Map([[prev.ink, next.ink], [prev.inkSoft, next.inkSoft], [prev.grid, next.grid], [prev.surface, next.surface], [prev.text, next.text]]);
  const swap = (val) => (Array.isArray(val) ? val.map(swap) : (typeof val === 'string' && map.has(val) ? map.get(val) : val));
  Object.values(state.charts || {}).forEach((c) => {
    try {
      c.data.datasets.forEach((ds) => { ds.backgroundColor = swap(ds.backgroundColor); ds.borderColor = swap(ds.borderColor); });
      Object.values(c.options.scales || {}).forEach((sc) => { if (sc.grid) sc.grid.color = swap(sc.grid.color); if (sc.ticks) sc.ticks.color = next.text; });
      if (c.options.plugins?.legend?.labels) c.options.plugins.legend.labels.color = next.text;
      c.update('none');
    } catch (e) { /* gráfico ya destruido */ }
  });
}

function destroyCharts() {
  Object.values(state.charts).forEach((c) => { try { c.destroy(); } catch (e) {} });
  state.charts = {};
}

// renderiza la vista dashboard; actualiza el DOM; realiza peticiones de red.
async function renderDashboard(content) {
  destroyCharts();
  content.innerHTML = loaderBlock('Cargando indicadores del dashboard…', 320);
  const isTech = (state.session?.user?.roles || []).includes('technician');
  if (isTech) {
    const res = await api('GET', '/api/v1/tecnico/mi-dashboard');
    if (!res.ok) {
      content.innerHTML = `<div style="color:var(--c-danger)">Error cargando dashboard: ${escapeHtml(res.body?.error || res.error || 'sin respuesta del servidor')}. <button type="button" class="sigos-btn-secondary" id="retryDash">Reintentar</button></div>`;
      $('#retryDash')?.addEventListener('click', () => renderDashboard(content));
      return;
    }
    const d = res.body;
    const counts = d.counts || {};
    const resumen = d.resumen || {};
    const orders = d.orders || [];
    // devuelve status label; sin efectos secundarios.
    const statusLabel = (s) => ({pending:'Pendiente',assigned:'Asignada',in_progress:'En proceso',completed:'Completada',cancelled:'Cancelada'}[s] || s);
    // devuelve status color; sin efectos secundarios.
    const statusColor = (s) => ({pending:'var(--c-warning)',assigned:'var(--c-info)',in_progress:'var(--c-info)',completed:'var(--c-success)',cancelled:'var(--c-danger)'}[s] || 'var(--c-text-2)');
    // devuelve status icon; sin efectos secundarios.
    const statusIcon = (s) => ({pending:'\u23F3',assigned:'\u{1F4CB}',in_progress:'\u{1F6B6}',completed:'\u2705',cancelled:'\u274C'}[s] || '');
    // devuelve chip; sin efectos secundarios.
    const chip = (val, label, color, show) => show ? `<span style="display:inline-block;background:color-mix(in srgb, ${color} 14%, transparent);color:${color};border-radius:12px;padding:2px 8px;font-size:11px;font-weight:600;margin:2px">${label}: ${val}</span>` : '';
    content.innerHTML = `<div class="sigos-card" style="padding:16px;margin-bottom:12px">
      <h3 style="font-family:Outfit;font-size:18px;color:var(--c-nav);margin:0 0 4px">Mi dia</h3>
      <div style="font-size:12px;color:var(--c-text-3);margin-bottom:12px">${new Date().toLocaleDateString('es-CO',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px">
        ${chip(resumen.hoy||0, 'Hoy', 'var(--c-nav)', true)}
        ${chip(resumen.en_proceso||0, 'En proceso', 'var(--c-info)', (resumen.en_proceso||0) > 0)}
        ${chip(resumen.completadas_hoy||0, 'Completadas hoy', 'var(--c-success)', (resumen.completadas_hoy||0) > 0)}
        ${chip(resumen.pendientes_vencidas||0, 'Pendientes/vencidas', 'var(--c-danger)', (resumen.pendientes_vencidas||0) > 0)}
      </div>
      ${orders.length ? orders.map(o=>`<div class="tbl-row" role="link" tabindex="0" aria-label="Abrir orden OS-${o.id}" style="border:1px solid var(--c-border);border-radius:8px;padding:10px;margin-bottom:8px;cursor:pointer" data-wo="${o.id}" data-vt-card>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span data-vt="code" style="font-weight:700;color:var(--c-nav)">OS-${o.id}</span>
          <span style="font-size:11px;font-weight:600;color:${statusColor(o.status)}">${statusIcon(o.status)} ${statusLabel(o.status)}</span>
        </div>
        <div data-vt="title" style="font-size:13px;color:var(--c-text-2)">${escapeHtml(o.title||'')}</div>
        <div style="font-size:11px;color:var(--c-text-3);margin-top:4px">${escapeHtml(o.customer_name||'Sin dato')} - ${escapeHtml(o.zone||o.legacy_zone||'Sin dato')}</div>
        ${o.scheduled_at ? `<div style="font-size:11px;color:var(--c-text-3)">Ventana: ${escapeHtml(o.scheduled_at)} - ${escapeHtml(o.scheduled_end||'')}</div>` : ''}
      </div>`).join('') : '<div style="text-align:center;color:var(--c-text-3);padding:20px">No tienes ordenes asignadas.</div>'}
    </div>`;
    bindOrderCards(content);
    return;
  }
  const range = state.dashboardRange || 7;
  const zone = state.dashboardZone || '';
  const tech = state.dashboardTech || '';
  const qs = new URLSearchParams({ range, ...(zone ? { zone } : {}), ...(tech ? { technician_id: tech } : {}) });
  const res = await api('GET', `/api/v1/dashboard/summary?${qs}`);
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  if (!res.ok) {
    content.innerHTML = `<div style="color:var(--c-danger)">Error cargando dashboard: ${escapeHtml(res.body?.error || res.error || 'sin respuesta del servidor')}. <button type="button" class="sigos-btn-secondary" id="retryDash">Reintentar</button></div>`;
    $('#retryDash')?.addEventListener('click', () => renderDashboard(content));
    return;
  }
  const d = res.body;

  const labelMap = { active: 'Órdenes activas', completed: 'Completadas', sla: 'Cumplimiento SLA', mean_time: 'Tiempo medio', techs: 'Técnicos disp.', stock: 'Alertas stock' };
  const colorMap = {}; // iconos neutros: el color se reserva para estados que requieren atencion
  const iconMap = { active: 'schedule', completed: 'check_circle', sla: 'check_circle', mean_time: 'sync', techs: 'engineering', stock: 'warning' };
  // kpiTile: indicador compacto; data-nav conserva la navegacion existente al hacer clic.
  const kpiTile = (k) => {
    const color = colorMap[k.key] || '#3A4552';
    const delta = k.delta_pct;
    let chip = '';
    if (delta !== null && delta !== undefined) {
      const good = (delta >= 0) === k.up_is_good;
      chip = `<span class="kpi-delta ${good ? 'is-good' : 'is-bad'}" title="Variación frente al periodo anterior">${delta >= 0 ? '\u25b2' : '\u25bc'} ${Math.abs(delta)}%</span>`;
    }
    return `<button type="button" class="kpi-tile" data-nav="${k.key}">
        <span class="kpi-tile__label"><span class="kpi-tile__icon">${icon(iconMap[k.key] || 'dashboard', 13)}</span>${escapeHtml(labelMap[k.key] || k.label)}</span>
        <span class="kpi-tile__value${k.key === 'stock' && Number(k.value) > 0 ? ' is-alert' : ''}">${escapeHtml(String(k.value))}${chip}</span>
      </button>`;
  };
  const kpiByKey = Object.fromEntries((d.kpis || []).map((k) => [k.key, k]));
  const KPI_GROUPS = [
    { title: 'Rendimiento', keys: ['active', 'completed', 'sla', 'mean_time'] },
    { title: 'Recursos', keys: ['techs', 'stock'] },
  ];
  const known = new Set(KPI_GROUPS.flatMap((g) => g.keys));
  const extra = (d.kpis || []).filter((k) => !known.has(k.key));
  const kpiHtml = KPI_GROUPS.map((g) => {
    const tiles = g.keys.map((key) => kpiByKey[key]).filter(Boolean).concat(g.title === 'Recursos' ? extra : []);
    return tiles.length ? `<div class="kpi-group"><div class="kpi-group__title">${g.title}</div><div class="kpi-group__tiles">${tiles.map(kpiTile).join('')}</div></div>` : '';
  }).join('');


  // devuelve recent orders; sin efectos secundarios.
  const recentOrders = (d.recent_orders || []).map((o) => {
    const st = statusOf(o.status);
    const pr = priorityOf(o.priority);
    const tech = o.assigned_to?.username || '—';
    const initials = tech === '—' ? '—' : tech.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
    return `<tr class="tbl-row" data-detail="${o.id}" data-vt-card>
      <td><span class="mono" data-vt="code" style="display:inline-block;font-size:12px;font-weight:600;color:var(--c-nav)">${o.id}</span></td>
      <td style="font-size:13px">${escapeHtml(o.customer_name || '—')}</td>
      <td><div style="display:flex;align-items:center;gap:6px"><div style="width:22px;height:22px;border-radius:50%;background:var(--c-surface-2);color:var(--c-text-2);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700">${escapeHtml(initials)}</div><span style="font-size:13px">${escapeHtml(tech)}</span></div></td>
      <td style="font-size:12px;color:var(--c-text-3)">${escapeHtml(o.created_at ? new Date(o.created_at).toLocaleString('es-ES') : '—')}</td>
      <td><span data-vt="status" class="${st.badge}">${escapeHtml(st.label)}</span></td>
      <td><span class="${pr.badge}">${escapeHtml(pr.label)}</span></td>
    </tr>`;
  }).join('');

  // devuelve techs html; sin efectos secundarios.
  const techsHtml = (d.technicians || []).slice(0, 5).map((t) => {
    const name = t.user?.username || '';
    const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
    const avail = t.is_available;
    const bg = 'var(--c-surface-2)';
    const fg = 'var(--c-text-2)';
    const ts = techStatusOf(avail);
    return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--c-border)">
      <div style="width:30px;height:30px;border-radius:50%;background:${bg};color:${fg};display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700">${escapeHtml(initials)}</div>
      <div style="flex:1"><div style="font-size:13px;font-weight:500;color:var(--c-text)">${escapeHtml(name)}</div><div style="font-size:11px;color:var(--c-text-3)">${escapeHtml(t.specialty || '')}</div></div>
      <span class="${ts.badge}">${escapeHtml(ts.label)}</span>
    </div>`;
  }).join('') || '<div style="color:var(--c-text-3);font-size:13px">Sin técnicos</div>';

  // devuelve notifs html; sin efectos secundarios.
  const notifsHtml = (d.notifications || []).slice(0, 5).map((n) => {
    const kind = n.subject?.toLowerCase().includes('stock') ? 'warn' : 'info';
    const bg = kind === 'warn' ? 'var(--c-warning-bg)' : 'var(--c-info-bg)';
    const fg = kind === 'warn' ? 'var(--c-warning)' : 'var(--c-info)';
    const glyph = kind === 'warn' ? '!' : 'i';
    return `<div style="display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid var(--c-border)">
      <div style="width:28px;height:28px;border-radius:6px;background:${bg};color:${fg};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700">${glyph}</div>
      <div><div style="font-size:13px;font-weight:500;color:var(--c-text)">${escapeHtml(n.subject || '')}</div><div style="font-size:12px;color:var(--c-text-3)">${escapeHtml(n.message || '')}</div></div>
    </div>`;
  }).join('') || '<div style="color:var(--c-text-3);font-size:13px">Sin notificaciones</div>';

  const stockCritical = d.stock?.critical || [];
  const stockLow = d.stock?.low || [];
  const stockHtml = (stockCritical.length || stockLow.length)
    ? [...stockCritical, ...stockLow].slice(0, 5).map((m) => `
      <div style="padding:6px 0;border-bottom:1px solid var(--c-border);display:flex;justify-content:space-between;align-items:center">
        <div style="font-size:13px;color:var(--c-text)">${escapeHtml(m.name)}</div>
        <span style="font-size:11px;font-weight:600;color:${stockCritical.includes(m) ? 'var(--c-danger)' : 'var(--c-warning)'}">${m.current_stock} de ${m.min_stock}</span>
      </div>`).join('')
    : '<div style="color:var(--c-text-3);font-size:13px">Sin alertas de stock</div>';
  const stockBoxBg = stockCritical.length ? 'var(--c-danger-bg)' : (stockLow.length ? 'var(--c-warning-bg)' : 'var(--c-surface)');
  const zoneBd = d.breakdowns?.zone || {};
  const typeBd = d.breakdowns?.type || {};
  const zoneEmpty = Object.keys(zoneBd).length === 1 && zoneBd['Sin zona'];
  const typeEmpty = Object.keys(typeBd).length === 1 && typeBd['Sin tipo'];

  // devuelve insights html; sin efectos secundarios.
  const insightsHtml = (d.insights || []).map((ins) => {
    const col = ins.kind === 'danger' ? 'var(--c-danger-solid)' : ins.kind === 'warn' ? '#E8A520' : ins.kind === 'ok' ? '#22C55E' : '#3B82F6';
    return `<div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0"><span style="width:8px;height:8px;border-radius:50%;background:${col};margin-top:5px;flex-shrink:0"></span><span style="font-size:13px;color:var(--c-text-2)">${escapeHtml(ins.text)}</span></div>`;
  }).join('');

  const longDate = new Date().toLocaleDateString('es-ES', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  content.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:16px;flex-wrap:wrap;gap:8px">
      <div>
        <h1 style="font-family:Outfit;font-weight:700;font-size:16px;color:var(--c-nav);margin:0">${(() => { const h = new Date().getHours(); return h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches'; })()}, ${escapeHtml(state.session.user.username || '')}</h1>
        <div style="font-size:11px;color:var(--c-text-3);margin-top:2px">${escapeHtml((kpiByKey.active?.value ?? 0) + ' órdenes activas · ' + (kpiByKey.techs?.value ?? '—') + ' técnicos disponibles ahora')}</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <select id="dashRange" aria-label="Periodo del dashboard" class="sigos-select"><option value="7" ${range==7?'selected':''}>7 días</option><option value="14" ${range==14?'selected':''}>14 días</option><option value="30" ${range==30?'selected':''}>30 días</option></select>
        <select id="dashZone" aria-label="Filtrar dashboard por zona" class="sigos-select"><option value="">Todas las zonas</option></select>
        <select id="dashTech" aria-label="Filtrar dashboard por técnico" class="sigos-select"><option value="">Todos los técnicos</option>${(d.technicians||[]).map((t)=>`<option value="${t.user?.id}" ${String(tech)===String(t.user?.id)?'selected':''}>${escapeHtml(t.user?.username||'')}</option>`).join('')}</select>
        <button type="button" class="sigos-btn-secondary" id="dashClear">Limpiar</button>
      </div>
    </div>

    <div class="kpi-strip sigos-card">${kpiHtml}</div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Órdenes por estado</h3><div class="cv"><canvas id="chartStack"></canvas></div></div>
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Creadas vs completadas</h3><div class="cv"><canvas id="chartCreated"></canvas></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Estado actual</h3><div class="cv sm"><canvas id="chartStatus"></canvas></div></div>
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Por prioridad</h3><div class="cv sm"><canvas id="chartPriority"></canvas></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Por zona</h3>${zoneEmpty ? '<div style="height:90px;display:flex;align-items:center;justify-content:center;color:var(--c-text-3);font-size:13px;text-align:center">Aún no hay datos de zona. Asigna zona a las órdenes.</div>' : '<div class="cv sm"><canvas id="chartZone"></canvas></div>'}</div>
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Carga por técnico</h3><div class="cv sm"><canvas id="chartLoad"></canvas></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Por tipo de instalación</h3>${typeEmpty ? '<div style="height:90px;display:flex;align-items:center;justify-content:center;color:var(--c-text-3);font-size:13px;text-align:center">Aún no hay datos de tipo de instalación. Asigna tipo a las órdenes.</div>' : '<div class="cv sm"><canvas id="chartType"></canvas></div>'}</div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 340px;gap:16px">
      <div class="sigos-card" style="padding:16px;overflow:hidden">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="margin:0;font-family:Outfit;font-weight:600;font-size:15px;color:var(--c-nav)">Órdenes recientes</h3>
          <button type="button" class="sigos-btn-secondary" id="goOrders">${icon('eye',14)} Ver todas</button>
        </div>
        <div class="table-scroll"><table class="tbl">
          <thead><tr><th>ID</th><th>Cliente</th><th>Técnico</th><th>Fecha</th><th>Estado</th><th>Prioridad</th></tr></thead>
          <tbody>${recentOrders || '<tr><td colspan="6" style="text-align:center;color:var(--c-text-3);padding:20px">Sin órdenes</td></tr>'}</tbody>
        </table></div>
      </div>
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="sigos-card" style="padding:14px 16px">
          <h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Análisis</h3>
          ${insightsHtml}
        </div>
        <div class="sigos-card" style="padding:14px 16px">
          <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Disponibilidad hoy</h3>
          ${techsHtml}
        </div>
        <div class="sigos-card" style="padding:16px">
          <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:15px;color:var(--c-nav)">Notificaciones recientes</h3>
          ${notifsHtml}
        </div>
        <div class="sigos-card" style="padding:16px;background:${stockBoxBg}">
          <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:15px;color:var(--c-nav)">Alerta de stock</h3>
          ${stockHtml}
        </div>
      </div>
    </div>`;

  $$('[data-nav]').forEach((el) => {
    el.addEventListener('click', () => {
      const key = el.dataset.nav;
      if (key === 'techs') { state.view = 'technicians'; render({ transition: 'nav' }); }
      else if (key === 'stock') { state.view = 'materials'; render({ transition: 'nav' }); }
      else { state.view = 'orders'; render({ transition: 'nav' }); }
    });
  });

  $('#dashRange')?.addEventListener('change', (e) => { state.dashboardRange = Number(e.target.value); renderDashboard(content); });
  $('#dashZone')?.addEventListener('change', (e) => { state.dashboardZone = e.target.value; renderDashboard(content); });
  $('#dashTech')?.addEventListener('change', (e) => { state.dashboardTech = e.target.value; renderDashboard(content); });
  $('#dashClear')?.addEventListener('click', () => { state.dashboardRange = 7; state.dashboardZone = ''; state.dashboardTech = ''; renderDashboard(content); });
  $('#goOrders')?.addEventListener('click', () => { state.view = 'orders'; render({ transition: 'nav' }); });
  $$('[data-detail]').forEach((b) => b.addEventListener('click', () => openOrderDetail(b.dataset.detail, b)));

  const zoneSel = $('#dashZone');
  if (zoneSel && !zoneSel.dataset.populated) {
    const zones = Object.keys(d.breakdowns?.zone || {});
    zones.forEach((z) => { const o = document.createElement('option'); o.value = z === 'Sin zona' ? '' : z; o.textContent = z; zoneSel.appendChild(o); });
    zoneSel.dataset.populated = '1';
    if (zone) zoneSel.value = zone;
  }

  try {
    Chart.defaults.font.family = 'DM Sans';
    Chart.defaults.font.size = 11;
    const th = chartTheme();
    _chartTheme = th;
    Chart.defaults.color = th.text;
    const labels = d.series?.labels || [];
    const shortLabels = labels.map((d) => { const dt = new Date(d); const wd = dt.toLocaleDateString('es-ES', { weekday: 'short' }).replace('.', ''); const abbr = (wd.charAt(0).toUpperCase() + wd.charAt(1).toLowerCase()); return `${abbr} ${dt.getDate()}`; });
    const stack = d.series?.stack || {};
    if ($('#chartStack')) state.charts.stack = new Chart($('#chartStack'), {
      type: 'bar',
      data: {
        labels: shortLabels,
        datasets: [
          { label: 'Pendiente', data: stack.pending || [], backgroundColor: '#C7D1CB', stack: 's' },
          { label: 'Programada', data: stack.assigned || [], backgroundColor: '#8FB09D', stack: 's' },
          { label: 'En proceso', data: stack.in_progress || [], backgroundColor: '#4F8A69', stack: 's' },
          { label: 'Completada', data: stack.completed || [], backgroundColor: '#2E7A50', stack: 's' },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true } } }, scales: { x: { stacked: true, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 7 } }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: th.grid }, border: { display: false } } } },
    });
    if ($('#chartCreated')) state.charts.created = new Chart($('#chartCreated'), {
      type: 'line',
      data: {
        labels: shortLabels,
        datasets: [
          { label: 'Creadas', data: d.series?.created || [], borderColor: th.ink, backgroundColor: th.inkSoft, fill: true, tension: 0.35, borderWidth: 2, pointRadius: 0 },
          { label: 'Completadas', data: d.series?.completed || [], borderColor: '#4AAF72', borderDash: [5, 5], fill: false, tension: 0.35, borderWidth: 2, pointRadius: 0 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true } } }, scales: { x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 7 } }, y: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: th.grid }, border: { display: false } } } },
    });
    // Colores por clave (no por posicion): el orden de las claves depende del backend.
    const STATUS_COLORS = { pending: '#C7D1CB', assigned: '#8FB09D', in_progress: '#4F8A69', completed: '#2E7A50', closed: th.ink, cancelled: '#B9B4AC' };
    const PRIORITY_COLORS = { high: th.ink, medium: '#4F8A69', low: '#C7D1CB' };
    const statusBd = d.breakdowns?.status || {};
    const statusKeys = Object.keys(statusBd).filter((k) => Number(statusBd[k]) > 0);
    if ($('#chartStatus')) state.charts.status = new Chart($('#chartStatus'), {
      type: 'doughnut',
      data: { labels: statusKeys.map((k) => statusOf(k).label), datasets: [{ data: statusKeys.map((k) => statusBd[k]), backgroundColor: statusKeys.map((k) => STATUS_COLORS[k] || '#94A3B8'), borderWidth: 2, borderColor: th.surface }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true, padding: 10 } } } },
    });
    const prioBd = d.breakdowns?.priority || {};
    if ($('#chartPriority')) state.charts.priority = new Chart($('#chartPriority'), {
      type: 'doughnut',
      data: (() => { const ks = ['high', 'medium', 'low'].filter((k) => Number(prioBd[k]) > 0).concat(Object.keys(prioBd).filter((k) => !['high', 'medium', 'low'].includes(k) && Number(prioBd[k]) > 0)); return { labels: ks.map((k) => priorityOf(k).label), datasets: [{ data: ks.map((k) => prioBd[k]), backgroundColor: ks.map((k) => PRIORITY_COLORS[k] || '#94A3B8'), borderWidth: 2, borderColor: th.surface }] }; })(),
      options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true, padding: 10 } } } },
    });
    if (!zoneEmpty && $('#chartZone')) {
      const zoneBd2 = d.breakdowns?.zone || {};
      state.charts.zone = new Chart($('#chartZone'), {
        type: 'bar',
        data: { labels: Object.keys(zoneBd2), datasets: [{ data: Object.values(zoneBd2), backgroundColor: '#2E7A50' }] },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: th.grid }, border: { display: false } }, y: { grid: { display: false } } } },
      });
    }
    const loadBd = d.breakdowns?.load || {};
    const loadLabels = Object.keys(loadBd).filter((k) => k !== 'Sin asignar').concat(loadBd['Sin asignar'] !== undefined ? ['Sin asignar'] : []);
    const loadData = loadLabels.map((k) => loadBd[k] || 0);
    const loadColors = loadLabels.map((k) => (k === 'Sin asignar' ? '#96908A' : '#2E7A50'));
    if ($('#chartLoad')) state.charts.load = new Chart($('#chartLoad'), {
      type: 'bar',
      data: { labels: loadLabels, datasets: [{ data: loadData, backgroundColor: loadColors, barThickness: 12, maxBarThickness: 14, borderRadius: 3 }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: th.grid }, border: { display: false } }, y: { grid: { display: false } } } },
    });
    if (!typeEmpty && $('#chartType')) {
      const typeBd2 = d.breakdowns?.type || {};
      state.charts.type = new Chart($('#chartType'), {
        type: 'bar',
        data: { labels: Object.keys(typeBd2), datasets: [{ data: Object.values(typeBd2), backgroundColor: '#2E7A50', barThickness: 12, maxBarThickness: 14, borderRadius: 3 }] },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: th.grid }, border: { display: false } }, y: { grid: { display: false } } } },
      });
    }
  } catch (e) {
    console.error('Chart error', e);
  }
}

// renderiza la vista orders; actualiza el DOM; realiza peticiones de red.
// renderOrders(content, { soft }): soft = refresco por filtro/pestaña/página. La tabla actual se mantiene
// mientras carga (sin pasar por "Cargando...") y el cambio se anima como transición de lista.
async function renderOrders(content, opts = {}) {
  if (!state.ordersState) state.ordersState = { filters: { q: '', status: '', technician_id: '', zone: '', priority: '', type: '', date_from: '', date_to: '', unassigned: false }, sort: 'created_at', order: 'desc', page: 1, pageSize: 10 };
  const st = state.ordersState;
  const soft = !!opts.soft && !!content.querySelector('table.tbl');
  if (soft) content.setAttribute('aria-busy', 'true');
  else content.innerHTML = loaderBlock('Consultando órdenes…', 320);

  const params = new URLSearchParams();
  if (st.filters.status) params.set('status', st.filters.status);
  if (st.filters.q) params.set('q', st.filters.q);
  if (st.filters.technician_id) params.set('technician_id', st.filters.technician_id);
  if (st.filters.zone) params.set('zone', st.filters.zone);
  if (st.filters.priority) params.set('priority', st.filters.priority);
  if (st.filters.type) params.set('type', st.filters.type);
  if (st.filters.date_from) params.set('date_from', st.filters.date_from);
  if (st.filters.date_to) params.set('date_to', st.filters.date_to);
  if (st.filters.unassigned) params.set('unassigned', 'true');
  params.set('sort', st.sort);
  params.set('order', st.order);
  params.set('page', st.page);
  params.set('page_size', st.pageSize);

  const [ordersRes, profilesRes] = await Promise.all([
    api('GET', `/api/v1/work-orders?${params}`),
    api('GET', '/api/v1/technician-profiles'),
  ]);
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  content.setAttribute('aria-busy', 'false');
  if (!ordersRes.ok) { content.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(ordersRes.body?.error || 'Error')}</div>`; return; }
  const body = ordersRes.body || {};
  const orders = body.items || [];
  const total = body.total || 0;
  const counts = body.counts || {};
  state.profiles = profilesRes.ok ? (profilesRes.body || []) : [];

  const tabs = [
    { key: '', label: 'Todas' },
    { key: 'pending', label: 'Pendientes' },
    { key: 'assigned', label: 'Programadas' },
    { key: 'in_progress', label: 'En proceso' },
    { key: 'completed', label: 'Completadas' },
  ];
  const tabHtml = tabs.map((t) => {
    const c = t.key === '' ? Object.values(counts).reduce((a, b) => a + b, 0) : (counts[t.key] || 0);
    const active = st.filters.status === t.key;
    return `<button type="button" class="tab-btn ${active ? 'active' : ''}" data-status="${t.key}" style="background:${active ? 'var(--c-strong)' : 'var(--c-surface)'};color:${active ? '#fff' : 'var(--c-text-2)'};border:1px solid var(--c-border);border-radius:4px;padding:6px 12px;font-size:13px;font-weight:500;cursor:pointer">${escapeHtml(t.label)} <i style="font-style:normal;background:${active ? 'rgba(255,255,255,.25)' : 'var(--c-neutral-bg)'};color:${active ? '#fff' : 'var(--c-text-3)'};border-radius:10px;padding:0 6px;font-size:11px;font-weight:700">${c}</i></button>`;
  }).join('');

  const hasFilters = st.filters.q || st.filters.technician_id || st.filters.zone || st.filters.priority || st.filters.type || st.filters.date_from || st.filters.date_to || st.filters.unassigned;
  const filterBorder = hasFilters ? 'border-color:var(--c-primary)' : '';

  const rows = orders.map((o) => {
    const stInfo = statusOf(o.status);
    const prInfo = priorityOf(o.priority);
    const tech = o.assigned_to?.username || '';
    const initials = tech ? tech.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase() : '';
    const techCell = tech
      ? `<div style="display:flex;align-items:center;gap:6px"><div style="width:22px;height:22px;border-radius:50%;background:var(--c-surface-2);color:var(--c-text-2);display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700">${escapeHtml(initials)}</div><span style="font-size:12px;color:var(--c-text-2)">${escapeHtml(tech)}</span></div>`
      : `<span style="font-size:12px;color:var(--c-text-3)">Sin asignar</span>`;
    const dateStr = o.scheduled_at ? new Date(o.scheduled_at).toLocaleString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) : '—';
    return `<tr class="tbl-row" data-detail="${o.id}" data-vt-row="order-${o.id}" data-vt-card>
      <td><span class="mono" data-vt="code" style="display:inline-block;font-size:12px;font-weight:600;color:var(--c-nav)">OS-${String(o.id).padStart(4, '0')}</span></td>
      <td><div style="font-size:13px;font-weight:500;color:var(--c-text)">${escapeHtml(o.customer_name || '—')}</div><div data-vt="title" style="font-size:11px;color:var(--c-text-3)">${escapeHtml(o.title || '')}</div></td>
      <td><div style="font-size:12px;color:var(--c-text-3);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(o.address || '')}">${escapeHtml(o.address || '—')}</div></td>
      <td style="font-size:12px;color:var(--c-text-2)">${escapeHtml(o.installation_type || '—')}</td>
      <td>${techCell}</td>
      <td style="font-size:12px;color:var(--c-text-2)">${escapeHtml(dateStr)}</td>
      <td><span data-vt="status" class="${stInfo.badge}">${escapeHtml(stInfo.label)}</span></td>
      <td><span class="${prInfo.badge}">${escapeHtml(prInfo.label)}</span></td>
      <td><div class="act"><a class="ver" href="#" data-detail="${o.id}" title="Ver" aria-label="Ver ${orderCode(o)}">${icon('eye', 16)}</a><a href="#" data-edit="${o.id}" title="Editar" aria-label="Editar ${orderCode(o)}">${icon('edit', 16)}</a>${canCancelOrders() && CANCELLABLE_STATUSES.has(o.status) ? `<a href="#" class="act-danger" data-cancel-order="${o.id}" title="Cancelar orden" aria-label="Cancelar ${orderCode(o)}">${icon('cancel', 16)}</a>` : ''}</div></td>
    </tr>`;
  }).join('');

  $('#topbarActions').innerHTML = `<button type="button" class="sigos-btn-primary" id="newOrderBtn">${icon('plus', 16)} Nueva orden</button>`;

  const paint = () => {
  content.innerHTML = `
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">${tabHtml}</div>
    <div class="sigos-card filters" style="margin-bottom:14px;${filterBorder}">
      <div style="flex:1 1 220px;min-width:220px">${searchField({ placeholder: 'Buscar por cliente, ID, dirección...', id: 'qInput', value: st.filters.q })}</div>
      <select id="filterTech" aria-label="Filtrar por técnico" class="sigos-select" style="height:36px">${'<option value="">Todos los técnicos</option>' + state.profiles.map((p) => `<option value="${p.user?.id}" ${String(st.filters.technician_id) === String(p.user?.id) ? 'selected' : ''}>${escapeHtml(p.user?.username || '')}</option>`).join('')}</select>
      <select id="filterZone" aria-label="Filtrar por zona" class="sigos-select" style="height:36px">${'<option value="">Todas las zonas</option>' + ['Zona Norte','Zona Sur','Zona Centro','Zona Industrial','Zona Oeste'].map((z) => `<option value="${z}" ${st.filters.zone === z ? 'selected' : ''}>${z}</option>`).join('')}</select>
      <button type="button" class="sigos-btn-secondary" id="applyFilters" style="height:36px;padding:0 14px">${icon('filter', 14)} Filtros</button>
      ${hasFilters ? '<button type="button" class="sigos-btn-secondary" id="clearFilters" style="height:36px;color:var(--c-danger);border-color:var(--c-danger-border)">Limpiar</button>' : ''}
      <div style="margin-left:auto;font-size:12px;color:var(--c-text-3)">${total === 1 ? '1 resultado' : total + ' resultados'}</div>
    </div>
    <div class="sigos-card" style="overflow:hidden">
      <table class="tbl">
        <thead><tr>${['ID Orden','Cliente','Dirección','Tipo','Técnico','Fecha visita','Estado','Prioridad','Acciones'].map((h) => `<th>${h}</th>`).join('')}</tr></thead>
        <tbody>${rows || '<tr><td colspan="9" class="empty-state__text">Sin resultados</td></tr>'}</tbody>
      </table>
      ${!orders.length ? `<div class="empty-state"><div class="empty-state__icon">${icon('orders', 24)}</div><div class="empty-state__title">Sin resultados</div><div class="empty-state__text">No encontramos órdenes con esos criterios.</div><div class="empty-state__action"><button type="button" class="sigos-btn-secondary" id="clearEmpty">Limpiar filtros</button></div></div>` : ''}
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-top:14px;flex-wrap:wrap;gap:8px">
      <div style="font-size:12px;color:var(--c-text-3)">Mostrando ${orders.length} de ${total} órdenes</div>
      <div style="display:flex;gap:4px">
        <button type="button" class="sigos-btn-secondary" id="prevPage" ${st.page <= 1 ? 'disabled' : ''}>‹</button>
        <span style="padding:6px 10px;font-size:12px">${st.page}</span>
        <button type="button" class="sigos-btn-secondary" id="nextPage" ${st.page * st.pageSize >= total ? 'disabled' : ''}>›</button>
        <select id="pageSize" aria-label="Órdenes por página" class="sigos-select" style="height:32px">${[10,25,50].map((n) => `<option value="${n}" ${st.pageSize === n ? 'selected' : ''}>${n}</option>`).join('')}</select>
      </div>
    </div>`;

  $$('.tab-btn').forEach((b) => b.addEventListener('click', () => { st.filters.status = b.dataset.status; st.page = 1; renderOrders(content, { soft: true }); }));
  $('#applyFilters')?.addEventListener('click', () => {
    st.filters.technician_id = $('#filterTech').value;
    st.filters.zone = $('#filterZone').value;
    st.filters.q = $('#qInput').value.trim();
    st.page = 1;
    renderOrders(content, { soft: true });
  });
  $('#qInput')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') $('#applyFilters').click(); if (e.key === 'Escape') { $('#qInput').value = ''; st.filters.q = ''; renderOrders(content, { soft: true }); } });
  $('#clearFilters')?.addEventListener('click', () => { st.filters = { q: '', status: '', technician_id: '', zone: '', priority: '', type: '', date_from: '', date_to: '', unassigned: false }; st.page = 1; renderOrders(content, { soft: true }); });
  $('#clearEmpty')?.addEventListener('click', () => { st.filters = { q: '', status: '', technician_id: '', zone: '', priority: '', type: '', date_from: '', date_to: '', unassigned: false }; st.page = 1; renderOrders(content, { soft: true }); });
  $('#newOrderBtn')?.addEventListener('click', () => showOrderForm(content));
  $$('[data-detail]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); openOrderDetail(b.dataset.detail, b); }));
  $$('[data-edit]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); showOrderForm(content, Number(b.dataset.edit)); }));
  $$('[data-cancel-order]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); openCancelOrder(Number(b.dataset.cancelOrder), () => renderOrders(content, { soft: true })); }));
  $('#prevPage')?.addEventListener('click', () => { if (st.page > 1) { st.page--; renderOrders(content, { soft: true }); } });
  $('#nextPage')?.addEventListener('click', () => { if (st.page * st.pageSize < total) { st.page++; renderOrders(content, { soft: true }); } });
  $('#pageSize')?.addEventListener('change', (e) => { st.pageSize = Number(e.target.value); st.page = 1; renderOrders(content, { soft: true }); });
  };
  if (soft) swapRows(content, paint);
  else paint();
  // Al volver del detalle, la fila de origen recibe el encabezado (transición inversa).
  if (state._vtReturnId) {
    const row = content.querySelector(`tr[data-vt-card][data-detail="${state._vtReturnId}"]`);
    state._vtReturnId = null;
    if (row && window.sigosVT) window.sigosVT.tagShared(row);
  }
}

// showOrderForm(content, orderId = null): muestra show order form; actualiza el DOM; realiza peticiones de red.
async function showOrderForm(content, orderId = null) {
  let existing = null;
  if (orderId) {
    const r = await api('GET', `/api/v1/work-orders/${orderId}`);
    if (r.ok) existing = r.body;
  }
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.innerHTML = `
    <form class="sigos-card modal-card" id="orderForm">
      <div class="modal-head"><h3 id="modalTitle">${orderId ? 'Editar orden' : 'Nueva orden de servicio'}</h3><button type="button" type="button" id="closeModal" style="background:none;border:none;cursor:pointer;color:var(--c-text-3)" aria-label="Cerrar">${icon('close', 20)}</button></div>
      <div class="modal-body">
        <div class="fld"><label for="fTitle">Título *</label><input class="sigos-input" id="fTitle" required placeholder="Título" value="${escapeHtml(existing?.title || '')}"></div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fCustomer">Cliente</label><input class="sigos-input" id="fCustomer" value="${escapeHtml(existing?.customer_name || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fPhone">Teléfono</label><input class="sigos-input" id="fPhone" value="${escapeHtml(existing?.customer_phone || '')}"></div>
        </div>
        <div class="fld"><label for="fAddress">Dirección</label><input class="sigos-input" id="fAddress" value="${escapeHtml(existing?.address || '')}"></div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fType">Tipo de instalación</label><input class="sigos-input" id="fType" value="${escapeHtml(existing?.installation_type || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fPriority">Prioridad</label><select class="sigos-select" id="fPriority" style="width:100%"><option value="low" ${existing?.priority==='low'?'selected':''}>Baja</option><option value="medium" ${(existing?.priority||'medium')==='medium'?'selected':''}>Media</option><option value="high" ${existing?.priority==='high'?'selected':''}>Alta</option></select></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fZone">Zona</label><input class="sigos-input" id="fZone" value="${escapeHtml(existing?.zone || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fAssign">Técnico</label><select class="sigos-select" id="fAssign" style="width:100%"><option value="">Sin asignar</option>${state.profiles.map((p) => `<option value="${p.user?.id}" ${existing?.assigned_to?.id === p.user?.id ? 'selected' : ''}>${escapeHtml(p.user?.username || '')}</option>`).join('')}</select></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fDate">Fecha visita</label><input class="sigos-input" type="date" id="fDate" value="${existing?.scheduled_at ? existing.scheduled_at.slice(0,10) : ''}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px" for="fTime">Hora</label><input class="sigos-input" type="time" id="fTime" value="${existing?.scheduled_at ? existing.scheduled_at.slice(11,16) : '09:00'}"></div>
        </div>
        <div class="fld"><label for="fNotes">Notas</label><textarea class="sigos-input" id="fNotes" rows="3">${escapeHtml(existing?.description || '')}</textarea></div>
      </div>
      <div class="modal-foot"><button type="button" type="button" class="sigos-btn-secondary" id="cancelForm">Cancelar</button><button type="button" type="button" class="sigos-btn-primary" id="saveOrder">${orderId ? 'Guardar cambios' : 'Crear orden'}</button></div>
    </form>`;
  document.body.appendChild(modal);
  // close(): cierra close; actualiza el DOM.
  const close = () => { document.removeEventListener('keydown', onKey); modal.remove(); };
  // devuelve on key; sin efectos secundarios.
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  $('#closeModal', modal).addEventListener('click', close);
  $('#cancelForm', modal).addEventListener('click', close);
  $('#saveOrder', modal).addEventListener('click', async () => {
    const btn = $('#saveOrder', modal);
    const title = $('#fTitle', modal).value.trim();
    if (!title) { notify('Título requerido', 'error'); return; }
    btn.disabled = true;
    const scheduled = $('#fDate', modal).value ? `${$('#fDate', modal).value}T${$('#fTime', modal).value || '09:00'}:00` : null;
    const body = {
      title,
      description: $('#fNotes', modal).value.trim() || null,
      priority: $('#fPriority', modal).value,
      customer_name: $('#fCustomer', modal).value.trim() || null,
      customer_phone: $('#fPhone', modal).value.trim() || null,
      address: $('#fAddress', modal).value.trim() || null,
      zone: $('#fZone', modal).value.trim() || null,
      installation_type: $('#fType', modal).value.trim() || null,
      scheduled_at: scheduled,
    };
    const assign = $('#fAssign', modal).value;
    if (assign) body.assigned_to_id = Number(assign); else body.assigned_to_id = null;
    let res;
    if (orderId) {
      res = await api('PATCH', `/api/v1/work-orders/${orderId}`, body);
    } else {
      res = await api('POST', '/api/v1/work-orders', body);
    }
    btn.disabled = false; btn.textContent = orderId ? 'Guardar cambios' : 'Crear orden';
    if (!res.ok) { notify(res.body?.error || 'Error al guardar', 'error'); return; }
    notify(orderId ? 'Orden actualizada' : `Orden OS-${String(res.body.id).padStart(4, '0')} creada`, 'success');
    close();
    if (!orderId) {
      state.selectedOrderId = res.body.id;
      state.view = 'order-detail';
      render();
    } else {
      renderOrders(content, { soft: true });
    }
  });
}

// renderiza la vista order detail; actualiza el DOM; comunica con Electron por IPC; realiza peticiones de red.
async function renderOrderDetail(content) {
  content.innerHTML = loaderBlock('Cargando detalle de la orden…', 320);
  const id = state.selectedOrderId;
  const [woRes, histRes, profilesRes] = await Promise.all([
    api('GET', `/api/v1/work-orders/${id}`),
    api('GET', `/api/v1/work-orders/${id}/history`),
    api('GET', '/api/v1/technician-profiles'),
  ]);
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  if (!woRes.ok) { content.innerHTML = `<div style="color:var(--c-danger)">Orden no encontrada</div><div style="margin-top:8px"><button type="button" class="sigos-btn-secondary" id="backBtn">Volver a órdenes</button></div>`; const b = $('#backBtn'); if (b) b.addEventListener('click', () => { state.view = 'orders'; state.selectedOrderId = null; render(); }); return; }
  const wo = woRes.body;
  const history = histRes.ok ? (histRes.body || []) : [];
  const profiles = profilesRes.ok ? (profilesRes.body || []) : [];
  const transitions = {
    pending: ['assigned', 'cancelled'],
    assigned: ['in_progress', 'cancelled'],
    in_progress: ['completed', 'cancelled'],
    completed: [],
    cancelled: [],
  };
  const isManager = hasRole('dispatcher') || hasRole('admin');
  const isTechnician = hasRole('technician');
  if (isTechnician) {
    if (transitions[wo.status]) transitions[wo.status] = transitions[wo.status].filter((x) => x !== 'cancelled');
  }
  const allowed = transitions[wo.status] || [];

  content.innerHTML = `
    <div class="sigos-card" id="odHead" style="padding:16px;margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div style="min-width:0">
          <span class="mono" data-vt="code" style="display:inline-block;font-size:12px;font-weight:600;color:var(--c-primary-ink)">OS-${String(wo.id).padStart(4, '0')}</span>
          <h2 style="margin:2px 0 0;display:flex;align-items:center;gap:10px;flex-wrap:wrap"><span data-vt="title" style="display:inline-block">${escapeHtml(wo.title)}</span> <span data-vt="status" class="${statusOf(wo.status).badge}">${escapeHtml(statusOf(wo.status).label)}</span></h2>
        </div>
        <button type="button" class="sigos-btn-secondary" id="backBtn">Volver</button>
      </div>
      <dl class="od-fields">
        <div><dt>Cliente</dt><dd>${escapeHtml(wo.customer_name || '—')}</dd></div>
        <div><dt>Teléfono</dt><dd>${escapeHtml(wo.customer_phone || '—')}</dd></div>
        <div><dt>Dirección</dt><dd>${escapeHtml(wo.address || '—')}</dd></div>
        <div><dt>Prioridad</dt><dd><span class="${priorityOf(wo.priority || 'medium').badge}">${escapeHtml(priorityOf(wo.priority || 'medium').label)}</span></dd></div>
        <div><dt>Asignado a</dt><dd>${escapeHtml(wo.assigned_to?.username || 'Sin asignar')}</dd></div>
        <div><dt>Creado por</dt><dd>${escapeHtml(wo.created_by?.username || '—')}</dd></div>
        <div class="od-fields__wide"><dt>Descripción</dt><dd>${escapeHtml(wo.description || 'Sin descripción')}</dd></div>
      </dl>
    </div>
    ${visibleActions(hasRole('admin') ? 'admin' : (hasRole('dispatcher') ? 'dispatcher' : 'technician'), wo.status).edit ? `<div class="sigos-card" style="padding:16px;margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h3 style="margin:0">Edición</h3>
        <button type="button" class="sigos-btn-secondary" id="editOrderBtn">Editar</button>
      </div>
      <div id="editPanel" style="display:none">
        <div class="fld"><label for="edType">Tipo de instalación</label><input id="edType" class="sigos-input" value="${escapeHtml(wo.installation_type || '')}"></div>
        <div class="fld"><label for="edTech">Técnico</label><select id="edTech" class="sigos-select" style="width:100%"><option value="">Sin cambios</option>${profiles.filter((p) => p.is_active !== false && p.user?.is_active !== false).map((p) => `<option value="${p.user?.id}" ${wo.assigned_to?.id === p.user?.id ? 'selected' : ''}>${escapeHtml(p.user?.username || p.name || '')}</option>`).join('')}</select></div>
        <div class="fld"><label for="edScheduled">Fecha/hora programada</label><input id="edScheduled" class="sigos-input" type="datetime-local" value="${wo.scheduled_at ? wo.scheduled_at.slice(0,16) : ''}"></div>
        ${hasRole('admin') ? `<div class="fld"><label for="edReason">Motivo *</label><textarea id="edReason" class="sigos-input" rows="2" placeholder="Motivo obligatorio"></textarea></div>` : ''}
        <div style="display:flex;gap:8px;align-items:center;margin-top:8px">
          <button type="button" class="sigos-btn-primary" id="saveEditBtn">Guardar cambios</button>
        </div>
        <div id="editError" style="color:var(--c-danger);font-size:12px;margin-top:4px"></div>
      </div>
    </div>` : ''}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
      <div class="sigos-card" style="padding:16px">
        <h3 style="margin:0 0 8px">Acciones</h3>
${isManager ? `        <div class="fld"><label for="assignSel">Asignar técnico</label>
          <select id="assignSel" class="sigos-select" style="width:100%">
            <option value="">Sin cambios</option>
            ${profiles.map((p) => `<option value="${p.user?.id}" ${wo.assigned_to?.id === p.user?.id ? 'selected' : ''}>${escapeHtml(p.user?.username || '')}</option>`).join('')}
          </select></div>
        <button type="button" class="sigos-btn-secondary" id="assignBtn" style="margin-bottom:12px">Asignar</button>` : ''}
        ${isManager ? `<div class="fld" style="margin-top:8px"><label for="schStart">Programar visita</label>
          <input id="schStart" class="sigos-input" type="datetime-local" value="${wo.scheduled_at ? wo.scheduled_at.slice(0,16) : ''}" style="margin-bottom:6px">
          <input id="schEnd" class="sigos-input" type="datetime-local" value="${wo.scheduled_end ? wo.scheduled_end.slice(0,16) : ''}" style="margin-bottom:6px">
          <select id="schTech" class="sigos-select" style="width:100%;margin-bottom:6px">
            <option value="">Técnico actual</option>
            ${profiles.map((p) => `<option value="${p.user?.id}" ${wo.assigned_to?.id === p.user?.id ? 'selected' : ''}>${escapeHtml(p.user?.username || '')}</option>`).join('')}
          </select>
          <textarea id="schReason" class="sigos-input" rows="2" placeholder="Motivo (si reprograma)"></textarea>
          <button type="button" class="sigos-btn-primary" id="schBtn" style="margin-top:6px">Programar</button>
          <div id="schError" style="color:var(--c-danger);font-size:12px;margin-top:4px"></div>` : ''}
        <div class="fld"><label for="statusSel">Cambiar estado</label>
          <select id="statusSel" class="sigos-select" style="width:100%">
            <option value="">Seleccionar</option>
            ${allowed.map((s) => `<option value="${s}">${escapeHtml(statusOf(s).label)}</option>`).join('')}
          </select></div>
        <div class="fld"><label for="statusNotes">Notas</label><textarea id="statusNotes" class="sigos-input" rows="2"></textarea></div>
        <button type="button" class="sigos-btn-primary" id="statusBtn">Aplicar estado</button>
        ${(isManager && allowed.includes('cancelled')) ? '<button type="button" class="sigos-btn-secondary" id="cancelBtn" style="margin-left:8px;background:var(--c-danger-bg);color:var(--c-danger);border-color:var(--c-danger-border)">Cancelar orden</button>' : ''}
      </div>
      <div class="sigos-card" style="padding:16px">
        <h3 style="margin:0 0 8px">Historial</h3>
        ${history.length ? history.map((h) => `<div style="padding:6px 0;border-bottom:1px solid var(--c-border)">${h.from_status ? `<span class="${statusOf(h.from_status).badge}">${escapeHtml(statusOf(h.from_status).label)}</span> → ` : ''}${h.to_status ? `<span class="${statusOf(h.to_status).badge}">${escapeHtml(statusOf(h.to_status).label)}</span>` : '<span style="font-size:12px;color:var(--c-text-3)">Cambio</span>'} <span style="font-size:12px;color:var(--c-text-3)">${escapeHtml(h.created_at)} por ${escapeHtml(h.changed_by?.username)}</span><div style="font-size:12px;color:var(--c-text-3)">${escapeHtml(h.notes || h.new_value || '')}</div></div>`).join('') : '<div class="empty-state__text">Sin historial</div>'}
      </div>
    </div>
    <div class="sigos-card" style="padding:16px;margin-top:16px">
      <h3 style="margin:0 0 8px">Materiales usados</h3>
      <div id="matList">${loaderBlock('Consultando materiales de la orden…', 80)}</div>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
        <select id="matSel" class="sigos-select" style="flex:1"></select>
        <input id="matQty" class="sigos-input" type="number" min="1" placeholder="Cantidad" style="width:100px">
        <button type="button" class="sigos-btn-secondary" id="matAddBtn">Registrar</button>
      </div>
      <div id="matError" style="color:var(--c-danger);font-size:12px;margin-top:4px"></div>
    </div>
    <div class="sigos-card" style="padding:16px;margin-top:16px">
      <h3 style="margin:0 0 8px">Evidencias</h3>
      <div id="evList">${loaderBlock('Consultando evidencias de la orden…', 80)}</div>
      <div class="fld" style="margin-top:8px"><label for="obsText">Nueva observación</label><textarea id="obsText" class="sigos-input" rows="2"></textarea></div>
      <button type="button" class="sigos-btn-secondary" id="addObs">Agregar observación</button>
      <div class="fld" style="margin-top:8px"><label for="fileInput">Adjuntar archivo</label><input type="file" id="fileInput" class="sigos-input"></div>
      <button type="button" class="sigos-btn-secondary" id="uploadFileBtn">Subir archivo</button>
      <div id="fileError" style="color:var(--c-danger);font-size:12px;margin-top:4px"></div>
    </div>`;

  // Encabezado = destino (y origen al volver) de la transición fila -> detalle.
  window.sigosVT?.tagShared($('#odHead'));
  $('#backBtn').addEventListener('click', () => {
    state._vtReturnId = wo.id; // renderOrders nombra esa fila para que el encabezado vuelva a ella
    state.view = 'orders'; state.selectedOrderId = null;
    render({ transition: 'detail', maxWait: 320 });
  });
  $('#editOrderBtn')?.addEventListener('click', () => {
    const panel = $('#editPanel');
    if (panel) panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  });
  $('#saveEditBtn')?.addEventListener('click', async () => {
    const errEl = $('#editError');
    if (errEl) errEl.textContent = '';
    const btn = $('#saveEditBtn');
    if (btn) btn.disabled = true;
    const isAdmin = hasRole('admin');
    if (isAdmin) {
      const reason = $('#edReason')?.value.trim();
      if (!reason) { if (errEl) errEl.textContent = 'Motivo obligatorio'; if (btn) btn.disabled = false; return; }
    }
    const techVal = $('#edTech')?.value;
    const scheduled = $('#edScheduled')?.value;
    const body = {
      installation_type: $('#edType')?.value.trim() || null,
    };
    if (techVal !== undefined) body.assigned_to_id = techVal ? Number(techVal) : null;
    if (scheduled) body.scheduled_at = scheduled.length === 16 ? scheduled + ':00' : scheduled;
    if (isAdmin) body.reason = $('#edReason').value.trim();
    const res = await api('PATCH', `/api/v1/work-orders/${id}`, body, null, { 'If-Match': String(wo.version) });
    if (btn) btn.disabled = false;
    if (!res.ok) {
      const status = res.status;
      let msg = res.body?.error || res.body?.message || 'Error al guardar';
      if (status === 409 || status === 412) {
        msg = 'Otra persona modificó esta orden';
        if (errEl) errEl.innerHTML = `${escapeHtml(msg)} <button type="button" class="sigos-btn-secondary" id="reloadOrderBtn" style="margin-left:8px">Recargar</button>`;
        const rb = $('#reloadOrderBtn');
        if (rb) rb.addEventListener('click', () => renderOrderDetail(content));
      } else if (status === 422) {
        msg = res.body?.error || res.body?.message || 'Datos inválidos';
        if (errEl) errEl.textContent = msg;
      } else if (status === 403 && (res.body?.code === 'sunday_authorization_required' || String(res.body?.error || '').toLowerCase().includes('sunday'))) {
        msg = 'Se requiere autorización de administrador para programar en domingo o festivo';
        if (errEl) errEl.textContent = msg;
      } else {
        if (String(msg).toLowerCase().includes('schedule_conflict') || String(msg).toLowerCase().includes('solape')) msg = 'Solape de horario del técnico';
        if (String(msg).toLowerCase().includes('invalid_time') || String(msg).toLowerCase().includes('fuera')) msg = 'Fuera de horario laboral';
        if (errEl) errEl.textContent = msg;
      }
      notify(msg, 'error');
      return;
    }
    notify('Cambios guardados', 'success');
    renderOrderDetail(content);
  });
  $('#assignBtn')?.addEventListener('click', async () => {
    const v = $('#assignSel').value;
    const body = { assigned_to_id: v ? Number(v) : null };
    const res = await api('PUT', `/api/v1/work-orders/${id}`, body);
    if (!res.ok) { notify(res.body?.error || 'Error', 'error'); return; }
    notify('Asignación actualizada', 'success');
    renderOrderDetail(content);
  });
  $('#schBtn')?.addEventListener('click', async () => {
    const errEl = $('#schError');
    if (errEl) errEl.textContent = '';
    const start = $('#schStart').value;
    const end = $('#schEnd').value;
    const tech = $('#schTech').value;
    const reason = $('#schReason').value.trim();
    const body = { start, end, version: wo.version };
    if (tech) body.technician_ids = [Number(tech)];
    if (reason) body.reason = reason;
    const res = await api('POST', `/api/v1/work-orders/${id}/schedule`, body);
    if (!res.ok) {
      const msg = res.body?.error || res.body?.message || 'Error al programar';
      if (errEl) errEl.textContent = msg;
      notify(msg, 'error');
      return;
    }
    notify('Visita programada', 'success');
    renderOrderDetail(content);
  });
  $('#statusBtn').addEventListener('click', async () => {
    const to = $('#statusSel').value;
    if (!to) { notify('Selecciona estado', 'error'); return; }
    const res = await api('POST', `/api/v1/work-orders/${id}/status`, { to_status: to, notes: $('#statusNotes').value.trim() || null });
    if (!res.ok) { notify(res.body?.error || 'Transición inválida', 'error'); return; }
    notify('Estado actualizado', 'success');
    renderOrderDetail(content);
  });
  $('#cancelBtn')?.addEventListener('click', () => openCancelOrder(id, () => renderOrderDetail(content)));
  loadEvidences(id);
  loadMaterials(id);
  $('#addObs').addEventListener('click', async () => {
    const desc = $('#obsText').value.trim();
    if (!desc) { notify('Observación vacía', 'error'); return; }
    const res = await api('POST', `/api/v1/work-orders/${id}/evidences`, null, { evidence_type: 'observation', description: desc });
    if (!res.ok) { notify(res.body?.error || 'Error al agregar observación', 'error'); return; }
    notify('Observación agregada', 'success');
    $('#obsText').value = '';
    loadEvidences(id);
  });
  $('#uploadFileBtn')?.addEventListener('click', async () => {
    const input = $('#fileInput');
    const errEl = $('#fileError');
    if (errEl) errEl.textContent = '';
    if (!input || !input.files || !input.files.length) { if (errEl) errEl.textContent = 'Selecciona un archivo'; return; }
    const file = input.files[0];
    const reader = new FileReader();
    reader.onload = async () => {
      const base64 = String(reader.result || '').split(',')[1] || '';
      const res = await ipcTracked('uploadFile', { method: 'POST', path: `/api/v1/work-orders/${id}/evidences`, fields: { evidence_type: 'photo' }, file: { data: base64, name: file.name, type: file.type }, token: state.session?.access_token }, { message: 'Procesando evidencia…' });
      if (!res.ok) { const msg = res.body?.error || 'Archivo rechazado'; if (errEl) errEl.textContent = msg; notify(msg, 'error'); return; }
      notify('Archivo subido', 'success');
      input.value = '';
      loadEvidences(id);
    };
    reader.readAsDataURL(file);
  });
}

// loadMaterials(id): carga load materials; actualiza el DOM; realiza peticiones de red.
async function loadMaterials(id) {
  const el = $('#matList');
  const sel = $('#matSel');
  if (!el) return;
  let matsRes, reqsRes;
  try {
    [matsRes, reqsRes] = await Promise.all([
      api('GET', '/api/v1/materials'),
      api('GET', `/api/v1/work-orders/${id}/material-requests`),
    ]);
  } catch (e) {
    el.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml((e && e.message) || 'Error')}</div><button type="button" class="sigos-btn-secondary" id="retryMaterials" style="margin-top:8px">Reintentar</button>`;
    const rb = $('#retryMaterials');
    if (rb) rb.addEventListener('click', () => loadMaterials(id));
    return;
  }
  if (!matsRes.ok) {
    const msg = matsRes.body?.error || matsRes.body?.message || 'Error al cargar materiales';
    el.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(msg)}</div><button type="button" class="sigos-btn-secondary" id="retryMaterials" style="margin-top:8px">Reintentar</button>`;
    const rb = $('#retryMaterials');
    if (rb) rb.addEventListener('click', () => loadMaterials(id));
    return;
  }
  if (!reqsRes.ok) {
    const msg = reqsRes.body?.error || reqsRes.body?.message || 'Error al cargar materiales';
    el.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(msg)}</div><button type="button" class="sigos-btn-secondary" id="retryMaterials" style="margin-top:8px">Reintentar</button>`;
    const rb = $('#retryMaterials');
    if (rb) rb.addEventListener('click', () => loadMaterials(id));
    return;
  }
  let mats = [], reqs = [];
  try {
    mats = asList(matsRes);
    reqs = asList(reqsRes);
  } catch (e) {
    const msg = (e && e.message) || 'Error al cargar materiales';
    el.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(msg)}</div><button type="button" class="sigos-btn-secondary" id="retryMaterials" style="margin-top:8px">Reintentar</button>`;
    const rb = $('#retryMaterials');
    if (rb) rb.addEventListener('click', () => loadMaterials(id));
    return;
  }
  if (sel) {
    sel.innerHTML = mats.map((m) => `<option value="${m.id}">${escapeHtml(m.name)} (stock ${m.current_stock})</option>`).join('');
  }
  el.innerHTML = reqs.length ? reqs.map((r) => `<div style="padding:4px 0;border-bottom:1px solid var(--c-border)">${escapeHtml(requestStatusLabel(r.status))} - ${escapeHtml(r.reason || '')}</div>`).join('') : '<div class="empty-state__text">Sin materiales registrados</div>';
  const btn = $('#matAddBtn');
  if (btn) btn.addEventListener('click', async () => {
    const matId = $('#matSel').value;
    const qty = Number($('#matQty').value);
    const errEl = $('#matError');
    if (errEl) errEl.textContent = '';
    if (!matId || !qty || qty <= 0) { if (errEl) errEl.textContent = 'Cantidad inválida'; return; }
    const res = await api('POST', `/api/v1/materials/${matId}/movements`, { quantity: qty, movement_type: 'CONSUMPTION', work_order_id: id });
    if (!res.ok) {
      const msg = res.body?.error || res.body?.message || 'Stock insuficiente';
      if (errEl) errEl.textContent = msg;
      notify(msg, 'error');
      return;
    }
    notify('Material registrado', 'success');
    $('#matQty').value = '';
    loadMaterials(id);
  });
}

// loadEvidences(id): carga load evidences; actualiza el DOM; realiza peticiones de red.
async function loadEvidences(id) {
  const res = await api('GET', `/api/v1/work-orders/${id}/evidences`);
  const el = $('#evList');
  if (!el) return;
  if (!res.ok) { el.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const evs = res.body || [];
  el.innerHTML = evs.length ? evs.map((e) => `<div style="padding:4px 0">${escapeHtml(e.evidence_type)} - ${escapeHtml(e.description || e.file_name)} <span style="color:var(--c-text-3);font-size:12px">${escapeHtml(e.created_at)}</span></div>`).join('') : '<div class="empty-state__text">Sin evidencias</div>';
}


// renderiza la vista technicians; actualiza el DOM; realiza peticiones de red.
async function renderTechnicians(content) {
  content.innerHTML = loaderBlock('Cargando información de técnicos…', 320);
  const res = await api('GET', '/api/v1/technicians');
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  if (!res.ok) { content.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const body = res.body || {};
  const techs = body.items || [];
  const counts = body.counts || {};
  const total = body.total || techs.length;

  $('#topbarActions').innerHTML = `<button type="button" class="sigos-btn-primary" id="newTechBtn">${icon('plus', 16)} Nuevo técnico</button>`;

  const summaryHtml = `
    <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px">
      ${[
        { label: 'Disponibles', value: counts.available || 0, color: 'var(--c-text-2)', bg: 'var(--c-surface-2)', icon: 'check_circle' },
        { label: 'Ocupados', value: counts.busy || 0, color: 'var(--c-text-2)', bg: 'var(--c-surface-2)', icon: 'sync' },
        { label: 'Fuera de servicio', value: counts.off_duty || 0, color: 'var(--c-text-2)', bg: 'var(--c-surface-2)', icon: 'cancel' },
        { label: 'Total asignaciones', value: techs.reduce((a, t) => a + (t.open_orders_count || 0), 0), color: 'var(--c-text-2)', bg: 'var(--c-surface-2)', icon: 'orders' },
      ].map((k) => `<div class="sigos-card" style="padding:14px 16px;display:flex;align-items:center;gap:12px"><div style="width:40px;height:40px;border-radius:8px;background:${k.bg};color:${k.color};display:flex;align-items:center;justify-content:center">${icon(k.icon, 20)}</div><div><div style="font-family:Outfit;font-weight:800;font-size:22px;color:var(--c-text)">${k.value}</div><div style="font-size:12px;font-weight:600;color:var(--c-text-2)">${k.label}</div></div></div>`).join('')}
    </div>`;

  const cardsHtml = techs.map((t) => {
    const name = t.name || t.user?.username || '';
    const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
    const avail = t.is_available;
    const bg = 'var(--c-surface-2)';
    const fg = 'var(--c-text-2)';
    const ts = techStatusOf(avail);
    const load = t.open_orders_count || 0;
    const pct = Math.min(100, load * 10);
    const barColor = pct >= 80 ? 'var(--c-warning)' : 'var(--c-primary)';
    return `<div class="sigos-card" style="padding:14px 16px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
        <div style="width:48px;height:48px;border-radius:50%;background:${bg};color:${fg};display:flex;align-items:center;justify-content:center;font-weight:700">${escapeHtml(initials)}</div>
        <div style="flex:1">
          <div style="font-size:14px;font-weight:600;color:var(--c-text)">${escapeHtml(name)}</div>
          <div style="font-size:12px;color:var(--c-text-3)">${escapeHtml(t.specialty || '')} - ${escapeHtml(t.zones || '—')}</div>
        </div>
        <span class="${ts.badge}">${escapeHtml(ts.label)}</span>
      </div>
      <div style="font-size:12px;color:var(--c-text-3);margin-bottom:4px">Tel: ${escapeHtml(t.phone || '—')} - ${load} ordenes abiertas</div>
      <div style="height:6px;background:var(--c-neutral-bg);border-radius:3px;overflow:hidden;margin-bottom:8px"><div style="height:100%;width:${pct}%;background:${barColor};border-radius:3px"></div></div>
      <div style="display:flex;gap:6px">
        <button type="button" class="sigos-btn-secondary" style="font-size:12px;padding:4px 8px" data-view-orders="${t.user?.id}">Ver ordenes</button>
        <button type="button" class="sigos-btn-secondary" style="font-size:12px;padding:4px 8px">Calendario</button>
        <button type="button" class="sigos-btn-secondary" style="font-size:12px;padding:4px 8px" data-edit-tech="${t.id}">Editar</button>
      </div>
    </div>`;
  }).join('');

  const loadBars = techs.map((t) => {
    const name = t.name || t.user?.username || '';
    const load = t.open_orders_count || 0;
    const max = Math.max(...techs.map((x) => x.open_orders_count || 0), 1);
    const pct = Math.round((load / max) * 100);
    return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px"><div style="width:120px;font-size:12px;color:var(--c-text-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(name)}</div><div style="flex:1;height:8px;background:var(--c-neutral-bg);border-radius:4px;overflow:hidden"><div style="height:100%;width:${pct}%;background:var(--c-primary);border-radius:4px"></div></div><div style="font-size:12px;color:var(--c-text-3);width:24px;text-align:right">${load}</div></div>`;
  }).join('');

  content.innerHTML = `
    ${summaryHtml}
    <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:16px">${cardsHtml || '<div class="sigos-card empty-state" style="grid-column:1/-1"><div class="empty-state__icon">' + icon('tech', 24) + '</div><div class="empty-state__title">Aún no hay técnicos</div><div class="empty-state__text">Cree el primero con «Nuevo técnico».</div></div>'}</div>
    <div class="sigos-card" style="padding:14px 16px">
      <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Carga de trabajo comparativa</h3>
      ${loadBars || '<div style="color:var(--c-text-3);font-size:13px">Sin datos</div>'}
    </div>`;

  $('#newTechBtn')?.addEventListener('click', () => showTechForm(content));
  $$('[data-view-orders]').forEach((b) => b.addEventListener('click', () => {
    const uid = b.dataset.viewOrders;
    state.view = 'orders';
    state.ordersState = state.ordersState || { filters: {}, page: 1, pageSize: 10, sort: 'created_at', order: 'desc' };
    state.ordersState.filters = state.ordersState.filters || {};
    state.ordersState.filters.technician_id = uid;
    render({ transition: 'nav' });
  }));
  $$('[data-edit-tech]').forEach((b) => b.addEventListener('click', () => showTechForm(content, Number(b.dataset.editTech))));
}

// showTechForm(content, techId = null): muestra show tech form; actualiza el DOM; realiza peticiones de red.
async function showTechForm(content, techId = null) {
  let existing = null;
  if (techId) {
    const r = await api('GET', `/api/v1/technicians/${techId}`);
    if (r.ok) existing = r.body;
  }
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.innerHTML = `
    <form class="sigos-card modal-card" id="techForm">
      <div class="modal-head"><h3 id="modalTitle">${techId ? 'Editar técnico' : 'Nuevo técnico'}</h3><button type="button" type="button" id="closeModal" style="background:none;border:none;cursor:pointer;color:var(--c-text-3)" aria-label="Cerrar">${icon('close', 20)}</button></div>
      <div class="modal-body">
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px">Nombre *</label><input class="sigos-input" id="tFirst" value="${escapeHtml(existing?.first_name || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px">Apellido *</label><input class="sigos-input" id="tLast" value="${escapeHtml(existing?.last_name || '')}"></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px">Telefono</label><input class="sigos-input" id="tPhone" value="${escapeHtml(existing?.phone || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px">Email</label><input class="sigos-input" id="tEmail" value="${escapeHtml(existing?.email || '')}"></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px">Especialidad *</label><select class="sigos-select" id="tSpec" style="width:100%"><option value="">Seleccionar</option></select></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px">Zonas</label><input class="sigos-input" id="tZones" value="${escapeHtml(existing?.zones || '')}" placeholder="Municipio, sector"></div>
        </div>
        <div class="fld"><label style="display:block;font-size:13px;font-weight:600;color:var(--c-text-2);margin-bottom:5px">Documento</label><input class="sigos-input" id="tDoc" value="${escapeHtml(existing?.document || '')}"></div>
      </div>
      <div class="modal-foot"><button type="button" type="button" class="sigos-btn-secondary" id="cancelTech">Cancelar</button><button type="button" type="button" class="sigos-btn-primary" id="saveTech">${techId ? 'Guardar' : 'Crear'}</button></div>
    </form>`;
  document.body.appendChild(modal);
  // close(): cierra close; actualiza el DOM.
  const close = () => { document.removeEventListener('keydown', onKey); modal.remove(); };
  // devuelve on key; sin efectos secundarios.
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  api('GET', '/api/v1/catalogs/specialties').then((r) => {
    if (r.ok) {
      const sel = $('#tSpec', modal);
      (r.body || []).forEach((s) => {
        const o = document.createElement('option');
        o.value = s.code;
        o.textContent = s.label;
        if (existing?.specialty_code === s.code || existing?.specialty === s.label) o.selected = true;
        sel.appendChild(o);
      });
    }
  });
  $('#closeModal', modal).addEventListener('click', close);
  $('#cancelTech', modal).addEventListener('click', close);
  $('#saveTech', modal).addEventListener('click', async () => {
    const btn = $('#saveTech', modal);
    const first = $('#tFirst', modal).value.trim();
    const last = $('#tLast', modal).value.trim();
    const spec = $('#tSpec', modal).value.trim();
    if (!first || !last || !spec) { notify('Completa los campos obligatorios', 'error'); return; }
    btn.disabled = true;
    const body = {
      first_name: first,
      last_name: last,
      phone: $('#tPhone', modal).value.trim() || null,
      email: $('#tEmail', modal).value.trim() || null,
      specialty_code: $('#tSpec', modal).value,
      zones: $('#tZones', modal).value.trim() || null,
      document: $('#tDoc', modal).value.trim() || null,
    };
    let res;
    if (techId) res = await api('PATCH', `/api/v1/technicians/${techId}`, body);
    else res = await api('POST', '/api/v1/technicians', body);
    btn.disabled = false; btn.textContent = techId ? 'Guardar' : 'Crear';
    if (!res.ok) { notify(res.body?.error || 'Error al guardar', 'error'); return; }
    if (!techId && res.body?.temporary_password) {
      close();
      showCredentials(res.body.username, res.body.temporary_password);
      renderTechnicians(content);
      return;
    }
    notify(techId ? 'Técnico actualizado' : 'Técnico creado', 'success');
    close();
    renderTechnicians(content);
  });
}

// showCredentials(username, password): muestra show credentials; actualiza el DOM.
function showCredentials(username, password) {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="sigos-card modal-card" style="padding:24px">
      <h3 style="margin:0 0 12px;font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav)">Credenciales generadas</h3>
      <div style="margin-bottom:8px"><label>Usuario</label><div style="display:flex;gap:8px"><input class="sigos-input" id="credUser" value="${escapeHtml(username)}" readonly><button type="button" class="sigos-btn-secondary" id="copyUser">Copiar</button></div></div>
      <div style="margin-bottom:12px"><label>Contrasena temporal</label><div style="display:flex;gap:8px"><input class="sigos-input" id="credPass" value="${escapeHtml(password)}" readonly><button type="button" class="sigos-btn-secondary" id="copyPass">Copiar</button></div></div>
      <label style="display:flex;align-items:center;gap:8px;font-size:13px"><input type="checkbox" id="credAck"> Ya guarde las credenciales</label>
      <div class="modal-foot"><button type="button" class="sigos-btn-primary" id="closeCred" disabled>Cerrar</button></div>
    </div>`;
  document.body.appendChild(modal);
  // close(): cierra close; sin efectos secundarios.
  const close = () => modal.remove();
  $('#copyUser', modal).addEventListener('click', () => navigator.clipboard?.writeText(username));
  $('#copyPass', modal).addEventListener('click', () => navigator.clipboard?.writeText(password));
  $('#credAck', modal).addEventListener('change', (e) => { $('#closeCred', modal).disabled = !e.target.checked; });
  $('#closeCred', modal).addEventListener('click', close);
}

// renderiza la vista materials; actualiza el DOM; realiza peticiones de red.
// renderMaterials(content, { soft }): soft = filtro, búsqueda, página o cambio tras un modal. La tabla actual
// se mantiene mientras carga y el cambio se anima como transición de lista (filas con su ID real).
async function renderMaterials(content, opts = {}) {
  if (!state.materialsFilters) state.materialsFilters = { q: '', status: '', unit: '', category: '' };
  if (!state.materialsPage) state.materialsPage = 1;
  const filters = state.materialsFilters;
  const soft = !!opts.soft && !!content.querySelector('table.tbl');
  if (soft) content.setAttribute('aria-busy', 'true');
  else content.innerHTML = loaderBlock('Consultando inventario…', 240);
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  if (filters.status) params.set('status', filters.status);
  if (filters.unit) params.set('unit', filters.unit);
  params.set('page', state.materialsPage);
  params.set('page_size', 20);

  const [matRes, catRes] = await Promise.all([
    api('GET', '/api/v1/materials?' + params.toString()),
    api('GET', '/api/v1/material-categories'),
  ]);
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  content.setAttribute('aria-busy', 'false');
  if (!matRes.ok) {
    const msg = (matRes.body && (matRes.body.message || matRes.body.error)) || 'Error al cargar materiales.';
    content.innerHTML = `<div style="color:var(--c-danger);margin-bottom:8px">${escapeHtml(msg)}</div><button type="button" class="sigos-btn-secondary" id="retryMaterials">Reintentar</button>`;
    const rb = $('#retryMaterials'); if (rb) rb.addEventListener('click', () => renderMaterials(content));
    return;
  }
  const data = matRes.body || {};
  const allItems = data.items || [];
  // client-side category filter (materials include category)
  const items = filters.category ? allItems.filter((m) => m.category === filters.category) : allItems;
  const counts = data.counts || { total: 0, ok: 0, low: 0, critical: 0 };
  const total = data.total || 0;
  const pageSize = data.page_size || 20;
  const currentPage = data.page || 1;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const totalValue = data.total_value || 0;
  const categories = catRes.ok ? (catRes.body || []) : [];
  items.forEach((m) => { if (!m.status) m.status = materialStatus(m.current_stock, m.min_stock).key; });

  const roles = (state.session?.user?.roles || []);
  const canManage = roles.includes('dispatcher');
  const isAdmin = roles.includes('admin');
  const units = Array.from(new Set(items.map((m) => m.unit).filter(Boolean)));

  // devuelve card; sin efectos secundarios.
  const card = (key, label, count, color) => `
    <div class="sigos-card" style="padding:14px;cursor:pointer;border:1px solid ${filters.status === key ? 'var(--c-primary)' : 'var(--c-border)'};box-shadow:${filters.status === key ? 'inset 0 0 0 1px var(--c-primary)' : 'none'}" data-filter-status="${key}" role="button" tabindex="0" aria-pressed="${filters.status === key}">
      <div style="font-size:12px;color:var(--c-text-3)">${label}</div>
      <div style="font-family:Outfit;font-weight:700;font-size:24px;color:${count > 0 && (key === 'low' || key === 'critical') ? color : 'var(--c-text)'}">${count}</div>
    </div>`;

  const paint = () => {
  content.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:12px;flex-wrap:wrap">
      <div>
        <h2 style="font-family:Outfit;font-weight:700;font-size:20px;color:var(--c-nav);margin:0">Inventario de Materiales</h2>
        <div style="font-size:13px;color:var(--c-text-3)">${total} materiales</div>
      </div>
      <div style="display:flex;gap:8px">
        ${isAdmin ? `<button type="button" class="sigos-btn-secondary" id="addCatalogBtn" style="height:36px">Agregar al catálogo</button>` : ''}
        ${canManage ? `<button type="button" class="sigos-btn-primary" id="addMaterialBtn" style="height:36px">${icon('plus',16)} Agregar material</button>` : ''}
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">
      ${card('', 'Total materiales', counts.total, 'var(--c-nav)')}
      ${card('ok', 'Stock OK', counts.ok, 'var(--c-success)')}
      ${card('low', 'Stock bajo', counts.low, 'var(--c-warning)')}
      ${card('critical', 'Nivel crítico', counts.critical, 'var(--c-danger)')}
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap">
      <select id="filterCategory" aria-label="Filtrar por categoría" class="sigos-select" style="height:36px">
        <option value="">Todas las categorías</option>
        ${categories.map((c) => `<option value="${escapeHtml(c.name)}" ${filters.category===c.name?'selected':''}>${escapeHtml(c.name)}</option>`).join('')}
      </select>
      <select id="filterStatus" aria-label="Filtrar por estado" class="sigos-select" style="height:36px">
        <option value="">Todos los estados</option>
        <option value="ok" ${filters.status==='ok'?'selected':''}>OK</option>
        <option value="low" ${filters.status==='low'?'selected':''}>Bajo</option>
        <option value="critical" ${filters.status==='critical'?'selected':''}>Crítico</option>
      </select>
      <select id="filterUnit" aria-label="Filtrar por unidad" class="sigos-select" style="height:36px">
        <option value="">Todas las unidades</option>
        ${units.map((u) => `<option value="${escapeHtml(u)}" ${filters.unit===u?'selected':''}>${escapeHtml(u)}</option>`).join('')}
      </select>
      ${canManage ? `<button type="button" id="exportCsvBtn" class="sigos-btn-secondary" style="height:36px">Exportar CSV</button>` : ''}
    </div>
    <div class="sigos-card" style="overflow:hidden">
      <table class="tbl">
        <thead><tr><th>Código</th><th>Nombre</th><th>Categoría</th><th>Unidad</th><th>Stock</th><th>Mínimo</th><th>Nivel</th><th>Estado</th><th>Precio</th>${canManage?'<th>Acciones</th>':''}</tr></thead>
        <tbody>
          ${items.map((m) => {
            const st = materialStatus(m.current_stock, m.min_stock);
            const pct = stockLevelPct(m.current_stock, m.min_stock);
            const inherited = (m.catalog_item_id == null);
            const cat = inherited ? 'Sin catálogo' : (m.category || '');
            return `<tr class="tbl-row" data-vt-row="mat-${m.id}">
              <td style="font-family:JetBrains Mono,monospace;font-size:12px">${escapeHtml(m.code || '')}</td>
              <td>${escapeHtml(m.name)}${inherited ? ' <span class="badge-pending" style="font-size:10px">Sin catálogo</span>' : ''}</td>
              <td>${escapeHtml(cat)}</td>
              <td>${escapeHtml(m.unit)}</td>
              <td>${m.current_stock}</td>
              <td>${m.min_stock}</td>
              <td style="min-width:120px"><div style="background:var(--c-neutral-bg);border-radius:4px;height:6px;overflow:hidden"><div style="width:${pct}%;background:${st.bar};height:6px"></div></div><div style="font-size:10px;color:var(--c-text-3);margin-top:2px">${pct}%</div></td>
              <td><span class="${st.badge}">${st.label}</span></td>
              <td>${formatCOP(m.unit_price)}</td>
              ${canManage ? `<td style="white-space:nowrap">
                ${inherited ? `
                  <button type="button" class="sigos-btn-secondary" style="height:28px;padding:0 8px" data-link="${m.id}">Vincular</button>
                  <button type="button" class="sigos-btn-secondary" style="height:28px;padding:0 8px;margin-left:4px" data-deactivate="${m.id}">Desactivar</button>
                ` : `
                  <button type="button" class="sigos-btn-secondary" style="height:28px;padding:0 8px" data-edit="${m.id}">Editar</button>
                  <button type="button" class="sigos-btn-primary" style="height:28px;padding:0 8px;margin-left:4px" data-replenish="${m.id}">Reponer</button>
                  <button type="button" class="sigos-btn-secondary" style="height:28px;padding:0 8px;margin-left:4px" data-adjust="${m.id}">Ajustar</button>
                `}
              </td>` : ''}
            </tr>`;
          }).join('') || `<tr><td colspan="${canManage?10:9}" class="empty-state__text">Sin materiales</td></tr>`}
        </tbody>
      </table>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;flex-wrap:wrap;gap:8px">
      <div style="font-size:13px;color:var(--c-text-2)">Valor del inventario: <strong>${formatCOP(totalValue)}</strong></div>
      <div style="display:flex;gap:8px;align-items:center">
        <button type="button" class="sigos-btn-secondary" id="prevPage" ${currentPage<=1?'disabled':''} style="height:32px">‹</button>
        <span style="font-size:12px;color:var(--c-text-3)">Página ${currentPage} de ${totalPages}</span>
        <button type="button" class="sigos-btn-secondary" id="nextPage" ${currentPage>=totalPages?'disabled':''} style="height:32px">›</button>
      </div>
    </div>
  `;

  const gs = $('#globalSearch');
  if (gs) {
    gs.placeholder = 'Buscar materiales por nombre o código…';
    gs.value = filters.q || '';
    // Búsqueda: espera a que se deje de escribir (180 ms) en lugar de recargar en cada tecla.
    gs.oninput = () => {
      clearTimeout(state._matSearchT);
      state._matSearchT = setTimeout(() => { filters.q = gs.value; state.materialsPage = 1; renderMaterials(content, { soft: true }); }, 180);
    };
  }

  $$('[data-filter-status]').forEach((el) => {
    const toggle = () => {
      const key = el.getAttribute('data-filter-status');
      filters.status = (filters.status === key) ? '' : key;
      state.materialsPage = 1;
      renderMaterials(content, { soft: true });
    };
    el.addEventListener('click', toggle);
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
  });

  const fc = $('#filterCategory');
  if (fc) fc.addEventListener('change', () => { filters.category = fc.value; state.materialsPage = 1; renderMaterials(content, { soft: true }); });
  const fsSel = $('#filterStatus');
  if (fsSel) fsSel.addEventListener('change', () => { filters.status = fsSel.value; state.materialsPage = 1; renderMaterials(content, { soft: true }); });
  const fuSel = $('#filterUnit');
  if (fuSel) fuSel.addEventListener('change', () => { filters.unit = fuSel.value; state.materialsPage = 1; renderMaterials(content, { soft: true }); });

  const prev = $('#prevPage'); if (prev) prev.addEventListener('click', () => { if (state.materialsPage > 1) { state.materialsPage--; renderMaterials(content, { soft: true }); } });
  const next = $('#nextPage'); if (next) next.addEventListener('click', () => { if (state.materialsPage < totalPages) { state.materialsPage++; renderMaterials(content, { soft: true }); } });

  const addBtn = $('#addMaterialBtn');
  if (addBtn) addBtn.addEventListener('click', () => openMaterialModal(content));
  const addCatBtn = $('#addCatalogBtn');
  if (addCatBtn) addCatBtn.addEventListener('click', () => openAddCatalogModal(content));
  const exportBtn = $('#exportCsvBtn');
  if (exportBtn) exportBtn.addEventListener('click', () => openExportModal(content, filters));

  $$('[data-edit]').forEach((b) => b.addEventListener('click', () => openMaterialModal(content, Number(b.getAttribute('data-edit')))));
  $$('[data-replenish]').forEach((b) => b.addEventListener('click', () => openReplenishModal(content, Number(b.getAttribute('data-replenish')))));
  $$('[data-adjust]').forEach((b) => b.addEventListener('click', () => openAdjustModal(content, Number(b.getAttribute('data-adjust')))));
  $$('[data-link]').forEach((b) => b.addEventListener('click', () => openLinkCatalogModal(content, Number(b.getAttribute('data-link')))));
  $$('[data-deactivate]').forEach((b) => b.addEventListener('click', async () => {
    if (!(await confirmDialog('El material dejará de estar disponible para nuevos movimientos.', { title: '¿Desactivar este material?', confirmLabel: 'Desactivar', danger: true }))) return;
    const r = await api('PUT', '/api/v1/materials/' + Number(b.getAttribute('data-deactivate')), { is_active: false });
    if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return; }
    notify('Material desactivado.', 'success');
    renderMaterials(content, { soft: true });
    updateMenuBadge();
  }));
  };
  if (soft) swapRows(content, paint);
  else paint();
}


// openAddCatalogModal(content): abre open add catalog modal; actualiza el DOM; realiza peticiones de red.
async function openAddCatalogModal(content) {
  const [catRes, unitRes] = await Promise.all([
    api('GET', '/api/v1/material-categories'),
    api('GET', '/api/v1/material-units'),
  ]);
  const categories = catRes.ok ? (catRes.body || []) : [];
  const units = unitRes.ok ? (unitRes.body || []) : [];
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
  overlay.innerHTML = `
    <div class="sigos-card" style="width:520px;max-width:95vw;padding:20px;max-height:90vh;overflow:auto">
      <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">Agregar al catálogo</h3>
      <div class="fld"><label for="cCat">Categoría *</label><select class="sigos-input" id="cCat">${categories.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('')}</select></div>
      <div class="fld"><label for="cCode">Código *</label><input class="sigos-input" id="cCode"></div>
      <div class="fld"><label for="cName">Nombre *</label><input class="sigos-input" id="cName" data-upper></div>
      <div class="fld"><label for="cUnit">Unidad *</label><select class="sigos-input" id="cUnit">${units.map((u) => `<option value="${u.id}">${escapeHtml(u.name)} (${escapeHtml(u.code)})</option>`).join('')}</select></div>
      <div class="fld"><label for="cMeasure">Medida</label><input class="sigos-input" id="cMeasure" data-upper></div>
      <div class="fld"><label for="cStage">Etapa</label><input class="sigos-input" id="cStage" data-upper></div>
      <div class="fld"><label for="cApplies">Aplica a</label><input class="sigos-input" id="cApplies" data-upper value="todos"></div>
      <div id="cWarn" style="color:var(--c-danger);font-size:12px;margin:8px 0"></div>
      <div id="cSimilar" style="color:var(--c-text-3);font-size:12px;margin:8px 0"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button type="button" class="sigos-btn-secondary" id="cCancel">Cancelar</button>
        <button type="button" class="sigos-btn-primary" id="cSave">Guardar</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  // close(): cierra close; sin efectos secundarios.
  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#cCancel').addEventListener('click', close);
  $('#cSave').addEventListener('click', async () => {
    const payload = {
      category_id: Number($('#cCat').value),
      code: $('#cCode').value.trim(),
      name: $('#cName').value.trim(),
      unit_id: Number($('#cUnit').value),
      measure: $('#cMeasure').value.trim() || null,
      stage: $('#cStage').value.trim() || null,
      applies_to: $('#cApplies').value.trim() || 'todos',
    };
    const r = await api('POST', '/api/v1/material-catalog', payload);
    if (!r.ok) {
      const msg = (r.body && (r.body.message || r.body.error)) || 'Error';
      $('#cWarn').textContent = msg;
      return;
    }
    if (r.body && r.body.similar && r.body.similar.length) {
      $('#cSimilar').textContent = 'Nombres similares: ' + r.body.similar.join(', ');
    }
    close();
    notify('Elemento agregado al catálogo.', 'success');
    renderMaterials(content, { soft: true });
  });
}

// openLinkCatalogModal(content, matId): abre open link catalog modal; actualiza el DOM; realiza peticiones de red.
async function openLinkCatalogModal(content, matId) {
  const [matRes, catalogRes] = await Promise.all([
    api('GET', '/api/v1/materials/' + matId),
    api('GET', '/api/v1/material-catalog?available=true'),
  ]);
  if (!matRes.ok) { notify('No se pudo cargar el material.', 'error'); return; }
  const mat = matRes.body;
  const catalog = catalogRes.ok ? (catalogRes.body || []) : [];
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
  overlay.innerHTML = `
    <div class="sigos-card" style="width:520px;max-width:95vw;padding:20px;max-height:90vh;overflow:auto">
      <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">Vincular a catálogo</h3>
      <div style="font-size:13px;color:var(--c-text-3);margin-bottom:8px">${escapeHtml(mat.name)} · stock: ${mat.current_stock}</div>
      <div class="fld"><label for="linkSearch">Buscar material</label><input class="sigos-input" id="linkSearch" data-upper placeholder="Buscar..."></div>
      <select class="sigos-input" id="linkCatalog" size="8" style="height:180px">
        ${catalog.map((c) => `<option value="${c.id}">${escapeHtml(c.code)} — ${escapeHtml(c.name)}</option>`).join('')}
      </select>
      <div id="linkWarn" style="color:var(--c-danger);font-size:12px;margin:8px 0"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button type="button" class="sigos-btn-secondary" id="linkCancel">Cancelar</button>
        <button type="button" class="sigos-btn-primary" id="linkSave">Vincular</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  // close(): cierra close; sin efectos secundarios.
  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#linkCancel').addEventListener('click', close);
  const searchInput = $('#linkSearch');
  const sel = $('#linkCatalog');
  if (searchInput && sel) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.trim().toLowerCase();
      Array.from(sel.options).forEach((opt) => {
        const item = catalog.find((c) => String(c.id) === opt.value);
        const hay = ((item?.code || '') + ' ' + (item?.name || '')).toLowerCase();
        opt.style.display = !q || hay.includes(q) ? '' : 'none';
      });
    });
  }
  $('#linkSave').addEventListener('click', async () => {
    const cid = Number(sel.value);
    if (!cid) { $('#linkWarn').textContent = 'Selecciona un material.'; return; }
    if (!(await confirmDialog('Se conservarán el stock y los movimientos.', { title: '¿Vincular este material al catálogo?', confirmLabel: 'Vincular' }))) return;
    const r = await api('PUT', '/api/v1/materials/' + matId, { catalog_item_id: cid });
    if (!r.ok) { $('#linkWarn').textContent = (r.body && (r.body.message || r.body.error)) || 'Error'; return; }
    close();
    notify('Material vinculado.', 'success');
    renderMaterials(content, { soft: true });
    updateMenuBadge();
  });
}


// openMaterialModal(content, matId): abre open material modal; actualiza el DOM; realiza peticiones de red.
async function openMaterialModal(content, matId) {
  const isEdit = !!matId;
  let mat = null;
  if (isEdit) {
    const r = await api('GET', '/api/v1/materials/' + matId);
    if (r.ok) mat = r.body;
  }
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
  overlay.innerHTML = `
    <div class="sigos-card" style="width:480px;max-width:95vw;padding:20px">
      <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">${isEdit ? 'Editar material' : 'Agregar material'}</h3>
      <div class="fld"><label for="mName">Nombre *</label><input class="sigos-input" id="mName" data-upper value="${escapeHtml(mat?.name || '')}"></div>
      <div class="fld"><label for="mCode">Código *</label><input class="sigos-input" id="mCode" value="${escapeHtml(mat?.code || '')}" ${isEdit?'disabled':''}></div>
      <div class="fld"><label for="mUnit">Unidad *</label><select class="sigos-input" id="mUnit"><option value="pza" ${(mat?.unit==='pza')?'selected':''}>pza</option><option value="lt" ${(mat?.unit==='lt')?'selected':''}>lt</option><option value="m" ${(mat?.unit==='m')?'selected':''}>m</option><option value="kg" ${(mat?.unit==='kg')?'selected':''}>kg</option></select></div>
      ${!isEdit ? `<div class="fld"><label for="mStock">Stock inicial</label><input type="number" class="sigos-input" id="mStock" value="0" min="0"></div>` : ''}
      <div class="fld"><label for="mMin">Mínimo</label><input type="number" class="sigos-input" id="mMin" value="${mat?.min_stock ?? 0}" min="0"></div>
      <div class="fld"><label for="mPrice">Precio (COP)</label><input type="number" class="sigos-input" id="mPrice" value="${mat?.unit_price ?? 0}" min="0"></div>
      ${isEdit ? `<div class="fld"><label><input type="checkbox" id="mActive" ${mat?.is_active?'checked':''}> Activo</label></div>` : ''}
      <div id="mWarn" style="color:var(--c-danger);font-size:12px;margin:8px 0"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button type="button" class="sigos-btn-secondary" id="mCancel">Cancelar</button>
        <button type="button" class="sigos-btn-primary" id="mSave">Guardar</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  // close(): cierra close; sin efectos secundarios.
  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#mCancel').addEventListener('click', close);
  $('#mSave').addEventListener('click', async () => {
    const min = Number($('#mMin').value || 0);
    if (min === 0) {
      if (!(await confirmDialog('Este material nunca generará alertas de stock.', { title: '¿Continuar sin stock mínimo?', confirmLabel: 'Continuar' }))) return;
    }
    const payload = {
      name: $('#mName').value.trim(),
      code: $('#mCode').value.trim(),
      unit: $('#mUnit').value,
      min_stock: min,
      unit_price: Number($('#mPrice').value || 0),
    };
    if (!isEdit) {
      payload.current_stock = Number($('#mStock').value || 0);
    } else {
      payload.is_active = !!$('#mActive').checked;
    }
    const url = isEdit ? ('/api/v1/materials/' + matId) : '/api/v1/materials';
    const method = isEdit ? 'PUT' : 'POST';
    const r = await api(method, url, payload);
    if (!r.ok) { $('#mWarn').textContent = (r.body && (r.body.message || r.body.error)) || 'Error'; return; }
    close();
    notify(isEdit ? 'Material actualizado.' : 'Material creado.', 'success');
    state.materialsPage = 1;
    renderMaterials(content, { soft: true });
    updateMenuBadge();
  });
}

// openReplenishModal(content, matId): abre open replenish modal; actualiza el DOM; realiza peticiones de red.
async function openReplenishModal(content, matId) {
  const r = await api('GET', '/api/v1/materials/' + matId);
  if (!r.ok) { notify('No se pudo cargar el material.', 'error'); return; }
  const mat = r.body;
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
  overlay.innerHTML = `
    <div class="sigos-card" style="width:420px;max-width:95vw;padding:20px">
      <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">Reponer stock</h3>
      <div style="font-size:13px;color:var(--c-text-3);margin-bottom:8px">${escapeHtml(mat.name)} · stock actual: ${mat.current_stock} ${escapeHtml(mat.unit)}</div>
      <div class="fld"><label for="repQty">Cantidad a ingresar</label><input type="number" class="sigos-input" id="repQty" min="1" value="1"></div>
      <div class="fld"><label for="repNotes">Motivo</label><input class="sigos-input" id="repNotes" data-upper placeholder="Compra, devolución..."></div>
      <div id="repResult" style="font-size:12px;color:var(--c-text-2);margin:8px 0"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button type="button" class="sigos-btn-secondary" id="repCancel">Cancelar</button>
        <button type="button" class="sigos-btn-primary" id="repSave">Confirmar</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  // close(): cierra close; sin efectos secundarios.
  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#repCancel').addEventListener('click', close);
  // updateResult(): actualiza update result; sin efectos secundarios.
  const updateResult = () => {
    const q = Number($('#repQty').value || 0);
    $('#repResult').textContent = 'Stock resultante: ' + (Number(mat.current_stock) + q) + ' ' + mat.unit;
  };
  $('#repQty').addEventListener('input', updateResult);
  updateResult();
  $('#repSave').addEventListener('click', async () => {
    const qty = Number($('#repQty').value || 0);
    if (qty <= 0) { notify('Cantidad inválida.', 'error'); return; }
    const r = await api('POST', '/api/v1/materials/' + matId + '/movements', { quantity: qty, movement_type: 'IN', notes: $('#repNotes').value.trim() || 'Reposición' });
    if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return; }
    close();
    notify('Stock repuesto.', 'success');
    renderMaterials(content, { soft: true });
    updateMenuBadge();
  });
}

// openAdjustModal(content, matId): abre open adjust modal; actualiza el DOM; realiza peticiones de red.
async function openAdjustModal(content, matId) {
  const r = await api('GET', '/api/v1/materials/' + matId);
  if (!r.ok) { notify('No se pudo cargar el material.', 'error'); return; }
  const mat = r.body;
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
  overlay.innerHTML = `
    <div class="sigos-card" style="width:420px;max-width:95vw;padding:20px">
      <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">Ajustar stock (conteo físico)</h3>
      <div style="font-size:13px;color:var(--c-text-3);margin-bottom:8px">${escapeHtml(mat.name)} · stock actual: ${mat.current_stock} ${escapeHtml(mat.unit)}</div>
      <div class="fld"><label for="adjCount">Nuevo conteo físico</label><input type="number" class="sigos-input" id="adjCount" min="0" value="${mat.current_stock}"></div>
      <div class="fld"><label for="adjReason">Motivo (obligatorio)</label><input class="sigos-input" id="adjReason" data-upper placeholder="Inventario físico..."></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button type="button" class="sigos-btn-secondary" id="adjCancel">Cancelar</button>
        <button type="button" class="sigos-btn-primary" id="adjSave">Confirmar</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  // close(): cierra close; sin efectos secundarios.
  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#adjCancel').addEventListener('click', close);
  $('#adjSave').addEventListener('click', async () => {
    const newCount = Number($('#adjCount').value || 0);
    const reason = $('#adjReason').value.trim();
    if (!reason) { notify('Motivo obligatorio.', 'error'); return; }
    const delta = newCount - Number(mat.current_stock);
    if (delta === 0) { notify('Sin cambios.', 'info'); close(); return; }
    const r = await api('POST', '/api/v1/materials/' + matId + '/movements', { quantity: delta, movement_type: 'ADJUSTMENT', notes: reason });
    if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return; }
    close();
    notify('Stock ajustado.', 'success');
    renderMaterials(content, { soft: true });
    updateMenuBadge();
  });
}

// openExportModal(content, filters): abre open export modal; actualiza el DOM; comunica con Electron por IPC; realiza peticiones de red.
async function openExportModal(content, filters) {
  const columns = [
    { key: 'codigo', label: 'Código' },
    { key: 'nombre', label: 'Nombre' },
    { key: 'categoria', label: 'Categoría' },
    { key: 'unidad', label: 'Unidad' },
    { key: 'stock', label: 'Stock' },
    { key: 'minimo', label: 'Mínimo' },
    { key: 'nivel', label: 'Nivel' },
    { key: 'estado', label: 'Estado' },
    { key: 'precio', label: 'Precio' },
    { key: 'valor', label: 'Valor' },
    { key: 'activo', label: 'Activo' },
  ];
  let selectedCols = ['codigo','nombre','categoria','unidad','stock','minimo','estado','precio','valor'];
  let format = 'csv';
  let separator = ';';
  let orientation = 'landscape';
  let previewData = null; // snapshot bytes/text
  let previewKind = null;

  const chips = [];
  if (filters.q) chips.push('Búsqueda: ' + filters.q);
  if (filters.status) chips.push('Estado: ' + filters.status);
  if (filters.unit) chips.push('Unidad: ' + filters.unit);
  if (filters.category) chips.push('Categoría: ' + filters.category);

  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
  overlay.innerHTML = `
    <div class="sigos-card" style="width:760px;max-width:96vw;padding:20px;max-height:92vh;overflow:auto">
      <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">Exportar inventario</h3>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">${chips.map((c) => `<span class="badge-medium" style="font-size:11px">${escapeHtml(c)}</span>`).join('') || '<span style="font-size:12px;color:var(--c-text-3)">Sin filtros</span>'}</div>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <label style="font-size:13px"><input type="radio" name="fmt" value="csv" checked> CSV</label>
        <label style="font-size:13px"><input type="radio" name="fmt" value="excel"> Excel</label>
        <label style="font-size:13px"><input type="radio" name="fmt" value="pdf"> PDF</label>
      </div>
      <div id="fmtOpts" style="margin-bottom:12px"></div>
      <div style="margin-bottom:12px">
        <div style="font-size:13px;font-weight:600;margin-bottom:4px">Columnas</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px">
          ${columns.map((c) => `<label style="font-size:12px"><input type="checkbox" data-col="${c.key}" ${selectedCols.includes(c.key)?'checked':''}> ${escapeHtml(c.label)}</label>`).join('')}
        </div>
      </div>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <button type="button" class="sigos-btn-secondary" id="previewBtn" style="height:32px">Vista previa</button>
        <button type="button" class="sigos-btn-primary" id="downloadBtn" style="height:32px" disabled>Descargar</button>
        <span id="rowCount" style="font-size:12px;color:var(--c-text-3);align-self:center"></span>
      </div>
      <div id="previewArea" style="border:1px solid var(--c-border);border-radius:6px;padding:8px;min-height:120px;max-height:320px;overflow:auto;font-size:12px"></div>
      <div id="exportWarn" style="color:var(--c-danger);font-size:12px;margin-top:8px"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button type="button" class="sigos-btn-secondary" id="exportCancel">Cerrar</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  // close(): cierra close; sin efectos secundarios.
  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#exportCancel').addEventListener('click', close);

  // getFormat(): obtiene get format; actualiza el DOM.
  const getFormat = () => (overlay.querySelector('input[name="fmt"]:checked') || {}).value || 'csv';
  // getColumns(): obtiene get columns; actualiza el DOM.
  const getColumns = () => Array.from(overlay.querySelectorAll('input[data-col]:checked')).map((i) => i.getAttribute('data-col'));
  // buildQuery(extra = {}): construye build query; sin efectos secundarios.
  const buildQuery = (extra = {}) => {
    const p = new URLSearchParams();
    if (filters.q) p.set('q', filters.q);
    if (filters.status) p.set('status', filters.status);
    if (filters.unit) p.set('unit', filters.unit);
    if (filters.category) p.set('category', filters.category);
    p.set('columns', getColumns().join(','));
    p.set('format', format);
    if (format === 'csv') p.set('separator', separator);
    if (format === 'pdf') p.set('orientation', orientation);
    Object.entries(extra).forEach(([k,v]) => p.set(k,v));
    return p.toString();
  };

  // renderiza la vista opts; actualiza el DOM.
  const renderOpts = () => {
    format = getFormat();
    const opts = $('#fmtOpts');
    if (!opts) return;
    if (format === 'csv') {
      opts.innerHTML = `<label style="font-size:12px">Separador: <select id="sepSel" class="sigos-select" style="height:28px"><option value=";" ${separator===';'?'selected':''}>; (punto y coma)</option><option value="," ${separator===','?'selected':''}>, (coma)</option></select></label>`;
      const s = $('#sepSel'); if (s) s.addEventListener('change', () => { separator = s.value; });
    } else if (format === 'pdf') {
      opts.innerHTML = `<label style="font-size:12px">Orientación: <select id="oriSel" class="sigos-select" style="height:28px"><option value="landscape" ${orientation==='landscape'?'selected':''}>Horizontal</option><option value="portrait" ${orientation==='portrait'?'selected':''}>Vertical</option></select></label>`;
      const o = $('#oriSel'); if (o) o.addEventListener('change', () => { orientation = o.value; });
    } else {
      opts.innerHTML = '';
    }
  };
  overlay.querySelectorAll('input[name="fmt"]').forEach((r) => r.addEventListener('change', () => { renderOpts(); previewData = null; $('#downloadBtn').disabled = true; }));
  renderOpts();

  // showPreview(data): muestra show preview; actualiza el DOM.
  const showPreview = (data) => {
    const area = $('#previewArea');
    if (!area) return;
    if (format === 'csv') {
      area.innerHTML = `<pre style="margin:0;white-space:pre-wrap">${escapeHtml(data.content || '')}</pre>`;
    } else if (format === 'excel') {
      const headers = data.headers || [];
      const rows = data.rows || [];
      area.innerHTML = `<div style="font-size:11px;color:var(--c-text-3);margin-bottom:4px">Pestaña Inventario (vista previa)</div>
        <table class="tbl" style="font-size:11px"><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map((r) => `<tr>${r.map((v) => `<td>${escapeHtml(String(v))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    } else if (format === 'pdf') {
      area.innerHTML = `<iframe src="data:application/pdf;base64,${data.content_base64}" style="width:100%;height:300px;border:none"></iframe>`;
    }
    const rc = $('#rowCount');
    if (rc) rc.textContent = (data.total_rows != null ? data.total_rows : (data.rows ? data.rows.length : '')) + ' filas';
    if (data.truncated) {
      const w = $('#exportWarn'); if (w) w.textContent = 'Se alcanzó el límite de filas. La descarga incluirá hasta el límite.';
    }
  };

  $('#previewBtn').addEventListener('click', async () => {
    format = getFormat();
    selectedCols = getColumns();
    const warn = $('#exportWarn'); if (warn) warn.textContent = '';
    const area = $('#previewArea'); if (area) area.innerHTML = loaderBlock('Preparando vista previa…', 120);
    const r = await api('GET', '/api/v1/materials/export/preview?' + buildQuery());
    if (!r.ok) {
      if (area) area.innerHTML = '';
      const msg = (r.body && (r.body.message || r.body.error)) || 'Error';
      if (warn) warn.textContent = msg;
      return;
    }
    previewData = r.body;
    previewKind = format;
    showPreview(r.body);
    // fetch full bytes for download snapshot by calling download? We'll store a flag; download will fetch same with limit none.
    $('#downloadBtn').disabled = false;
  });

  $('#downloadBtn').addEventListener('click', async () => {
    if (!previewData) { notify('Genera la vista previa primero.', 'error'); return; }
    format = getFormat();
    selectedCols = getColumns();
    const btn = $('#downloadBtn');
    const params = buildQuery();
    const defaultName = 'inventario.' + (format === 'excel' ? 'xlsx' : format === 'pdf' ? 'pdf' : 'csv');
    const exportMsg = format === 'excel' ? 'Preparando archivo XLSX…' : format === 'pdf' ? 'Generando documento PDF…' : 'Exportando información…';
    const r = await ipcTracked('exportDownload', { query: params, defaultName, token: state.session?.access_token }, { mode: btn ? 'button' : undefined, target: btn, message: exportMsg });
    if (!r || r.canceled) { return; }
    if (!r.ok) { notify((r.error) || 'Error al descargar.', 'error'); return; }
    notify('Archivo guardado: ' + r.path, 'success');
    const ofBtn = document.createElement('button');
    ofBtn.className = 'sigos-btn-secondary';
    ofBtn.style.cssText = 'height:28px;margin-left:8px';
    ofBtn.textContent = 'Abrir carpeta';
    ofBtn.addEventListener('click', async () => { await window.sigos.openFolder(r.path); });
    const alerts = $('#alerts') || $('#content');
    if (alerts) alerts.prepend(ofBtn);
  });
}


// renderiza la vista requests; actualiza el DOM; realiza peticiones de red.
// Estados de solicitudes de material: la API usa códigos en inglés; la interfaz muestra estas etiquetas.
const REQUEST_STATUS = {
  DRAFT: ['Borrador', 'badge-medium'],
  SUBMITTED: ['Enviada', 'badge-pending'],
  APPROVED: ['Aprobada', 'badge-completed'],
  PARTIALLY_APPROVED: ['Aprobada parcialmente', 'badge-pending'],
  REJECTED: ['Rechazada', 'badge-cancelled'],
  PARTIALLY_DELIVERED: ['Entregada parcialmente', 'badge-pending'],
  DELIVERED: ['Entregada', 'badge-completed'],
  CANCELLED: ['Cancelada', 'badge-cancelled'],
};
const requestStatusLabel = (st) => (REQUEST_STATUS[st] ? REQUEST_STATUS[st][0] : String(st || ''));

// renderRequests(content, { soft }): soft = filtro o página; mantiene la tabla mientras carga y anima la lista.
async function renderRequests(content, opts = {}) {
  if (!state.requestsFilters) state.requestsFilters = { status: '', work_order_id: '', mine: false };
  if (!state.requestsPage) state.requestsPage = 1;
  const filters = state.requestsFilters;
  const soft = !!opts.soft && !!content.querySelector('table.tbl');
  if (soft) content.setAttribute('aria-busy', 'true');
  else content.innerHTML = loaderBlock('Consultando solicitudes…', 240);
  const roles = (state.session?.user?.roles || []);
  const isAdmin = roles.includes('admin');
  const isDispatcher = roles.includes('dispatcher');
  const canManage = isAdmin || isDispatcher;
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.work_order_id) params.set('work_order_id', filters.work_order_id);
  if (filters.mine && !canManage) params.set('mine', 'true');
  params.set('page', state.requestsPage);
  params.set('page_size', 20);
  const res = await api('GET', '/api/v1/material-requests?' + params.toString());
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  content.setAttribute('aria-busy', 'false');
  if (!res.ok) {
    const msg = (res.body && (res.body.message || res.body.error)) || 'Error al cargar solicitudes.';
    content.innerHTML = `<div style="color:var(--c-danger);margin-bottom:8px">${escapeHtml(msg)}</div><button type="button" class="sigos-btn-secondary" id="retryReq">Reintentar</button>`;
    const rb = $('#retryReq'); if (rb) rb.addEventListener('click', () => renderRequests(content));
    return;
  }
  const data = res.body || {};
  const items = data.items || [];
  const total = data.total || 0;
  const pageSize = data.page_size || 20;
  const currentPage = data.page || 1;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // devuelve status badge; sin efectos secundarios.
  const statusBadge = (st) => {
    const map = { DRAFT:'badge-medium', SUBMITTED:'badge-pending', APPROVED:'badge-completed', PARTIALLY_APPROVED:'badge-pending', REJECTED:'badge-cancelled', PARTIALLY_DELIVERED:'badge-pending', DELIVERED:'badge-completed', CANCELLED:'badge-cancelled' };
    return `<span class="${(REQUEST_STATUS[st] || [])[1] || map[st] || ''}">${escapeHtml(requestStatusLabel(st))}</span>`;
  };

  const paint = () => {
  content.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:12px;flex-wrap:wrap">
      <div>
        <h2 style="font-family:Outfit;font-weight:700;font-size:20px;color:var(--c-nav);margin:0">Solicitudes de materiales</h2>
        <div style="font-size:13px;color:var(--c-text-3)">${total} solicitudes</div>
      </div>
      <button type="button" class="sigos-btn-primary" id="newReqBtn" style="height:36px">${icon('plus',16)} Nueva solicitud</button>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <select id="reqStatus" aria-label="Filtrar solicitudes por estado" class="sigos-select" style="height:36px">
        <option value="">Todos los estados</option>
        ${['DRAFT','SUBMITTED','APPROVED','PARTIALLY_APPROVED','REJECTED','PARTIALLY_DELIVERED','DELIVERED','CANCELLED'].map((s) => `<option value="${s}" ${filters.status===s?'selected':''}>${requestStatusLabel(s)}</option>`).join('')}
      </select>
      <input class="sigos-input" id="reqWo" aria-label="Filtrar por número de orden de trabajo" placeholder="Orden de trabajo ID" value="${escapeHtml(filters.work_order_id)}" style="height:36px;width:180px">
      ${!canManage ? `<label style="font-size:12px;align-self:center"><input type="checkbox" id="reqMine" ${filters.mine?'checked':''}> Solo mías</label>` : ''}
    </div>
    <div class="sigos-card" style="overflow:hidden">
      <table class="tbl">
        <thead><tr><th>Código</th><th>Orden</th><th>Solicitante</th><th>Fecha</th><th>Materiales</th><th>Estado</th><th>Acciones</th></tr></thead>
        <tbody>
          ${items.map((r) => `<tr class="tbl-row" data-vt-row="req-${r.id}">
            <td style="font-family:JetBrains Mono,monospace;font-size:12px">${r.id}</td>
            <td>${r.work_order_id || '-'}</td>
            <td>${escapeHtml(r.requester?.username || '')}</td>
            <td style="font-size:12px;color:var(--c-text-3)">${escapeHtml((r.created_at || '').slice(0,10))}</td>
            <td>${(r.items || []).length}</td>
            <td>${statusBadge(r.status)}</td>
            <td><button type="button" class="sigos-btn-secondary" style="height:28px;padding:0 8px" data-viewreq="${r.id}">Ver</button></td>
          </tr>`).join('') || `<tr><td colspan="7" class="empty-state__text">Sin solicitudes</td></tr>`}
        </tbody>
      </table>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
      <div></div>
      <div style="display:flex;gap:8px;align-items:center">
        <button type="button" class="sigos-btn-secondary" id="prevReq" ${currentPage<=1?'disabled':''} style="height:32px">‹</button>
        <span style="font-size:12px;color:var(--c-text-3)">Página ${currentPage} de ${totalPages}</span>
        <button type="button" class="sigos-btn-secondary" id="nextReq" ${currentPage>=totalPages?'disabled':''} style="height:32px">›</button>
      </div>
    </div>
  `;

  const rs = $('#reqStatus'); if (rs) rs.addEventListener('change', () => { filters.status = rs.value; state.requestsPage = 1; renderRequests(content, { soft: true }); });
  const rwo = $('#reqWo'); if (rwo) rwo.addEventListener('change', () => { filters.work_order_id = rwo.value.trim(); state.requestsPage = 1; renderRequests(content, { soft: true }); });
  const rm = $('#reqMine'); if (rm) rm.addEventListener('change', () => { filters.mine = rm.checked; state.requestsPage = 1; renderRequests(content, { soft: true }); });
  const prev = $('#prevReq'); if (prev) prev.addEventListener('click', () => { if (state.requestsPage > 1) { state.requestsPage--; renderRequests(content, { soft: true }); } });
  const next = $('#nextReq'); if (next) next.addEventListener('click', () => { if (state.requestsPage < totalPages) { state.requestsPage++; renderRequests(content, { soft: true }); } });

  $('#newReqBtn').addEventListener('click', () => openRequestModal(content));
  $$('[data-viewreq]').forEach((b) => b.addEventListener('click', () => openRequestDetail(content, Number(b.getAttribute('data-viewreq')))));
  };
  if (soft) swapRows(content, paint);
  else paint();
}

// openRequestModal(content, reqId): abre open request modal; actualiza el DOM; realiza peticiones de red.
async function openRequestModal(content, reqId) {
  const isEdit = !!reqId;
  let req = null;
  if (isEdit) {
    const r = await api('GET', '/api/v1/material-requests/' + reqId);
    if (r.ok) req = r.body;
  }
  const catRes = await api('GET', '/api/v1/material-categories');
  const categories = catRes.ok ? (catRes.body || []) : [];
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
  overlay.innerHTML = `
    <div class="sigos-card" style="width:640px;max-width:95vw;padding:20px;max-height:90vh;overflow:auto">
      <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">${isEdit ? 'Editar borrador' : 'Nueva solicitud'}</h3>
      <div class="fld"><label for="rWo">Orden de trabajo (opcional)</label><input type="number" class="sigos-input" id="rWo" value="${req?.work_order_id || ''}"></div>
      <div class="fld"><label for="rReason">Motivo</label><input class="sigos-input" id="rReason" value="${escapeHtml(req?.reason || '')}"></div>
      <div class="fld"><label for="rTech">Técnico destinatario (id)</label><input type="number" class="sigos-input" id="rTech" value="${req?.technician_id || ''}"></div>
      <div style="font-size:13px;font-weight:600;margin:8px 0">Materiales</div>
      <div id="rItems"></div>
      <button type="button" class="sigos-btn-secondary" id="rAddItem" style="height:28px;margin:8px 0">+ Agregar material</button>
      <div id="rWarn" style="color:var(--c-danger);font-size:12px;margin:8px 0"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button type="button" class="sigos-btn-secondary" id="rCancel">Cancelar</button>
        <button type="button" class="sigos-btn-secondary" id="rSaveDraft">Guardar borrador</button>
        <button type="button" class="sigos-btn-primary" id="rSubmit">Enviar</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  // close(): cierra close; sin efectos secundarios.
  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#rCancel').addEventListener('click', close);

  const items = req ? (req.items || []).map((it) => ({ material_id: it.material_id, quantity: it.quantity_requested || it.quantity })) : [];
  // cargar materiales para selector (sin IDs manuales)
  if (!state._materialsOpts) {
    try {
      const mr = await api('GET', '/api/v1/materials?page_size=200&is_active=true');
      const mats = (mr.body && mr.body.items) || [];
      state._materialsOpts = mats.map((m) => `<option value="${m.id}">${escapeHtml(m.name || '')} (${escapeHtml(m.code || '')}) - ${escapeHtml(m.unit || '')} - stock: ${m.current_stock ?? 0}</option>`).join('');
    } catch (e) { state._materialsOpts = ''; }
  }
  // renderiza la vista items; actualiza el DOM.
  const renderItems = () => {
    const c = $('#rItems');
    if (!c) return;
    c.innerHTML = items.map((it, idx) => `
      <div style="display:flex;gap:8px;margin-bottom:6px;align-items:center">
        <select class="sigos-input" data-idx="${idx}" data-field="material_id" style="width:260px;height:32px">
          <option value="">Seleccionar material</option>
          ${state._materialsOpts}
        </select>
        <input type="number" class="sigos-input" placeholder="Cantidad" value="${it.quantity}" data-idx="${idx}" data-field="quantity" style="width:100px;height:32px" min="1">
        <button type="button" class="sigos-btn-secondary" data-remove="${idx}" style="height:32px" aria-label="Quitar material">${icon('close', 14)}</button>
      </div>`).join('');
    items.forEach((it, idx) => {
      const sel = c.querySelector(`select[data-idx="${idx}"]`);
      if (sel && it.material_id) sel.value = String(it.material_id);
    });
    $$('select[data-field], input[data-field]').forEach((inp) => inp.addEventListener('change', () => {
      const idx = Number(inp.getAttribute('data-idx'));
      const field = inp.getAttribute('data-field');
      items[idx][field] = field === 'quantity' ? Number(inp.value) : (inp.value ? Number(inp.value) : null);
    }));
    $$('button[data-remove]').forEach((b) => b.addEventListener('click', () => { items.splice(Number(b.getAttribute('data-remove')), 1); renderItems(); }));
  };
  renderItems();
  $('#rAddItem').addEventListener('click', () => { items.push({ material_id: '', quantity: 1 }); renderItems(); });

  // devuelve gather; sin efectos secundarios.
  const gather = () => ({
    work_order_id: $('#rWo').value ? Number($('#rWo').value) : null,
    reason: $('#rReason').value.trim() || null,
    technician_id: $('#rTech').value ? Number($('#rTech').value) : null,
    items: items.map((it) => ({ material_id: Number(it.material_id), quantity: Number(it.quantity) })),
  });

  // save(draft): guarda save; realiza peticiones de red.
  const save = async (draft) => {
    const payload = gather();
    payload.draft = draft;
    if (!payload.items.length) { $('#rWarn').textContent = 'Agrega al menos un material.'; return; }
    const url = isEdit ? ('/api/v1/material-requests/' + reqId) : '/api/v1/material-requests';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await api(method, url, payload);
    if (!r.ok) { $('#rWarn').textContent = (r.body && (r.body.message || r.body.error)) || 'Error'; return; }
    close();
    notify(draft ? 'Borrador guardado.' : 'Solicitud creada.', 'success');
    renderRequests(content, { soft: true });
  };
  $('#rSaveDraft').addEventListener('click', () => save(true));
  $('#rSubmit').addEventListener('click', async () => {
    const payload = gather();
    payload.draft = true;
    // create as draft then submit
    const url = isEdit ? ('/api/v1/material-requests/' + reqId) : '/api/v1/material-requests';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await api(method, url, payload);
    if (!r.ok) { $('#rWarn').textContent = (r.body && (r.body.message || r.body.error)) || 'Error'; return; }
    const rid = r.body.id;
    const rs = await api('POST', '/api/v1/material-requests/' + rid + '/submit', {});
    if (!rs.ok) { $('#rWarn').textContent = (rs.body && (rs.body.message || rs.body.error)) || 'Error'; return; }
    close();
    notify('Solicitud enviada.', 'success');
    renderRequests(content, { soft: true });
  });
}

// openRequestDetail(content, reqId): abre open request detail; actualiza el DOM; realiza peticiones de red.
async function openRequestDetail(content, reqId) {
  // load(): carga load; realiza peticiones de red.
  const load = async () => {
    const r = await api('GET', '/api/v1/material-requests/' + reqId);
    if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return null; }
    return r.body;
  };
  let req = await load();
  if (!req) return;
  const roles = (state.session?.user?.roles || []);
  const canManage = roles.includes('dispatcher');

  // renderiza la vista overlay; actualiza el DOM; realiza peticiones de red.
  const renderOverlay = () => {
    const old = document.getElementById('reqDetailOverlay');
    if (old) old.remove();
    const overlay = document.createElement('div');
    overlay.id = 'reqDetailOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000';
    const canApprove = canManage && (req.status === 'SUBMITTED' || req.status === 'PARTIALLY_APPROVED');
    const canDeliver = canManage && ['APPROVED','PARTIALLY_APPROVED','PARTIALLY_DELIVERED'].includes(req.status);
    const canCancel = !['DELIVERED','CANCELLED','REJECTED'].includes(req.status) && (canManage || req.requester_id === state.session?.user?.id);
    overlay.innerHTML = `
      <div class="sigos-card" style="width:760px;max-width:95vw;padding:20px;max-height:90vh;overflow:auto">
        <h3 style="font-family:Outfit;font-weight:700;font-size:18px;color:var(--c-nav);margin:0 0 12px">Solicitud #${req.id}</h3>
        <div style="font-size:13px;color:var(--c-text-3);margin-bottom:8px">Estado: <strong>${escapeHtml(requestStatusLabel(req.status))}</strong> · Solicitante: ${escapeHtml(req.requester?.username || '')} · Orden: ${req.work_order_id || '-'}</div>
        <table class="tbl" style="font-size:12px;margin-bottom:12px">
          <thead><tr><th>Material</th><th>Solicitado</th><th>Aprobado</th><th>Entregado</th><th>Pendiente</th>${canApprove ? '<th>Aprobar (cant.)</th>' : ''}${canDeliver ? '<th>Entregar (cant.)</th>' : ''}</tr></thead>
          <tbody>${(req.items || []).map((it) => {
            const pending = (it.quantity_approved || 0) - (it.quantity_delivered || 0);
            return `<tr>
              <td>${escapeHtml(it.material?.name || it.material_id)}</td>
              <td>${it.quantity_requested}</td>
              <td>${it.quantity_approved}</td>
              <td>${it.quantity_delivered}</td>
              <td>${pending}</td>
              ${canApprove ? `<td><input type="number" min="0" max="${it.quantity_requested}" value="${it.quantity_approved || 0}" data-appr="${it.id}" style="width:80px;height:28px"></td>` : ''}
              ${canDeliver ? `<td><input type="number" min="0" max="${pending}" value="${pending > 0 ? pending : 0}" data-deliv="${it.id}" style="width:80px;height:28px"></td>` : ''}
            </tr>`;
          }).join('')}</tbody>
        </table>
        <div style="font-size:13px;font-weight:600;margin-bottom:4px">Historial de eventos</div>
        <div style="font-size:12px;color:var(--c-text-2);margin-bottom:12px;max-height:160px;overflow:auto">
          ${(req.events || []).map((e) => `<div style="padding:4px 0;border-bottom:1px solid var(--c-border)">${escapeHtml(e.created_at || '')} — ${escapeHtml(e.action)} ${escapeHtml(e.from_status || '')} → ${escapeHtml(e.to_status || '')} (actor ${e.actor_id})</div>`).join('') || 'Sin eventos'}
        </div>
        <div style="font-size:13px;font-weight:600;margin-bottom:4px">Entregas</div>
        <div style="font-size:12px;color:var(--c-text-2);margin-bottom:12px;max-height:120px;overflow:auto">
          ${(req.deliveries || []).map((d) => `<div style="padding:4px 0;border-bottom:1px solid var(--c-border)">Entrega #${d.id} — ${escapeHtml(d.created_at || '')} por ${d.actor_id}: ${(d.items||[]).map((i)=>i.quantity_delivered).join(', ')}</div>`).join('') || 'Sin entregas'}
        </div>
        ${canManage ? `
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
            ${req.status === 'SUBMITTED' || req.status === 'PARTIALLY_APPROVED' ? `<button type="button" class="sigos-btn-primary" id="approveBtn" style="height:32px">Aprobar</button>
            <button type="button" class="sigos-btn-secondary" id="rejectBtn" style="height:32px">Rechazar</button>` : ''}
            ${['APPROVED','PARTIALLY_APPROVED','PARTIALLY_DELIVERED'].includes(req.status) ? `<button type="button" class="sigos-btn-primary" id="deliverBtn" style="height:32px">Entregar</button>` : ''}
            ${!['DELIVERED','CANCELLED','REJECTED'].includes(req.status) ? `<button type="button" class="sigos-btn-secondary" id="cancelBtn" style="height:32px">Cancelar</button>` : ''}
          </div>
        ` : ''}
        <div style="display:flex;justify-content:flex-end;margin-top:12px">
          <button type="button" class="sigos-btn-secondary" id="closeDetail">Cerrar</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    // close(): cierra close; sin efectos secundarios.
    const close = () => overlay.remove();
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    $('#closeDetail').addEventListener('click', close);

    const approveBtn = $('#approveBtn');
    if (approveBtn) approveBtn.addEventListener('click', async () => {
      // devuelve approvals; actualiza el DOM.
      const approvals = (req.items || []).map((it) => {
        const inp = overlay.querySelector(`input[data-appr="${it.id}"]`);
        return { item_id: it.id, quantity_approved: Number(inp ? inp.value : it.quantity_requested) };
      });
      if (!(await confirmDialog('Se aplicarán las cantidades aprobadas a la solicitud.', { title: '¿Aplicar aprobación?', confirmLabel: 'Aprobar' }))) return;
      const r = await api('POST', '/api/v1/material-requests/' + reqId + '/approve', { items: approvals });
      if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return; }
      close(); notify('Solicitud aprobada.', 'success'); renderRequests(content, { soft: true });
    });
    const rejectBtn = $('#rejectBtn');
    if (rejectBtn) rejectBtn.addEventListener('click', async () => {
      const reason = window.prompt('Motivo de rechazo:');
      if (reason === null) return;
      const r = await api('POST', '/api/v1/material-requests/' + reqId + '/reject', { reason });
      if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return; }
      close(); notify('Solicitud rechazada.', 'success'); renderRequests(content, { soft: true });
    });
    const deliverBtn = $('#deliverBtn');
    if (deliverBtn) deliverBtn.addEventListener('click', async () => {
      // devuelve deliveries; actualiza el DOM.
      const deliveries = (req.items || []).map((it) => {
        const inp = overlay.querySelector(`input[data-deliv="${it.id}"]`);
        const val = inp ? Number(inp.value) : 0;
        return val > 0 ? { item_id: it.id, quantity_delivered: val } : null;
      }).filter(Boolean);
      if (!deliveries.length) { notify('Ingresa cantidades a entregar.', 'error'); return; }
      if (!(await confirmDialog('Se descontará el stock entregado.', { title: '¿Registrar entrega?', confirmLabel: 'Registrar entrega' }))) return;
      const opId = 'del-' + reqId + '-' + Date.now();
      const r = await api('POST', '/api/v1/material-requests/' + reqId + '/deliver', { items: deliveries, operation_id: opId });
      if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return; }
      close(); notify('Entrega registrada.', 'success'); renderRequests(content, { soft: true });
    });
    const cancelBtn = $('#cancelBtn');
    if (cancelBtn) cancelBtn.addEventListener('click', async () => {
      if (!(await confirmDialog('La solicitud quedará cancelada.', { title: '¿Cancelar la solicitud?', confirmLabel: 'Cancelar solicitud', cancelLabel: 'Volver', danger: true }))) return;
      const r = await api('POST', '/api/v1/material-requests/' + reqId + '/cancel', { reason: 'Cancelada por usuario' });
      if (!r.ok) { notify((r.body && (r.body.message || r.body.error)) || 'Error', 'error'); return; }
      close(); notify('Solicitud cancelada.', 'success'); renderRequests(content, { soft: true });
    });
  };
  renderOverlay();
}


// updateMenuBadge(): actualiza update menu badge; actualiza el DOM; realiza peticiones de red.
async function updateMenuBadge() {
  try {
    const r = await api('GET', '/api/v1/materials?status=low&page=1&page_size=1');
    // need counts; fetch first page with counts
    const r2 = await api('GET', '/api/v1/materials?page=1&page_size=1');
    if (!r2.ok) return;
    const counts = r2.body.counts || {};
    const low = counts.low || 0;
    const crit = counts.critical || 0;
    const total = low + crit;
    const badge = document.querySelector('[data-menu-badge="materials"]');
    if (!badge) return;
    if (total === 0) { badge.style.display = 'none'; return; }
    badge.style.display = 'inline-block';
    badge.textContent = total;
    badge.style.background = crit > 0 ? '#D63B3B' : '#E8A520';
  } catch (e) {}
}


// ---------- Usuarios: administracion de cuentas (solo admin; el backend valida cada operacion) ----------
const ROLE_LABELS = { admin: 'Administrador', dispatcher: 'Coordinador', technician: 'Técnico' };
const roleLabel = (r) => ROLE_LABELS[r] || r;
if (!state.usersFilters) state.usersFilters = { q: '', role: '', status: '' };

// fmtDateTime(v): fecha/hora corta en es-CO o guion.
function fmtDateTime(v) {
  return v ? new Date(v).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '—';
}

// userApiError(res): mensaje legible a partir de {error, code, field}.
function userApiError(res, fallback) {
  return res?.body?.error || fallback || 'No se pudo completar la operación';
}

// renderUsers(content): tabla de usuarios con busqueda, filtros y acciones.
async function renderUsers(content) {
  const f = state.usersFilters;
  content.innerHTML = `
    <div class="sigos-card" style="padding:14px;margin-bottom:14px">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
        <div class="fld" style="flex:2;min-width:200px;margin:0"><label for="usQ">Buscar</label><input id="usQ" aria-label="Buscar usuario o correo" class="sigos-input" placeholder="Usuario o correo" value="${escapeHtml(f.q)}"></div>
        <div class="fld" style="flex:1;min-width:150px;margin:0"><label for="usRole">Rol</label><select id="usRole" aria-label="Filtrar por rol" class="sigos-select" style="width:100%"><option value="">Todos</option>${Object.keys(ROLE_LABELS).map((r) => `<option value="${r}" ${f.role === r ? 'selected' : ''}>${roleLabel(r)}</option>`).join('')}</select></div>
        <div class="fld" style="flex:1;min-width:150px;margin:0"><label for="usStatus">Estado</label><select id="usStatus" aria-label="Filtrar por estado de la cuenta" class="sigos-select" style="width:100%"><option value="">Todos</option><option value="active" ${f.status === 'active' ? 'selected' : ''}>Activos</option><option value="inactive" ${f.status === 'inactive' ? 'selected' : ''}>Inactivos</option></select></div>
        <button type="button" class="sigos-btn-primary" id="usNew">+ Nuevo usuario</button>
      </div>
    </div>
    <div class="sigos-card" style="overflow:auto"><div id="usTable">${loaderBlock('Consultando usuarios…', 200)}</div></div>`;
  let t;
  $('#usQ').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => { f.q = e.target.value.trim(); loadUsersTable(); }, 300); });
  $('#usRole').addEventListener('change', (e) => { f.role = e.target.value; loadUsersTable(); });
  $('#usStatus').addEventListener('change', (e) => { f.status = e.target.value; loadUsersTable(); });
  $('#usNew').addEventListener('click', () => openUserForm(null));
  loadUsersTable();
}

// loadUsersTable(): consulta /users con filtros y pinta la tabla.
async function loadUsersTable() {
  const el = $('#usTable');
  if (!el) return;
  const f = state.usersFilters;
  const qs = new URLSearchParams();
  if (f.q) qs.set('q', f.q);
  if (f.role) qs.set('role', f.role);
  if (f.status) qs.set('status', f.status);
  const res = await api('GET', '/api/v1/users' + (qs.toString() ? '?' + qs : ''));
  if (!$('#usTable')) return;
  if (!res.ok) {
    el.innerHTML = `<div style="padding:16px;color:var(--c-danger)">${escapeHtml(userApiError(res, 'No se pudieron cargar los usuarios'))} <button type="button" class="sigos-btn-secondary" id="usRetry" style="margin-left:8px">Reintentar</button></div>`;
    $('#usRetry').addEventListener('click', loadUsersTable);
    return;
  }
  const users = Array.isArray(res.body) ? res.body : [];
  const me = state.session?.user?.id;
  if (!users.length) {
    const filtered = f.q || f.role || f.status;
    swapRows(el, () => { el.innerHTML = `<div class="empty-state" style="padding:24px"><div class="empty-state__title">${filtered ? 'Sin resultados' : 'No hay usuarios'}</div><div class="empty-state__text">${filtered ? 'Ningún usuario coincide con la búsqueda o los filtros.' : 'Cree el primer usuario con «Nuevo usuario».'}</div></div>`; });
    return;
  }
  // Filtrar, crear, editar o desactivar: cada fila conserva su identidad (ID real) y se mueve a su nueva posición.
  swapRows(el, () => {
  el.innerHTML = `
    <table class="tbl" style="width:100%">
      <thead><tr><th>Usuario</th><th>Correo</th><th>Rol</th><th>Estado</th><th>Creado</th><th>Último acceso</th><th style="text-align:right">Acciones</th></tr></thead>
      <tbody>${users.map((u) => `
        <tr class="tbl-row" data-vt-row="user-${u.id}">
          <td><strong>${escapeHtml(u.username)}</strong>${u.id === me ? ' <span style="font-size:11px;color:var(--c-text-3)">(usted)</span>' : ''}${u.must_change_password ? '<div style="font-size:11px;color:var(--c-warning)">Debe cambiar contraseña</div>' : ''}</td>
          <td>${escapeHtml(u.email)}</td>
          <td>${escapeHtml((u.roles || []).map(roleLabel).join(', ') || '—')}</td>
          <td><span class="${u.is_active ? 'badge-available' : 'badge-offduty'}">${u.is_active ? 'Activo' : 'Inactivo'}</span></td>
          <td>${escapeHtml(fmtDateTime(u.created_at))}</td>
          <td>${escapeHtml(fmtDateTime(u.last_login))}</td>
          <td style="text-align:right;white-space:nowrap">
            <button type="button" class="sigos-btn-secondary" data-us-view="${u.id}" style="height:28px;padding:0 8px">Ver</button>
            <button type="button" class="sigos-btn-secondary" data-us-edit="${u.id}" style="height:28px;padding:0 8px">Editar</button>
            ${u.id !== me ? `<button type="button" class="sigos-btn-secondary" data-us-reset="${u.id}" style="height:28px;padding:0 8px">Restablecer contraseña</button>
            <button type="button" class="sigos-btn-secondary" data-us-toggle="${u.id}" style="height:28px;padding:0 8px;${u.is_active ? 'color:var(--c-danger)' : ''}">${u.is_active ? 'Desactivar' : 'Activar'}</button>` : ''}
          </td>
        </tr>`).join('')}</tbody>
    </table>`;
  const byId = (id) => users.find((u) => u.id === Number(id));
  $$('[data-us-view]').forEach((b) => b.addEventListener('click', () => openUserDetail(Number(b.dataset.usView))));
  $$('[data-us-edit]').forEach((b) => b.addEventListener('click', () => openUserForm(byId(b.dataset.usEdit))));
  $$('[data-us-reset]').forEach((b) => b.addEventListener('click', () => resetUserPassword(byId(b.dataset.usReset))));
  $$('[data-us-toggle]').forEach((b) => b.addEventListener('click', () => toggleUserActive(byId(b.dataset.usToggle), b)));
  });
}

// swapRows(container, apply): aplica un cambio de lista con transición si hay soporte; si no, al instante.
// El control que tenía el foco (filtro, pestaña, paginador) lo recupera tras volver a pintar.
function swapRows(container, apply) {
  const active = document.activeElement;
  const focusId = active && active !== container && container.contains(active) ? active.id : '';
  const focusStatus = active && active.dataset ? (active.dataset.status ?? active.dataset.filterStatus) : undefined;
  const run = () => {
    apply();
    let el = focusId ? document.getElementById(focusId) : null;
    if (!el && focusStatus !== undefined) el = container.querySelector(`[data-status="${focusStatus}"], [data-filter-status="${focusStatus}"]`);
    if (el && !el.disabled) el.focus({ preventScroll: true });
  };
  if (window.sigosVT) return window.sigosVT.swapList(container, run);
  run();
  return Promise.resolve();
}

// userModal(title, bodyHtml, footHtml): modal del modulo Usuarios sobre sigosModal; [data-us-close] cierra.
function userModal(title, bodyHtml, footHtml, opts = {}) {
  const m = sigosModal({ title, body: bodyHtml, footer: footHtml, dismissible: opts.dismissible !== false });
  m.card.querySelectorAll('[data-us-close]').forEach((b) => b.addEventListener('click', () => m.close()));
  return { modal: m.card, close: m.close };
}

// openUserForm(user): modal de alta (user=null) o edicion.
function openUserForm(user) {
  const isEdit = !!user;
  const me = state.session?.user?.id;
  const self = isEdit && user.id === me;
  const curRole = isEdit ? (user.roles || [])[0] || '' : 'dispatcher';
  const body = `
    <div class="fld"><label for="ufUser">Nombre de usuario *</label><input id="ufUser" class="sigos-input" maxlength="80" value="${escapeHtml(isEdit ? user.username : '')}" autocomplete="off"><div class="uf-err" data-for="username"></div></div>
    <div class="fld"><label for="ufEmail">Correo electrónico *</label><input id="ufEmail" type="email" class="sigos-input" maxlength="120" value="${escapeHtml(isEdit ? user.email : '')}" autocomplete="off"><div class="uf-err" data-for="email"></div></div>
    <div class="fld"><label for="ufRole">Rol *</label><select id="ufRole" class="sigos-select" style="width:100%" ${self ? 'disabled title="No puede cambiar su propio rol"' : ''}>${Object.keys(ROLE_LABELS).map((r) => `<option value="${r}" ${curRole === r ? 'selected' : ''}>${roleLabel(r)}</option>`).join('')}</select><div class="uf-err" data-for="role_names"></div>
      ${!isEdit ? '<div style="font-size:11px;color:var(--c-text-3);margin-top:4px">Para técnicos con ficha de campo, use el módulo Técnicos.</div>' : ''}</div>
    ${isEdit ? `<div class="fld"><label style="display:flex;gap:8px;align-items:center;font-weight:normal"><input type="checkbox" id="ufActive" ${user.is_active ? 'checked' : ''} ${self ? 'disabled' : ''}> Cuenta activa</label><div class="uf-err" data-for="is_active"></div></div>` : `
    <div class="fld"><label>Contraseña inicial</label>
      <label style="display:flex;gap:8px;align-items:center;font-weight:normal;margin-bottom:6px"><input type="radio" name="ufPwMode" value="temp" checked> Generar contraseña temporal segura (recomendado)</label>
      <label style="display:flex;gap:8px;align-items:center;font-weight:normal"><input type="radio" name="ufPwMode" value="manual"> Definir contraseña</label>
      <input id="ufPass" type="password" class="sigos-input" style="margin-top:6px;display:none" autocomplete="new-password" placeholder="Mín. 10 caracteres, mayúscula, minúscula y número">
      <div class="uf-err" data-for="password"></div>
      <div style="font-size:11px;color:var(--c-text-3);margin-top:4px">Con contraseña temporal el usuario deberá cambiarla en su primer acceso.</div></div>`}
    <div id="ufError" style="color:var(--c-danger);font-size:12px"></div>`;
  const foot = `<button type="button" class="sigos-btn-secondary" data-us-close>Cancelar</button><button type="button" class="sigos-btn-primary" id="ufSave">${isEdit ? 'Guardar cambios' : 'Crear usuario'}</button>`;
  const { modal, close } = userModal(isEdit ? `Editar usuario` : 'Nuevo usuario', body, foot);
  const q = (s) => modal.querySelector(s);
  modal.querySelectorAll('.uf-err').forEach((e) => { e.style.cssText = 'color:var(--c-danger);font-size:11px;margin-top:2px'; });
  modal.querySelectorAll('input[name="ufPwMode"]').forEach((r) => r.addEventListener('change', () => { q('#ufPass').style.display = r.value === 'manual' && r.checked ? 'block' : (q('input[name="ufPwMode"]:checked').value === 'manual' ? 'block' : 'none'); }));
  const setErr = (field, msg) => { const e = q(`.uf-err[data-for="${field}"]`); if (e) e.textContent = msg || ''; else q('#ufError').textContent = msg || ''; };
  q('#ufUser').focus();
  q('#ufSave').addEventListener('click', async () => {
    modal.querySelectorAll('.uf-err').forEach((e) => { e.textContent = ''; });
    q('#ufError').textContent = '';
    const username = q('#ufUser').value.trim().toLowerCase();
    const email = q('#ufEmail').value.trim().toLowerCase();
    const role = q('#ufRole').value;
    let bad = false;
    if (!/^[a-z0-9._-]{3,80}$/.test(username)) { setErr('username', 'De 3 a 80 caracteres: letras, números, punto, guion o guion bajo'); bad = true; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { setErr('email', 'Correo electrónico inválido'); bad = true; }
    if (!role) { setErr('role_names', 'Seleccione un rol'); bad = true; }
    const payload = { username, email };
    if (!self) payload.role_names = [role];
    if (isEdit) {
      if (!self) payload.is_active = q('#ufActive').checked;
    } else if (q('input[name="ufPwMode"]:checked').value === 'manual') {
      const pw = q('#ufPass').value;
      if (pw.length < 10 || !/[A-Z]/.test(pw) || !/[a-z]/.test(pw) || !/\d/.test(pw)) { setErr('password', 'Mín. 10 caracteres con mayúscula, minúscula y número'); bad = true; }
      payload.password = pw;
    }
    if (bad) return;
    if (isEdit && user.is_active && payload.is_active === false && !(await confirmDialog(`No podrá iniciar sesión; su historial se conserva.`, { title: `¿Desactivar la cuenta de ${user.username}?`, confirmLabel: 'Desactivar', danger: true }))) return;
    const btn = q('#ufSave');
    btn.disabled = true;
    const res = await api(isEdit ? 'PUT' : 'POST', isEdit ? `/api/v1/users/${user.id}` : '/api/v1/users', payload);
    btn.disabled = false; btn.textContent = isEdit ? 'Guardar cambios' : 'Crear usuario';
    if (!res.ok) { setErr(res.body?.field, userApiError(res)); return; }
    close();
    notify(isEdit ? 'Usuario actualizado' : 'Usuario creado', 'success');
    loadUsersTable();
    if (res.body?.temporary_password) showTemporaryPassword(res.body.username, res.body.temporary_password, 'Usuario creado');
  });
}

// showTemporaryPassword: muestra la contrasena temporal una sola vez; no se guarda en el estado de la app.
function showTemporaryPassword(username, password, title) {
  const body = `
    <div style="background:var(--c-warning-bg);color:var(--c-warning);font-size:12px;padding:8px 10px;border-radius:6px;margin-bottom:12px">Esta contraseña se muestra <strong>una sola vez</strong>. Entréguela al usuario por un canal seguro; deberá cambiarla al iniciar sesión.</div>
    <div class="fld"><label>Usuario</label><input class="sigos-input" value="${escapeHtml(username)}" readonly></div>
    <div class="fld"><label>Contraseña temporal</label><div style="display:flex;gap:8px"><input class="sigos-input" id="tpPass" value="${escapeHtml(password)}" readonly style="font-family:monospace"><button type="button" class="sigos-btn-secondary" id="tpCopy">Copiar</button></div></div>
    <label style="display:flex;align-items:center;gap:8px;font-size:13px"><input type="checkbox" id="tpAck"> Ya entregué o guardé la contraseña</label>`;
  const { modal, close } = userModal(title, body, '<button type="button" class="sigos-btn-primary" id="tpClose" disabled>Cerrar</button>', { dismissible: false });
  const q = (s) => modal.querySelector(s);
  q('#tpCopy').addEventListener('click', () => { navigator.clipboard?.writeText(password); notify('Contraseña copiada', 'success'); });
  q('#tpAck').addEventListener('change', (e) => { q('#tpClose').disabled = !e.target.checked; });
  q('#tpClose').addEventListener('click', () => { q('#tpPass').value = ''; close(); });
}

// resetUserPassword(user): confirma y genera contrasena temporal en el backend.
async function resetUserPassword(user) {
  if (!user) return;
  if (!(await confirmDialog(`Se generará una contraseña temporal, la actual dejará de funcionar y sus sesiones abiertas quedarán bloqueadas hasta que la cambie.`, { title: `¿Restablecer la contraseña de ${user.username}?`, confirmLabel: 'Restablecer' }))) return;
  const res = await api('POST', `/api/v1/users/${user.id}/reset-password`);
  if (!res.ok) { notify(userApiError(res, 'No se pudo restablecer la contraseña'), 'error'); return; }
  loadUsersTable();
  showTemporaryPassword(res.body.username, res.body.temporary_password, 'Contraseña restablecida');
}

// toggleUserActive(user): activa/desactiva con confirmacion; el backend protege al propio admin y al ultimo admin.
async function toggleUserActive(user, btn) {
  if (!user) return;
  const deactivate = user.is_active;
  if (deactivate && !(await confirmDialog(`No podrá iniciar sesión y sus sesiones abiertas se cerrarán. Su historial y relaciones se conservan.`, { title: `¿Desactivar la cuenta de ${user.username}?`, confirmLabel: 'Desactivar', danger: true }))) return;
  if (btn) btn.disabled = true;
  const res = await api('PUT', `/api/v1/users/${user.id}`, { is_active: !deactivate });
  if (btn) btn.disabled = false;
  if (!res.ok) { notify(userApiError(res), 'error'); return; }
  notify(deactivate ? 'Cuenta desactivada' : 'Cuenta activada', 'success');
  loadUsersTable();
}

// openUserDetail(id): consulta la cuenta y su historial de auditoria.
async function openUserDetail(id) {
  const { modal } = userModal('Detalle de usuario', loaderBlock('Cargando información del usuario…', 160), '<button type="button" class="sigos-btn-secondary" data-us-close>Cerrar</button>');
  const res = await api('GET', `/api/v1/users/${id}`);
  const bodyEl = modal.querySelector('.modal-body');
  if (!bodyEl) return;
  if (!res.ok) { bodyEl.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(userApiError(res, 'No se pudo cargar el usuario'))}</div>`; return; }
  const u = res.body;
  const ACTIONS = { user_created: 'Cuenta creada', user_updated: 'Cuenta modificada', password_reset: 'Contraseña restablecida', reset_password: 'Contraseña restablecida', unlock: 'Cuenta desbloqueada' };
  const row = (l, v) => `<div><div style="font-size:11px;color:var(--c-text-3)">${l}</div><div style="font-size:13px;color:var(--c-nav)">${v}</div></div>`;
  const describe = (a) => {
    if (!a.changes) return '';
    try {
      const c = JSON.parse(a.changes);
      return Object.entries(c).map(([k, v]) => Array.isArray(v) && v.length === 2 ? `${k}: ${JSON.stringify(v[0])} → ${JSON.stringify(v[1])}` : `${k}: ${JSON.stringify(v)}`).join(' · ');
    } catch { return ''; }
  };
  bodyEl.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
      ${row('Usuario', escapeHtml(u.username))}${row('Correo', escapeHtml(u.email))}
      ${row('Rol', escapeHtml((u.roles || []).map(roleLabel).join(', ') || '—'))}${row('Estado', `<span class="${u.is_active ? 'badge-available' : 'badge-offduty'}">${u.is_active ? 'Activo' : 'Inactivo'}</span>`)}
      ${row('Creado', escapeHtml(fmtDateTime(u.created_at)))}${row('Último acceso', escapeHtml(fmtDateTime(u.last_login)))}
      ${row('Cambio de contraseña pendiente', u.must_change_password ? 'Sí' : 'No')}
    </div>
    <h4 style="margin:0 0 6px;font-size:13px;color:var(--c-nav)">Historial de cambios</h4>
    ${(u.audit || []).length ? (u.audit || []).map((a) => `<div style="padding:6px 0;border-bottom:1px solid var(--c-border);font-size:12px"><strong>${escapeHtml(ACTIONS[a.action] || a.action)}</strong> <span style="color:var(--c-text-3)">${escapeHtml(fmtDateTime(a.created_at))}</span><div style="color:var(--c-text-2)">${escapeHtml(describe(a))}</div></div>`).join('') : '<div class="empty-state__text">Sin cambios registrados</div>'}`;
}


// renderiza la vista notifications; actualiza el DOM; realiza peticiones de red.
async function renderNotifications(content) {
  content.innerHTML = loaderBlock('Cargando notificaciones…', 240);
  const res = await api('GET', '/api/v1/notifications');
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  if (!res.ok) { content.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const ns = res.body || [];
  content.innerHTML = `
    <div class="sigos-card" style="padding:16px">
      ${ns.map((n) => `<div style="padding:8px 0;border-bottom:1px solid var(--c-border)"><strong>${escapeHtml(n.subject || '')}</strong> <span class="badge-${n.status === 'sent' ? 'completed' : 'pending'}">${escapeHtml(n.status)}</span><div style="color:var(--c-text-3);font-size:13px">${escapeHtml(n.message)}</div><div style="color:var(--c-text-3);font-size:12px">${escapeHtml(n.created_at)} via ${escapeHtml(n.channel)}</div></div>`).join('') || '<div class="empty-state__text">Sin notificaciones</div>'}
    </div>`;
}

const ADMIN_ONLY_VIEWS = new Set(['users', 'settings', 'reports']);
// isTechnicianRole(): verifica is technician role; sin efectos secundarios.
function isTechnicianRole() { return (state.session?.user?.roles || []).includes('technician'); }
// devuelve view to hash; sin efectos secundarios.
function viewToHash(view) {
  if (view === 'order-detail' && state.selectedOrderId) return '#/ordenes/' + state.selectedOrderId;
  const map = { dashboard: 'dashboard', orders: 'ordenes', technicians: 'tecnicos', calendar: 'calendario', materials: 'materiales', requests: 'solicitudes', evidence: 'evidencias', reports: 'reportes', users: 'usuarios', notifications: 'notificaciones', settings: 'configuracion' };
  return '#/' + (map[view] || 'dashboard');
}
let _hashSyncing = false;
// syncHash(): sincroniza sync hash; sin efectos secundarios.
function syncHash() {
  const desired = viewToHash(state.view);
  if (location.hash !== desired) { _hashSyncing = true; location.hash = desired; _hashSyncing = false; }
}
// hashToView(hash): verifica hash to view; sin efectos secundarios.
function hashToView(hash) {
  const raw = (hash || '').replace(/^#\/?/, '');
  const parts = raw.split('/').filter(Boolean);
  if (!parts.length) return { view: 'dashboard' };
  const seg = parts[0];
  const id = parts[1];
  const map = { dashboard: 'dashboard', ordenes: 'orders', tecnicos: 'technicians', calendario: 'calendar', materiales: 'materials', solicitudes: 'requests', evidencias: 'evidence', reportes: 'reports', usuarios: 'users', notificaciones: 'notifications', configuracion: 'settings' };
  let view = map[seg] || 'dashboard';
  const out = { view: view };
  if (seg === 'ordenes' && id) { out.view = 'order-detail'; out.orderId = id; }
  if ((isTechnicianRole() && ADMIN_ONLY_VIEWS.has(out.view)) || !viewAllowed(out.view)) { out.view = 'dashboard'; delete out.orderId; }
  return out;
}
window.addEventListener('hashchange', () => {
  if (_hashSyncing) return;
  if (!state.session) return;
  // hashchange es asincrono: si el hash ya refleja la vista actual (lo puso syncHash), no volver a renderizar.
  if (location.hash === viewToHash(state.view)) return;
  const r = hashToView(location.hash);
  state.view = r.view;
  if (r.orderId) state.selectedOrderId = r.orderId;
  render({ transition: 'nav' });
});
// Inicializa la aplicacion de escritorio: valida la sesion guardada, restaura la ruta pendiente y renderiza la vista inicial.
(async function init() {
  try { state.uiPrefs = (await window.sigos?.getPrefs?.()) || {}; } catch { state.uiPrefs = {}; }
  // El archivo de preferencias manda sobre localStorage (theme-init.js ya aplicó este último sin destello).
  const savedTheme = state.uiPrefs.theme;
  if (savedTheme && window.sigosVT && savedTheme !== window.sigosVT.theme.pref()) window.sigosVT.theme.apply(savedTheme);
  const ok = await (window.SigosLoading ? window.SigosLoading.run({ mode: 'global', message: 'Recuperando sesión…', delay: 300 }, loadSession) : loadSession());
  if (ok) {
    if (location.hash && location.hash !== '#' && location.hash !== '#/') {
      state.pendingRoute = location.hash;
    }
    if (state.pendingRoute) {
      const r = hashToView(state.pendingRoute);
      state.view = r.view;
      if (r.orderId) state.selectedOrderId = r.orderId;
      state.pendingRoute = null;
    } else if (!state.view) {
      state.view = 'dashboard';
    }
  } else {
    // Tras un cierre de sesion la app se recarga sin ruta: no se restaura la vista de la cuenta anterior.
    state.pendingRoute = location.hash;
  }
  render();
  const ended = new URLSearchParams(location.search).get('ended');
  if (ended && !state.session) notify(ended === 'expired' ? 'La sesión expiró. Inicie sesión de nuevo.' : 'Sesión cerrada.', ended === 'expired' ? 'error' : 'info');
})();

// closeContextMenu(): cierra close context menu; actualiza el DOM.
function closeContextMenu() {
  const m = document.getElementById('calContextMenu');
  if (m) m.remove();
}

// showContextMenu(x, y, eventId): muestra show context menu; actualiza el DOM; realiza peticiones de red.
function showContextMenu(x, y, eventId) {
  closeContextMenu();
  const menu = document.createElement('div');
  menu.id = 'calContextMenu';
  menu.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;background:var(--c-surface);border:1px solid var(--c-border);border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.15);padding:4px;z-index:9999;min-width:160px;';
  const items = [
    { label: 'Abrir orden', action: 'open' },
    { label: 'Programar/Reprogramar', action: 'schedule' },
    { label: 'Asignar/Reasignar', action: 'assign' },
    { label: 'Cambiar estado', action: 'transition-next' },
    ...(canCancelOrders() ? [{ label: 'Cancelar orden', action: 'cancel' }] : []),
    { label: 'Ver historial', action: 'history' },
  ];
  items.forEach(it => {
    const b = document.createElement('button');
    b.textContent = it.label;
    b.style.cssText = 'display:block;width:100%;text-align:left;border:none;background:none;padding:6px 8px;font-size:12px;cursor:pointer;border-radius:4px;';
    b.addEventListener('mouseenter', () => b.style.background = 'var(--c-hover)');
    b.addEventListener('mouseleave', () => b.style.background = 'none');
    b.addEventListener('click', async () => {
      closeContextMenu();
      if (it.action === 'open') { state.selectedOrderId = eventId; state.view = 'order-detail'; render(); return; }
      if (it.action === 'schedule' || it.action === 'assign') { notify('Disponible en Fase 2.', 'info'); return; }
      if (it.action === 'history') { openHistoryDrawer(eventId); return; }
      if (it.action === 'cancel') { openCancelOrder(eventId, () => render()); return; }
      if (it.action === 'transition-next') {
        // advance one step based on current event status if possible
        notify('Usa los botones del panel para transiciones específicas.', 'info');
      }
    });
    menu.appendChild(b);
  });
  document.body.appendChild(menu);
  // close(ev): cierra close; actualiza el DOM.
  const close = (ev) => { if (!menu.contains(ev.target)) { closeContextMenu(); document.removeEventListener('click', close); } };
  setTimeout(() => document.addEventListener('click', close), 0);
}

// openHistoryDrawer(orderId): abre open history drawer; actualiza el DOM; realiza peticiones de red.
async function openHistoryDrawer(orderId) {
  const existing = document.getElementById('calHistoryDrawer');
  if (existing) existing.remove();
  const drawer = document.createElement('div');
  drawer.id = 'calHistoryDrawer';
  drawer.style.cssText = 'position:fixed;right:0;top:0;height:100%;width:360px;background:var(--c-surface);border-left:1px solid var(--c-border);box-shadow:-4px 0 12px rgba(0,0,0,.1);z-index:9998;padding:16px;overflow:auto;';
  drawer.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Historial</div><button type="button" id="calHistoryClose" class="sigos-btn-secondary" style="height:28px;padding:0 8px">Cerrar</button></div><div id="calHistoryBody">' + loaderBlock('Cargando historial de la visita…', 120) + '</div>';
  document.body.appendChild(drawer);
  document.getElementById('calHistoryClose').addEventListener('click', () => drawer.remove());
  try {
    const res = await api('GET', '/api/v1/work-orders/' + orderId + '/history');
    const body = document.getElementById('calHistoryBody');
    if (!res.ok) { body.innerHTML = '<div style="color:var(--c-danger)">No se pudo cargar el historial.</div>'; return; }
    const items = res.body || [];
    if (!items.length) { body.innerHTML = '<div style="color:var(--c-text-3);font-size:12px">Sin historial.</div>'; return; }
    body.innerHTML = items.map(h => {
      const who = (h.changed_by && (h.changed_by.username || h.changed_by.name)) || 'Sistema';
      const when = h.created_at ? new Date(h.created_at).toLocaleString('es-CO') : '';
      const what = (h.from_status || '') + ' ? ' + (h.to_status || '');
      const reason = h.notes ? '<div style="font-size:11px;color:var(--c-text-3);margin-top:2px">' + escapeHtml(h.notes) + '</div>' : '';
      return '<div style="padding:8px;border-bottom:1px solid var(--c-border)"><div style="font-size:12px;font-weight:600">' + escapeHtml(what) + '</div><div style="font-size:11px;color:var(--c-text-3)">' + escapeHtml(who) +  ' · ' + escapeHtml(when) + '</div>' + reason + '</div>';
    }).join('');
  } catch (e) {
    const body = document.getElementById('calHistoryBody');
    if (body) body.innerHTML = '<div style="color:var(--c-danger)">Error de conexión.</div>';
  }
}

document.addEventListener('keydown', (ev) => {
  if (state.view !== 'calendar') return;
  const cs = state.calendarState;
  if (!cs) return;
  const tag = (document.activeElement && document.activeElement.tagName) || '';
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  if (ev.key === 'Escape') { closeContextMenu(); const d = document.getElementById('calHistoryDrawer'); if (d) d.remove(); return; }
  if (ev.key === 't' || ev.key === 'T') { cs.anchor = calTodayStr(); cs.selectedDay = calTodayStr(); render(); return; }
  if (ev.key === 'd' || ev.key === 'D') { cs.view = 'day'; render(); return; }
  if (ev.key === 'w' || ev.key === 'W') { cs.view = 'week'; render(); return; }
  if (ev.key === 'm' || ev.key === 'M') { cs.view = 'month'; render(); return; }
  if (ev.key === 'n' || ev.key === 'N') { notify('Programación disponible en Fase 2.', 'info'); return; }
  if (ev.key === 'ArrowLeft') { cs.anchor = calAddDays(new Date(cs.anchor + 'T00:00:00'), cs.view === 'month' ? -30 : cs.view === 'day' ? -1 : -7).toISOString().slice(0,10); render(); return; }
  if (ev.key === 'ArrowRight') { cs.anchor = calAddDays(new Date(cs.anchor + 'T00:00:00'), cs.view === 'month' ? 30 : cs.view === 'day' ? 1 : 7).toISOString().slice(0,10); render(); return; }
  if (ev.key === 'ArrowUp' || ev.key === 'ArrowDown') {
    // move selection among events of selected day
    const items = (state._calItems || []);
    const dayEvents = items.filter(e => e.start.slice(0,10) === cs.selectedDay);
    if (!dayEvents.length) return;
    const idx = dayEvents.findIndex(e => e.order_id === cs.selectedEventId);
    let next = idx;
    if (ev.key === 'ArrowDown') next = Math.min(dayEvents.length - 1, (idx < 0 ? 0 : idx + 1));
    else next = Math.max(0, (idx < 0 ? 0 : idx - 1));
    cs.selectedEventId = dayEvents[next].order_id;
    render();
    return;
  }
  if (ev.key === 'Enter') {
    if (cs.selectedEventId) { state.selectedOrderId = cs.selectedEventId; state.view = 'order-detail'; render(); }
    return;
  }
});

// openScheduleModal(opts): abre open schedule modal; actualiza el DOM; realiza peticiones de red.
async function openScheduleModal(opts) {
  opts = opts || {};
  const canSchedule = hasRole('dispatcher');
  if (!canSchedule) { notify('Sin permisos para programar.', 'error'); return; }
  const unRes = await api('GET', '/api/v1/calendar/unassigned?page_size=100');
  const unassigned = (unRes.ok && unRes.body && unRes.body.items) || [];
  const techRes = await api('GET', '/api/v1/technicians?page_size=200&active=true');
  const techs = (techRes.ok && techRes.body && techRes.body.items) || [];
  const pubRes = await api('GET', '/api/v1/settings/public');
  const pub = (pubRes.ok && pubRes.body) || {};
  const defaultDur = pub.default_visit_duration || 60;
  const workStart = pub.work_start || '07:00';

  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:10000;display:flex;align-items:center;justify-content:center;';
  const modal = document.createElement('div');
  modal.style.cssText = 'width:560px;max-width:95vw;max-height:90vh;overflow:auto;background:var(--c-surface);border-radius:8px;padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.2);';
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div style="font-family:Outfit;font-weight:600;font-size:15px;color:var(--c-nav)">Programar visita</div>
      <button type="button" id="schClose" class="sigos-btn-secondary" style="height:28px;padding:0 8px">Cerrar</button>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
      <div style="grid-column:1/-1">
        <label style="font-size:12px;color:var(--c-text-3)">Orden *</label>
        <input type="search" id="schOrderSearch" class="sigos-input" style="height:32px;width:100%;margin-bottom:4px" placeholder="Buscar orden...">
        <select id="schOrder" class="sigos-input" style="height:36px;width:100%"></select>
      </div>
      <div>
        <label style="font-size:12px;color:var(--c-text-3)">Fecha *</label>
        <input type="date" id="schDate" class="sigos-input" style="height:36px;width:100%">
      </div>
      <div>
        <label style="font-size:12px;color:var(--c-text-3)">Inicio *</label>
        <input type="time" id="schStart" class="sigos-input" style="height:36px;width:100%" step="900">
      </div>
      <div>
        <label style="font-size:12px;color:var(--c-text-3)">Fin *</label>
        <input type="time" id="schEnd" class="sigos-input" style="height:36px;width:100%" step="900">
      </div>
      <div style="grid-column:1/-1">
        <label style="font-size:12px;color:var(--c-text-3)">Técnico</label>
        <select id="schTech" class="sigos-input" style="height:36px;width:100%"></select>
        <div id="schTechWarn" style="font-size:11px;color:var(--c-warning);margin-top:2px"></div>
      </div>
      <div style="grid-column:1/-1">
        <label style="font-size:12px;color:var(--c-text-3)">Observaciones</label>
        <textarea id="schNotes" class="sigos-input" style="width:100%;min-height:60px"></textarea>
      </div>
      <div id="schReasonWrap" style="grid-column:1/-1;display:none">
        <label style="font-size:12px;color:var(--c-text-3)">Motivo del cambio *</label>
        <select id="schReason" class="sigos-input" style="height:36px;width:100%;margin-bottom:4px">
          <option value="">Selecciona motivo</option>
          <option value="Cliente reprogramó">Cliente reprogramó</option>
          <option value="Técnico no disponible">Técnico no disponible</option>
          <option value="Clima">Clima</option>
          <option value="Falta de material">Falta de material</option>
          <option value="Otro">Otro</option>
        </select>
        <div id="schReasonError" style="font-size:11px;color:var(--c-danger);margin-top:2px"></div>
        <input type="text" id="schReasonComment" class="sigos-input" style="height:32px;width:100%" placeholder="Comentario adicional">
      </div>
    </div>

    <div id="schValidation" style="margin-top:8px;font-size:12px"></div>
    <div id="schConflictActions" style="margin-top:8px;display:none;gap:6px"></div>
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px">
      <button type="button" id="schCancel" class="sigos-btn-secondary" style="height:36px">Cancelar</button>
      <button type="button" id="schSave" class="sigos-btn-primary" style="height:36px">Guardar</button>
    </div>
  `;
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  let dirty = false;
  // devuelve mark dirty; sin efectos secundarios.
  const markDirty = () => { dirty = true; };

  const orderSel = modal.querySelector('#schOrder');
  const porProgramar = unassigned.filter(o => !o.scheduled_at);
  const porAsignar = unassigned.filter(o => o.scheduled_at && !o.assigned_to_id);
  // devuelve make opt; sin efectos secundarios.
  const makeOpt = (o) => {
    const code = orderCode(o);
    const label = code +  ' · ' + (o.customer_name || '—') +  ' · ' + (o.installation_type_code || o.installation_type || '—');
    return '<option value="' + o.id + '" data-version="' + (o.version || 0) + '" data-scheduled="' + (o.scheduled_at || '') + '">' + escapeHtml(label) + '</option>';
  };
  orderSel.innerHTML = '<optgroup label="Por programar">' + porProgramar.map(makeOpt).join('') + '</optgroup>' +
    '<optgroup label="Por asignar">' + porAsignar.map(makeOpt).join('') + '</optgroup>';
  if (opts.orderId) orderSel.value = String(opts.orderId);

  const dateInput = modal.querySelector('#schDate');
  const startInput = modal.querySelector('#schStart');
  const endInput = modal.querySelector('#schEnd');
  const today = opts.date || calTodayStr();
  dateInput.value = today;
  const sh = (opts.hour != null) ? String(opts.hour).padStart(2,'0') : (workStart.split(':')[0] || '08');
  const sm = (opts.minute != null) ? String(opts.minute).padStart(2,'0') : '00';
  startInput.value = sh + ':' + sm;
  // setEndDefault(): establece set end default; sin efectos secundarios.
  function setEndDefault() {
    const [h, m] = startInput.value.split(':').map(Number);
    const total = h * 60 + m + defaultDur;
    const eh = String(Math.floor(total / 60)).padStart(2,'0');
    const em = String(total % 60).padStart(2,'0');
    endInput.value = eh + ':' + em;
  }
  if (!opts.end) setEndDefault();

  const techSel = modal.querySelector('#schTech');
  // devuelve refresh tech options; actualiza el DOM.
  function refreshTechOptions() {
    const date = dateInput.value;
    const st = startInput.value;
    const en = endInput.value;
    let html = '<option value="">Dejar pendiente de asignación</option>';
    techs.forEach(t => {
      const prof = t; // t is profile
      const uid = t.user_id || t.id;
      let status = (t.is_available === false) ? 'offduty' : 'available';
      // check overlap from state items
      if (status === 'available' && date && st && en) {
        const selStart = new Date(date + 'T' + st + ':00');
        const selEnd = new Date(date + 'T' + en + ':00');
        // devuelve occ; sin efectos secundarios.
        const occ = (state._calItems || []).filter(e => (e.technicians||[]).some(tt => tt.id === uid) && e.start.slice(0,10) === date);
        for (const e of occ) {
          const es = new Date(e.start); const ee = new Date(e.end);
          if (es < selEnd && selStart < ee) { status = 'busy'; break; }
        }
      }
      const label = (t.full_name || t.name || t.username || ('Tecnico ' + uid)) + ' - ' + (status === 'offduty' ? 'Fuera de servicio' : status === 'busy' ? 'Ocupado en ese horario' : 'Disponible');
      html += '<option value="' + uid + '" data-available="' + (t.is_available !== false) + '">' + escapeHtml(label) + '</option>';
    });
    techSel.innerHTML = html;
  }
  refreshTechOptions();

  // reason wrap visibility based on selected order scheduled
  const reasonWrap = modal.querySelector('#schReasonWrap');
  // updateReasonVisibility(): actualiza update reason visibility; sin efectos secundarios.
  function updateReasonVisibility() {
    const opt = orderSel.selectedOptions[0];
    const scheduled = opt && opt.dataset.scheduled;
    reasonWrap.style.display = scheduled ? 'block' : 'none';
  }
  updateReasonVisibility();

  // tech warning on change
  const techWarn = modal.querySelector('#schTechWarn');
  // updateTechWarning(): actualiza update tech warning; sin efectos secundarios.
  function updateTechWarning() {
    const uid = techSel.value;
    if (!uid) { techWarn.textContent = ''; return; }
    const t = techs.find(x => String(x.user_id || x.id) === String(uid));
    const o = unassigned.find(x => String(x.id) === String(orderSel.value));
    if (!t || !o) { techWarn.textContent = ''; return; }
    const covs = t.coverage || t.coverages || [];
    // coverage array from profile.to_dict is 'coverage'
    const coverages = t.coverage || t.coverages || [];
    let covered = !o.city_id && !o.zone_id;
    if (o.city_id || o.zone_id) {
      covered = (coverages || []).some(c => c.city_id === o.city_id && (o.zone_id == null || c.zone_id === o.zone_id || c.zone_id == null));
    }
    if (!covered) techWarn.textContent = 'Advertencia: el técnico no cubre la zona/ciudad de la orden.';
    else techWarn.textContent = '';
  }


  const valDiv = modal.querySelector('#schValidation');
  const conflictActions = modal.querySelector('#schConflictActions');
  let validateTimer = null;
  // devuelve run validation; actualiza el DOM; realiza peticiones de red.
  async function runValidation() {
    const oid = orderSel.value;
    if (!oid || !dateInput.value || !startInput.value || !endInput.value) { valDiv.innerHTML = ''; return; }
    const payload = {
      order_id: Number(oid),
      start: dateInput.value + 'T' + startInput.value + ':00',
      end: dateInput.value + 'T' + endInput.value + ':00',
      technician_ids: techSel.value ? [Number(techSel.value)] : [],
      reason: modal.querySelector('#schReason').value || undefined,
    };
    const res = await api('POST', '/api/v1/calendar/validate', payload, null, null, true, { loading: false }); // validación en vivo
    if (!res.ok) { valDiv.innerHTML = '<span style="color:var(--c-danger)">Error de validación.</span>'; return; }
    const r = res.body || {};
    if (r.ok) {
      valDiv.innerHTML = '<span style="color:var(--c-success)">Sin conflictos.</span>';
      conflictActions.style.display = 'none';
    } else {
      // devuelve msgs; actualiza el DOM.
      const msgs = (r.conflicts || []).map(c => escapeHtml(c.message || c.code) + (c.conflicting_order_code ? ' (' + escapeHtml(c.conflicting_order_code) + ')' : '')).join('<br>');
      // devuelve warns; actualiza el DOM.
      const warns = (r.warnings || []).map(w => escapeHtml(w.message || w.code)).join('<br>');
      valDiv.innerHTML = '<span style="color:var(--c-danger)">' + (msgs || 'Conflicto') + '</span>' + (warns ? '<br><span style="color:var(--c-warning)">' + warns + '</span>' : '');
      conflictActions.style.display = 'flex';
      conflictActions.innerHTML = '';
      const b1 = document.createElement('button');
      b1.className = 'sigos-btn-secondary'; b1.style.height = '28px'; b1.textContent = 'Elegir otro horario';
      b1.addEventListener('click', () => startInput.focus());
      conflictActions.appendChild(b1);
      const uid = techSel.value;
      if (uid) {
        const b2 = document.createElement('button');
        b2.className = 'sigos-btn-secondary'; b2.style.height = '28px'; b2.textContent = 'Ver agenda de ' + (techSel.selectedOptions[0] ? techSel.selectedOptions[0].textContent.split( ' · ')[0] : 'técnico');
        b2.addEventListener('click', () => { closeScheduleModal(); csFilterByTech(uid); });
        conflictActions.appendChild(b2);
      }
    }
  }
  // devuelve schedule validate; sin efectos secundarios.
  function scheduleValidate() {
    clearTimeout(validateTimer);
    validateTimer = setTimeout(runValidation, 350);
  }

  // closeScheduleModal(): cierra close schedule modal; sin efectos secundarios.
  function closeScheduleModal() {
    overlay.remove();
  }

  [orderSel, dateInput, startInput, endInput, techSel, modal.querySelector('#schReason')].forEach(el => {
    el.addEventListener('change', () => { markDirty(); updateReasonVisibility(); refreshTechOptions(); updateTechWarning(); scheduleValidate(); });
    el.addEventListener('input', () => { markDirty(); scheduleValidate(); });
  });
  modal.querySelector('#schOrderSearch').addEventListener('input', (e) => {
    const q = normalizeText(e.target.value);
    Array.from(orderSel.options).forEach(opt => {
      const txt = normalizeText(opt.textContent);
      opt.style.display = txt.includes(q) ? '' : 'none';
    });
  });
  modal.querySelector('#schClose').addEventListener('click', async () => {
    if (dirty && !(await confirmDialog('Los cambios no guardados se perderán.', { title: '¿Descartar cambios?', confirmLabel: 'Descartar', cancelLabel: 'Seguir editando', danger: true }))) return;
    closeScheduleModal();
  });
  modal.querySelector('#schCancel').addEventListener('click', async () => {
    if (dirty && !(await confirmDialog('Los cambios no guardados se perderán.', { title: '¿Descartar cambios?', confirmLabel: 'Descartar', cancelLabel: 'Seguir editando', danger: true }))) return;
    closeScheduleModal();
  });
  overlay.addEventListener('click', async (e) => { if (e.target === overlay) { if (dirty && !(await confirmDialog('Los cambios no guardados se perderán.', { title: '¿Descartar cambios?', confirmLabel: 'Descartar', cancelLabel: 'Seguir editando', danger: true }))) return; closeScheduleModal(); } });

  modal.querySelector('#schSave').addEventListener('click', async () => {
    const oid = orderSel.value;
    if (!oid) { notify('Selecciona una orden.', 'error'); return; }
    if (!dateInput.value || !startInput.value || !endInput.value) { notify('Completa fecha y hora.', 'error'); return; }
    const isReprogram = !!(orderSel.selectedOptions[0] && orderSel.selectedOptions[0].dataset.scheduled);
     const reasonErr = modal.querySelector('#schReasonError');
     if (reasonErr) reasonErr.textContent = '';
     if (isReprogram) {
       const reason = modal.querySelector('#schReason').value;
       if (!reason) { if (reasonErr) reasonErr.textContent = 'Motivo del cambio obligatorio.'; modal.querySelector('#schReason').focus(); return; }
     }
    const payload = {
      start: dateInput.value + 'T' + startInput.value + ':00',
      end: dateInput.value + 'T' + endInput.value + ':00',
      notes: modal.querySelector('#schNotes').value || undefined,
      version: Number(orderSel.selectedOptions[0].dataset.version || 0),
    };
    if (techSel.value) payload.technician_ids = [Number(techSel.value)];
    else payload.technician_ids = [];
    if (isReprogram) payload.reason = modal.querySelector('#schReason').value + (modal.querySelector('#schReasonComment').value ?  ' · ' + modal.querySelector('#schReasonComment').value : '');

    const path = isReprogram ? ('/api/v1/work-orders/' + oid + '/schedule') : ('/api/v1/work-orders/' + oid + '/schedule');
    const method = isReprogram ? 'PATCH' : 'POST';
    const res = await api(method, path, payload);
    if (res.ok) {
      closeScheduleModal();
      notify('Visita programada.', 'success');
   const cs = state.calendarState;
      cs.selectedEventId = Number(oid);
      cs.highlightId = Number(oid);
      render();
      setTimeout(() => { if (cs.highlightId === Number(oid)) { cs.highlightId = null; quietRender(); } }, 1500);
    } else {
      const code = res.body && res.body.code;
      if (res.status === 409 && res.body && res.body.code === 'STALE_VERSION') {
        notify('Otro usuario modificó esta orden.', 'error');
        const reloadBtn = document.createElement('button');
        reloadBtn.className = 'sigos-btn-secondary'; reloadBtn.style.height = '28px'; reloadBtn.textContent = 'Recargar';
        reloadBtn.addEventListener('click', () => { closeScheduleModal(); render(); });
        conflictActions.style.display = 'flex';
        conflictActions.innerHTML = '';
        conflictActions.appendChild(reloadBtn);
      } else if (res.status === 409) {
        const msg = (res.body && (res.body.message || res.body.error)) || 'Conflicto de horario.';
        valDiv.innerHTML = '<span style="color:var(--c-danger)">' + escapeHtml(msg) + '</span>';
        conflictActions.style.display = 'flex';
        conflictActions.innerHTML = '';
        const b1 = document.createElement('button'); b1.className='sigos-btn-secondary'; b1.style.height='28px'; b1.textContent='Elegir otro horario';
        b1.addEventListener('click', () => startInput.focus()); conflictActions.appendChild(b1);
        if (techSel.value) {
          const b2 = document.createElement('button'); b2.className='sigos-btn-secondary'; b2.style.height='28px'; b2.textContent='Ver agenda de ' + (techSel.selectedOptions[0].textContent.split( ' · ')[0]);
          b2.addEventListener('click', () => { closeScheduleModal(); csFilterByTech(techSel.value); });
          conflictActions.appendChild(b2);
        }
        notify(msg, 'error');
      } else if (res.status === 422) {
        notify((res.body && (res.body.message || res.body.error)) || 'Datos inválidos.', 'error');
      } else if (res.status === 403) {
        notify('Sin permisos.', 'error');
      } else {
        notify((res.body && (res.body.message || res.body.error)) || 'Error del servidor.', 'error');
      }
    }
  });

  updateReasonVisibility();
  runValidation();

  // highlight saved event in grid after render? handled by cs.highlightId
}

// devuelve cs filter by tech; sin efectos secundarios.
function csFilterByTech(uid) {
  const cs = state.calendarState;
  if (!cs) return;
  cs.filters.technician_id = String(uid);
  cs.selectedDay = cs.selectedDay || calTodayStr();
  render();
}

// close modal helper available globally
// closeScheduleModal(): cierra close schedule modal; actualiza el DOM.
function closeScheduleModal() {
  const overlay = document.querySelector('div[style*="z-index:10000"]');
  if (overlay) overlay.remove();
}

// askReason(): solicita ask reason; actualiza el DOM.
function askReason() {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:10001;display:flex;align-items:center;justify-content:center;';
    const modal = document.createElement('div');
    modal.style.cssText = 'width:320px;background:var(--c-surface);border-radius:8px;padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.2);';
    modal.innerHTML = `
      <div style="font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav);margin-bottom:8px">Motivo del cambio</div>
      <select id="reasonSel" class="sigos-input" style="height:36px;width:100%;margin-bottom:6px">
        <option value="">Selecciona motivo</option>
        <option value="Cliente reprogramó">Cliente reprogramó</option>
        <option value="Técnico no disponible">Técnico no disponible</option>
        <option value="Clima">Clima</option>
        <option value="Falta de material">Falta de material</option>
        <option value="Otro">Otro</option>
      </select>
      <input id="reasonComment" class="sigos-input" style="height:32px;width:100%" placeholder="Comentario">
      <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px">
        <button type="button" id="reasonCancel" class="sigos-btn-secondary" style="height:32px">Cancelar</button>
        <button type="button" id="reasonOk" class="sigos-btn-primary" style="height:32px">Aceptar</button>
      </div>
    `;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    modal.querySelector('#reasonCancel').addEventListener('click', () => { overlay.remove(); resolve(null); });
    modal.querySelector('#reasonOk').addEventListener('click', () => {
      const v = modal.querySelector('#reasonSel').value;
      if (!v) { notify('Motivo obligatorio.', 'error'); return; }
      const c = modal.querySelector('#reasonComment').value;
      overlay.remove();
      resolve(v + (c ?  ' · ' + c : ''));
    });
  });
}

let _dragState = null;
let _ghost = null;
let _validateTimer = null;
let _lastValidateKey = '';

// devuelve remove ghost; sin efectos secundarios.
function removeGhost() {
  if (_ghost) { _ghost.remove(); _ghost = null; }
}

// devuelve begin drag event; actualiza el DOM.
function beginDragEvent(ev, eventId) {
  const cs = state.calendarState;
  if (!cs) return;
  if (!hasRole('admin') && !hasRole('dispatcher')) return;
  // devuelve ev obj; sin efectos secundarios.
  const evObj = (state._calItems || []).find(e => e.order_id === eventId);
  if (!evObj) return;
  if (!['pending','assigned','in_progress'].includes(evObj.status)) return;
  _dragState = {
    type: 'event',
    eventId,
    evObj: JSON.parse(JSON.stringify(evObj)),
    pointerId: ev.pointerId,
    startX: ev.clientX,
    startY: ev.clientY,
    currentX: ev.clientX,
    currentY: ev.clientY,
    started: false,
    target: null,
    lastValidation: null,
  };
  const el = ev.currentTarget;
  try { el.setPointerCapture(ev.pointerId); } catch(e) {}
  // devuelve on move; actualiza el DOM.
  const onMove = (e) => onDragMove(e);
  // devuelve on up; actualiza el DOM.
  const onUp = (e) => onDragEnd(e);
  // devuelve on cancel; actualiza el DOM.
  const onCancel = () => cancelDrag();
  document.addEventListener('pointermove', onMove);
  document.addEventListener('pointerup', onUp);
  document.addEventListener('pointercancel', onCancel);
  _dragState._cleanup = () => {
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    document.removeEventListener('pointercancel', onCancel);
  };
  // threshold check via move
}

// devuelve begin drag tray; actualiza el DOM.
function beginDragTray(ev, orderId) {
  if (!hasRole('admin') && !hasRole('dispatcher')) return;
  // devuelve order; sin efectos secundarios.
  const order = (state._calUnassigned || []).find(o => o.id === orderId) || (state._calItems || []).find(o => o.order_id === orderId);
  _dragState = {
    type: 'tray',
    orderId,
    pointerId: ev.pointerId,
    startX: ev.clientX,
    startY: ev.clientY,
    currentX: ev.clientX,
    currentY: ev.clientY,
    started: false,
  };
  try { ev.currentTarget.setPointerCapture(ev.pointerId); } catch(e) {}
  // devuelve on move; actualiza el DOM.
  const onMove = (e) => onDragMove(e);
  // devuelve on up; actualiza el DOM.
  const onUp = (e) => onDragEnd(e);
  // devuelve on cancel; actualiza el DOM.
  const onCancel = () => cancelDrag();
  document.addEventListener('pointermove', onMove);
  document.addEventListener('pointerup', onUp);
  document.addEventListener('pointercancel', onCancel);
  _dragState._cleanup = () => {
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    document.removeEventListener('pointercancel', onCancel);
  };
}

// devuelve begin resize; actualiza el DOM.
function beginResize(ev, eventId) {
  // devuelve ev obj; sin efectos secundarios.
  const evObj = (state._calItems || []).find(e => e.order_id === eventId);
  if (!evObj) return;
  if (!['pending','assigned','in_progress'].includes(evObj.status)) return;
  _dragState = {
    type: 'resize',
    eventId,
    evObj: JSON.parse(JSON.stringify(evObj)),
    pointerId: ev.pointerId,
    startY: ev.clientY,
    started: true,
  };
  try { ev.currentTarget.setPointerCapture(ev.pointerId); } catch(e) {}
  // devuelve on move; actualiza el DOM.
  const onMove = (e) => onResizeMove(e);
  // devuelve on up; actualiza el DOM.
  const onUp = (e) => onResizeEnd(e);
  // devuelve on cancel; actualiza el DOM.
  const onCancel = () => cancelDrag();
  document.addEventListener('pointermove', onMove);
  document.addEventListener('pointerup', onUp);
  document.addEventListener('pointercancel', onCancel);
  _dragState._cleanup = () => {
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    document.removeEventListener('pointercancel', onCancel);
  };
}

// devuelve on drag move; actualiza el DOM.
function onDragMove(e) {
  if (!_dragState) return;
  _dragState.currentX = e.clientX;
  _dragState.currentY = e.clientY;
  const dx = e.clientX - _dragState.startX;
  const dy = e.clientY - _dragState.startY;
  if (!_dragState.started) {
    if (Math.hypot(dx, dy) < 4) return;
    _dragState.started = true;
    if (_dragState.type !== 'resize') {
      _ghost = document.createElement('div');
      _ghost.style.cssText = 'position:fixed;pointer-events:none;z-index:10002;opacity:.7;background:var(--c-primary-soft);border:2px dashed var(--c-primary);border-radius:4px;padding:2px 4px;font-size:11px;white-space:nowrap;';
      _ghost.textContent = _dragState.type === 'tray' ? 'Programar' : (orderCode(_dragState.evObj) || 'Visita');
      document.body.appendChild(_ghost);
    }
  }
  if (_dragState.started && _ghost) {
    _ghost.style.left = (e.clientX + 12) + 'px';
    _ghost.style.top = (e.clientY + 12) + 'px';
  }
  const scroller = document.querySelector('.cal-grid-scroll');
  if (scroller) {
    const rect = scroller.getBoundingClientRect();
    if (e.clientY < rect.top + 40) scroller.scrollTop -= 8;
    if (e.clientY > rect.bottom - 40) scroller.scrollTop += 8;
  }
  const target = (e.target && e.target.closest) ? e.target.closest('[data-slot-date],[data-day]') : null;
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const slot = el ? el.closest('[data-slot-date]') : null;
  const dayCell = el ? el.closest('[data-day]') : null;
  if (slot) {
    const date = slot.dataset.slotDate;
    const hour = Number(slot.dataset.slotHour);
    const rect = slot.getBoundingClientRect();
    const snap = (state.calendarState && state.calendarState.view) ? 30 : 30;
    // use settings interval if available? default 30
    const interval = 30;
    const y = e.clientY - rect.top;
    const rawMin = (y / rect.height) * 60;
    const minute = Math.max(0, Math.min(59, Math.round(rawMin / interval) * interval));
    if (minute === 60) { /* carry */ }
    const startStr = String(hour).padStart(2,'0') + ':' + String(minute).padStart(2,'0');
    _dragState.target = { date, time: startStr, slot };
    if (_dragState.type === 'event') {
      validateDragTarget(_dragState, date, startStr);
    } else if (_dragState.type === 'tray') {
      if (_ghost) _ghost.style.background = 'var(--c-cal-today)';
    }
  } else if (dayCell) {
    const date = dayCell.dataset.day;
    _dragState.target = { date, time: (_dragState.evObj ? _dragState.evObj.start.slice(11,16) : '08:00') };
    if (_ghost) _ghost.style.background = 'var(--c-cal-today)';
  } else {
    _dragState.target = null;
    if (_ghost) _ghost.style.background = 'var(--c-danger-bg)';
  }
}

// validateDragTarget(ds, date, time): valida validate drag target; realiza peticiones de red.
function validateDragTarget(ds, date, time) {
  const key = date + 'T' + time;
  if (key === _lastValidateKey) return;
  _lastValidateKey = key;
  clearTimeout(_validateTimer);
  _validateTimer = setTimeout(async () => {
    const evObj = ds.evObj;
    const dur = new Date(evObj.end) - new Date(evObj.start);
    const endMin = (parseInt(time.split(':')[0],10)*60 + parseInt(time.split(':')[1],10)) + dur/60000;
    const endH = String(Math.floor(endMin/60)).padStart(2,'0');
    const endM = String(Math.round(endMin%60)).padStart(2,'0');
    const payload = {
      order_id: ds.eventId,
      start: date + 'T' + time + ':00',
      end: date + 'T' + endH + ':' + endM + ':00',
      technician_ids: (evObj.technicians||[]).map(t=>t.id),
      reason: 'drag',
    };
    const res = await api('POST', '/api/v1/calendar/validate', payload, null, null, true, { loading: false }); // validación en vivo
    if (!_dragState || _dragState !== ds) return;
    if (res.ok && res.body && res.body.ok) {
      ds.lastValidation = { ok: true };
      if (_ghost) { _ghost.style.background = 'var(--c-success-bg)'; _ghost.style.borderColor = 'var(--c-success)'; }
    } else {
      const msg = (res.body && res.body.conflicts && res.body.conflicts[0] && (res.body.conflicts[0].message || res.body.conflicts[0].code)) || 'Conflicto';
      ds.lastValidation = { ok: false, message: msg };
      if (_ghost) { _ghost.style.background = 'var(--c-danger-bg)'; _ghost.style.borderColor = 'var(--c-danger)'; _ghost.title = msg; }
    }
  }, 250);
}

// devuelve on drag end; actualiza el DOM; realiza peticiones de red.
async function onDragEnd(e) {
  if (!_dragState) return;
  const ds = _dragState;
  const cleanup = ds._cleanup;
  if (cleanup) cleanup();
  const started = ds.started;
  const target = ds.target;
  removeGhost();
  if (!started) { _dragState = null; _lastValidateKey = ''; return; } // simple click

  // tray drag -> open modal preloaded
  if (ds.type === 'tray') {
    if (target && target.date) {
      openScheduleModal({ orderId: ds.orderId, date: target.date, hour: (target.time||'08:00').split(':')[0], minute: (target.time||'08:00').split(':')[1] });
    }
    _dragState = null; _lastValidateKey = ''; return;
  }

  if (ds.type === 'resize') { _dragState = null; return; }

  if (!target) { _dragState = null; _lastValidateKey = ''; notify('Soltar en una celda válida.', 'error'); return; }
  const evObj = ds.evObj;
  const origStart = new Date(evObj.start);
  const origEnd = new Date(evObj.end);
  const dur = origEnd - origStart;
  const newStartStr = target.date + 'T' + target.time + ':00';
  const newStart = new Date(newStartStr);
  const newEnd = new Date(newStart.getTime() + dur);
  // if no change, do nothing
  if (newStart.getTime() === origStart.getTime() && target.date === evObj.start.slice(0,10)) {
    _dragState = null; _lastValidateKey = ''; return;
  }
  // validate one last time
  if (ds.lastValidation && ds.lastValidation.ok === false) {
    notify(ds.lastValidation.message || 'Conflicto', 'error');
    _dragState = null; _lastValidateKey = ''; return;
  }
  const reason = await askReason();
  if (!reason) { _dragState = null; _lastValidateKey = ''; return; }

  const items = state._calItems || [];
  const idx = items.findIndex(x => x.order_id === ds.eventId);
  const backup = idx >= 0 ? JSON.parse(JSON.stringify(items[idx])) : null;
  if (idx >= 0) {
    items[idx].start = newStart.toISOString();
    items[idx].end = newEnd.toISOString();
  }
  state._calItems = items;
  render();

  const payload = {
    start: newStartStr,
    end: newStart.toISOString().slice(0,10) + 'T' + String(newEnd.getHours()).padStart(2,'0') + ':' + String(newEnd.getMinutes()).padStart(2,'0') + ':00',
    technician_ids: (evObj.technicians||[]).map(t=>t.id),
    reason,
    version: evObj.version,
  };
  const method = evObj.start ? 'PATCH' : 'POST';
  const res = await api('PATCH', '/api/v1/work-orders/' + ds.eventId + '/schedule', payload);
  if (res.ok) {
    notify('Movido. Deshacer disponible 8 s.', 'success');
    const undoBtn = document.createElement('button');
    // simple notify with undo
    const el = document.createElement('div');
    el.style.cssText = 'background:var(--c-success-bg);color:var(--c-success);border-radius:4px;padding:8px 12px;font-size:13px;margin-bottom:8px;display:flex;align-items:center;gap:8px;';
    el.innerHTML = '<span>Movido correctamente.</span>';
    const ub = document.createElement('button');
    ub.textContent = 'Deshacer';
    ub.className = 'sigos-btn-secondary';
    ub.style.height = '24px';
    ub.addEventListener('click', async () => {
      const revPayload = {
        start: evObj.start.slice(0,19),
        end: evObj.end.slice(0,19),
        technician_ids: (evObj.technicians||[]).map(t=>t.id),
        reason: 'Deshacer',
        version: (res.body && res.body.version) ? res.body.version : evObj.version,
      };
      const r2 = await api('PATCH', '/api/v1/work-orders/' + ds.eventId + '/schedule', revPayload);
      if (r2.ok) { notify('Deshacer aplicado.', 'success'); render(); }
      else notify('No se pudo deshacer.', 'error');
      el.remove();
    });
    el.appendChild(ub);
    const container = document.getElementById('alerts') || document.getElementById('content');
    if (container) container.prepend(el);
    setTimeout(() => el.remove(), 8000);
    const cs2 = state.calendarState;
    cs2.highlightId = ds.eventId;
    render();
    setTimeout(() => { if (cs2.highlightId === ds.eventId) { cs2.highlightId = null; quietRender(); } }, 1500);
  } else {
    if (backup && idx >= 0) { items[idx] = backup; state._calItems = items; render(); }
    const msg = (res.body && (res.body.message || res.body.error || res.body.code)) || 'Error al mover.';
    notify(msg, 'error');
  }
  _dragState = null;
  _lastValidateKey = '';
}

// devuelve on resize move; sin efectos secundarios.
function onResizeMove(e) {
  if (!_dragState || _dragState.type !== 'resize') return;
  // visual feedback not implemented; store new end on up
  _dragState.currentY = e.clientY;
}

// devuelve on resize end; realiza peticiones de red.
async function onResizeEnd(e) {
  if (!_dragState || _dragState.type !== 'resize') return;
  const ds = _dragState;
  const cleanup = ds._cleanup;
  if (cleanup) cleanup();
  const evObj = ds.evObj;
  const origStart = new Date(evObj.start);
  const origEnd = new Date(evObj.end);
  const slotHeight = 48; // px per hour? approximate
  const dy = e.clientY - ds.startY;
  const minutesDelta = Math.round((dy / slotHeight) * 60);
  const interval = 30;
  const snapped = Math.round(minutesDelta / interval) * interval;
  let newDur = (origEnd - origStart)/60000 + snapped;
  const minDur = 15;
  const maxDur = 480;
  if (newDur < minDur) newDur = minDur;
  if (newDur > maxDur) newDur = maxDur;
  const newEnd = new Date(origStart.getTime() + newDur*60000);
  if (newEnd.getTime() === origEnd.getTime()) { _dragState = null; return; }
  const reason = await askReason();
  if (!reason) { _dragState = null; return; }
  const payload = {
    start: evObj.start.slice(0,19),
    end: newEnd.toISOString().slice(0,19),
    technician_ids: (evObj.technicians||[]).map(t=>t.id),
    reason,
    version: evObj.version,
  };
  const res = await api('PATCH', '/api/v1/work-orders/' + ds.eventId + '/schedule', payload);
  if (res.ok) {
    notify('Duración actualizada.', 'success');
    const cs = state.calendarState;
    cs.highlightId = ds.eventId;
    render();
    setTimeout(() => { if (cs.highlightId === ds.eventId) { cs.highlightId = null; quietRender(); } }, 1500);
  } else {
    notify((res.body && (res.body.message || res.body.error)) || 'Error', 'error');
  }
  _dragState = null;
}

// cancelDrag(): verifica cancel drag; sin efectos secundarios.
function cancelDrag() {
  if (!_dragState) return;
  const cleanup = _dragState._cleanup;
  if (cleanup) cleanup();
  removeGhost();
  _dragState = null;
  _lastValidateKey = '';
}

document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') cancelDrag();
});

window.addEventListener('focus', () => {
  if (state.view === 'calendar') render();
});

// openCalendarAt(date, techId): abre open calendar at; sin efectos secundarios.
function openCalendarAt(date, techId) {
  if (!state.calendarState) state.calendarState = { view: 'week', anchor: calTodayStr(), selectedDay: calTodayStr(), filters: { technician_id: '', status: '', type: '', priority: '', city_id: '', zone_id: '', include_cancelled: false } };
  const cs = state.calendarState;
  if (date) { cs.anchor = String(date).slice(0,10); cs.selectedDay = String(date).slice(0,10); }
  if (techId) cs.filters.technician_id = String(techId);
  state.view = 'calendar';
  render();
}

window.addEventListener('error', (e) => {
  console.error('Runtime error:', e.error || e.message);
  const c = document.getElementById('content');
  if (c) c.innerHTML = '<div class="sigos-card"><div class="empty-state"><div class="empty-state__title">Error en la vista</div><div class="empty-state__text">' + escapeHtml(e.message || 'Error desconocido') + '</div></div></div>';
});

window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled rejection:', e.reason);
  const c = document.getElementById('content');
  if (c) c.innerHTML = '<div class="sigos-card"><div class="empty-state"><div class="empty-state__title">Error en la vista</div><div class="empty-state__text">' + escapeHtml(String(e.reason && (e.reason.message || e.reason) || 'Error desconocido')) + '</div></div></div>';
});



// devuelve day agenda html; sin efectos secundarios.
function dayAgendaHtml(dayKey, byDay, pub, cs, todayStr) {
  const d = new Date(dayKey + "T00:00:00");
  const evs = (byDay && byDay[dayKey]) || [];
  // devuelve cols; sin efectos secundarios.
  const cols = (typeof layoutOverlaps === "function") ? layoutOverlaps(evs) : [];
  let html = '<div class="sigos-card" style="padding:12px 14px;margin-top:8px">';
  html += '<div style="font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav);margin-bottom:6px">' + escapeHtml(d.toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" })) + '</div>';
  if (!evs.length) {
    html += '<div style="font-size:12px;color:var(--c-text-3);padding:8px 0">Sin eventos para este día.</div>';
    html += '</div>';
    return html;
  }
  html += '<div style="display:grid;grid-template-columns:60px 1fr;position:relative">';
  const startHour = parseInt((pub.work_start || "07:00").split(":")[0], 10);
  const endHour = parseInt((pub.work_end || "18:00").split(":")[0], 10);
  for (let h = 7; h <= 17; h++) {
    const out = (h < startHour || h >= endHour);
    const rowBg = out ? "background:var(--c-cal-muted);" : "";
    html += '<div style="border-top:1px solid var(--c-border);padding:2px 4px;font-size:10px;color:var(--c-text-3);font-family:JetBrains Mono,monospace;' + rowBg + '">' + String(h).padStart(2, "0") + ":00</div>";
    html += '<div style="border-left:1px solid var(--c-border);border-top:1px solid var(--c-border);min-height:48px;' + rowBg + '"></div>';
  }
  html += '</div>';
  html += '<div style="position:relative;margin-top:-' + (11 * 48) + 'px;padding-left:60px">';
  html += '<div style="position:relative;height:' + (11 * 48) + 'px">';
  cols.forEach((col) => {
    col.forEach((e) => {
      const s = new Date(e.start); const en = new Date(e.end);
      const startMin = (s.getHours() - 7) * 60 + s.getMinutes();
      const durMin = Math.max(20, (en - s) / 60000);
      const top = (startMin / 60) * 48;
      const height = (durMin / 60) * 48;
      const color = e.status === "in_progress" ? "var(--c-ev-progress)" : e.status === "completed" ? 'var(--c-ev-done)' : 'var(--c-ev-idle)';
      html += '<div data-order-modal="\' + e.order_id + \'" role="button" tabindex="0" style="position:absolute;top:' + top + 'px;left:0;width:100%;height:' + height + 'px;background:var(--c-primary-soft);border:1px solid ' + color + ';border-radius:4px;padding:2px 4px;font-size:11px;overflow:hidden;cursor:pointer">';
      html += '<div style="font-family:JetBrains Mono,monospace;font-size:10px">' + escapeHtml(orderCode(e)) + '</div>';
      html += '<div style="font-weight:600">' + escapeHtml(e.title) + '</div>';
      html += '<div style="color:var(--c-text-3)">' + escapeHtml((e.technicians || []).map((t) => t.name).join(", ") || "Por asignar") + '</div>';
      html += '</div>';
    });
  });
  html += '</div></div>';
  html += '</div>';
  return html;
}



// openModal(html): modal generico con contenido libre; delega en sigosModal (ui-components.js).
function openModal(html) {
  const m = sigosModal({ body: html, raw: true, size: 'md' });
  return { overlay: m.overlay, modal: m.card, close: m.close };
}

// openDayModal(dayKey): abre open day modal; sin efectos secundarios.
function openDayModal(dayKey) {
  const byDay = {};
  (state._calItems || []).forEach(e => { const d = e.start.slice(0,10); (byDay[d]=byDay[d]||[]).push(e); });
  const pub = state._calPublic || {};
  const html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div style="font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Agenda del día</div><button type="button" data-close class="sigos-btn-secondary" style="height:28px;padding:0 8px">Cerrar</button></div>' + dayAgendaHtml(dayKey, byDay, pub, state.calendarState, calTodayStr());
  openModal(html);
}

// openPendingModal(): abre open pending modal; sin efectos secundarios.
function openPendingModal() {
  const unassigned = state._calUnassigned || [];
  const porProgramar = unassigned.filter(o => !o.scheduled_at);
  const porAsignar = unassigned.filter(o => o.scheduled_at && !o.assigned_to_id);
  // devuelve pending line; sin efectos secundarios.
  const pendingLine = (o) => {
    const code = orderCode(o);
    const main = o.title || o.customer_name || '';
    // devuelve pr; actualiza el DOM.
    const pr = (typeof priorityOf === 'function' && o.priority) ? priorityOf(o.priority).label : (o.priority || '');
    const parts = [main, pr].filter(Boolean);
    return escapeHtml(code) + (parts.length ? ' - ' + parts.map(escapeHtml).join(' - ') : '');
  };
  let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div style="font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">Pendientes</div><button type="button" data-close class="sigos-btn-secondary" style="height:28px;padding:0 8px">Cerrar</button></div>';
  html += '<div style="font-size:12px;font-weight:600;color:var(--c-text-3)">Por programar (' + porProgramar.length + ')</div>';
  porProgramar.slice(0,20).forEach(o => { html += '<div style="font-size:11px;padding:4px;border-bottom:1px solid var(--c-border)">' + pendingLine(o) + '</div>'; });
  html += '<div style="font-size:12px;font-weight:600;color:var(--c-text-3);margin-top:6px">Por asignar (' + porAsignar.length + ')</div>';
  porAsignar.slice(0,20).forEach(o => { html += '<div style="font-size:11px;padding:4px;border-bottom:1px solid var(--c-border)">' + pendingLine(o) + '</div>'; });
  openModal(html);
}

// openOrderModal(orderId): abre open order modal; actualiza el DOM.
function openOrderModal(orderId) {
  // devuelve ev; sin efectos secundarios.
  const ev = (state._calItems || []).find(e => e.order_id === orderId);
  // devuelve ord; sin efectos secundarios.
  const ord = (state._calUnassigned || []).find(o => o.id === orderId);
  const o = ev || ord;
  if (!o) { notify('Orden no encontrada.', 'error'); return; }
  const code = orderCode(o);
  const title = o.title || 'Orden';
  // devuelve techs; actualiza el DOM.
  const techs = (o.technicians || []).map(t => t.name).join(', ') || 'Por asignar';
  let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><div style="font-family:Outfit;font-weight:600;font-size:14px;color:var(--c-nav)">' + escapeHtml(code) + '</div><button type="button" data-close class="sigos-btn-secondary" style="height:28px;padding:0 8px">Cerrar</button></div>';
  html += '<div style="font-weight:600;font-size:13px;margin-bottom:6px">' + escapeHtml(title) + '</div>';
  html += '<div style="font-size:11px;margin-bottom:2px"><span style="color:var(--c-text-3)">Técnico:</span> ' + escapeHtml(techs) + '</div>';
  if (o.start) html += '<div style="font-size:11px;margin-bottom:2px"><span style="color:var(--c-text-3)">Horario:</span> ' + escapeHtml(o.start.slice(11,16)) + '–' + escapeHtml(o.end.slice(11,16)) + '</div>';
  html += '<div style="font-size:11px;margin-bottom:2px"><span style="color:var(--c-text-3)">Estado:</span> ' + escapeHtml((typeof statusOf === 'function' ? statusOf(o.status).label : o.status)) + '</div>';
  html += '<div style="display:flex;gap:6px;margin-top:10px">';
  html += '<button type="button" class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" data-open-order="\' + orderId + \'">Abrir orden</button>';
  html += '</div>';
  openModal(html);
}






// renderiza la vista reports; actualiza el DOM.
// ---------- Reportes (RF-22 / RF-24) ----------
const reportState = { estado: '', tecnico_id: '', zona: '', desde: '', hasta: '', campo_fecha: 'created_at', pagina: 1, por_pagina: 20 };

// reportQuery(extra): arma el query string del reporte con los filtros activos.
function reportQuery(extra = {}) {
  const q = new URLSearchParams();
  Object.entries({ ...reportState, ...extra }).forEach(([k, v]) => { if (v !== '' && v !== null && v !== undefined) q.set(k, String(v)); });
  return q.toString();
}

// renderReports(content): panel de reportes con filtros, resumen por estado, tabla paginada y exportacion.
async function renderReports(content) {
  const profilesRes = await api('GET', '/api/v1/technician-profiles');
  if (!content.isConnected) return; // la vista cambio mientras cargaba
  const profiles = profilesRes.ok && Array.isArray(profilesRes.body) ? profilesRes.body : [];
  const statuses = ['pending', 'assigned', 'in_progress', 'completed', 'cancelled'];
  const opt = (v, label, cur) => `<option value="${escapeHtml(v)}" ${String(cur) === String(v) ? 'selected' : ''}>${escapeHtml(label)}</option>`;
  content.innerHTML = `
    <div class="sigos-card" style="padding:16px;margin-bottom:16px">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;align-items:end">
        <div class="fld"><label for="rpEstado">Estado</label><select id="rpEstado" class="sigos-select" style="width:100%">${opt('', 'Todos', reportState.estado)}${statuses.map((s) => opt(s, statusOf(s).label, reportState.estado)).join('')}</select></div>
        <div class="fld"><label for="rpTec">Técnico</label><select id="rpTec" class="sigos-select" style="width:100%">${opt('', 'Todos', reportState.tecnico_id)}${profiles.filter((p) => p.user?.id).map((p) => opt(p.user.id, p.user.username || p.first_name || '', reportState.tecnico_id)).join('')}</select></div>
        <div class="fld"><label for="rpZona">Zona</label><input id="rpZona" class="sigos-input" value="${escapeHtml(reportState.zona)}" placeholder="Cualquiera"></div>
        <div class="fld"><label for="rpCampo">Fecha por</label><select id="rpCampo" class="sigos-select" style="width:100%">${opt('created_at', 'Creación', reportState.campo_fecha)}${opt('scheduled_at', 'Programación', reportState.campo_fecha)}</select></div>
        <div class="fld"><label for="rpDesde">Desde</label><input id="rpDesde" type="date" class="sigos-input" value="${escapeHtml(reportState.desde)}"></div>
        <div class="fld"><label for="rpHasta">Hasta</label><input id="rpHasta" type="date" class="sigos-input" value="${escapeHtml(reportState.hasta)}"></div>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button type="button" class="sigos-btn-primary" id="rpApply">Aplicar filtros</button>
        <button type="button" class="sigos-btn-secondary" id="rpClear">Limpiar</button>
        <span style="flex:1"></span>
        <button type="button" class="sigos-btn-secondary" id="rpExport">Exportar…</button>
      </div>
      <div id="rpError" style="color:var(--c-danger);font-size:12px;margin-top:6px"></div>
    </div>
    <div id="rpSummary" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:16px"></div>
    <div class="sigos-card" style="overflow:auto"><div id="rpTable">${loaderBlock('Consultando datos del reporte…', 200)}</div></div>`;

  const readFilters = () => {
    reportState.estado = $('#rpEstado').value;
    reportState.tecnico_id = $('#rpTec').value;
    reportState.zona = $('#rpZona').value.trim();
    reportState.campo_fecha = $('#rpCampo').value;
    reportState.desde = $('#rpDesde').value;
    reportState.hasta = $('#rpHasta').value;
  };
  $('#rpApply').addEventListener('click', () => {
    readFilters();
    if (reportState.desde && reportState.hasta && reportState.desde > reportState.hasta) { $('#rpError').textContent = 'La fecha "desde" no puede ser mayor que "hasta"'; return; }
    reportState.pagina = 1; loadReport();
  });
  $('#rpClear').addEventListener('click', () => {
    Object.assign(reportState, { estado: '', tecnico_id: '', zona: '', desde: '', hasta: '', campo_fecha: 'created_at', pagina: 1 });
    renderReports(content);
  });
  $('#rpExport').addEventListener('click', () => { readFilters(); $('#exportBtn')?.click(); });
  loadReport();
}

// loadReport(): consulta /reportes/ordenes y pinta resumen + tabla + paginacion.
async function loadReport() {
  const tableEl = $('#rpTable');
  const sumEl = $('#rpSummary');
  const errEl = $('#rpError');
  if (!tableEl) return;
  if (errEl) errEl.textContent = '';
  tableEl.innerHTML = loaderBlock('Consultando datos del reporte…', 200);
  const res = await api('GET', '/api/v1/reportes/ordenes?' + reportQuery());
  if (!$('#rpTable')) return;
  if (!res.ok) {
    tableEl.innerHTML = `<div style="color:var(--c-danger)">${escapeHtml(res.body?.error || 'No se pudo generar el reporte')}</div>`;
    return;
  }
  const data = res.body || {};
  const resumen = data.resumen || {};
  const total = Number(data.total || 0);
  const totalAll = Object.values(resumen).reduce((a, b) => a + Number(b || 0), 0);
  sumEl.innerHTML = [`<div class="sigos-card" style="padding:12px"><div style="font-size:12px;color:var(--c-text-3)">Total</div><div style="font-size:22px;font-weight:600;color:var(--c-nav)">${totalAll}</div></div>`]
    .concat(Object.entries(resumen).map(([st, n]) => `<div class="sigos-card" style="padding:12px"><div style="font-size:12px;color:var(--c-text-3)"><span class="${statusOf(st).badge}">${escapeHtml(statusOf(st).label)}</span></div><div style="font-size:22px;font-weight:600;color:var(--c-nav);margin-top:4px">${Number(n || 0)}</div></div>`)).join('');
  const items = Array.isArray(data.items) ? data.items : [];
  const pages = Math.max(1, Math.ceil(total / (data.page_size || reportState.por_pagina)));
  const fmt = (v) => (v ? new Date(v).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '');
  tableEl.innerHTML = items.length ? `
    <table class="tbl" style="width:100%">
      <thead><tr><th>ID</th><th>Título</th><th>Estado</th><th>Prioridad</th><th>Cliente</th><th>Zona</th><th>Técnico</th><th>Creada</th><th>Cierre</th></tr></thead>
      <tbody>${items.map((o) => `<tr class="tbl-row" data-rp-order="${o.id}" style="cursor:pointer">
        <td>${o.id}</td><td>${escapeHtml(o.title)}</td><td><span class="${statusOf(o.status).badge}">${escapeHtml(statusOf(o.status).label)}</span></td>
        <td>${escapeHtml(o.priority)}</td><td>${escapeHtml(o.customer_name || '')}</td><td>${escapeHtml(o.zone || '')}</td>
        <td>${escapeHtml(o.assigned_to?.username || '')}</td><td>${escapeHtml(fmt(o.created_at))}</td><td>${escapeHtml(fmt(o.completed_at))}</td></tr>`).join('')}</tbody>
    </table>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;font-size:12px;color:var(--c-text-2)">
      <span>${total} órdenes · página ${data.page || reportState.pagina} de ${pages}</span>
      <span style="display:flex;gap:6px">
        <button type="button" class="sigos-btn-secondary" id="rpPrev" ${reportState.pagina <= 1 ? 'disabled' : ''}>Anterior</button>
        <button type="button" class="sigos-btn-secondary" id="rpNext" ${reportState.pagina >= pages ? 'disabled' : ''}>Siguiente</button>
      </span>
    </div>` : '<div class="empty-state__text">Sin órdenes para los filtros seleccionados</div>';
  $('#rpPrev')?.addEventListener('click', () => { reportState.pagina -= 1; loadReport(); });
  $('#rpNext')?.addEventListener('click', () => { reportState.pagina += 1; loadReport(); });
  $$('[data-rp-order]').forEach((tr) => tr.addEventListener('click', () => openOrderDetail(tr.dataset.rpOrder, tr)));
}


// renderiza la vista mobile; actualiza el DOM.
function renderMobile(content) {
  content.innerHTML = '<div class="sigos-card" style="padding:16px"><h3 style="font-family:Outfit;font-size:15px;color:var(--c-nav);margin:0 0 8px">Vista Tecnico</h3><div style="font-size:13px;color:var(--c-text-2)">Dashboard del tecnico en construccion.</div></div>';
}



// ---------- Indicadores de carga de las vistas ----------
// trackView(fn, message): envuelve una función de vista async(content, ...) con un indicador local sobre su
// contenedor. Si la vista ya pintó su placeholder (loaderBlock) no se duplica; si conserva datos en pantalla
// (filtros, paginación) la capa aparece encima sin perder el contexto. Los refrescos automáticos (quietRender) no lo muestran.
function trackView(fn, message) {
  return async function trackedView(content, ...rest) {
    const L = window.SigosLoading;
    if (!L || state._quietRender || !(content instanceof Element)) return fn.call(this, content, ...rest);
    const id = L.start({ mode: 'local', target: content, message });
    try { return await fn.call(this, content, ...rest); } finally { L.end(id); }
  };
}

// quietRender(): re-render de refresco automático (agenda cada 45 s, fin de resaltado) sin indicador de carga.
function quietRender() {
  state._quietRender = true;
  try { return render(); } finally { state._quietRender = false; }
}

renderDashboard = trackView(renderDashboard, 'Cargando indicadores del dashboard…');
renderOrders = trackView(renderOrders, 'Consultando órdenes…');
renderOrderDetail = trackView(renderOrderDetail, 'Cargando detalle de la orden…');
renderTechnicians = trackView(renderTechnicians, 'Cargando información de técnicos…');
renderCalendar = trackView(renderCalendar, 'Cargando agenda…');
renderSettings = trackView(renderSettings, 'Cargando configuración…');
renderMaterials = trackView(renderMaterials, 'Consultando inventario…');
renderRequests = trackView(renderRequests, 'Consultando solicitudes…');
renderEvidenceList = trackView(renderEvidenceList, 'Consultando evidencias…');
renderEvidenceOrder = trackView(renderEvidenceOrder, 'Cargando evidencias de la orden…');
renderUsers = trackView(renderUsers, 'Consultando usuarios…');
renderNotifications = trackView(renderNotifications, 'Cargando notificaciones…');
renderReports = trackView(renderReports, 'Preparando reportes…');
if (typeof renderEvidenceInbox === 'function') renderEvidenceInbox = trackView(renderEvidenceInbox, 'Cargando bandeja de evidencias…');
