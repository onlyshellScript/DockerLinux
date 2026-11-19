// normalize.test.js: pruebas de normalizacion de texto.
const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizeText } = require('../src/common/normalize');

// normalizeText matches API: verifica el comportamiento esperado del caso indicado.
test('normalizeText matches API', () => {
  assert.equal(normalizeText('  Suba  '), 'suba');
  assert.equal(normalizeText('Súba'), 'suba');
  assert.equal(normalizeText('CHÍA'), 'chia');
  assert.equal(normalizeText('Chía'), 'chia');
});
