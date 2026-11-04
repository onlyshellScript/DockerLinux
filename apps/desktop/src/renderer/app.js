
const state = {
  session: null,
  view: 'dashboard',
  selectedOrderId: null,
  orders: [],
  materials: [],
  profiles: [],
  notifications: [],
  filters: { status: '', assigned_to_id: '', q: '' },
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function searchField({ placeholder = '', id = '', value = '' } = {}) {
  return `<label class="search-field"><svg class="search-field__icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z"/><path d="M21 21l-4.35-4.35"/></svg><input type="search" class="search-field__input" id="${escapeHtml(id)}" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(value)}" aria-label="Buscar"></label>`;
}

function normalizeText(value) {
  if (value === null || value === undefined) return '';
  let text = String(value).trim().toLowerCase();
  text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  text = text.replace(/\s+/g, ' ').trim();
  return text;
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function orderCode(o) {
  if (!o) return '';
  if (o.order_code) return o.order_code;
  if (o.code) return o.code;
  const id = o.order_id || o.id;
  return id != null ? 'OS-' + String(id).padStart(4, '0') : '';
}

async function api(method, path, body = null, form = null, canRetry = true) {
  const res = await window.sigos.apiRequest({ method, path, body, form, token: state.session?.access_token });
  if (res.status !== 401 || !canRetry || !state.session?.refresh_token) return res;
  const refreshed = await window.sigos.apiRequest({
    method: 'POST',
    path: '/api/v1/auth/refresh',
    body: { refresh_token: state.session.refresh_token },
  });
  if (refreshed.ok && refreshed.body?.access_token) {
    state.session.access_token = refreshed.body.access_token;
    if (refreshed.body.user) state.session.user = refreshed.body.user;
    await saveSession();
    return api(method, path, body, form, false);
  }
  await clearSession();
  render();
  notify('La sesión expiró. Inicia sesión de nuevo.', 'error');
  return res;
}

function notify(message, type = 'info') {
  const colors = { error: ['#FEE2E2', '#991B1B'], success: ['#DCFCE7', '#166534'], info: ['#EEF2F7', '#374151'] };
  const [bg, fg] = colors[type] || colors.info;
  const el = document.createElement('div');
  el.style.cssText = `background:${bg};color:${fg};border-radius:4px;padding:8px 12px;font-size:13px;margin-bottom:8px;`;
  el.textContent = message;
  const container = $('#alerts') || $('#content');
  container.prepend(el);
  setTimeout(() => el.remove(), 4000);
}

function decodeJwtPayload(token) {
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(part));
  } catch { return {}; }
}

async function loadSession() {
  const s = await window.sigos.loadSession();
  if (s && s.access_token) { state.session = s; return true; }
  return false;
}

async function saveSession() {
  if (state.session) await window.sigos.saveSession(state.session);
}

async function clearSession() {
  state.session = null;
  await window.sigos.clearSession();
}

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

function icon(name, size = 18) {
  const inner = ICON_SVG[name] || '';
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

const NAV = [
  { key: 'dashboard', label: 'Dashboard', icon: 'dashboard', roles: null },
  { key: 'orders', label: 'Órdenes', icon: 'orders', roles: null },
  { key: 'technicians', label: 'Técnicos', icon: 'tech', roles: ['admin', 'dispatcher'] },
  { key: 'calendar', label: 'Calendario', icon: 'calendar', roles: null },
  { key: 'materials', label: 'Materiales', icon: 'materials', roles: ['admin', 'dispatcher'] },
  { key: 'evidence', label: 'Evidencias', icon: 'evidence', roles: null },
  { key: 'reports', label: 'Reportes', icon: 'reports', roles: ['admin', 'dispatcher'] },
  { key: 'users', label: 'Usuarios', icon: 'users', roles: ['admin'] },
];

const NAV_BOTTOM = [
  { key: 'notifications', label: 'Notificaciones', icon: 'bell', roles: null },
  { key: 'settings', label: 'Configuración', icon: 'settings', roles: ['admin', 'dispatcher'] },
  { key: 'mobile', label: 'Vista Técnico', icon: 'mobile', roles: null },
];

function navAllowed(item) {
  return !item.roles || item.roles.some((r) => hasRole(r));
}

function statusClass(s) {
  return s === 'in_progress' ? 'inprogress' : (s || '');
}

function render() {
  const app = $('#app');
  if (!state.session) { app.innerHTML = loginTemplate(); bindLogin(); return; }
  app.innerHTML = shellTemplate();
  bindShell();
  renderView();
}

function loginTemplate() {
  const user = state.session?.user || {};
  return `
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#F5F2EB">
    <div class="sigos-card" style="width:420px;padding:32px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px">
        <div class="sb-logo-mark">${icon('orders', 18)}</div>
        <div class="tb-title" style="font-size:20px">SIGOS</div>
      </div>
      <h2 style="font-family:Outfit;font-size:20px;color:#163028;margin-bottom:16px">Iniciar sesión</h2>
      <div id="alerts"></div>
      <div class="fld"><label>Usuario</label><input id="username" class="sigos-input" autocomplete="username"></div>
      <div class="fld"><label>Contraseña</label><input id="password" type="password" class="sigos-input" autocomplete="current-password"></div>
      <button id="loginBtn" class="sigos-btn-primary" style="width:100%;justify-content:center;padding:10px">Ingresar</button>
      <div class="section-label" style="margin:20px 0 8px">Credenciales de desarrollo</div>
      <div class="muted">admin / Admin123!</div>
    </div>
  </div>`;
}

function bindLogin() {
  const btn = $('#loginBtn');
  btn.addEventListener('click', async () => {
    const username = $('#username').value.trim();
    const password = $('#password').value;
    if (!username || !password) { notify('Usuario y contraseña requeridos', 'error'); return; }
    btn.disabled = true; btn.textContent = 'Ingresando...';
    const res = await api('POST', '/api/v1/auth/login', { username, password });
    btn.disabled = false; btn.textContent = 'Ingresar';
    if (!res.ok) { notify(res.body?.error || 'Credenciales inválidas', 'error'); return; }
    state.session = res.body;
    await saveSession();
    notify('Sesión iniciada', 'success');
    render();
  });
  $('#password').addEventListener('keydown', (e) => { if (e.key === 'Enter') btn.click(); });
}

function shellTemplate() {
  const user = state.session.user;
  const roles = (user.roles || []).join(', ');
  const items = (list) => list.filter(navAllowed).map((item) => `
    <a href="#" class="sidebar-nav-item${state.view === item.key ? ' active' : ''}" data-view="${item.key}">
      <span style="flex-shrink:0">${icon(item.icon, 18)}</span><span style="flex:1">${escapeHtml(item.label)}</span>
    </a>`).join('');
  return `
  <div class="shell">
    <aside class="sidebar">
      <div class="sb-logo">
        <div class="sb-logo-mark">${icon('orders', 18)}</div>
        <div><div class="sb-name">SIGOS</div><div class="sb-ver">v2.4.1 — Gas Natural</div></div>
      </div>
      <div class="sb-label">Principal</div>
      <nav class="sb-nav">
        ${items(NAV)}
        <div class="sb-sep"></div>
        <div class="sb-label" style="padding:0 24px 6px">Sistema</div>
        ${items(NAV_BOTTOM)}
      </nav>
      <div class="sb-user">
        <div class="avatar-lg">${escapeHtml(user.initials || (user.username || '').slice(0, 2).toUpperCase())}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(user.username || user.name || '')}</div>
          <div style="font-size:11px;color:rgba(255,255,255,.4);margin-top:1px">${escapeHtml(roles)}</div>
        </div>
        <a href="#" id="logoutBtn" title="Cerrar sesión" aria-label="Cerrar sesión" style="color:rgba(255,255,255,.4);padding:4px;display:flex">${icon('logout', 16)}</a>
      </div>
    </aside>
    <div class="main">
      <header class="topbar">
        <div style="flex:1"><div class="tb-title" id="viewTitle">SIGOS</div><div class="tb-sub" id="viewSub"></div></div>
        <div style="width:300px">${searchField({ placeholder: 'Buscar órdenes, técnicos, clientes...', id: 'globalSearch' })}</div>
        <div id="topbarActions" style="display:flex;gap:8px;align-items:center"></div>
        <button class="tb-btn" aria-label="Ayuda">Ayuda</button>
        <a class="bell" href="#" id="bellBtn" aria-label="Notificaciones">${icon('bell', 18)}<span id="bellBadge" style="display:none">0</span></a>
        <a class="tb-btn" href="#" id="fieldBtn" aria-label="Vista técnico">${icon('mobile', 16)}<span>Campo</span></a>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="avatar-sm">${escapeHtml(user.initials || (user.username || '').slice(0, 2).toUpperCase())}</div>
          <div><div style="font-size:12px;font-weight:600;color:#1A1F27;line-height:1.2">${escapeHtml(user.username || user.name || '')}</div><div style="font-size:10px;color:#96908A">${escapeHtml(roles)}</div></div>
        </div>
      </header>
      <div id="alerts" style="padding:0 24px"></div>
      <main class="content" id="content" aria-busy="false" style="flex:1;overflow:auto;padding:20px 24px"></main>
    </div>
  </div>`;
}

function bindShell() {
  $$('[data-view]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); state.view = b.dataset.view; state.selectedOrderId = null; render(); }));
  $('#logoutBtn').addEventListener('click', async (e) => { e.preventDefault(); await clearSession(); render(); });
  $('#bellBtn').addEventListener('click', (e) => { e.preventDefault(); state.view = 'notifications'; render(); });
  $('#fieldBtn').addEventListener('click', (e) => { e.preventDefault(); state.view = 'mobile'; render(); });
}

const VIEW_META = {
  dashboard: ['Dashboard', 'Resumen general del sistema'],
  orders: ['Órdenes de servicio', 'Gestión de órdenes'],
  'order-detail': ['Detalle de orden', ''],
  technicians: ['Técnicos', 'Perfiles y disponibilidad'],
  calendar: ['Calendario', 'Visitas programadas'],
  materials: ['Materiales', 'Inventario y stock'],
  evidence: ['Evidencias', 'Archivos y observaciones'],
  reports: ['Reportes', 'Indicadores y exportación'],
  users: ['Usuarios', 'Gestión de accesos'],
  notifications: ['Notificaciones', 'Avisos del sistema'],
  settings: ['Configuración', 'Preferencias'],
  mobile: ['Vista Técnico', 'Modo campo'],
};

function renderView() {
  const content = $('#content');
  const meta = VIEW_META[state.view] || [state.view, ''];
  $('#viewTitle').textContent = meta[0];
  const longDate = new Date().toLocaleDateString('es-ES', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  $('#viewSub').textContent = longDate.charAt(0).toUpperCase() + longDate.slice(1);
  $('#topbarActions').innerHTML = '';
  if (state.view === 'dashboard') renderDashboard(content);
  else if (state.view === 'orders') renderOrders(content);
  else if (state.view === 'order-detail') renderOrderDetail(content);
  else if (state.view === 'technicians') renderTechnicians(content);
  else if (state.view === 'calendar') renderCalendar(content);
  else if (state.view === 'settings') renderSettings(content);
  else if (state.view === 'materials') renderMaterials(content);
  else if (state.view === 'users') renderUsers(content);
  else if (state.view === 'notifications') renderNotifications(content);
  else pendingView(content, meta[0]);
}

const CAL_TZ = (state.calendarTz) || 'America/Bogota';
function calTodayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: CAL_TZ });
}
function isoWeekNumber(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(),0,1));
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}
function calStartOfWeek(d) {
  const x = new Date(d);
  const day = x.getDay();
  const diff = (day === 0 ? -6 : 1 - day);
  x.setDate(x.getDate() + diff);
  x.setHours(0,0,0,0);
  return x;
}
function calAddDays(d, n) { const x = new Date(d); x.setDate(x.getDate()+n); return x; }
function calFmtDate(d, opts) { return d.toLocaleDateString('es-CO', opts); }
function calShortDay(d) { return d.toLocaleDateString('es-CO', { weekday: 'short' }).replace('.',''); }

