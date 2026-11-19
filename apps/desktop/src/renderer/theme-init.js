// theme-init.js: fija data-theme en <html> antes del primer pintado (sin destello de tema claro).
// Se carga bloqueante en <head>; la CSP no permite scripts inline. La preferencia vive en localStorage
// ('light' | 'dark' | 'system') y se refleja en el archivo de preferencias del proceso principal (app.js).
(function () {
  var pref = 'system';
  try { pref = localStorage.getItem('sigos.theme') || 'system'; } catch (e) { /* sin almacenamiento: sigue el sistema */ }
  var dark = pref === 'dark' || (pref === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
})();
