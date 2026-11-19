// connecting.js: espera a que el API responda health UP y entonces pide al proceso principal abrir la app.
// No arranca ningun backend: solo consulta el configurado (proxy local o servidor remoto).
(function () {
  const detail = document.getElementById('detail');
  const urlEl = document.getElementById('url');
  let attempts = 0;
  let timer = null;

  async function check() {
    clearTimeout(timer);
    attempts += 1;
    let res = null;
    try { res = await window.sigos.getHealth(); } catch { res = null; }
    if (res && res.ok && res.body && res.body.status === 'UP') {
      await window.sigos.openApp();
      return;
    }
    if (attempts >= 3) {
      detail.textContent = res && res.status
        ? `El servidor respondió con estado ${res.status} (${(res.body && res.body.status) || 'no disponible'}). Reintentando…`
        : 'Todavía no hay respuesta del servidor. Reintentando… Si persiste, ejecute «sigos status» o reinicie el equipo.';
    }
    timer = setTimeout(check, Math.min(2000 + attempts * 500, 5000));
  }

  window.sigos.getApiBaseUrl().then((u) => { urlEl.textContent = u; }).catch(() => {});
  document.getElementById('retry').addEventListener('click', () => { attempts = 0; check(); });
  check();
})();
