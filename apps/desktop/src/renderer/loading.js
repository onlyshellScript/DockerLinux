// loading.js: SigosLoading, gestor central de estados de carga. Usa MetaballLoader como única pieza visual.
//
// Cada operación tiene un id propio: terminar una nunca cierra el indicador de otra que siga activa.
// Modalidades (misma identidad visual):
//   'global'  overlay sobre la aplicación con mensaje; block:true bloquea la interacción (inert) mientras dura.
//             Si una operación bloqueante supera longAfterMs pasa a aviso no bloqueante: la app nunca queda congelada.
//   'local'   capa sobre un contenedor (vista, tabla, formulario); no bloquea el resto de la app.
//   'button'  indicador compacto dentro del botón; lo deshabilita al instante (evita dobles envíos) y conserva su tamaño.
// Reglas: retraso de aparición (evita parpadeos en operaciones rápidas), tiempo mínimo visible y salida con transición
// una vez mostrado, cierre garantizado con try/finally (run/button), reset() al cambiar de sesión.
(function () {
  const DEFAULTS = {
    global: { delay: 350, minVisible: 380, block: true, longAfterMs: 60000 },
    local: { delay: 250, minVisible: 300 },
    button: { delay: 120, minVisible: 0 },
  };
  const FADE_MS = 180;
  const ops = new Map();
  let seq = 0;
  let epoch = 0;
  let immediate = false; // durante reset(): se retira todo sin transiciones

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const mb = (size) => window.MetaballLoader.markup({ size });

  // ---------------- global ----------------
  let overlay = null;
  let overlayShownAt = 0;
  let overlayHideTimer = 0;
  let inertNodes = [];
  let minVisibleOfLast = DEFAULTS.global.minVisible;

  function ensureOverlay() {
    if (overlay && overlay.isConnected) return overlay;
    overlay = document.createElement('div');
    overlay.className = 'ld-global';
    overlay.hidden = true;
    overlay.innerHTML = `<div class="ld-global__panel" role="status" aria-live="polite">${mb('lg')}<p class="ld-msg"></p></div>`;
    document.body.appendChild(overlay);
    return overlay;
  }

  // hideOverlay(): oculta el overlay y lo retira del DOM; así su metaball deja de contar y el ciclo de animación se detiene.
  function hideOverlay() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.classList.remove('is-leaving');
    overlay.remove();
  }

  function setBlocking(on) {
    if (on && !inertNodes.length) {
      inertNodes = Array.from(document.body.children).filter((n) => n !== overlay && !n.inert && n.tagName !== 'SCRIPT');
      inertNodes.forEach((n) => { n.inert = true; });
    } else if (!on && inertNodes.length) {
      inertNodes.forEach((n) => { n.inert = false; });
      inertNodes = [];
    }
  }

  function syncGlobal() {
    const shown = [...ops.values()].filter((o) => o.mode === 'global' && o.shown);
    if (!shown.length) {
      if (!overlay || overlay.hidden || overlayHideTimer) return;
      const wait = Math.max(0, overlayShownAt + minVisibleOfLast - performance.now());
      overlayHideTimer = setTimeout(() => {
        overlay.classList.add('is-leaving');
        setBlocking(false);
        overlayHideTimer = setTimeout(() => {
          overlayHideTimer = 0;
          if ([...ops.values()].some((o) => o.mode === 'global' && o.shown)) { overlay.classList.remove('is-leaving'); syncGlobal(); return; }
          hideOverlay();
        }, FADE_MS);
      }, wait);
      return;
    }
    const el = ensureOverlay();
    if (overlayHideTimer) { clearTimeout(overlayHideTimer); overlayHideTimer = 0; el.classList.remove('is-leaving'); }
    const top = shown[shown.length - 1]; // la más reciente manda el mensaje
    const blocking = shown.some((o) => o.block && !o.long);
    el.querySelector('.ld-msg').textContent = top.message;
    el.classList.toggle('is-passive', !blocking);
    if (el.hidden) { el.hidden = false; overlayShownAt = performance.now(); }
    minVisibleOfLast = top.minVisible;
    setBlocking(blocking);
  }

  // ---------------- local ----------------
  const hosts = new Map(); // target -> { ids:Set, node }

  function showLocal(op) {
    const t = op.target;
    if (!t || !t.isConnected) return;
    // Si el contenedor ya muestra un placeholder con el metaball (carga inicial de la vista), no se duplica.
    if (t.querySelector('.ld-block')) return;
    let h = hosts.get(t);
    if (!h) { h = { ids: new Set(), node: null }; hosts.set(t, h); }
    h.ids.add(op.id);
    if (!h.node || !h.node.isConnected) {
      h.node = document.createElement('div');
      h.node.className = 'ld-local';
      h.node.innerHTML = `<div class="ld-local__panel" role="status" aria-live="polite">${mb('md')}<p class="ld-msg"></p></div>`;
      t.classList.add('ld-host');
      t.appendChild(h.node);
    }
    h.node.querySelector('.ld-msg').textContent = op.message;
    t.setAttribute('aria-busy', 'true');
    op.shown = true;
  }

  function endLocal(op) {
    const h = hosts.get(op.target);
    if (!h) return;
    h.ids.delete(op.id);
    if (h.ids.size) {
      const last = ops.get([...h.ids].pop());
      if (last && h.node) h.node.querySelector('.ld-msg').textContent = last.message;
      return;
    }
    hosts.delete(op.target);
    const node = h.node;
    const t = op.target;
    const finish = () => { node?.remove(); if (!hosts.has(t)) { t.classList.remove('ld-host'); t.removeAttribute('aria-busy'); } };
    if (node && node.isConnected && !immediate) {
      const wait = Math.max(0, op.shownAt + op.minVisible - performance.now());
      setTimeout(() => { node.classList.add('is-leaving'); setTimeout(finish, FADE_MS); }, wait);
    } else finish();
  }

  // ---------------- button ----------------
  const btnState = new WeakMap(); // button -> { count, disabled, width, ariaBusy }

  function lockButton(op) {
    const b = op.target;
    let st = btnState.get(b);
    if (!st) {
      st = { count: 0, disabled: b.disabled, width: b.style.width, ariaBusy: b.getAttribute('aria-busy') };
      btnState.set(b, st);
      b.style.width = b.getBoundingClientRect().width + 'px'; // sin saltos de tamaño
      b.disabled = true; // al instante: evita el doble envío
      b.setAttribute('aria-busy', 'true');
      b.style.setProperty('--ld-color', getComputedStyle(b).color);
    }
    st.count++;
  }

  function showButton(op) {
    const b = op.target;
    if (!b.isConnected || b.querySelector(':scope > .ld-btn')) { op.shown = true; return; }
    const span = document.createElement('span');
    span.className = 'ld-btn';
    span.innerHTML = mb('xs') + `<span class="sr-only">${esc(op.message)}</span>`;
    b.classList.add('is-loading');
    b.appendChild(span);
    op.shown = true;
  }

  function unlockButton(op) {
    const b = op.target;
    const st = btnState.get(b);
    if (!st) return;
    st.count--;
    if (st.count > 0) return;
    btnState.delete(b);
    b.querySelector(':scope > .ld-btn')?.remove();
    b.classList.remove('is-loading');
    b.style.width = st.width;
    b.style.removeProperty('--ld-color');
    if (st.ariaBusy === null) b.removeAttribute('aria-busy'); else b.setAttribute('aria-busy', st.ariaBusy);
    b.disabled = st.disabled;
  }

  // ---------------- API ----------------
  // start({ mode, message, target, block, delay, minVisible }): registra una operación y devuelve su id.
  function start(opts = {}) {
    const mode = opts.mode === 'local' || opts.mode === 'button' ? opts.mode : 'global';
    const d = DEFAULTS[mode];
    const id = ++seq;
    const op = {
      id, mode, epoch,
      message: opts.message || 'Cargando información…',
      target: opts.target || null,
      block: mode === 'global' ? (opts.block ?? d.block) : false,
      minVisible: opts.minVisible ?? d.minVisible,
      shown: false, shownAt: 0, long: false, timers: [],
    };
    if ((mode === 'local' || mode === 'button') && !(op.target instanceof Element)) { op.mode = 'global'; op.block = false; }
    ops.set(id, op);
    if (op.mode === 'button') lockButton(op);
    const show = () => {
      if (!ops.has(id)) return;
      op.shownAt = performance.now();
      if (op.mode === 'global') { op.shown = true; syncGlobal(); }
      else if (op.mode === 'local') showLocal(op);
      else showButton(op);
    };
    const delay = opts.delay ?? d.delay;
    if (delay > 0) op.timers.push(setTimeout(show, delay)); else show();
    if (op.mode === 'global' && op.block) {
      op.timers.push(setTimeout(() => {
        if (!ops.has(id)) return;
        op.long = true;
        op.message = op.message.replace(/…$/, '') + ' (está tardando más de lo habitual)…';
        syncGlobal();
      }, opts.longAfterMs ?? d.longAfterMs));
    }
    return id;
  }

  // update(id, message): cambia el mensaje de una operación activa.
  function update(id, message) {
    const op = ops.get(id);
    if (!op || !message) return;
    op.message = message;
    if (op.mode === 'global') syncGlobal();
    else if (op.mode === 'local') { const h = hosts.get(op.target); if (h?.node) h.node.querySelector('.ld-msg').textContent = message; }
  }

  // end(id): termina una operación (éxito o error). Idempotente; ids desconocidos se ignoran.
  function end(id) {
    const op = ops.get(id);
    if (!op) return;
    ops.delete(id);
    op.timers.forEach(clearTimeout);
    if (op.mode === 'global') syncGlobal();
    else if (op.mode === 'local') endLocal(op);
    else unlockButton(op);
  }

  // run(opts, fn): ejecuta fn() con el indicador; lo cierra siempre (try/finally), también si fn lanza.
  async function run(opts, fn) {
    const id = start(opts);
    try { return await fn(); } finally { end(id); }
  }

  // button(btn, fn, message): atajo de run() en modo botón. Si el botón ya está ocupado no repite la acción.
  async function button(btn, fn, message) {
    if (btn && btnState.has(btn)) return undefined;
    return run({ mode: 'button', target: btn, message }, fn);
  }

  // reset(): cambio o cierre de sesión. Termina todas las operaciones, quita overlays y restaura botones;
  // incrementa epoch para que las respuestas de la sesión anterior se descarten (ver api() en app.js).
  function reset() {
    epoch++;
    immediate = true;
    try { [...ops.keys()].forEach(end); } finally { immediate = false; }
    clearTimeout(overlayHideTimer); overlayHideTimer = 0;
    setBlocking(false);
    hideOverlay();
    hosts.forEach((h, t) => { h.node?.remove(); t.classList.remove('ld-host'); t.removeAttribute('aria-busy'); });
    hosts.clear();
  }

  // block(message, opts): placeholder de carga como HTML, para contenedores que aún no tienen contenido.
  function block(message, { height = 0, size = 'md' } = {}) {
    return `<div class="ld-block" role="status" aria-live="polite"${height ? ` style="min-height:${Number(height)}px"` : ''}>${mb(size)}<p class="ld-msg">${esc(message || 'Cargando información…')}</p></div>`;
  }

  // ---------------- botón de la acción en curso ----------------
  // Las mutaciones de api() se asocian al botón que las originó: el último botón pulsado (o el que envía el formulario),
  // mientras siga en pantalla; si se cerró un diálogo de confirmación, el foco vuelve al botón que lo abrió.
  // Pulsar fuera de un botón (p. ej. al arrastrar en el calendario) borra la referencia.
  let lastAction = null;
  // Doble envío: un clic o envío sobre un botón ocupado no llega a sus manejadores (incluye clics sintéticos).
  const busy = (el) => el instanceof Element && el.closest('button[aria-busy="true"]');
  document.addEventListener('click', (e) => { if (busy(e.target)) { e.preventDefault(); e.stopImmediatePropagation(); } }, true);
  document.addEventListener('submit', (e) => { if (e.submitter && busy(e.submitter)) { e.preventDefault(); e.stopImmediatePropagation(); } }, true);
  document.addEventListener('click', (e) => {
    const b = e.target instanceof Element ? e.target.closest('button') : null;
    if (b) lastAction = b;
  }, true);
  document.addEventListener('submit', (e) => { if (e.submitter) lastAction = e.submitter; }, true);
  document.addEventListener('pointerdown', (e) => { if (!(e.target instanceof Element && e.target.closest('button'))) lastAction = null; }, true);

  function actionButton() {
    const ok = (b) => b && b.isConnected && b.tagName === 'BUTTON' && !b.closest('[hidden], [inert]') && !b.matches('[data-modal-close], [data-close]');
    if (ok(lastAction)) return lastAction;
    const a = document.activeElement;
    if (ok(a)) return a;
    return null;
  }

  // ---------------- mensajes por operación ----------------
  const ROUTES = [
    [/^POST \/api\/v1\/auth\/login/, 'Iniciando sesión…'],
    [/^POST \/api\/v1\/auth\/change-password/, 'Actualizando contraseña…'],
    [/^POST \/api\/v1\/users\/\d+\/reset-password/, 'Restableciendo contraseña…'],
    [/^PUT \/api\/v1\/users\//, 'Actualizando usuario…'],
    [/^POST \/api\/v1\/users/, 'Creando usuario…'],
    [/^POST \/api\/v1\/me\/signature/, 'Guardando firma…'],
    [/^POST \/api\/v1\/work-orders\/\d+\/evidences\/submit/, 'Enviando expediente a revisión…'],
    [/^POST \/api\/v1\/work-orders\/\d+\/evidences\/resubmit/, 'Reenviando expediente…'],
    [/^POST \/api\/v1\/work-orders\/\d+\/evidences\/(start-review|approve|reject|request-correction)/, 'Actualizando expediente…'],
    [/^POST \/api\/v1\/work-orders\/\d+\/evidences/, 'Procesando evidencia…'],
    [/^POST \/api\/v1\/work-orders\/\d+\/signatures/, 'Guardando firma del cliente…'],
    [/^POST \/api\/v1\/work-orders\/\d+\/checklist/, 'Guardando actividad…'],
    [/^POST \/api\/v1\/work-orders\/\d+\/(status|transitions)/, 'Cambiando estado de la orden…'],
    [/^(POST|PATCH) \/api\/v1\/work-orders\/\d+\/schedule/, 'Programando visita…'],
    [/^POST \/api\/v1\/work-orders$/, 'Creando orden…'],
    [/^(PUT|PATCH) \/api\/v1\/work-orders\//, 'Actualizando orden…'],
    [/^POST \/api\/v1\/materials\/\d+\/movements/, 'Registrando movimiento de inventario…'],
    [/^POST \/api\/v1\/material-catalog/, 'Guardando material…'],
    [/^PUT \/api\/v1\/materials\//, 'Actualizando material…'],
    [/^POST \/api\/v1\/material-requests\/\d+\/submit/, 'Enviando solicitud…'],
    [/^POST \/api\/v1\/material-requests\/\d+\/approve/, 'Aprobando solicitud…'],
    [/^POST \/api\/v1\/material-requests\/\d+\/reject/, 'Rechazando solicitud…'],
    [/^POST \/api\/v1\/material-requests\/\d+\/deliver/, 'Registrando entrega…'],
    [/^POST \/api\/v1\/material-requests\/\d+\/cancel/, 'Cancelando solicitud…'],
    [/^POST \/api\/v1\/material-requests/, 'Creando solicitud…'],
    [/^(POST|PATCH) \/api\/v1\/technicians/, 'Guardando técnico…'],
    [/^PATCH \/api\/v1\/settings\//, 'Guardando configuración…'],
    [/^POST \/api\/v1\/settings\/operations\/impact/, 'Validando el impacto de los cambios…'],
  ];
  const BY_METHOD = { POST: 'Guardando cambios…', PUT: 'Actualizando registro…', PATCH: 'Actualizando registro…', DELETE: 'Eliminando registro…', GET: 'Cargando información…' };
  function describe(method, path) {
    const key = `${String(method || 'GET').toUpperCase()} ${String(path || '').split('?')[0]}`;
    const hit = ROUTES.find(([re]) => re.test(key));
    return hit ? hit[1] : (BY_METHOD[String(method || 'GET').toUpperCase()] || BY_METHOD.GET);
  }

  window.SigosLoading = Object.freeze({
    start, update, end, run, button, reset, block, describe, actionButton,
    get epoch() { return epoch; },
    active: () => ops.size,
    _debug: () => ({ ops: [...ops.values()].map(({ id, mode, message, shown, block: b, long }) => ({ id, mode, message, shown, block: b, long })), hosts: hosts.size, overlayVisible: !!overlay && !overlay.hidden, blocking: inertNodes.length > 0 }),
  });
})();
