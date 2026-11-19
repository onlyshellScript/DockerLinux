// i18n-status.test.js: pruebas de etiquetas de estado y roles.
const test = require('node:test');
const assert = require('node:assert/strict');
const { statusOf, priorityOf } = require('../src/renderer/i18n-status.js');

// statusOf maps backend statuses: verifica el comportamiento esperado del caso indicado.
test('statusOf maps backend statuses', () => {
  assert.equal(statusOf('pending').label, 'Pendiente');
  assert.equal(statusOf('in_progress').label, 'En proceso');
  assert.equal(statusOf('unknown_value').label, 'Unknown value');
});

// priorityOf maps priorities: verifica el comportamiento esperado del caso indicado.
test('priorityOf maps priorities', () => {
  assert.equal(priorityOf('high').label, 'Alta');
  assert.equal(priorityOf('low').label, 'Baja');
});
