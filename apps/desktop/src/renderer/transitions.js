// transitions.js: capa única sobre la View Transition API (same-document) para la SPA.
//   - run(update, opts): envuelve una actualización del DOM en una transición; sin soporte la aplica al instante.
//   - tagShared(root, ns): nombra los elementos compartidos tarjeta/fila -> detalle ([data-vt="code|title|status"]).
//   - swapList(container, apply): transición de lista; cada fila [data-vt-row] usa su ID real como nombre.
//   - Modales: cualquier .modal-overlay que se añada al body se expande desde el elemento que lo abrió
//     y al cerrarse (overlay.remove()) vuelve a él. No hace falta tocar cada modal.
//   - theme: cambio claro/oscuro con un círculo que crece desde el botón (clip-path).
// Con prefers-reduced-motion las transiciones espaciales se omiten y el resto queda en un fundido breve (CSS).
(function () {
  const root = document.documentElement;
  const supported = typeof document.startViewTransition === 'function';
  const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = () => reducedQuery.matches;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const noop = () => {};
  let active = null;

  // run(update, { types, maxWait, spatial }):
  //   types: tipos de transición (CSS :active-view-transition-type()).
  //   maxWait: si update devuelve una promesa (vista que carga datos), espera como mucho maxWait ms antes de
  //            capturar el estado nuevo; así no se pasa por el esqueleto si la API responde rápido.
  //   spatial: transición que mueve o redimensiona elementos; se omite con movimiento reducido.
  // Devuelve { updated, finished }: updated se resuelve cuando el DOM ya cambió.
  function run(update, opts = {}) {
    const { types = [], maxWait = 0, spatial = false } = opts;
    if (!supported || document.visibilityState === 'hidden' || (spatial && reduced())) {
      try { update(); } catch (e) { console.error(e); }
      const done = Promise.resolve();
      return { updated: done, finished: done };
    }
    // Lo que ya está en el contenido al capturar el estado nuevo entra con la transición, no con su animación CSS.
    const markEntered = () => document.querySelectorAll('.app-content > *').forEach((el) => el.classList.add('vt-entered'));
    const cb = () => {
      const r = update();
      if (maxWait > 0 && r && typeof r.then === 'function') return Promise.race([r.catch(noop), wait(maxWait)]).then(markEntered);
      markEntered();
      return undefined;
    };
    if (active) { try { active.skipTransition(); } catch (e) { /* ya terminó */ } }
    let vt;
    try { vt = document.startViewTransition({ update: cb, types }); } catch (e) { vt = document.startViewTransition(cb); }
    active = vt;
    vt.ready.catch(noop);
    const finished = vt.finished.catch(noop).then(() => { if (active === vt) active = null; });
    return { updated: vt.updateCallbackDone.catch((e) => console.error(e)), finished };
  }

  // Nombres de transición: se guardan los previos para restaurarlos (una fila puede llevar ya el suyo).
  function setName(el, name, cls) {
    if (!el) return;
    if (el.__vtPrev === undefined) el.__vtPrev = el.style.viewTransitionName || '';
    el.style.viewTransitionName = name;
    if (cls) el.style.viewTransitionClass = cls;
  }
  function clearName(el) {
    if (!el) return;
    el.style.viewTransitionName = el.__vtPrev || '';
    el.style.viewTransitionClass = '';
    el.__vtPrev = undefined;
  }

  // tagShared(root, ns): el contenedor pasa a ser `${ns}-card` y cada [data-vt] su `${ns}-${clave}`.
  //   Antes de nombrar, libera los nombres de la etiqueta anterior: un nombre duplicado cancelaría la transición.
  let sharedTagged = [];
  function tagShared(rootEl, ns = 'order') {
    sharedTagged.forEach(clearName);
    sharedTagged = [];
    if (!rootEl) return [];
    const els = [rootEl, ...rootEl.querySelectorAll('[data-vt]')];
    setName(rootEl, `${ns}-card`);
    els.slice(1).forEach((el) => setName(el, `${ns}-${el.dataset.vt}`));
    sharedTagged = els;
    return els;
  }
  const untag = (els) => (els || []).forEach(clearName);

  // Filas de lista: nombre estable a partir del ID real (nunca aleatorio); los duplicados se omiten porque
  // un nombre repetido cancela toda la transición.
  const safeId = (v) => String(v).replace(/[^a-zA-Z0-9_-]/g, '_');
  function nameRows(container) {
    const seen = new Set();
    const named = [];
    container.querySelectorAll('[data-vt-row]').forEach((el) => {
      const key = el.getAttribute('data-vt-row');
      if (!key || seen.has(key)) return;
      seen.add(key);
      setName(el, `row-${safeId(key)}`, 'vt-row');
      named.push(el);
    });
    return named;
  }
  function swapList(container, apply) {
    if (!container || !supported || reduced()) { apply(); return Promise.resolve(); }
    const oldRows = nameRows(container);
    let newRows = [];
    const t = run(() => { untag(oldRows); apply(); newRows = nameRows(container); }, { types: ['list'] });
    t.finished.then(() => untag(newRows));
    return t.updated;
  }

  // ---------- Modales contextuales ----------
  const INVOKER = 'button, a[href], [role="button"], [tabindex]:not([tabindex="-1"]), tr[data-detail], [data-filter-status]';
  let lastInvoker = null;
  let lastInvokeAt = 0;
  document.addEventListener('click', (e) => {
    const el = e.target instanceof Element ? e.target.closest(INVOKER) : null;
    if (el && !el.closest('.modal-overlay.is-closing')) { lastInvoker = el; lastInvokeAt = performance.now(); }
  }, true);

  function visibleRect(el) {
    if (!el || !el.isConnected) return null;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return null;
    if (r.bottom < 0 || r.right < 0 || r.top > window.innerHeight || r.left > window.innerWidth) return null;
    return r;
  }
  function pickOrigin(overlay) {
    // El modal puede abrirse tras una petición de red: se acepta el último elemento pulsado en ~1.5 s.
    if (!lastInvoker || performance.now() - lastInvokeAt > 1500) return null;
    if (overlay.contains(lastInvoker)) return null;
    return visibleRect(lastInvoker) ? lastInvoker : null;
  }
  const origins = new WeakMap();
  const cardOf = (overlay) => overlay.querySelector('.modal-card, [role="dialog"]') || overlay.firstElementChild;

  function openModal(overlay) {
    if (overlay.__vt) return;
    overlay.__vt = true;
    if (!supported || reduced()) return; // la animación CSS de siempre
    const card = cardOf(overlay);
    if (!card) return;
    const origin = pickOrigin(overlay);
    origins.set(overlay, origin);
    overlay.classList.add('vt-managed');
    // Estado viejo: el modal ya está en el DOM pero transparente (opacity no le quita el foco a sus campos).
    overlay.style.opacity = '0';
    if (origin) setName(origin, 'modal-origin');
    const t = run(() => {
      if (origin) clearName(origin);
      overlay.style.opacity = '';
      if (origin) setName(card, 'modal-origin');
    }, { types: ['modal-open'] });
    t.finished.then(() => clearName(card));
  }

  function closeModal(overlay, nativeRemove) {
    overlay.__closing = true;
    overlay.classList.add('is-closing');
    const card = cardOf(overlay);
    const origin = origins.get(overlay);
    const back = origin && visibleRect(origin) ? origin : null;
    if (back && card) setName(card, 'modal-origin');
    const t = run(() => {
      nativeRemove.call(overlay);
      if (card) clearName(card);
      if (back) setName(back, 'modal-origin');
    }, { types: ['modal-close'] });
    t.finished.then(() => { if (back) clearName(back); });
  }

  if (document.body) {
    new MutationObserver((muts) => {
      for (const m of muts) {
        m.addedNodes.forEach((n) => { if (n.nodeType === 1 && n.classList.contains('modal-overlay')) openModal(n); });
      }
    }).observe(document.body, { childList: true });
  }
  // Cierre: los modales se cierran con overlay.remove(); se intercepta solo para .modal-overlay ya gestionados.
  const nativeRemove = Element.prototype.remove;
  Element.prototype.remove = function remove() {
    if (supported && !reduced() && this.__vt && !this.__closing && this.isConnected
        && this.classList && this.classList.contains('modal-overlay') && document.visibilityState !== 'hidden') {
      closeModal(this, nativeRemove);
      return;
    }
    nativeRemove.call(this);
  };

  // ---------- Tema claro / oscuro ----------
  const THEME_KEY = 'sigos.theme';
  const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const themePref = () => { try { return localStorage.getItem(THEME_KEY) || 'system'; } catch (e) { return 'system'; } };
  const resolve = (pref) => (pref === 'dark' || (pref === 'system' && darkQuery.matches) ? 'dark' : 'light');
  const currentTheme = () => root.getAttribute('data-theme') || 'light';

  function applyTheme(pref) {
    try { localStorage.setItem(THEME_KEY, pref); } catch (e) { /* sin persistencia local */ }
    const theme = resolve(pref);
    const changed = theme !== currentTheme();
    root.setAttribute('data-theme', theme);
    if (changed) window.dispatchEvent(new CustomEvent('sigos:themechange', { detail: { theme, pref } }));
    return theme;
  }

  // toggle(originEl): el tema nuevo se revela con un círculo que nace en el botón.
  function toggleTheme(originEl) {
    const next = currentTheme() === 'dark' ? 'light' : 'dark';
    if (!supported || document.visibilityState === 'hidden') return applyTheme(next);
    if (reduced()) { run(() => applyTheme(next), { types: ['theme-fade'] }); return next; }
    const r = originEl ? originEl.getBoundingClientRect() : { left: window.innerWidth, top: 0, width: 0, height: 0 };
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    root.classList.add('vt-theme');
    if (active) { try { active.skipTransition(); } catch (e) { /* nada */ } }
    let vt;
    try { vt = document.startViewTransition({ update: () => applyTheme(next), types: ['theme'] }); } catch (e) { vt = document.startViewTransition(() => applyTheme(next)); }
    active = vt;
    vt.ready.then(() => {
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 520, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', pseudoElement: '::view-transition-new(root)' },
      );
    }).catch(noop);
    vt.finished.catch(noop).then(() => { root.classList.remove('vt-theme'); if (active === vt) active = null; });
    return next;
  }

  // Si la preferencia es "sistema", seguir los cambios del sistema operativo (sin animación).
  darkQuery.addEventListener('change', () => { if (themePref() === 'system') applyTheme('system'); });

  window.sigosVT = {
    supported,
    reduced,
    run,
    tagShared,
    untag,
    swapList,
    theme: { current: currentTheme, pref: themePref, apply: applyTheme, toggle: toggleTheme },
  };
})();
