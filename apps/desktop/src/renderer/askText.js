// askText.js: dialogo modal de texto reutilizable.
// askText(message): solicita ask text; actualiza el DOM.
function askText(message) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;z-index:9999;';
    const box = document.createElement('div');
    box.style.cssText = 'background:#fff;border-radius:8px;padding:20px;width:360px;max-width:90vw;box-shadow:0 12px 32px rgba(0,0,0,0.2);';
    const label = document.createElement('div');
    label.style.cssText = 'font-family:Outfit;font-size:16px;color:#163028;margin-bottom:12px;';
    label.textContent = message;
    const input = document.createElement('input');
    input.className = 'sigos-input';
    input.style.cssText = 'width:100%;margin-bottom:12px;';
    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'sigos-btn-secondary';
    cancel.textContent = 'Cancelar';
    const ok = document.createElement('button');
    ok.type = 'button';
    ok.className = 'sigos-btn-primary';
    ok.textContent = 'Aceptar';
    actions.appendChild(cancel);
    actions.appendChild(ok);
    box.appendChild(label);
    box.appendChild(input);
    box.appendChild(actions);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    input.focus();
    // devuelve cleanup; sin efectos secundarios.
    const cleanup = (val) => { overlay.remove(); resolve(val); };
    cancel.addEventListener('click', () => cleanup(null));
    ok.addEventListener('click', () => cleanup(input.value.trim() || null));
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') cleanup(input.value.trim() || null); if (e.key === 'Escape') cleanup(null); });
  });
}