async function renderCalendar(content) {
   if (!state.calendarState) state.calendarState = { view: 'week', anchor: calTodayStr(), selectedDay: calTodayStr(), filters: { technician_id: '', status: '', type: '', priority: '', city_id: '', zone_id: '', include_cancelled: false } };
  const cs = state.calendarState;
  // load tz from settings public
  try {
    const s = await api('GET', '/api/v1/settings/public');
    if (s.body && s.body.timezone) { state.calendarTz = s.body.timezone; }
  } catch (e) {}
  const tz = state.calendarTz || CAL_TZ;
  const anchor = new Date(cs.anchor + 'T00:00:00');
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
  content.innerHTML = '<div class="empty-state"><div class="empty-state__title">Cargando calendario...</div></div>';
  const params = new URLSearchParams();
  params.set('from', fromIso);
  params.set('to', toIso);
  Object.entries(cs.filters).forEach(([k,v]) => { if (v) params.set(k, v); });
  if (cs.filters.include_cancelled) params.set('include_cancelled', 'true');
  let items = [], unassigned = [], error = null, offline = false, eventsErrorDetail = null, unassignedError = null;
  try {
    const res = await api('GET', '/api/v1/calendar/events?' + params.toString());
    if (res.ok) items = (res.body && res.body.items) || [];
    else { error = (res.body && (res.body.message || res.body.error)) || 'Error del servidor'; eventsErrorDetail = { status: res.status, code: (res.body && res.body.code) || null, url: '/api/v1/calendar/events', body: res.body, transportError: res.error || null }; console.error('calendar events error', eventsErrorDetail); }
    const ures = await api('GET', '/api/v1/calendar/unassigned?page_size=50');
    if (ures.ok) unassigned = (ures.body && ures.body.items) || [];
    else { unassignedError = (ures.body && (ures.body.message || ures.body.error)) || 'Error del servidor'; console.error('calendar unassigned error', ures); }
    state._calItems = items;
    let techOpts = [], cityOpts = [], zoneOpts = [], typeOpts = [];
    if (hasRole('admin') || hasRole('dispatcher')) {
      try { const tr = await api('GET', '/api/v1/technicians?page_size=200&active=true'); if (tr.ok) techOpts = (tr.body && tr.body.items) || []; } catch(e) {}
    }
    try { const cr = await api('GET', '/api/v1/catalogs/cities'); if (cr.ok) cityOpts = cr.body || []; } catch(e) {}
    try { const zr = await api('GET', '/api/v1/catalogs/zones'); if (zr.ok) zoneOpts = zr.body || []; } catch(e) {}
    try { const itr = await api('GET', '/api/v1/catalogs/installation-types'); if (itr.ok) typeOpts = itr.body || []; } catch(e) {}
  } catch (e) { offline = true; error = String(e); }
  // period label
  let label = '';
  if (cs.view === 'day') label = anchor.toLocaleDateString('es-CO', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
  else if (cs.view === 'month') label = anchor.toLocaleDateString('es-CO', { month:'long', year:'numeric' });
  else label = 'Semana ' + isoWeekNumber(anchor) + ' · ' + calFmtDate(days[0], { day:'numeric', month:'short' }) + ' – ' + calFmtDate(days[6], { day:'numeric', month:'short', year:'numeric' });
  // summary counts
  const hasEventsError = !!error;
  const programmed = hasEventsError ? '—' : items.length;
  const unassignedCount = hasEventsError ? '—' : unassigned.length;
  const inProgress = hasEventsError ? '—' : items.filter(e => e.status === 'in_progress').length;
  const byDay = {};
  items.forEach(e => { const d = e.start.slice(0,10); (byDay[d]=byDay[d]||[]).push(e); });
  const todayStr = calTodayStr();
  let html = '';
  // topbar actions area handled by view title; add period nav
   const canSchedule = hasRole('admin') || hasRole('dispatcher');
   html += '<div style="display:flex;flex-direction:column;height:100%;gap:8px">';
   // row 1
   html += '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">';
   html += '<button class="sigos-btn-secondary" style="width:36px;height:36px;padding:0;display:inline-flex;align-items:center;justify-content:center" id="calPrev" aria-label="Anterior"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg></button>';
   html += '<button class="sigos-btn-secondary" style="height:36px" id="calToday">Hoy</button>';
   html += '<button class="sigos-btn-secondary" style="width:36px;height:36px;padding:0;display:inline-flex;align-items:center;justify-content:center" id="calNext" aria-label="Siguiente"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg></button>';
   html += '<span style="font-family:Outfit;font-weight:600;font-size:15px;color:#163028;margin-left:8px">' + escapeHtml(label) + '</span>';
   html += '<div style="margin-left:12px;display:flex;gap:4px">';
   ['day','week','month'].forEach(v => {
     const lbl = v==='day'?'Día':v==='week'?'Semana':'Mes';
     html += '<button class="sigos-btn-secondary" data-calview="' + v + '" style="height:36px' + (cs.view===v?';background:#163028;color:#fff':'') + '">' + lbl + '</button>';
   });
   html += '</div>';
   html += '<div style="margin-left:auto;display:flex;gap:6px">';
   html += '<button class="sigos-btn-primary" ' + (canSchedule?'':'disabled title="Sin permisos"') + ' style="height:36px" id="calSchedule">+ Programar visita</button>';
   html += '</div></div>';
   // row 2: chips + filters
   const hasActiveFilters = !!(cs.filters.technician_id || cs.filters.status || cs.filters.type || cs.filters.priority || cs.filters.city_id || cs.filters.zone_id || cs.filters.include_cancelled);
   html += '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">';
   html += '<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid #DDD9D3;border-radius:999px;font-size:12px;cursor:pointer" id="chipProg">Programadas <span style="font-family:Outfit;font-weight:800;font-size:18px;color:#2A5C45">' + programmed + '</span></span>';
   html += '<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid #DDD9D3;border-radius:999px;font-size:12px;cursor:pointer" id="chipUnas">Sin asignar <span style="font-family:Outfit;font-weight:800;font-size:18px;color:#C9892A">' + unassignedCount + '</span></span>';
   html += '<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid #DDD9D3;border-radius:999px;font-size:12px;cursor:pointer" id="chipProg2">En ejecución <span style="font-family:Outfit;font-weight:800;font-size:18px;color:#2A5C45">' + inProgress + '</span></span>';
   // technician select
   const techOptions = techOpts.map(t => '<option value="' + (t.user_id||t.id) + '"' + (String(cs.filters.technician_id)===String(t.user_id||t.id)?' selected':'') + '>' + escapeHtml(t.full_name||t.username||('Técnico '+(t.user_id||t.id))) + '</option>').join('');
   const statusOpts = ['pending','assigned','in_progress','completed','closed','cancelled'].map(s => '<option value="' + s + '"' + (cs.filters.status===s?' selected':'') + '>' + escapeHtml(s) + '</option>').join('');
   const typeOptions = typeOpts.map(t => '<option value="' + escapeHtml(t.code) + '"' + (cs.filters.type===t.code?' selected':'') + '>' + escapeHtml(t.label) + '</option>').join('');
   const prioOptions = ['low','medium','high','urgent'].map(p => '<option value="' + p + '"' + (cs.filters.priority===p?' selected':'') + '>' + escapeHtml(p) + '</option>').join('');
   const cityOptions = cityOpts.map(c => '<option value="' + c.id + '"' + (String(cs.filters.city_id)===String(c.id)?' selected':'') + '>' + escapeHtml(c.name||c.label) + '</option>').join('');
   const zoneOptions = zoneOpts.map(z => '<option value="' + z.id + '"' + (String(cs.filters.zone_id)===String(z.id)?' selected':'') + '>' + escapeHtml(z.name) + '</option>').join('');
   html += '<select class="sigos-input" style="height:36px;min-width:150px" id="calFiltTech"><option value="">Todos los técnicos</option>' + techOptions + '</select>';
   html += '<select class="sigos-input" style="height:36px;min-width:130px" id="calFiltStatus"><option value="">Todos los estados</option>' + statusOpts + '</select>';
   html += '<select class="sigos-input" style="height:36px;min-width:120px" id="calFiltType"><option value="">Todos los tipos</option>' + typeOptions + '</select>';
   html += '<select class="sigos-input" style="height:36px;min-width:130px" id="calFiltPrio"><option value="">Todas las prioridades</option>' + prioOptions + '</select>';
   html += '<select class="sigos-input" style="height:36px;min-width:130px" id="calFiltCity"><option value="">Todas las ciudades</option>' + cityOptions + '</select>';
   html += '<select class="sigos-input" style="height:36px;min-width:130px" id="calFiltZone"><option value="">Todas las zonas</option>' + zoneOptions + '</select>';
   html += '<label style="font-size:12px;display:inline-flex;align-items:center;gap:4px"><input type="checkbox" id="calFiltCancel"> Incluir canceladas</label>';
   if (hasActiveFilters) html += '<button class="sigos-btn-secondary" style="height:36px" id="calClear">Limpiar</button>';
   if (!error) html += '<span style="font-size:12px;color:#96908A">' + items.length + ' resultado' + (items.length===1?'':'s') + '</span>';
   html += '</div>';
  if (offline) {
    html += '<div style="background:#FDECEA;color:#D63B3B;padding:8px;border-radius:6px;font-size:12px">Sin conexión · datos de las ' + new Date().toLocaleTimeString('es-CO') + '</div>';
  } else if (error) {
    const d = eventsErrorDetail || {};
    html += '<div class="sigos-card" style="margin:12px"><div class="empty-state"><div style="font-size:24px">⚠</div><div class="empty-state__title">No se pudo cargar la agenda</div><div class="empty-state__text">' + escapeHtml(error) + '</div><button class="sigos-btn-secondary" id="calRetry">Reintentar</button><details style="margin-top:8px;font-size:11px;color:#96908A"><summary>Detalle técnico</summary><div>status: ' + escapeHtml(d.status||'') + '</div><div>code: ' + escapeHtml(d.code||'') + '</div><div>url: ' + escapeHtml(d.url||'') + '</div><div>request_id: ' + escapeHtml((d.body && d.body.request_id)||'') + '</div></details></div></div>';
  } else if (!error && !items.length && !unassigned.length) {
    html += '<div class="sigos-card"><div class="empty-state"><div class="empty-state__title">📅 Sin visitas programadas</div><div class="empty-state__text">No hay visitas en este rango. Programa una nueva desde Órdenes.</div><button class="sigos-btn-secondary" id="calGoOrders">Ir a Órdenes</button></div></div>';
  }
  // main layout: grid + panel
  html += '<div style="display:flex;gap:8px;flex:1;min-height:0">';
  // calendar grid
  html += '<div style="flex:1;min-width:0;overflow:auto;border:1px solid #DDD9D3;border-radius:8px;background:#fff">';
  if (cs.view === 'month') {
    html += '<div style="display:grid;grid-template-columns:repeat(7,1fr)">';
    ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'].forEach(d => { html += '<div style="padding:6px;font-size:11px;font-weight:600;color:#96908A;border-bottom:1px solid #DDD9D3;text-align:center">' + d + '</div>'; });
    days.forEach(d => {
      const key = d.toISOString().slice(0,10);
      const evs = byDay[key] || [];
      const isToday = key === todayStr;
      html += '<div style="min-height:70px;border:1px solid #F0ECE4;padding:4px;cursor:pointer" data-day="' + key + '">';
      html += '<div style="font-size:11px;font-weight:600;' + (isToday?'color:#fff;background:#2A5C45;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center':'color:#3A4552') + '">' + d.getDate() + '</div>';
      if (evs.length) {
        html += '<div style="margin-top:2px;display:flex;gap:2px;flex-wrap:wrap">';
        evs.slice(0,4).forEach(e => { html += '<span style="width:6px;height:6px;border-radius:50%;background:' + (e.status==='in_progress'?'#C9892A':e.status==='completed'?'#2A5C45':'#96908A') + '"></span>'; });
        html += '</div><div style="font-size:10px;color:#96908A">' + evs.length + '</div>';
      }
      html += '</div>';
    });
    html += '</div>';
  } else {
    // week/day grid
    const viewDays = cs.view === 'day' ? 1 : 7;
    const gDays = days.slice(0, viewDays);
    html += '<div style="display:grid;grid-template-columns:60px repeat(' + viewDays + ',1fr);position:relative">';
    // header row
    html += '<div style="position:sticky;top:0;background:#fff;z-index:2;border-bottom:1px solid #DDD9D3"></div>';
    gDays.forEach(d => {
      const key = d.toISOString().slice(0,10);
      const isToday = key === todayStr;
      const isWeekend = d.getDay()===0 || d.getDay()===6;
      let bg = isToday ? '#F3F8F5' : (isWeekend ? '#F7F4EE' : '#fff');
      html += '<div data-day="' + key + '" style="position:sticky;top:0;background:' + bg + ';z-index:2;border-bottom:1px solid #DDD9D3;padding:6px;text-align:center;font-size:12px;font-weight:600;color:' + (isToday?'#2A5C45':'#3A4552') + ';cursor:pointer">' + calShortDay(d) + ' ' + d.getDate() + (isToday?' <span style="background:#2A5C45;color:#fff;border-radius:50%;padding:1px 5px;font-size:10px">HOY</span>':'') + '</div>';
    });
    // hour rows
     for (let h=7; h<=17; h++) {
       html += '<div style="border-top:1px solid #F0ECE4;padding:2px 4px;font-size:10px;color:#96908A;font-family:JetBrains Mono,monospace">' + String(h).padStart(2,'0') + ':00</div>';
       for (let di=0; di<viewDays; di++) {
         const dkey = gDays[di].toISOString().slice(0,10);
         html += '<div data-slot-date="' + dkey + '" data-slot-hour="' + h + '" style="border-left:1px solid #F0ECE4;border-top:1px solid #F0ECE4;position:relative;min-height:48px;cursor:pointer"></div>';
       }
     }
    html += '</div>';
    // overlay events positioned absolutely
    // We'll render events in a separate layer per day using top offsets
    html += '<div style="position:relative;margin-top:-' + (11*48+24) + 'px;padding-left:60px;display:grid;grid-template-columns:repeat(' + viewDays + ',1fr);gap:0;pointer-events:none">';
    gDays.forEach((d, di) => {
      const key = d.toISOString().slice(0,10);
      const evs = byDay[key] || [];
      // compute overlaps columns
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
           const color = e.status==='in_progress'?'#C9892A':e.status==='completed'?'#2A5C45':'#8A847C';
           const dash = e.schedule_status === 'unassigned' ? 'border-style:dashed' : '';
           const selected = cs.selectedEventId === e.order_id;
           const highlighted = cs.highlightId === e.order_id;
           const selStyle = highlighted ? 'border:2px solid #2E7A50;box-shadow:0 0 0 4px rgba(46,122,80,.25);background:#EAF4EE;' : selected ? 'border:2px solid #2E7A50;box-shadow:0 4px 12px rgba(46,122,80,.25);' : ('border:1px solid ' + color + ';');
           html += '<div class="cal-event" data-event-id="' + e.order_id + '" tabindex="0" title="' + escapeHtml(orderCode(e) + ' ' + e.title) + '" style="position:absolute;top:' + top + 'px;left:' + left + ';width:' + width + ';height:' + height + 'px;background:#F3F8F5;' + selStyle + dash + ';border-radius:4px;padding:2px 4px;font-size:11px;overflow:hidden;pointer-events:auto;cursor:pointer">';
          html += '<div style="font-family:JetBrains Mono,monospace;font-size:10px">' + escapeHtml(orderCode(e)) + '</div>';
          html += '<div style="font-weight:600">' + escapeHtml(e.title) + '</div>';
          html += '<div style="color:#64748B">' + escapeHtml((e.technicians||[]).map(t=>t.name).join(', ') || 'Por asignar') + '</div>';
          html += '</div>';
        });
      });
      html += '</div>';
    });
    html += '</div>';
  }
  html += '</div>';
  // right panel
  html += '<div style="width:340px;flex-shrink:0;display:flex;flex-direction:column;gap:8px">';
  // unassigned tray
  html += '<div class="sigos-card" style="padding:10px"><div style="font-family:Outfit;font-weight:600;font-size:13px;color:#163028;margin-bottom:6px">Pendientes</div>';
  const porProgramar = unassigned.filter(o => !o.scheduled_at);
  const porAsignar = unassigned.filter(o => o.scheduled_at && !o.assigned_to_id);
  if (unassignedError) {
    html += '<div style="font-size:11px;color:#D63B3B">No se pudieron cargar los pendientes</div>';
  } else {
    html += '<div style="font-size:12px;font-weight:600;color:#96908A">Por programar (' + porProgramar.length + ')</div>';
    if (!porProgramar.length && !unassignedError) html += '<div style="font-size:11px;color:#96908A">Todo programado ✓</div>';
  }
   const pendingLine = (o) => {
     const code = orderCode(o);
     const parts = [o.customer_name || '—', o.installation_type_code || o.installation_type || '—', o.priority || '—'].filter(Boolean);
     return escapeHtml(code) + (parts.length ? ' · ' + parts.map(escapeHtml).join(' · ') : '');
   };
   porProgramar.slice(0,8).forEach(o => { html += '<div style="font-size:11px;padding:4px;border-bottom:1px solid #F0ECE4">' + pendingLine(o) + '</div>'; });
  html += '<div style="font-size:12px;font-weight:600;color:#96908A;margin-top:6px">Por asignar (' + porAsignar.length + ')</div>';
  if (!porAsignar.length) html += '<div style="font-size:11px;color:#96908A">Sin pendientes</div>';
   porAsignar.slice(0,8).forEach(o => { html += '<div style="font-size:11px;padding:4px;border-bottom:1px solid #F0ECE4">' + pendingLine(o) + '</div>'; });
  html += '</div>';
   const selectedEvent = (items || []).find(e => e.order_id === cs.selectedEventId) || null;
   if (cs.selectedEventId && !selectedEvent) cs.selectedEventId = null;
   // selected event detail
   html += '<div class="sigos-card" style="padding:10px"><div style="font-family:Outfit;font-weight:600;font-size:13px;color:#163028;margin-bottom:6px">Detalle de la visita</div>';
   if (selectedEvent) {
     const e = selectedEvent;
     const techs = (e.technicians||[]).map(t=>t.name).join(', ') || 'Por asignar';
     html += '<div style="font-family:JetBrains Mono,monospace;font-size:11px;margin-bottom:2px">' + escapeHtml(orderCode(e)) + '</div>';
     html += '<div style="font-weight:600;font-size:13px;margin-bottom:6px">' + escapeHtml(e.title) + '</div>';
     const fields = [
       ['Cliente', e.customer_name || '—'],
       ['Dirección', e.address || e.city || '—'],
       ['Tipo', e.installation_type || e.type || '—'],
       ['Estado', (typeof statusOf === 'function' ? statusOf(e.status).label : e.status)],
       ['Prioridad', (typeof priorityOf === 'function' ? priorityOf(e.priority).label : e.priority)],
       ['Horario', e.start.slice(11,16) + '–' + e.end.slice(11,16)],
       ['Técnico', techs],
       ['Observaciones', e.schedule_notes || e.notes || '—'],
     ];
     fields.forEach(([k,v]) => { html += '<div style="font-size:11px;margin-bottom:2px"><span style="color:#96908A">' + escapeHtml(k) + ':</span> ' + escapeHtml(v) + '</div>'; });
     // actions
     const canSchedule = hasRole('admin') || hasRole('dispatcher');
     const st = e.status;
     const canProgram = canSchedule && ['pending','assigned'].includes(st);
     const canReprogram = canSchedule && ['pending','assigned','in_progress'].includes(st);
     const canAssign = canSchedule && ['pending','assigned'].includes(st);
     const canCancel = canSchedule && ['pending','assigned','in_progress'].includes(st);
     const transitions = {
       pending: ['assigned','cancelled'],
       assigned: ['in_progress','cancelled'],
       in_progress: ['completed'],
       completed: ['closed'],
       closed: [],
       cancelled: [],
     };
     const validNext = (transitions[st] || []).filter(s => !(s==='cancelled' && !canCancel));
     html += '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px">';
     html += '<button class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" data-cal-action="open">Abrir orden</button>';
     if (canProgram || canReprogram) html += '<button class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" data-cal-action="schedule">' + (e.scheduled_at?'Reprogramar':'Programar') + '</button>';
     else html += '<button class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" disabled title="No permitido en este estado">Programar</button>';
     if (canAssign) html += '<button class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" data-cal-action="assign">Asignar/Reasignar</button>';
     validNext.forEach(ns => {
       const label = ns === 'cancelled' ? 'Cancelar' : ('Cambiar a ' + ns);
       html += '<button class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" data-cal-action="transition" data-next="' + ns + '">' + escapeHtml(label) + '</button>';
     });
     html += '<button class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" data-cal-action="history">Ver historial</button>';
     html += '</div>';
   } else {
     html += '<div style="font-size:12px;color:#96908A">Selecciona una visita para ver su detalle y acciones.</div>';
   }
   html += '</div>';
   if (!cs.selectedDay) cs.selectedDay = todayStr;
   const selDay = cs.selectedDay;
   html += '<div class="sigos-card" style="padding:10px;flex:1;overflow:auto"><div style="font-family:Outfit;font-weight:600;font-size:13px;color:#163028;margin-bottom:6px">Órdenes del día seleccionado</div>';
   const selEvs = byDay[selDay] || [];
   if (!selEvs.length) html += '<div style="font-size:12px;color:#96908A">Selecciona un día para ver sus visitas.</div>';
   selEvs.forEach(e => {
     html += '<div style="padding:8px;border:1px solid #E8E2D8;border-radius:6px;margin-bottom:6px">';
     html += '<div style="font-family:JetBrains Mono,monospace;font-size:11px">' + escapeHtml(orderCode(e)) + '</div>';
     html += '<div style="font-weight:600;font-size:12px">' + escapeHtml(e.title) + '</div>';
     const parts = [e.city, e.zone].filter(Boolean);
     html += '<div style="font-size:11px;color:#64748B">' + escapeHtml(parts.join(' · ') || '—') + '</div>';
     html += '<div style="font-size:11px;color:#64748B">' + escapeHtml(e.start.slice(11,16)) + '–' + escapeHtml(e.end.slice(11,16)) + ' · ' + escapeHtml((e.technicians||[]).map(t=>t.name).join(', ')||'Por asignar') + '</div>';
     html += '<div style="display:flex;gap:4px;margin-top:6px"><button class="sigos-btn-secondary" style="font-size:11px;padding:2px 6px" onclick="state.selectedOrderId=' + e.order_id + ';state.view=\'order-detail\';render()">Abrir orden</button></div>';
     html += '</div>';
   });
   html += '</div>';
  html += '</div>';
  html += '</div>';
  content.innerHTML = html;
  // bind events
  const prev = document.getElementById('calPrev');
  const next = document.getElementById('calNext');
  const todayBtn = document.getElementById('calToday');
  if (prev) prev.addEventListener('click', () => { cs.anchor = calAddDays(anchor, cs.view==='month'?-30:cs.view==='day'?-1:-7).toISOString().slice(0,10); render(); });
  if (next) next.addEventListener('click', () => { cs.anchor = calAddDays(anchor, cs.view==='month'?30:cs.view==='day'?1:7).toISOString().slice(0,10); render(); });
  if (todayBtn) todayBtn.addEventListener('click', () => { cs.anchor = calTodayStr(); render(); });
  document.querySelectorAll('[data-calview]').forEach(b => b.addEventListener('click', () => { cs.view = b.dataset.calview; render(); }));
   // event selection
   content.querySelectorAll('.cal-event').forEach(el => {
     const eid = Number(el.dataset.eventId);
     el.addEventListener('click', (ev) => { ev.stopPropagation(); cs.selectedEventId = eid; render(); });
     el.addEventListener('dblclick', (ev) => { ev.stopPropagation(); cs.selectedEventId = eid; state.selectedOrderId = eid; state.view = 'order-detail'; render(); });
     el.addEventListener('contextmenu', (ev) => { ev.preventDefault(); ev.stopPropagation(); cs.selectedEventId = eid; showContextMenu(ev.clientX, ev.clientY, eid); });
     el.addEventListener('keydown', (ev) => {
       if (ev.key === 'Enter') { ev.preventDefault(); state.selectedOrderId = eid; state.view = 'order-detail'; render(); }
     });
   });
   // day header selection already via data-day
   // actions
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
         const actionName = next === 'assigned' ? 'assign' : next === 'in_progress' ? 'start' : next === 'completed' ? 'complete' : next === 'closed' ? 'close' : next === 'cancelled' ? 'cancel' : next;
         const res = await api('POST', '/api/v1/work-orders/' + eid + '/transitions', { action: actionName, reason });
         if (res.ok) { notify('Estado actualizado.', 'success'); cs.selectedEventId = eid; render(); }
         else { notify((res.body && (res.body.message || res.body.error)) || 'Error', 'error'); }
       }
     });
   });
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
  const retry = document.getElementById('calRetry');
  if (retry) retry.addEventListener('click', () => render());
   document.querySelectorAll('[data-day]').forEach(el => el.addEventListener('click', () => { cs.selectedDay = el.dataset.day; render(); }));
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
}

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

