// Pruebas del sistema de carga: MetaballLoader (componente) y SigosLoading (gestor de estados).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const SRC = path.join(__dirname, '..', 'src', 'renderer');
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const windows = [];
test.after(() => windows.forEach((w) => w.close()));

// setup(): documento nuevo con los dos scripts cargados tal como en index.html.
function setup({ reduced = false } = {}) {
  const dom = new JSDOM('<!doctype html><body><div id="app"><main id="content"></main><button id="save">Guardar</button></div></body>', { runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  windows.push(w);
  w.matchMedia = () => ({ matches: reduced, addEventListener() {} });
  w.eval(fs.readFileSync(path.join(SRC, 'metaball-loader.js'), 'utf8'));
  w.eval(fs.readFileSync(path.join(SRC, 'loading.js'), 'utf8'));
  return { w, doc: w.document, L: w.SigosLoading, MB: w.MetaballLoader };
}
const overlay = (doc) => doc.querySelector('.ld-global');
const overlayVisible = (doc) => !!overlay(doc) && !overlay(doc).hidden;

test('MetaballLoader: empieza y termina fusionado, se separa a mitad del ciclo', () => {
  const { MB } = setup();
  const same = (p) => p.every(([x, y]) => x === 115 && y === 80);
  assert.ok(same(MB.positionsAt(0)));
  assert.ok(same(MB.positionsAt(1)));
  const mid = MB.positionsAt(0.38);
  assert.equal(JSON.stringify(mid.map((p) => p.map(Math.round))), JSON.stringify([[67, 77], [115, 104], [163, 77]]));
  const cross = MB.positionsAt(0.58); // las trayectorias se cruzan: el círculo 1 pasa a la derecha del centro
  assert.ok(cross[1][0] > 115 && cross[0][0] < 115);
});

test('MetaballLoader: un solo filtro compartido y tres círculos sólidos por instancia', () => {
  const { doc, MB } = setup();
  doc.body.insertAdjacentHTML('beforeend', MB.markup({ size: 'md' }) + MB.markup({ size: 'xs' }));
  assert.equal(doc.querySelectorAll('#sigos-goo').length, 1);
  const svgs = doc.querySelectorAll('svg.mb');
  assert.equal(svgs.length, 2);
  svgs.forEach((s) => {
    assert.equal(s.querySelectorAll('circle').length, 3);
    assert.equal(s.getAttribute('aria-hidden'), 'true');
    assert.equal(s.querySelector('g').getAttribute('filter'), 'url(#sigos-goo)');
  });
  assert.ok(!/gradient/i.test(MB.markup()));
});

test('MetaballLoader: el ciclo se detiene sin instancias y no corre con movimiento reducido', async () => {
  const { doc, MB } = setup();
  doc.body.insertAdjacentHTML('beforeend', `<div id="x">${MB.markup()}</div>`);
  await wait(60);
  assert.equal(MB._isRunning(), true);
  doc.getElementById('x').remove();
  await wait(80);
  assert.equal(MB._isRunning(), false);
  const r = setup({ reduced: true });
  r.doc.body.insertAdjacentHTML('beforeend', r.MB.markup());
  await wait(60);
  assert.equal(r.MB._isRunning(), false);
  assert.equal(Number(r.doc.querySelector('circle').getAttribute('cx')), 115);
});

test('global: operaciones simultáneas no se cierran entre sí', async () => {
  const { doc, L } = setup();
  const a = L.start({ message: 'Generando documento PDF…', delay: 0, minVisible: 0 });
  const b = L.start({ message: 'Guardando cambios…', delay: 0, minVisible: 0 });
  assert.ok(overlayVisible(doc));
  assert.equal(doc.querySelector('.ld-msg').textContent, 'Guardando cambios…');
  L.end(b);
  await wait(250);
  assert.ok(overlayVisible(doc), 'A sigue activa: el overlay no debe cerrarse');
  assert.equal(doc.querySelector('.ld-global .ld-msg').textContent, 'Generando documento PDF…');
  L.end(a);
  L.end(a); // idempotente
  await wait(250);
  assert.equal(overlayVisible(doc), false);
  assert.equal(L.active(), 0);
  await wait(50);
  assert.equal(doc.querySelectorAll('svg.mb').length, 0, 'sin indicador visible no queda ninguna instancia animándose');
});

test('global: operación rápida no parpadea (retraso de aparición)', async () => {
  const { doc, L } = setup();
  const id = L.start({ message: 'Cargando…', delay: 100 });
  await wait(20);
  L.end(id);
  await wait(150);
  assert.equal(overlayVisible(doc), false);
});

test('global: bloquea la interacción solo mientras está activa y nunca queda congelada', async () => {
  const { doc, L } = setup();
  const id = L.start({ message: 'Iniciando sesión…', delay: 0, minVisible: 0, longAfterMs: 50 });
  assert.equal(doc.getElementById('app').inert, true);
  await wait(80); // operación larga: pasa a aviso no bloqueante
  assert.equal(doc.getElementById('app').inert, false);
  assert.ok(overlay(doc).classList.contains('is-passive'));
  assert.match(doc.querySelector('.ld-global .ld-msg').textContent, /tardando más de lo habitual/);
  L.end(id);
  await wait(250);
  assert.equal(overlayVisible(doc), false);
});

test('global: con mínimo visible, se mantiene y sale con transición', async () => {
  const { doc, L } = setup();
  const id = L.start({ message: 'x', delay: 0, minVisible: 120 });
  L.end(id);
  await wait(60);
  assert.ok(overlayVisible(doc) && !overlay(doc).classList.contains('is-leaving'));
  await wait(110);
  assert.ok(overlay(doc).classList.contains('is-leaving'));
  await wait(220);
  assert.equal(overlayVisible(doc), false);
});

test('run(): cierra el indicador también cuando la operación falla', async () => {
  const { doc, L } = setup();
  await assert.rejects(L.run({ message: 'Guardando…', delay: 0, minVisible: 0 }, async () => { throw new Error('500'); }));
  assert.equal(L.active(), 0);
  await wait(250);
  assert.equal(overlayVisible(doc), false);
  assert.equal(doc.getElementById('app').inert, false);
});

test('botón: se deshabilita al instante, conserva su tamaño, evita el doble envío y se restaura', async () => {
  const { doc, L } = setup();
  const btn = doc.getElementById('save');
  btn.style.width = '';
  let calls = 0;
  let release;
  const first = L.button(btn, () => { calls++; return new Promise((r) => { release = r; }); }, 'Guardando cambios…');
  assert.equal(btn.disabled, true);
  assert.equal(btn.getAttribute('aria-busy'), 'true');
  assert.match(btn.style.width, /px$/);
  const second = await L.button(btn, () => { calls++; }, 'Guardando cambios…');
  assert.equal(second, undefined);
  assert.equal(calls, 1);
  await wait(160);
  assert.ok(btn.classList.contains('is-loading'));
  assert.equal(btn.querySelectorAll('.ld-btn svg.mb').length, 1);
  assert.equal(btn.querySelector('.ld-btn .sr-only').textContent, 'Guardando cambios…');
  release();
  await first;
  assert.equal(btn.disabled, false);
  assert.equal(btn.style.width, '');
  assert.equal(btn.querySelector('.ld-btn'), null);
  assert.equal(btn.hasAttribute('aria-busy'), false);
  assert.equal(btn.textContent, 'Guardar');
});

test('botón: si ya estaba deshabilitado antes, vuelve a ese estado', async () => {
  const { doc, L } = setup();
  const btn = doc.getElementById('save');
  btn.disabled = true;
  await L.run({ mode: 'button', target: btn, message: 'm' }, async () => {});
  assert.equal(btn.disabled, true);
});

test('local: no duplica un placeholder y limpia el contenedor', async () => {
  const { doc, L } = setup();
  const content = doc.getElementById('content');
  content.innerHTML = L.block('Consultando solicitudes…');
  const a = L.start({ mode: 'local', target: content, message: 'Consultando solicitudes…', delay: 0 });
  assert.equal(content.querySelector('.ld-local'), null);
  L.end(a);
  content.innerHTML = '<table></table>';
  const b = L.start({ mode: 'local', target: content, message: 'Consultando solicitudes…', delay: 0, minVisible: 0 });
  const c = L.start({ mode: 'local', target: content, message: 'Actualizando…', delay: 0, minVisible: 0 });
  assert.equal(content.querySelectorAll('.ld-local').length, 1);
  assert.equal(content.getAttribute('aria-busy'), 'true');
  L.end(b);
  assert.ok(content.querySelector('.ld-local'), 'c sigue activa');
  L.end(c);
  await wait(250);
  assert.equal(content.querySelector('.ld-local'), null);
  assert.equal(content.classList.contains('ld-host'), false);
  assert.equal(content.hasAttribute('aria-busy'), false);
});

test('local: si la vista se reemplaza durante la carga no queda indicador huérfano', async () => {
  const { doc, L } = setup();
  const content = doc.getElementById('content');
  content.innerHTML = '<p>datos</p>';
  const id = L.start({ mode: 'local', target: content, message: 'x', delay: 0, minVisible: 0 });
  content.remove(); // cambio de módulo: el contenedor desaparece
  L.end(id);
  await wait(250);
  assert.equal(L.active(), 0);
  assert.equal(doc.querySelectorAll('.ld-local').length, 0);
});

test('reset(): cambio de sesión termina todo, restaura botones y avanza la época', async () => {
  const { doc, L } = setup();
  const btn = doc.getElementById('save');
  const content = doc.getElementById('content');
  const e0 = L.epoch;
  L.start({ message: 'a', delay: 0 });
  L.start({ mode: 'button', target: btn, message: 'b' });
  L.start({ mode: 'local', target: content, message: 'c', delay: 0 });
  L.start({ message: 'pendiente', delay: 5000 });
  L.reset();
  assert.equal(L.active(), 0);
  assert.equal(L.epoch, e0 + 1);
  assert.equal(btn.disabled, false);
  assert.equal(overlayVisible(doc), false);
  assert.equal(content.querySelector('.ld-local'), null);
  assert.equal(doc.getElementById('app').inert, false);
});

test('describe(): mensajes según la operación real', () => {
  const { L } = setup();
  assert.equal(L.describe('POST', '/api/v1/auth/login'), 'Iniciando sesión…');
  assert.equal(L.describe('POST', '/api/v1/work-orders/5/evidences'), 'Procesando evidencia…');
  assert.equal(L.describe('POST', '/api/v1/work-orders/5/evidences/submit'), 'Enviando expediente a revisión…');
  assert.equal(L.describe('POST', '/api/v1/material-requests/3/approve'), 'Aprobando solicitud…');
  assert.equal(L.describe('PATCH', '/api/v1/work-orders/9/schedule'), 'Programando visita…');
  assert.equal(L.describe('PUT', '/api/v1/users/2'), 'Actualizando usuario…');
  assert.equal(L.describe('DELETE', '/api/v1/algo/1'), 'Eliminando registro…');
  assert.ok(!/%/.test(L.describe('POST', '/x')));
});
