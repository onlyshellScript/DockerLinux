// Módulo de escritorio para la vista y el proceso principal.
const test = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');

// jsdom smoke: render placeholder: verifica el comportamiento esperado del caso indicado.
test('jsdom smoke: render placeholder', () => {
  const dom = new JSDOM('<div id="app"></div>');
  const doc = dom.window.document;
  doc.getElementById('app').innerHTML = '<div class="sigos-card">OrderDetail</div>';
  assert.ok(doc.querySelector('.sigos-card'));
});