async function renderSettings(content) {
  content.innerHTML = '<div class="empty-state"><div class="empty-state__title">Cargando configuración...</div></div>';
  try {
    const res = await api('GET', '/api/v1/settings/public');
    const p = (res.body) || {};
    content.innerHTML = '<div class="sigos-card" style="padding:16px"><h3 style="font-family:Outfit;font-size:15px;color:#163028;margin:0 0 8px">Configuración</h3><div style="font-size:13px;color:#3A4552">Zona horaria: ' + escapeHtml(p.timezone || '') + '</div><div style="font-size:13px;color:#3A4552">Horario: ' + escapeHtml(p.work_start || '') + ' – ' + escapeHtml(p.work_end || '') + '</div><div style="font-size:13px;color:#3A4552">Duración visita: ' + escapeHtml(p.default_visit_duration || '') + ' min</div><div style="font-size:12px;color:#96908A;margin-top:8px">Administración completa disponible para roles autorizados.</div></div>';
  } catch (e) {
    content.innerHTML = '<div class="sigos-card"><div class="empty-state"><div class="empty-state__title">Error</div><div class="empty-state__text">' + escapeHtml(String(e)) + '</div></div></div>';
  }
}

function pendingView(content, title) {
  content.innerHTML = `
    <div class="sigos-card"><div class="empty-state">
      <div class="empty-state__icon">${icon("hourglass", 24)}</div>
      <div class="empty-state__title">${escapeHtml(title)}</div>
      <div class="empty-state__text">Vista pendiente de migrar desde React.</div>
    </div></div>`;
}

if (!state.charts) state.charts = {};
function destroyCharts() {
  Object.values(state.charts).forEach((c) => { try { c.destroy(); } catch (e) {} });
  state.charts = {};
}

