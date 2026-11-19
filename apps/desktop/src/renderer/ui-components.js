// ui-components.js: componentes de interfaz compartidos (modal, confirmacion, entrada de texto).
// Todos usan las clases del sistema de diseño (design-system.css), atrapan el foco, cierran con Escape
// y devuelven el foco al elemento que los abrio.

(function () {
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const CLOSE_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>';
  let seq = 0;

  // sigosModal(opts): crea un modal accesible.
  //   title (texto), body / footer (HTML), size: 'sm' | 'md' | 'lg', raw: true => body es el contenido completo de la tarjeta,
  //   dismissible (default true): cerrar con fondo/Escape/X; beforeClose(): devuelve false o Promise<false> para impedir el cierre.
  // Devuelve { overlay, card, body, close, q } — q(sel) busca dentro del modal.
  function sigosModal(opts = {}) {
    const { title = '', body = '', footer = '', size = 'md', raw = false, dismissible = true, beforeClose = null, onClose = null } = opts;
    const opener = document.activeElement;
    const id = 'sgm' + (++seq);
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    const widths = { sm: '420px', md: '560px', lg: '760px' };
    overlay.innerHTML = raw
      ? `<div class="sigos-card modal-card" role="dialog" aria-modal="true" style="width:${widths[size] || widths.md};padding:20px 24px">${body}</div>`
      : `<div class="sigos-card modal-card" role="dialog" aria-modal="true" aria-labelledby="${id}-t" style="width:${widths[size] || widths.md}">
          <div class="modal-head"><h3 id="${id}-t">${esc(title)}</h3>${dismissible ? `<button type="button" class="icon-btn" data-modal-close aria-label="Cerrar">${CLOSE_SVG}</button>` : ''}</div>
          <div class="modal-body">${body}</div>
          ${footer ? `<div class="modal-foot">${footer}</div>` : ''}
        </div>`;
    const card = overlay.querySelector('.modal-card');
    document.body.appendChild(overlay);

    let closed = false;
    const close = (result) => {
      if (closed) return;
      closed = true;
      document.removeEventListener('keydown', onKey, true);
      overlay.remove();
      if (opener && typeof opener.focus === 'function' && document.contains(opener)) opener.focus();
      if (onClose) onClose(result);
    };
    const tryClose = async () => {
      if (!dismissible) return;
      if (beforeClose && (await beforeClose()) === false) return;
      close();
    };
    function onKey(e) {
      if (!document.body.contains(overlay)) return;
      const overlays = document.querySelectorAll('.modal-overlay');
      if (overlays[overlays.length - 1] !== overlay) return; // solo el modal superior reacciona
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); tryClose(); }
      if (e.key === 'Tab') {
        const f = Array.from(card.querySelectorAll(FOCUSABLE)).filter((el) => el.offsetParent !== null);
        if (!f.length) return;
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    }
    document.addEventListener('keydown', onKey, true);
    overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) tryClose(); });
    card.querySelectorAll('[data-modal-close], [data-close]').forEach((b) => b.addEventListener('click', tryClose));
    setTimeout(() => {
      const first = card.querySelector('[autofocus]') || card.querySelector('.modal-body ' + FOCUSABLE) || card.querySelector(FOCUSABLE);
      if (first) first.focus();
    }, 0);
    return { overlay, card, body: card.querySelector('.modal-body') || card, close, q: (sel) => card.querySelector(sel) };
  }

  // confirmDialog(message, opts): reemplazo de window.confirm. Devuelve Promise<boolean>.
  //   opts: title, confirmLabel, cancelLabel, danger (boton rojo).
  function confirmDialog(message, opts = {}) {
    const { title = 'Confirmar', confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', danger = false } = opts;
    return new Promise((resolve) => {
      let answered = false;
      const m = sigosModal({
        title,
        size: 'sm',
        body: `<p style="margin:0;font-size:14px;color:var(--c-text-2);white-space:pre-line;line-height:1.5">${esc(message)}</p>`,
        footer: `<button type="button" class="sigos-btn-secondary" data-cd="no">${esc(cancelLabel)}</button><button type="button" class="${danger ? 'sigos-btn-danger' : 'sigos-btn-primary'}" data-cd="yes">${esc(confirmLabel)}</button>`,
        onClose: () => { if (!answered) resolve(false); },
      });
      m.q('[data-cd="no"]').addEventListener('click', () => { answered = true; resolve(false); m.close(); });
      m.q('[data-cd="yes"]').addEventListener('click', () => { answered = true; resolve(true); m.close(); });
      setTimeout(() => m.q(danger ? '[data-cd="no"]' : '[data-cd="yes"]')?.focus(), 0);
    });
  }

  // askText(message, opts): pide un texto. Devuelve Promise<string|null> (null si se cancela o queda vacio).
  //   opts: title, placeholder, multiline, confirmLabel, required (default true).
  function askText(message, opts = {}) {
    const { title = message, placeholder = '', multiline = false, confirmLabel = 'Aceptar', required = true } = opts;
    return new Promise((resolve) => {
      let answered = false;
      const field = multiline
        ? `<textarea class="sigos-input" data-at="input" rows="3" placeholder="${esc(placeholder)}" aria-label="${esc(message)}"></textarea>`
        : `<input class="sigos-input" data-at="input" placeholder="${esc(placeholder)}" aria-label="${esc(message)}">`;
      const m = sigosModal({
        title,
        size: 'sm',
        body: `${title !== message ? `<p style="margin:0 0 10px;font-size:13px;color:var(--c-text-2)">${esc(message)}</p>` : ''}${field}<div class="fld-error" data-at="err" role="alert"></div>`,
        footer: `<button type="button" class="sigos-btn-secondary" data-at="no">Cancelar</button><button type="button" class="sigos-btn-primary" data-at="ok">${esc(confirmLabel)}</button>`,
        onClose: () => { if (!answered) resolve(null); },
      });
      const input = m.q('[data-at="input"]');
      const submit = () => {
        const v = input.value.trim();
        if (!v && required) { m.q('[data-at="err"]').textContent = 'Este campo es obligatorio'; input.setAttribute('aria-invalid', 'true'); input.focus(); return; }
        answered = true; resolve(v || null); m.close();
      };
      m.q('[data-at="no"]').addEventListener('click', () => { answered = true; resolve(null); m.close(); });
      m.q('[data-at="ok"]').addEventListener('click', submit);
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !multiline) { e.preventDefault(); submit(); } });
    });
  }

  window.sigosModal = sigosModal;
  window.confirmDialog = confirmDialog;
  window.askText = askText;
  if (typeof module !== 'undefined' && module.exports) module.exports = { sigosModal, confirmDialog, askText };
})();