async function renderDashboard(content) {
  destroyCharts();
  content.innerHTML = '<div class="empty-state"><div class="empty-state__title">Cargando dashboard...</div></div>';
  const range = state.dashboardRange || 7;
  const zone = state.dashboardZone || '';
  const tech = state.dashboardTech || '';
  const qs = new URLSearchParams({ range, ...(zone ? { zone } : {}), ...(tech ? { technician_id: tech } : {}) });
  const res = await api('GET', `/api/v1/dashboard/summary?${qs}`);
  if (!res.ok) {
    content.innerHTML = `<div style="color:#991B1B">Error cargando dashboard: ${escapeHtml(res.body?.error || res.error || 'sin respuesta del servidor')}. <button class="sigos-btn-secondary" id="retryDash">Reintentar</button></div>`;
    $('#retryDash')?.addEventListener('click', () => renderDashboard(content));
    return;
  }
  const d = res.body;

  const labelMap = { active: 'Órdenes activas', completed: 'Completadas', sla: 'Cumplimiento SLA', mean_time: 'Tiempo medio', techs: 'Técnicos disp.', stock: 'Alertas stock' };
  const colorMap = { active: '#E8A520', completed: '#22C55E', sla: '#22C55E', mean_time: '#0EA5E9', techs: '#3B82F6', stock: '#D63B3B' };
  const iconMap = { active: 'schedule', completed: 'check_circle', sla: 'check_circle', mean_time: 'sync', techs: 'engineering', stock: 'warning' };
  const kpiHtml = (d.kpis || []).map((k) => {
    const color = colorMap[k.key] || '#3A4552';
    const upGood = k.up_is_good;
    const delta = k.delta_pct;
    let chip = '';
    if (delta !== null && delta !== undefined) {
      const good = (delta >= 0) === upGood;
      const col = good ? '#22C55E' : '#D63B3B';
      const arrow = delta >= 0 ? '\u25b2' : '\u25bc';
      chip = `<span style="font-size:11px;font-weight:600;color:${col}">${arrow} ${Math.abs(delta)}%</span>`;
    }
    return `
      <div class="sigos-card sigos-card--interactive" style="padding:14px 16px;min-height:0" data-nav="${k.key}">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <div style="width:28px;height:28px;border-radius:6px;background:${color}22;display:flex;align-items:center;justify-content:center;color:${color}">${icon(iconMap[k.key] || 'dashboard', 14)}</div>
          <div style="font-family:Outfit;font-weight:800;font-size:22px;line-height:1;color:#1A1F27">${escapeHtml(String(k.value))}</div>
          ${chip}
        </div>
        <div style="font-size:12px;font-weight:600;color:#3A4552;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(labelMap[k.key] || k.label)}</div>
      </div>`;
  }).join('');


  const recentOrders = (d.recent_orders || []).map((o) => {
    const st = statusOf(o.status);
    const pr = priorityOf(o.priority);
    const tech = o.assigned_to?.username || '—';
    const initials = tech === '—' ? '—' : tech.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
    return `<tr class="tbl-row" data-detail="${o.id}">
      <td><span class="mono" style="font-size:12px;font-weight:600;color:#163028">${o.id}</span></td>
      <td style="font-size:13px">${escapeHtml(o.customer_name || '—')}</td>
      <td><div style="display:flex;align-items:center;gap:6px"><div style="width:22px;height:22px;border-radius:50%;background:#D1FAE5;color:#166534;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700">${escapeHtml(initials)}</div><span style="font-size:13px">${escapeHtml(tech)}</span></div></td>
      <td style="font-size:12px;color:#64748B">${escapeHtml(o.created_at ? new Date(o.created_at).toLocaleString('es-ES') : '—')}</td>
      <td><span class="${st.badge}">${escapeHtml(st.label)}</span></td>
      <td><span class="${pr.badge}">${escapeHtml(pr.label)}</span></td>
    </tr>`;
  }).join('');

  const techsHtml = (d.technicians || []).slice(0, 5).map((t) => {
    const name = t.user?.username || '';
    const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
    const avail = t.is_available;
    const bg = avail ? '#D1FAE5' : '#DBEAFE';
    const fg = avail ? '#166534' : '#1E40AF';
    const ts = techStatusOf(avail);
    return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #F5F2EB">
      <div style="width:30px;height:30px;border-radius:50%;background:${bg};color:${fg};display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700">${escapeHtml(initials)}</div>
      <div style="flex:1"><div style="font-size:13px;font-weight:500;color:#1A1F27">${escapeHtml(name)}</div><div style="font-size:11px;color:#96908A">${escapeHtml(t.specialty || '')}</div></div>
      <span class="${ts.badge}">${escapeHtml(ts.label)}</span>
    </div>`;
  }).join('') || '<div style="color:#96908A;font-size:13px">Sin técnicos</div>';

  const notifsHtml = (d.notifications || []).slice(0, 5).map((n) => {
    const kind = n.subject?.toLowerCase().includes('stock') ? 'warn' : 'info';
    const bg = kind === 'warn' ? '#FEF3C7' : '#E0F2FE';
    const fg = kind === 'warn' ? '#92400E' : '#0369A1';
    const glyph = kind === 'warn' ? '!' : 'i';
    return `<div style="display:flex;align-items:flex-start;gap:8px;padding:8px 0;border-bottom:1px solid #F5F2EB">
      <div style="width:28px;height:28px;border-radius:6px;background:${bg};color:${fg};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700">${glyph}</div>
      <div><div style="font-size:13px;font-weight:500;color:#1A1F27">${escapeHtml(n.subject || '')}</div><div style="font-size:12px;color:#96908A">${escapeHtml(n.message || '')}</div></div>
    </div>`;
  }).join('') || '<div style="color:#96908A;font-size:13px">Sin notificaciones</div>';

  const stockCritical = d.stock?.critical || [];
  const stockLow = d.stock?.low || [];
  const stockHtml = (stockCritical.length || stockLow.length)
    ? [...stockCritical, ...stockLow].slice(0, 5).map((m) => `
      <div style="padding:6px 0;border-bottom:1px solid #F5F2EB;display:flex;justify-content:space-between;align-items:center">
        <div style="font-size:13px;color:#1A1F27">${escapeHtml(m.name)}</div>
        <span style="font-size:11px;font-weight:600;color:${stockCritical.includes(m) ? '#D63B3B' : '#E8A520'}">${m.current_stock} de ${m.min_stock}</span>
      </div>`).join('')
    : '<div style="color:#96908A;font-size:13px">Sin alertas de stock</div>';
  const stockBoxBg = stockCritical.length ? '#FEE2E2' : (stockLow.length ? '#FEF3C7' : '#FFFFFF');
  const zoneBd = d.breakdowns?.zone || {};
  const typeBd = d.breakdowns?.type || {};
  const zoneEmpty = Object.keys(zoneBd).length === 1 && zoneBd['Sin zona'];
  const typeEmpty = Object.keys(typeBd).length === 1 && typeBd['Sin tipo'];

  const insightsHtml = (d.insights || []).map((ins) => {
    const col = ins.kind === 'danger' ? '#D63B3B' : ins.kind === 'warn' ? '#E8A520' : ins.kind === 'ok' ? '#22C55E' : '#3B82F6';
    return `<div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0"><span style="width:8px;height:8px;border-radius:50%;background:${col};margin-top:5px;flex-shrink:0"></span><span style="font-size:13px;color:#3A4552">${escapeHtml(ins.text)}</span></div>`;
  }).join('');

  const longDate = new Date().toLocaleDateString('es-ES', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  content.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:16px;flex-wrap:wrap;gap:8px">
      <div>
        <h1 style="font-family:Outfit;font-weight:700;font-size:16px;color:#163028;margin:0">Buenos días, ${escapeHtml(state.session.user.username || '')}</h1>
        <div style="font-size:11px;color:#96908A;margin-top:2px">${escapeHtml((d.kpis?.[0]?.value || 0) + ' órdenes activas · ' + (d.kpis?.[4]?.value || '') + ' técnicos disponibles ahora')}</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <select id="dashRange" class="sigos-select"><option value="7" ${range==7?'selected':''}>7 días</option><option value="14" ${range==14?'selected':''}>14 días</option><option value="30" ${range==30?'selected':''}>30 días</option></select>
        <select id="dashZone" class="sigos-select"><option value="">Todas las zonas</option></select>
        <select id="dashTech" class="sigos-select"><option value="">Todos los técnicos</option>${(d.technicians||[]).map((t)=>`<option value="${t.user?.id}" ${String(tech)===String(t.user?.id)?'selected':''}>${escapeHtml(t.user?.username||'')}</option>`).join('')}</select>
        <button class="sigos-btn-secondary" id="dashClear">Limpiar</button>
        <button class="sigos-btn-secondary" id="dashExport">Exportar</button>
      </div>
    </div>

    <div class="kpi-grid" style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px;margin-bottom:20px">${kpiHtml}</div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Órdenes por estado</h3><div class="cv"><canvas id="chartStack"></canvas></div></div>
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Creadas vs completadas</h3><div class="cv"><canvas id="chartCreated"></canvas></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Estado actual</h3><div class="cv sm"><canvas id="chartStatus"></canvas></div></div>
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Por prioridad</h3><div class="cv sm"><canvas id="chartPriority"></canvas></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Por zona</h3>${zoneEmpty ? '<div style="height:90px;display:flex;align-items:center;justify-content:center;color:#96908A;font-size:13px;text-align:center">Aún no hay datos de zona. Asigna zona a las órdenes.</div>' : '<div class="cv sm"><canvas id="chartZone"></canvas></div>'}</div>
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Carga por técnico</h3><div class="cv sm"><canvas id="chartLoad"></canvas></div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr;gap:14px;margin-bottom:14px;align-items:start">
      <div class="sigos-card" style="padding:14px 16px"><h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Por tipo de instalación</h3>${typeEmpty ? '<div style="height:90px;display:flex;align-items:center;justify-content:center;color:#96908A;font-size:13px;text-align:center">Aún no hay datos de tipo de instalación. Asigna tipo a las órdenes.</div>' : '<div class="cv sm"><canvas id="chartType"></canvas></div>'}</div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 340px;gap:16px">
      <div class="sigos-card" style="padding:16px;overflow:hidden">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="margin:0;font-family:Outfit;font-weight:600;font-size:15px;color:#163028">Órdenes recientes</h3>
          <button class="sigos-btn-secondary" id="goOrders">${icon('eye',14)} Ver todas</button>
        </div>
        <table class="tbl">
          <thead><tr><th>ID</th><th>Cliente</th><th>Técnico</th><th>Fecha</th><th>Estado</th><th>Prioridad</th></tr></thead>
          <tbody>${recentOrders || '<tr><td colspan="6" style="text-align:center;color:#96908A;padding:20px">Sin órdenes</td></tr>'}</tbody>
        </table>
      </div>
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="sigos-card" style="padding:14px 16px">
          <h3 style="margin:0 0 6px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Análisis</h3>
          ${insightsHtml}
        </div>
        <div class="sigos-card" style="padding:14px 16px">
          <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Disponibilidad hoy</h3>
          ${techsHtml}
        </div>
        <div class="sigos-card" style="padding:16px">
          <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:15px;color:#163028">Notificaciones recientes</h3>
          ${notifsHtml}
        </div>
        <div class="sigos-card" style="padding:16px;background:${stockBoxBg}">
          <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:15px;color:#163028">Alerta de stock</h3>
          ${stockHtml}
        </div>
      </div>
    </div>`;

  // KPI click navigation
  $$('[data-nav]').forEach((el) => {
    el.addEventListener('click', () => {
      const key = el.dataset.nav;
      if (key === 'techs') { state.view = 'technicians'; render(); }
      else if (key === 'stock') { state.view = 'materials'; render(); }
      else { state.view = 'orders'; render(); }
    });
  });

  // filters
  $('#dashRange')?.addEventListener('change', (e) => { state.dashboardRange = Number(e.target.value); renderDashboard(content); });
  $('#dashZone')?.addEventListener('change', (e) => { state.dashboardZone = e.target.value; renderDashboard(content); });
  $('#dashTech')?.addEventListener('change', (e) => { state.dashboardTech = e.target.value; renderDashboard(content); });
  $('#dashClear')?.addEventListener('click', () => { state.dashboardRange = 7; state.dashboardZone = ''; state.dashboardTech = ''; renderDashboard(content); });
  $('#goOrders')?.addEventListener('click', () => { state.view = 'orders'; render(); });
  $$('[data-detail]').forEach((b) => b.addEventListener('click', () => {
    state.selectedOrderId = Number(b.dataset.detail);
    state.view = 'order-detail';
    render();
  }));

  // populate zone select
  const zoneSel = $('#dashZone');
  if (zoneSel && !zoneSel.dataset.populated) {
    const zones = Object.keys(d.breakdowns?.zone || {});
    zones.forEach((z) => { const o = document.createElement('option'); o.value = z === 'Sin zona' ? '' : z; o.textContent = z; zoneSel.appendChild(o); });
    zoneSel.dataset.populated = '1';
    if (zone) zoneSel.value = zone;
  }

  // charts
  try {
    Chart.defaults.font.family = 'DM Sans';
    Chart.defaults.font.size = 11;
    Chart.defaults.color = '#64748B';
    const labels = d.series?.labels || [];
    const shortLabels = labels.map((d) => { const dt = new Date(d); const wd = dt.toLocaleDateString('es-ES', { weekday: 'short' }).replace('.', ''); const abbr = (wd.charAt(0).toUpperCase() + wd.charAt(1).toLowerCase()); return `${abbr} ${dt.getDate()}`; });
    const stack = d.series?.stack || {};
    if ($('#chartStack')) state.charts.stack = new Chart($('#chartStack'), {
      type: 'bar',
      data: {
        labels: shortLabels,
        datasets: [
          { label: 'Pendiente', data: stack.pending || [], backgroundColor: '#E8A520', stack: 's' },
          { label: 'Programada', data: stack.assigned || [], backgroundColor: '#3B82F6', stack: 's' },
          { label: 'En proceso', data: stack.in_progress || [], backgroundColor: '#0EA5E9', stack: 's' },
          { label: 'Completada', data: stack.completed || [], backgroundColor: '#22C55E', stack: 's' },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true } } }, scales: { x: { stacked: true, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 7 } }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: '#F1EEE8' }, border: { display: false } } } },
    });
    if ($('#chartCreated')) state.charts.created = new Chart($('#chartCreated'), {
      type: 'line',
      data: {
        labels: shortLabels,
        datasets: [
          { label: 'Creadas', data: d.series?.created || [], borderColor: '#163028', backgroundColor: 'rgba(22,48,40,0.1)', fill: true, tension: 0.35, borderWidth: 2, pointRadius: 0 },
          { label: 'Completadas', data: d.series?.completed || [], borderColor: '#4AAF72', borderDash: [5, 5], fill: false, tension: 0.35, borderWidth: 2, pointRadius: 0 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true } } }, scales: { x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 7 } }, y: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: '#F1EEE8' }, border: { display: false } } } },
    });
    const statusBd = d.breakdowns?.status || {};
    if ($('#chartStatus')) state.charts.status = new Chart($('#chartStatus'), {
      type: 'doughnut',
      data: { labels: Object.keys(statusBd).map((k) => statusOf(k).label), datasets: [{ data: Object.values(statusBd), backgroundColor: ['#E8A520', '#3B82F6', '#0EA5E9', '#22C55E', '#16A34A', '#D63B3B'], borderWidth: 2, borderColor: '#fff' }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true, padding: 10 } } } },
    });
    const prioBd = d.breakdowns?.priority || {};
    if ($('#chartPriority')) state.charts.priority = new Chart($('#chartPriority'), {
      type: 'doughnut',
      data: { labels: Object.keys(prioBd).map((k) => priorityOf(k).label), datasets: [{ data: Object.values(prioBd), backgroundColor: ['#163028', '#4AAF72', '#D1FAE5'], borderWidth: 2, borderColor: '#fff' }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, usePointStyle: true, padding: 10 } } } },
    });
    if (!zoneEmpty && $('#chartZone')) {
      const zoneBd2 = d.breakdowns?.zone || {};
      state.charts.zone = new Chart($('#chartZone'), {
        type: 'bar',
        data: { labels: Object.keys(zoneBd2), datasets: [{ data: Object.values(zoneBd2), backgroundColor: '#2E7A50' }] },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: '#F1EEE8' }, border: { display: false } }, y: { grid: { display: false } } } },
      });
    }
    const loadBd = d.breakdowns?.load || {};
    const loadLabels = Object.keys(loadBd).filter((k) => k !== 'Sin asignar').concat(loadBd['Sin asignar'] !== undefined ? ['Sin asignar'] : []);
    const loadData = loadLabels.map((k) => loadBd[k] || 0);
    const loadColors = loadLabels.map((k) => (k === 'Sin asignar' ? '#96908A' : '#2E7A50'));
    if ($('#chartLoad')) state.charts.load = new Chart($('#chartLoad'), {
      type: 'bar',
      data: { labels: loadLabels, datasets: [{ data: loadData, backgroundColor: loadColors, barThickness: 12, maxBarThickness: 14, borderRadius: 3 }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: '#F1EEE8' }, border: { display: false } }, y: { grid: { display: false } } } },
    });
    if (!typeEmpty && $('#chartType')) {
      const typeBd2 = d.breakdowns?.type || {};
      state.charts.type = new Chart($('#chartType'), {
        type: 'bar',
        data: { labels: Object.keys(typeBd2), datasets: [{ data: Object.values(typeBd2), backgroundColor: '#2E7A50', barThickness: 12, maxBarThickness: 14, borderRadius: 3 }] },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0, maxTicksLimit: 5 }, grid: { color: '#F1EEE8' }, border: { display: false } }, y: { grid: { display: false } } } },
      });
    }
  } catch (e) {
    console.error('Chart error', e);
  }
}

async function renderOrders(content) {
  if (!state.ordersState) state.ordersState = { filters: { q: '', status: '', technician_id: '', zone: '', priority: '', type: '', date_from: '', date_to: '', unassigned: false }, sort: 'created_at', order: 'desc', page: 1, pageSize: 10 };
  const st = state.ordersState;
  content.innerHTML = '<div class="empty-state"><div class="empty-state__title">Cargando órdenes...</div></div>';

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
  if (!ordersRes.ok) { content.innerHTML = `<div style="color:#991B1B">${escapeHtml(ordersRes.body?.error || 'Error')}</div>`; return; }
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
    return `<button class="tab-btn ${active ? 'active' : ''}" data-status="${t.key}" style="background:${active ? '#163028' : '#fff'};color:${active ? '#fff' : '#3A4552'};border:1px solid #DDD9D3;border-radius:4px;padding:6px 12px;font-size:13px;font-weight:500;cursor:pointer">${escapeHtml(t.label)} <i style="font-style:normal;background:${active ? 'rgba(255,255,255,.25)' : '#F1F5F9'};color:${active ? '#fff' : '#64748B'};border-radius:10px;padding:0 6px;font-size:11px;font-weight:700">${c}</i></button>`;
  }).join('');

  const hasFilters = st.filters.q || st.filters.technician_id || st.filters.zone || st.filters.priority || st.filters.type || st.filters.date_from || st.filters.date_to || st.filters.unassigned;
  const filterBorder = hasFilters ? 'border-color:#2E7A50' : '';

  const rows = orders.map((o) => {
    const stInfo = statusOf(o.status);
    const prInfo = priorityOf(o.priority);
    const tech = o.assigned_to?.username || '';
    const initials = tech ? tech.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase() : '';
    const techCell = tech
      ? `<div style="display:flex;align-items:center;gap:6px"><div style="width:22px;height:22px;border-radius:50%;background:#D1FAE5;color:#166534;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700">${escapeHtml(initials)}</div><span style="font-size:12px;color:#3A4552">${escapeHtml(tech)}</span></div>`
      : `<span style="font-size:12px;color:#96908A">Sin asignar</span>`;
    const dateStr = o.scheduled_at ? new Date(o.scheduled_at).toLocaleString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) : '—';
    return `<tr class="tbl-row" data-detail="${o.id}">
      <td><span class="mono" style="font-size:12px;font-weight:600;color:#163028">OS-${String(o.id).padStart(4, '0')}</span></td>
      <td><div style="font-size:13px;font-weight:500;color:#1A1F27">${escapeHtml(o.customer_name || '—')}</div><div style="font-size:11px;color:#96908A">${escapeHtml(o.title || '')}</div></td>
      <td><div style="font-size:12px;color:#64748B;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(o.address || '')}">${escapeHtml(o.address || '—')}</div></td>
      <td style="font-size:12px;color:#3A4552">${escapeHtml(o.installation_type || '—')}</td>
      <td>${techCell}</td>
      <td style="font-size:12px;color:#3A4552">${escapeHtml(dateStr)}</td>
      <td><span class="${stInfo.badge}">${escapeHtml(stInfo.label)}</span></td>
      <td><span class="${prInfo.badge}">${escapeHtml(prInfo.label)}</span></td>
      <td><div class="act"><a class="ver" href="#" data-detail="${o.id}" title="Ver">${icon('eye', 16)}</a><a href="#" data-edit="${o.id}" title="Editar">${icon('edit', 16)}</a></div></td>
    </tr>`;
  }).join('');

  $('#topbarActions').innerHTML = `<button class="sigos-btn-primary" id="newOrderBtn">${icon('plus', 16)} Nueva orden</button>`;

  content.innerHTML = `
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">${tabHtml}</div>
    <div class="sigos-card filters" style="margin-bottom:14px;${filterBorder}">
      <div style="flex:1 1 220px;min-width:220px">${searchField({ placeholder: 'Buscar por cliente, ID, dirección...', id: 'qInput', value: st.filters.q })}</div>
      <select id="filterTech" class="sigos-select" style="height:36px">${'<option value="">Todos los técnicos</option>' + state.profiles.map((p) => `<option value="${p.user?.id}" ${String(st.filters.technician_id) === String(p.user?.id) ? 'selected' : ''}>${escapeHtml(p.user?.username || '')}</option>`).join('')}</select>
      <select id="filterZone" class="sigos-select" style="height:36px">${'<option value="">Todas las zonas</option>' + ['Zona Norte','Zona Sur','Zona Centro','Zona Industrial','Zona Oeste'].map((z) => `<option value="${z}" ${st.filters.zone === z ? 'selected' : ''}>${z}</option>`).join('')}</select>
      <button class="sigos-btn-secondary" id="applyFilters" style="height:36px;padding:0 14px">${icon('filter', 14)} Filtros</button>
      ${hasFilters ? '<button class="sigos-btn-secondary" id="clearFilters" style="height:36px;color:#D63B3B;border-color:#FCA5A5">Limpiar</button>' : ''}
      <div style="margin-left:auto;font-size:12px;color:#96908A">${total === 1 ? '1 resultado' : total + ' resultados'}</div>
    </div>
    <div class="sigos-card" style="overflow:hidden">
      <table class="tbl">
        <thead><tr>${['ID Orden','Cliente','Dirección','Tipo','Técnico','Fecha visita','Estado','Prioridad','Acciones'].map((h) => `<th>${h}</th>`).join('')}</tr></thead>
        <tbody>${rows || '<tr><td colspan="9" class="empty-state__text">Sin resultados</td></tr>'}</tbody>
      </table>
      ${!orders.length ? `<div class="empty-state"><div class="empty-state__icon">${icon('orders', 24)}</div><div class="empty-state__title">Sin resultados</div><div class="empty-state__text">No encontramos órdenes con esos criterios.</div><div class="empty-state__action"><button class="sigos-btn-secondary" id="clearEmpty">Limpiar filtros</button></div></div>` : ''}
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-top:14px;flex-wrap:wrap;gap:8px">
      <div style="font-size:12px;color:#96908A">Mostrando ${orders.length} de ${total} órdenes</div>
      <div style="display:flex;gap:4px">
        <button class="sigos-btn-secondary" id="prevPage" ${st.page <= 1 ? 'disabled' : ''}>‹</button>
        <span style="padding:6px 10px;font-size:12px">${st.page}</span>
        <button class="sigos-btn-secondary" id="nextPage" ${st.page * st.pageSize >= total ? 'disabled' : ''}>›</button>
        <select id="pageSize" class="sigos-select" style="height:32px">${[10,25,50].map((n) => `<option value="${n}" ${st.pageSize === n ? 'selected' : ''}>${n}</option>`).join('')}</select>
      </div>
    </div>`;

  // tab clicks
  $$('.tab-btn').forEach((b) => b.addEventListener('click', () => { st.filters.status = b.dataset.status; st.page = 1; renderOrders(content); }));
  $('#applyFilters')?.addEventListener('click', () => {
    st.filters.technician_id = $('#filterTech').value;
    st.filters.zone = $('#filterZone').value;
    st.filters.q = $('#qInput').value.trim();
    st.page = 1;
    renderOrders(content);
  });
  $('#qInput')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') $('#applyFilters').click(); if (e.key === 'Escape') { $('#qInput').value = ''; st.filters.q = ''; renderOrders(content); } });
  $('#clearFilters')?.addEventListener('click', () => { st.filters = { q: '', status: '', technician_id: '', zone: '', priority: '', type: '', date_from: '', date_to: '', unassigned: false }; st.page = 1; renderOrders(content); });
  $('#clearEmpty')?.addEventListener('click', () => { st.filters = { q: '', status: '', technician_id: '', zone: '', priority: '', type: '', date_from: '', date_to: '', unassigned: false }; st.page = 1; renderOrders(content); });
  $('#newOrderBtn')?.addEventListener('click', () => showOrderForm(content));
  $$('[data-detail]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); state.selectedOrderId = Number(b.dataset.detail); state.view = 'order-detail'; render(); }));
  $$('[data-edit]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); showOrderForm(content, Number(b.dataset.edit)); }));
  $('#prevPage')?.addEventListener('click', () => { if (st.page > 1) { st.page--; renderOrders(content); } });
  $('#nextPage')?.addEventListener('click', () => { if (st.page * st.pageSize < total) { st.page++; renderOrders(content); } });
  $('#pageSize')?.addEventListener('change', (e) => { st.pageSize = Number(e.target.value); st.page = 1; renderOrders(content); });
}

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
      <div class="modal-head"><h3 id="modalTitle">${orderId ? 'Editar orden' : 'Nueva orden de servicio'}</h3><button type="button" id="closeModal" style="background:none;border:none;cursor:pointer;color:#96908A" aria-label="Cerrar">${icon('close', 20)}</button></div>
      <div class="modal-body">
        <div class="fld"><label for="fTitle">Título *</label><input class="sigos-input" id="fTitle" required placeholder="Título" value="${escapeHtml(existing?.title || '')}"></div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fCustomer">Cliente</label><input class="sigos-input" id="fCustomer" value="${escapeHtml(existing?.customer_name || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fPhone">Teléfono</label><input class="sigos-input" id="fPhone" value="${escapeHtml(existing?.customer_phone || '')}"></div>
        </div>
        <div class="fld"><label for="fAddress">Dirección</label><input class="sigos-input" id="fAddress" value="${escapeHtml(existing?.address || '')}"></div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fType">Tipo de instalación</label><input class="sigos-input" id="fType" value="${escapeHtml(existing?.installation_type || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fPriority">Prioridad</label><select class="sigos-select" id="fPriority" style="width:100%"><option value="low" ${existing?.priority==='low'?'selected':''}>Baja</option><option value="medium" ${(existing?.priority||'medium')==='medium'?'selected':''}>Media</option><option value="high" ${existing?.priority==='high'?'selected':''}>Alta</option></select></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fZone">Zona</label><input class="sigos-input" id="fZone" value="${escapeHtml(existing?.zone || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fAssign">Técnico</label><select class="sigos-select" id="fAssign" style="width:100%"><option value="">Sin asignar</option>${state.profiles.map((p) => `<option value="${p.user?.id}" ${existing?.assigned_to?.id === p.user?.id ? 'selected' : ''}>${escapeHtml(p.user?.username || '')}</option>`).join('')}</select></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fDate">Fecha visita</label><input class="sigos-input" type="date" id="fDate" value="${existing?.scheduled_at ? existing.scheduled_at.slice(0,10) : ''}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px" for="fTime">Hora</label><input class="sigos-input" type="time" id="fTime" value="${existing?.scheduled_at ? existing.scheduled_at.slice(11,16) : '09:00'}"></div>
        </div>
        <div class="fld"><label for="fNotes">Notas</label><textarea class="sigos-input" id="fNotes" rows="3">${escapeHtml(existing?.description || '')}</textarea></div>
      </div>
      <div class="modal-foot"><button type="button" class="sigos-btn-secondary" id="cancelForm">Cancelar</button><button type="button" class="sigos-btn-primary" id="saveOrder">${orderId ? 'Guardar cambios' : 'Crear orden'}</button></div>
    </form>`;
  document.body.appendChild(modal);
  const close = () => { document.removeEventListener('keydown', onKey); modal.remove(); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  $('#closeModal', modal).addEventListener('click', close);
  $('#cancelForm', modal).addEventListener('click', close);
  $('#saveOrder', modal).addEventListener('click', async () => {
    const btn = $('#saveOrder', modal);
    const title = $('#fTitle', modal).value.trim();
    if (!title) { notify('Título requerido', 'error'); return; }
    btn.disabled = true; btn.textContent = 'Guardando…';
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
      renderOrders(content);
    }
  });
}

async function renderOrderDetail(content) {
  content.innerHTML = `<div class="skeleton" style="height:160px;margin-bottom:14px"></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:14px"><div class="skeleton" style="height:220px"></div><div class="skeleton" style="height:220px"></div></div>`;
  const id = state.selectedOrderId;
  const [woRes, histRes, profilesRes] = await Promise.all([
    api('GET', `/api/v1/work-orders/${id}`),
    api('GET', `/api/v1/work-orders/${id}/history`),
    api('GET', '/api/v1/technician-profiles'),
  ]);
  if (!woRes.ok) { content.innerHTML = `<div style="color:#991B1B">${escapeHtml(woRes.body?.error || 'No encontrada')}</div>`; return; }
  const wo = woRes.body;
  const history = histRes.ok ? (histRes.body || []) : [];
  const profiles = profilesRes.ok ? (profilesRes.body || []) : [];
  const transitions = {
    pending: ['assigned', 'cancelled'],
    assigned: ['in_progress', 'cancelled'],
    in_progress: ['completed'],
    completed: ['closed'],
    closed: [],
    cancelled: [],
  };
  const allowed = transitions[wo.status] || [];

  content.innerHTML = `
    <div class="sigos-card" style="padding:16px;margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h2 style="margin:0">${escapeHtml(wo.title)} <span class="${statusOf(wo.status).badge}">${escapeHtml(statusOf(wo.status).label)}</span></h2>
        <button class="sigos-btn-secondary" id="backBtn">Volver</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div><label>Cliente</label><div>${escapeHtml(wo.customer_name)}</div></div>
        <div><label>Teléfono</label><div>${escapeHtml(wo.customer_phone)}</div></div>
        <div><label>Dirección</label><div>${escapeHtml(wo.address)}</div></div>
        <div><label>Prioridad</label><div><span class="badge-${wo.priority || 'medium'}">${escapeHtml(wo.priority)}</span></div></div>
        <div><label>Asignado a</label><div>${escapeHtml(wo.assigned_to?.username)}</div></div>
        <div><label>Creado por</label><div>${escapeHtml(wo.created_by?.username)}</div></div>
      </div>
      <div style="margin-top:12px"><label>Descripción</label><div>${escapeHtml(wo.description)}</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
      <div class="sigos-card" style="padding:16px">
        <h3 style="margin:0 0 8px">Acciones</h3>
        <div class="fld"><label>Asignar técnico</label>
          <select id="assignSel" class="sigos-select" style="width:100%">
            <option value="">Sin cambios</option>
            ${profiles.map((p) => `<option value="${p.user?.id}" ${wo.assigned_to?.id === p.user?.id ? 'selected' : ''}>${escapeHtml(p.user?.username || '')}</option>`).join('')}
          </select></div>
        <button class="sigos-btn-secondary" id="assignBtn" style="margin-bottom:12px">Asignar</button>
        <div class="fld"><label>Cambiar estado</label>
          <select id="statusSel" class="sigos-select" style="width:100%">
            <option value="">Seleccionar</option>
            ${allowed.map((s) => `<option value="${s}">${escapeHtml(statusOf(s).label)}</option>`).join('')}
          </select></div>
        <div class="fld"><label>Notas</label><textarea id="statusNotes" class="sigos-input" rows="2"></textarea></div>
        <button class="sigos-btn-primary" id="statusBtn">Aplicar estado</button>
        ${allowed.includes('cancelled') ? '<button class="sigos-btn-secondary" id="cancelBtn" style="margin-left:8px;background:#FEE2E2;color:#991B1B;border-color:#FCA5A5">Cancelar orden</button>' : ''}
      </div>
      <div class="sigos-card" style="padding:16px">
        <h3 style="margin:0 0 8px">Historial</h3>
        ${history.length ? history.map((h) => `<div style="padding:6px 0;border-bottom:1px solid #F5F2EB"><span class="${statusOf(h.to_status).badge}">${escapeHtml(statusOf(h.to_status).label)}</span> <span style="font-size:12px;color:#96908A">${escapeHtml(h.created_at)} por ${escapeHtml(h.changed_by?.username)}</span><div style="font-size:12px;color:#96908A">${escapeHtml(h.notes)}</div></div>`).join('') : '<div class="empty-state__text">Sin historial</div>'}
      </div>
    </div>
    <div class="sigos-card" style="padding:16px;margin-top:16px">
      <h3 style="margin:0 0 8px">Evidencias</h3>
      <div id="evList" style="color:#96908A">Cargando...</div>
      <div class="fld" style="margin-top:8px"><label>Nueva observación</label><textarea id="obsText" class="sigos-input" rows="2"></textarea></div>
      <button class="sigos-btn-secondary" id="addObs">Agregar observación</button>
    </div>`;

  $('#backBtn').addEventListener('click', () => { state.view = 'orders'; state.selectedOrderId = null; render(); });
  $('#assignBtn').addEventListener('click', async () => {
    const v = $('#assignSel').value;
    const body = { assigned_to_id: v ? Number(v) : null };
    const res = await api('PUT', `/api/v1/work-orders/${id}`, body);
    if (!res.ok) { notify(res.body?.error || 'Error', 'error'); return; }
    notify('Asignación actualizada', 'success');
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
  $('#cancelBtn')?.addEventListener('click', async () => {
    if (!confirm('¿Cancelar la orden?')) return;
    const res = await api('POST', `/api/v1/work-orders/${id}/status`, { to_status: 'cancelled', notes: 'Cancelada desde UI' });
    if (!res.ok) { notify(res.body?.error || 'Error', 'error'); return; }
    notify('Orden cancelada', 'success');
    renderOrderDetail(content);
  });
  loadEvidences(id);
  $('#addObs').addEventListener('click', async () => {
    const desc = $('#obsText').value.trim();
    if (!desc) { notify('Observación vacía', 'error'); return; }
    const res = await api('POST', `/api/v1/work-orders/${id}/evidences`, null, { evidence_type: 'observation', description: desc });
    if (!res.ok) { notify(res.body?.error || 'Error al agregar observación', 'error'); return; }
    notify('Observación agregada', 'success');
    $('#obsText').value = '';
    loadEvidences(id);
  });
}

async function loadEvidences(id) {
  const res = await api('GET', `/api/v1/work-orders/${id}/evidences`);
  const el = $('#evList');
  if (!res.ok) { el.innerHTML = `<div style="color:#991B1B">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const evs = res.body || [];
  el.innerHTML = evs.length ? evs.map((e) => `<div style="padding:4px 0">${escapeHtml(e.evidence_type)} - ${escapeHtml(e.description || e.file_name)} <span style="color:#96908A;font-size:12px">${escapeHtml(e.created_at)}</span></div>`).join('') : '<div class="empty-state__text">Sin evidencias</div>';
}

async function renderTechnicians(content) {
  content.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const res = await api('GET', '/api/v1/technician-profiles');
  if (!res.ok) { content.innerHTML = `<div style="color:#991B1B">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const profiles = res.body || [];
  content.innerHTML = `
    <div class="sigos-card" style="overflow:hidden">
      <table class="tbl">
        <thead><tr><th>Nombre</th><th>Especialidad</th><th>Zona</th><th>Disponibilidad</th></tr></thead>
        <tbody>${profiles.map((p) => `<tr class="tbl-row"><td>${escapeHtml(p.user?.username || '')}</td><td>${escapeHtml(p.specialty || '')}</td><td>${escapeHtml(p.zone || '')}</td><td><span class="badge-${p.is_available ? 'available' : 'offduty'}">${p.is_available ? 'Disponible' : 'No disponible'}</span></td></tr>`).join('') || '<tr><td colspan="4" class="empty-state__text">Sin técnicos</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderTechnicians(content) {
  content.innerHTML = '<div class="empty-state"><div class="empty-state__title">Cargando tecnicos...</div></div>';
  const res = await api('GET', '/api/v1/technicians');
  if (!res.ok) { content.innerHTML = `<div style="color:#991B1B">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const body = res.body || {};
  const techs = body.items || [];
  const counts = body.counts || {};
  const total = body.total || techs.length;

  $('#topbarActions').innerHTML = `<button class="sigos-btn-primary" id="newTechBtn">${icon('plus', 16)} Nuevo tecnico</button>`;

  const summaryHtml = `
    <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px">
      ${[
        { label: 'Disponibles', value: counts.available || 0, color: '#22C55E', bg: '#DCFCE7', icon: 'check_circle' },
        { label: 'Ocupados', value: counts.busy || 0, color: '#3B82F6', bg: '#DBEAFE', icon: 'sync' },
        { label: 'Fuera de servicio', value: counts.off_duty || 0, color: '#94A3B8', bg: '#F1F5F9', icon: 'cancel' },
        { label: 'Total asignaciones', value: techs.reduce((a, t) => a + (t.open_orders_count || 0), 0), color: '#2E7A50', bg: '#D1FAE5', icon: 'assignment' },
      ].map((k) => `<div class="sigos-card" style="padding:14px 16px;display:flex;align-items:center;gap:12px"><div style="width:40px;height:40px;border-radius:8px;background:${k.bg};color:${k.color};display:flex;align-items:center;justify-content:center">${icon(k.icon, 20)}</div><div><div style="font-family:Outfit;font-weight:800;font-size:22px;color:#1A1F27">${k.value}</div><div style="font-size:12px;font-weight:600;color:#3A4552">${k.label}</div></div></div>`).join('')}
    </div>`;

  const cardsHtml = techs.map((t) => {
    const name = t.name || t.user?.username || '';
    const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
    const avail = t.is_available;
    const bg = avail ? '#D1FAE5' : '#F1F5F9';
    const fg = avail ? '#166534' : '#475569';
    const ts = techStatusOf(avail);
    const load = t.open_orders_count || 0;
    const pct = Math.min(100, load * 10);
    const barColor = pct >= 60 ? '#E8A520' : '#2E7A50';
    return `<div class="sigos-card" style="padding:14px 16px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
        <div style="width:48px;height:48px;border-radius:50%;background:${bg};color:${fg};display:flex;align-items:center;justify-content:center;font-weight:700">${escapeHtml(initials)}</div>
        <div style="flex:1">
          <div style="font-size:14px;font-weight:600;color:#1A1F27">${escapeHtml(name)}</div>
          <div style="font-size:12px;color:#64748B">${escapeHtml(t.specialty || '')} - ${escapeHtml(t.zones || '—')}</div>
        </div>
        <span class="${ts.badge}">${escapeHtml(ts.label)}</span>
      </div>
      <div style="font-size:12px;color:#64748B;margin-bottom:4px">Tel: ${escapeHtml(t.phone || '—')} - ${load} ordenes abiertas</div>
      <div style="height:6px;background:#F1F5F9;border-radius:3px;overflow:hidden;margin-bottom:8px"><div style="height:100%;width:${pct}%;background:${barColor};border-radius:3px"></div></div>
      <div style="display:flex;gap:6px">
        <button class="sigos-btn-secondary" style="font-size:12px;padding:4px 8px" data-view-orders="${t.user?.id}">Ver ordenes</button>
        <button class="sigos-btn-secondary" style="font-size:12px;padding:4px 8px">Calendario</button>
        <button class="sigos-btn-secondary" style="font-size:12px;padding:4px 8px" data-edit-tech="${t.id}">Editar</button>
      </div>
    </div>`;
  }).join('');

  const loadBars = techs.map((t) => {
    const name = t.name || t.user?.username || '';
    const load = t.open_orders_count || 0;
    const max = Math.max(...techs.map((x) => x.open_orders_count || 0), 1);
    const pct = Math.round((load / max) * 100);
    return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px"><div style="width:120px;font-size:12px;color:#3A4552;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(name)}</div><div style="flex:1;height:8px;background:#F1F5F9;border-radius:4px;overflow:hidden"><div style="height:100%;width:${pct}%;background:#2E7A50;border-radius:4px"></div></div><div style="font-size:12px;color:#64748B;width:24px;text-align:right">${load}</div></div>`;
  }).join('');

  content.innerHTML = `
    ${summaryHtml}
    <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:16px">${cardsHtml || '<div class="empty-state"><div class="empty-state__icon">' + icon('tech', 24) + '</div><div class="empty-state__title">Aun no hay tecnicos. Crea el primero.</div></div>'}</div>
    <div class="sigos-card" style="padding:14px 16px">
      <h3 style="margin:0 0 8px;font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Carga de trabajo comparativa</h3>
      ${loadBars || '<div style="color:#96908A;font-size:13px">Sin datos</div>'}
    </div>`;

  $('#newTechBtn')?.addEventListener('click', () => showTechForm(content));
  $$('[data-view-orders]').forEach((b) => b.addEventListener('click', () => {
    const uid = b.dataset.viewOrders;
    state.view = 'orders';
    state.ordersState = state.ordersState || { filters: {}, page: 1, pageSize: 10, sort: 'created_at', order: 'desc' };
    state.ordersState.filters = state.ordersState.filters || {};
    state.ordersState.filters.technician_id = uid;
    render();
  }));
  $$('[data-edit-tech]').forEach((b) => b.addEventListener('click', () => showTechForm(content, Number(b.dataset.editTech))));
}

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
      <div class="modal-head"><h3 id="modalTitle">${techId ? 'Editar tecnico' : 'Nuevo tecnico'}</h3><button type="button" id="closeModal" style="background:none;border:none;cursor:pointer;color:#96908A" aria-label="Cerrar">${icon('close', 20)}</button></div>
      <div class="modal-body">
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px">Nombre *</label><input class="sigos-input" id="tFirst" value="${escapeHtml(existing?.first_name || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px">Apellido *</label><input class="sigos-input" id="tLast" value="${escapeHtml(existing?.last_name || '')}"></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px">Telefono</label><input class="sigos-input" id="tPhone" value="${escapeHtml(existing?.phone || '')}"></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px">Email</label><input class="sigos-input" id="tEmail" value="${escapeHtml(existing?.email || '')}"></div>
        </div>
        <div class="grid2">
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px">Especialidad *</label><select class="sigos-select" id="tSpec" style="width:100%"><option value="">Seleccionar</option></select></div>
          <div><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px">Zonas</label><input class="sigos-input" id="tZones" value="${escapeHtml(existing?.zones || '')}" placeholder="Municipio, sector"></div>
        </div>
        <div class="fld"><label style="display:block;font-size:13px;font-weight:600;color:#3A4552;margin-bottom:5px">Documento</label><input class="sigos-input" id="tDoc" value="${escapeHtml(existing?.document || '')}"></div>
      </div>
      <div class="modal-foot"><button type="button" class="sigos-btn-secondary" id="cancelTech">Cancelar</button><button type="button" class="sigos-btn-primary" id="saveTech">${techId ? 'Guardar' : 'Crear'}</button></div>
    </form>`;
  document.body.appendChild(modal);
  const close = () => { document.removeEventListener('keydown', onKey); modal.remove(); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  // load specialties
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
    btn.disabled = true; btn.textContent = 'Guardando...';
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
    notify(techId ? 'Tecnico actualizado' : 'Tecnico creado', 'success');
    close();
    renderTechnicians(content);
  });
}

function showCredentials(username, password) {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="sigos-card modal-card" style="padding:24px">
      <h3 style="margin:0 0 12px;font-family:Outfit;font-weight:700;font-size:18px;color:#163028">Credenciales generadas</h3>
      <div style="margin-bottom:8px"><label>Usuario</label><div style="display:flex;gap:8px"><input class="sigos-input" id="credUser" value="${escapeHtml(username)}" readonly><button class="sigos-btn-secondary" id="copyUser">Copiar</button></div></div>
      <div style="margin-bottom:12px"><label>Contrasena temporal</label><div style="display:flex;gap:8px"><input class="sigos-input" id="credPass" value="${escapeHtml(password)}" readonly><button class="sigos-btn-secondary" id="copyPass">Copiar</button></div></div>
      <label style="display:flex;align-items:center;gap:8px;font-size:13px"><input type="checkbox" id="credAck"> Ya guarde las credenciales</label>
      <div class="modal-foot"><button class="sigos-btn-primary" id="closeCred" disabled>Cerrar</button></div>
    </div>`;
  document.body.appendChild(modal);
  const close = () => modal.remove();
  $('#copyUser', modal).addEventListener('click', () => navigator.clipboard?.writeText(username));
  $('#copyPass', modal).addEventListener('click', () => navigator.clipboard?.writeText(password));
  $('#credAck', modal).addEventListener('change', (e) => { $('#closeCred', modal).disabled = !e.target.checked; });
  $('#closeCred', modal).addEventListener('click', close);
}

async function renderMaterials(content) {
  content.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const res = await api('GET', '/api/v1/materials');
  if (!res.ok) { content.innerHTML = `<div style="color:#991B1B">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const mats = res.body || [];
  content.innerHTML = `
    <div class="sigos-card" style="overflow:hidden">
      <table class="tbl">
        <thead><tr><th>Nombre</th><th>Unidad</th><th>Stock</th><th>Mínimo</th><th>Precio</th></tr></thead>
        <tbody>${mats.map((m) => `<tr class="tbl-row"><td>${escapeHtml(m.name)}</td><td>${escapeHtml(m.unit)}</td><td>${m.current_stock ?? m.stock ?? ''}</td><td>${m.min_stock ?? m.minStock ?? ''}</td><td>${m.unit_price ?? ''}</td></tr>`).join('') || '<tr><td colspan="5" class="empty-state__text">Sin materiales</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderUsers(content) {
  content.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const res = await api('GET', '/api/v1/users');
  if (!res.ok) { content.innerHTML = `<div style="color:#991B1B">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const users = res.body || [];
  content.innerHTML = `
    <div class="sigos-card" style="overflow:hidden">
      <table class="tbl">
        <thead><tr><th>Usuario</th><th>Email</th><th>Roles</th><th>Activo</th></tr></thead>
        <tbody>${users.map((u) => `<tr class="tbl-row"><td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.email)}</td><td>${escapeHtml((u.roles || []).join(', '))}</td><td>${u.is_active}</td></tr>`).join('') || '<tr><td colspan="4" class="empty-state__text">Sin usuarios</td></tr>'}</tbody>
      </table>
    </div>`;
}

async function renderNotifications(content) {
  content.innerHTML = `<div class="skeleton" style="height:240px"></div>`;
  const res = await api('GET', '/api/v1/notifications');
  if (!res.ok) { content.innerHTML = `<div style="color:#991B1B">${escapeHtml(res.body?.error || 'Error')}</div>`; return; }
  const ns = res.body || [];
  content.innerHTML = `
    <div class="sigos-card" style="padding:16px">
      ${ns.map((n) => `<div style="padding:8px 0;border-bottom:1px solid #F5F2EB"><strong>${escapeHtml(n.subject || '')}</strong> <span class="badge-${n.status === 'sent' ? 'completed' : 'pending'}">${escapeHtml(n.status)}</span><div style="color:#96908A;font-size:13px">${escapeHtml(n.message)}</div><div style="color:#96908A;font-size:12px">${escapeHtml(n.created_at)} via ${escapeHtml(n.channel)}</div></div>`).join('') || '<div class="empty-state__text">Sin notificaciones</div>'}
    </div>`;
}

(async function init() {
  const ok = await loadSession();
  render();
})();

function closeContextMenu() {
  const m = document.getElementById('calContextMenu');
  if (m) m.remove();
}

function showContextMenu(x, y, eventId) {
  closeContextMenu();
  const menu = document.createElement('div');
  menu.id = 'calContextMenu';
  menu.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;background:#fff;border:1px solid #DDD9D3;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.15);padding:4px;z-index:9999;min-width:160px;';
  const items = [
    { label: 'Abrir orden', action: 'open' },
    { label: 'Programar/Reprogramar', action: 'schedule' },
    { label: 'Asignar/Reasignar', action: 'assign' },
    { label: 'Cambiar estado', action: 'transition-next' },
    { label: 'Cancelar', action: 'cancel' },
    { label: 'Ver historial', action: 'history' },
  ];
  items.forEach(it => {
    const b = document.createElement('button');
    b.textContent = it.label;
    b.style.cssText = 'display:block;width:100%;text-align:left;border:none;background:none;padding:6px 8px;font-size:12px;cursor:pointer;border-radius:4px;';
    b.addEventListener('mouseenter', () => b.style.background = '#F3F8F5');
    b.addEventListener('mouseleave', () => b.style.background = 'none');
    b.addEventListener('click', async () => {
      closeContextMenu();
      if (it.action === 'open') { state.selectedOrderId = eventId; state.view = 'order-detail'; render(); return; }
      if (it.action === 'schedule' || it.action === 'assign') { notify('Disponible en Fase 2.', 'info'); return; }
      if (it.action === 'history') { openHistoryDrawer(eventId); return; }
      if (it.action === 'cancel') {
        const reason = window.prompt('Motivo de cancelaci�n (obligatorio):');
        if (!reason) { notify('Motivo obligatorio.', 'error'); return; }
        const res = await api('POST', '/api/v1/work-orders/' + eventId + '/transitions', { action: 'cancel', reason });
        if (res.ok) { notify('Cancelado.', 'success'); render(); } else notify((res.body && (res.body.message || res.body.error)) || 'Error', 'error');
        return;
      }
      if (it.action === 'transition-next') {
        // advance one step based on current event status if possible
        notify('Usa los botones del panel para transiciones espec�ficas.', 'info');
      }
    });
    menu.appendChild(b);
  });
  document.body.appendChild(menu);
  const close = (ev) => { if (!menu.contains(ev.target)) { closeContextMenu(); document.removeEventListener('click', close); } };
  setTimeout(() => document.addEventListener('click', close), 0);
}

async function openHistoryDrawer(orderId) {
  const existing = document.getElementById('calHistoryDrawer');
  if (existing) existing.remove();
  const drawer = document.createElement('div');
  drawer.id = 'calHistoryDrawer';
  drawer.style.cssText = 'position:fixed;right:0;top:0;height:100%;width:360px;background:#fff;border-left:1px solid #DDD9D3;box-shadow:-4px 0 12px rgba(0,0,0,.1);z-index:9998;padding:16px;overflow:auto;';
  drawer.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div style="font-family:Outfit;font-weight:600;font-size:14px;color:#163028">Historial</div><button id="calHistoryClose" class="sigos-btn-secondary" style="height:28px;padding:0 8px">Cerrar</button></div><div id="calHistoryBody">Cargando...</div>';
  document.body.appendChild(drawer);
  document.getElementById('calHistoryClose').addEventListener('click', () => drawer.remove());
  try {
    const res = await api('GET', '/api/v1/work-orders/' + orderId + '/history');
    const body = document.getElementById('calHistoryBody');
    if (!res.ok) { body.innerHTML = '<div style="color:#991B1B">No se pudo cargar el historial.</div>'; return; }
    const items = res.body || [];
    if (!items.length) { body.innerHTML = '<div style="color:#96908A;font-size:12px">Sin historial.</div>'; return; }
    body.innerHTML = items.map(h => {
      const who = (h.changed_by && (h.changed_by.username || h.changed_by.name)) || 'Sistema';
      const when = h.created_at ? new Date(h.created_at).toLocaleString('es-CO') : '';
      const what = (h.from_status || '') + ' ? ' + (h.to_status || '');
      const reason = h.notes ? '<div style="font-size:11px;color:#64748B;margin-top:2px">' + escapeHtml(h.notes) + '</div>' : '';
      return '<div style="padding:8px;border-bottom:1px solid #F0ECE4"><div style="font-size:12px;font-weight:600">' + escapeHtml(what) + '</div><div style="font-size:11px;color:#96908A">' + escapeHtml(who) + ' � ' + escapeHtml(when) + '</div>' + reason + '</div>';
    }).join('');
  } catch (e) {
    const body = document.getElementById('calHistoryBody');
    if (body) body.innerHTML = '<div style="color:#991B1B">Error de conexi�n.</div>';
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
  if (ev.key === 'n' || ev.key === 'N') { notify('Programaci�n disponible en Fase 2.', 'info'); return; }
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

async function openScheduleModal(opts) {
  opts = opts || {};
  const canSchedule = hasRole('admin') || hasRole('dispatcher');
  if (!canSchedule) { notify('Sin permisos para programar.', 'error'); return; }
  // fetch data
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
  modal.style.cssText = 'width:560px;max-width:95vw;max-height:90vh;overflow:auto;background:#fff;border-radius:8px;padding:16px;box-shadow:0 8px 24px rgba(0,0,0,.2);';
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div style="font-family:Outfit;font-weight:600;font-size:15px;color:#163028">Programar visita</div>
      <button id="schClose" class="sigos-btn-secondary" style="height:28px;padding:0 8px">Cerrar</button>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
      <div style="grid-column:1/-1">
        <label style="font-size:12px;color:#96908A">Orden *</label>
        <input type="search" id="schOrderSearch" class="sigos-input" style="height:32px;width:100%;margin-bottom:4px" placeholder="Buscar orden...">
        <select id="schOrder" class="sigos-input" style="height:36px;width:100%"></select>
      </div>
      <div>
        <label style="font-size:12px;color:#96908A">Fecha *</label>
        <input type="date" id="schDate" class="sigos-input" style="height:36px;width:100%">
      </div>
      <div>
        <label style="font-size:12px;color:#96908A">Inicio *</label>
        <input type="time" id="schStart" class="sigos-input" style="height:36px;width:100%" step="900">
      </div>
      <div>
        <label style="font-size:12px;color:#96908A">Fin *</label>
        <input type="time" id="schEnd" class="sigos-input" style="height:36px;width:100%" step="900">
      </div>
      <div style="grid-column:1/-1">
        <label style="font-size:12px;color:#96908A">T�cnico</label>
        <select id="schTech" class="sigos-input" style="height:36px;width:100%"></select>
        <div id="schTechWarn" style="font-size:11px;color:#C9892A;margin-top:2px"></div>
      </div>
      <div style="grid-column:1/-1">
        <label style="font-size:12px;color:#96908A">Observaciones</label>
        <textarea id="schNotes" class="sigos-input" style="width:100%;min-height:60px"></textarea>
      </div>
      <div id="schReasonWrap" style="grid-column:1/-1;display:none">
        <label style="font-size:12px;color:#96908A">Motivo del cambio *</label>
        <select id="schReason" class="sigos-input" style="height:36px;width:100%;margin-bottom:4px">
          <option value="">Selecciona motivo</option>
          <option value="Cliente reprogram�">Cliente reprogram�</option>
          <option value="T�cnico no disponible">T�cnico no disponible</option>
          <option value="Clima">Clima</option>
          <option value="Falta de material">Falta de material</option>
          <option value="Otro">Otro</option>
        </select>
        <input type="text" id="schReasonComment" class="sigos-input" style="height:32px;width:100%" placeholder="Comentario adicional">
      </div>
    </div>
    <div id="schSummary" style="margin-top:8px;font-size:12px;color:#3A4552;font-weight:600"></div>
    <div id="schValidation" style="margin-top:8px;font-size:12px"></div>
    <div id="schConflictActions" style="margin-top:8px;display:none;gap:6px"></div>
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px">
      <button id="schCancel" class="sigos-btn-secondary" style="height:36px">Cancelar</button>
      <button id="schSave" class="sigos-btn-primary" style="height:36px">Guardar</button>
    </div>
  `;
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  let dirty = false;
  const markDirty = () => { dirty = true; };

  // populate order select
  const orderSel = modal.querySelector('#schOrder');
  const porProgramar = unassigned.filter(o => !o.scheduled_at);
  const porAsignar = unassigned.filter(o => o.scheduled_at && !o.assigned_to_id);
  const makeOpt = (o) => {
    const code = orderCode(o);
    const label = code + ' � ' + (o.customer_name || '�') + ' � ' + (o.installation_type_code || o.installation_type || '�');
    return '<option value="' + o.id + '" data-version="' + (o.version || 0) + '" data-scheduled="' + (o.scheduled_at || '') + '">' + escapeHtml(label) + '</option>';
  };
  orderSel.innerHTML = '<optgroup label="Por programar">' + porProgramar.map(makeOpt).join('') + '</optgroup>' +
    '<optgroup label="Por asignar">' + porAsignar.map(makeOpt).join('') + '</optgroup>';
  if (opts.orderId) orderSel.value = String(opts.orderId);

  // date/time defaults
  const dateInput = modal.querySelector('#schDate');
  const startInput = modal.querySelector('#schStart');
  const endInput = modal.querySelector('#schEnd');
  const today = opts.date || calTodayStr();
  dateInput.value = today;
  const sh = (opts.hour != null) ? String(opts.hour).padStart(2,'0') : (workStart.split(':')[0] || '08');
  const sm = (opts.minute != null) ? String(opts.minute).padStart(2,'0') : '00';
  startInput.value = sh + ':' + sm;
  // end default
  function setEndDefault() {
    const [h, m] = startInput.value.split(':').map(Number);
    const total = h * 60 + m + defaultDur;
    const eh = String(Math.floor(total / 60)).padStart(2,'0');
    const em = String(total % 60).padStart(2,'0');
    endInput.value = eh + ':' + em;
  }
  if (!opts.end) setEndDefault();

  // technician select
  const techSel = modal.querySelector('#schTech');
  function refreshTechOptions() {
    const date = dateInput.value;
    const st = startInput.value;
    const en = endInput.value;
    let html = '<option value="">Dejar pendiente de asignaci�n</option>';
    techs.forEach(t => {
      const prof = t; // t is profile
      const uid = t.user_id || t.id;
      // availability
      let status = (t.is_available === false) ? 'offduty' : 'available';
      // check overlap from state items
      if (status === 'available' && date && st && en) {
        const selStart = new Date(date + 'T' + st + ':00');
        const selEnd = new Date(date + 'T' + en + ':00');
        const occ = (state._calItems || []).filter(e => (e.technicians||[]).some(tt => tt.id === uid) && e.start.slice(0,10) === date);
        for (const e of occ) {
          const es = new Date(e.start); const ee = new Date(e.end);
          if (es < selEnd && selStart < ee) { status = 'busy'; break; }
        }
      }
      const label = (t.full_name || t.name || t.username || ('T�cnico ' + uid)) + ' � ' + (status === 'offduty' ? 'Fuera de servicio' : status === 'busy' ? 'Ocupado en ese horario' : 'Disponible');
      html += '<option value="' + uid + '" data-available="' + (t.is_available !== false) + '">' + escapeHtml(label) + '</option>';
    });
    techSel.innerHTML = html;
  }
  refreshTechOptions();

  // reason wrap visibility based on selected order scheduled
  const reasonWrap = modal.querySelector('#schReasonWrap');
  function updateReasonVisibility() {
    const opt = orderSel.selectedOptions[0];
    const scheduled = opt && opt.dataset.scheduled;
    reasonWrap.style.display = scheduled ? 'block' : 'none';
  }
  updateReasonVisibility();

  // tech warning on change
  const techWarn = modal.querySelector('#schTechWarn');
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
    if (!covered) techWarn.textContent = 'Advertencia: el t�cnico no cubre la zona/ciudad de la orden.';
    else techWarn.textContent = '';
  }

  // summary
  const summary = modal.querySelector('#schSummary');
  function updateSummary() {
    const o = unassigned.find(x => String(x.id) === String(orderSel.value));
    const techOpt = techSel.selectedOptions[0];
    const techLabel = techSel.value ? (techOpt ? techOpt.textContent.split(' � ')[0] : 'T�cnico') : 'Sin asignar';
    summary.textContent = (dateInput.value || '') + ' � ' + (startInput.value || '') + '�' + (endInput.value || '') + ' � T�cnico: ' + techLabel + (o ? ' � ' + orderCode(o) : '');
  }

  // validation
  const valDiv = modal.querySelector('#schValidation');
  const conflictActions = modal.querySelector('#schConflictActions');
  let validateTimer = null;
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
    const res = await api('POST', '/api/v1/calendar/validate', payload);
    if (!res.ok) { valDiv.innerHTML = '<span style="color:#991B1B">Error de validaci�n.</span>'; return; }
    const r = res.body || {};
    if (r.ok) {
      valDiv.innerHTML = '<span style="color:#166534">Sin conflictos.</span>';
      conflictActions.style.display = 'none';
    } else {
      const msgs = (r.conflicts || []).map(c => escapeHtml(c.message || c.code) + (c.conflicting_order_code ? ' (' + escapeHtml(c.conflicting_order_code) + ')' : '')).join('<br>');
      const warns = (r.warnings || []).map(w => escapeHtml(w.message || w.code)).join('<br>');
      valDiv.innerHTML = '<span style="color:#991B1B">' + (msgs || 'Conflicto') + '</span>' + (warns ? '<br><span style="color:#C9892A">' + warns + '</span>' : '');
      // conflict actions
      conflictActions.style.display = 'flex';
      conflictActions.innerHTML = '';
      const b1 = document.createElement('button');
      b1.className = 'sigos-btn-secondary'; b1.style.height = '28px'; b1.textContent = 'Elegir otro horario';
      b1.addEventListener('click', () => startInput.focus());
      conflictActions.appendChild(b1);
      const uid = techSel.value;
      if (uid) {
        const b2 = document.createElement('button');
        b2.className = 'sigos-btn-secondary'; b2.style.height = '28px'; b2.textContent = 'Ver agenda de ' + (techSel.selectedOptions[0] ? techSel.selectedOptions[0].textContent.split(' � ')[0] : 't�cnico');
        b2.addEventListener('click', () => { closeScheduleModal(); csFilterByTech(uid); });
        conflictActions.appendChild(b2);
      }
    }
  }
  function scheduleValidate() {
    clearTimeout(validateTimer);
    validateTimer = setTimeout(runValidation, 350);
  }

  function closeScheduleModal() {
    overlay.remove();
  }

  // events
  [orderSel, dateInput, startInput, endInput, techSel, modal.querySelector('#schReason')].forEach(el => {
    el.addEventListener('change', () => { markDirty(); updateReasonVisibility(); refreshTechOptions(); updateTechWarning(); updateSummary(); scheduleValidate(); });
    el.addEventListener('input', () => { markDirty(); updateSummary(); scheduleValidate(); });
  });
  modal.querySelector('#schOrderSearch').addEventListener('input', (e) => {
    const q = normalizeText(e.target.value);
    Array.from(orderSel.options).forEach(opt => {
      const txt = normalizeText(opt.textContent);
      opt.style.display = txt.includes(q) ? '' : 'none';
    });
  });
  modal.querySelector('#schClose').addEventListener('click', () => {
    if (dirty && !window.confirm('�Descartar cambios?')) return;
    closeScheduleModal();
  });
  modal.querySelector('#schCancel').addEventListener('click', () => {
    if (dirty && !window.confirm('�Descartar cambios?')) return;
    closeScheduleModal();
  });
  overlay.addEventListener('click', (e) => { if (e.target === overlay) { if (dirty && !window.confirm('�Descartar cambios?')) return; closeScheduleModal(); } });

  modal.querySelector('#schSave').addEventListener('click', async () => {
    const oid = orderSel.value;
    if (!oid) { notify('Selecciona una orden.', 'error'); return; }
    if (!dateInput.value || !startInput.value || !endInput.value) { notify('Completa fecha y hora.', 'error'); return; }
    const isReprogram = !!(orderSel.selectedOptions[0] && orderSel.selectedOptions[0].dataset.scheduled);
    if (isReprogram) {
      const reason = modal.querySelector('#schReason').value;
      if (!reason) { notify('Motivo del cambio obligatorio.', 'error'); return; }
    }
    const payload = {
      start: dateInput.value + 'T' + startInput.value + ':00',
      end: dateInput.value + 'T' + endInput.value + ':00',
      notes: modal.querySelector('#schNotes').value || undefined,
      version: Number(orderSel.selectedOptions[0].dataset.version || 0),
    };
    if (techSel.value) payload.technician_ids = [Number(techSel.value)];
    else payload.technician_ids = [];
    if (isReprogram) payload.reason = modal.querySelector('#schReason').value + (modal.querySelector('#schReasonComment').value ? ' � ' + modal.querySelector('#schReasonComment').value : '');

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
      setTimeout(() => { if (cs.highlightId === Number(oid)) { cs.highlightId = null; render(); } }, 1500);
    } else {
      const code = res.body && res.body.code;
      if (res.status === 409) {
        const msg = (res.body && (res.body.message || res.body.error)) || 'Conflicto de horario.';
        valDiv.innerHTML = '<span style="color:#991B1B">' + escapeHtml(msg) + '</span>';
        conflictActions.style.display = 'flex';
        conflictActions.innerHTML = '';
        const b1 = document.createElement('button'); b1.className='sigos-btn-secondary'; b1.style.height='28px'; b1.textContent='Elegir otro horario';
        b1.addEventListener('click', () => startInput.focus()); conflictActions.appendChild(b1);
        if (techSel.value) {
          const b2 = document.createElement('button'); b2.className='sigos-btn-secondary'; b2.style.height='28px'; b2.textContent='Ver agenda de ' + (techSel.selectedOptions[0].textContent.split(' � ')[0]);
          b2.addEventListener('click', () => { closeScheduleModal(); csFilterByTech(techSel.value); });
          conflictActions.appendChild(b2);
        }
        notify(msg, 'error');
      } else if (res.status === 422) {
        notify((res.body && (res.body.message || res.body.error)) || 'Datos inv�lidos.', 'error');
      } else if (res.status === 403) {
        notify('Sin permisos.', 'error');
      } else {
        notify((res.body && (res.body.message || res.body.error)) || 'Error del servidor.', 'error');
      }
    }
  });

  // reason wrap initial
  updateReasonVisibility();
  updateSummary();
  runValidation();

  // highlight saved event in grid after render? handled by cs.highlightId
}

function csFilterByTech(uid) {
  const cs = state.calendarState;
  if (!cs) return;
  cs.filters.technician_id = String(uid);
  cs.selectedDay = cs.selectedDay || calTodayStr();
  render();
}

// close modal helper available globally
function closeScheduleModal() {
  const overlay = document.querySelector('div[style*="z-index:10000"]');
  if (overlay) overlay.remove();
}
