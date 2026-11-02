const test = require('node:test');
const assert = require('node:assert/strict');
const { statusOf, priorityOf } = require('../src/renderer/i18n-status.js');

test('statusOf maps backend statuses', () => {
  assert.equal(statusOf('pending').label, 'Pendiente');
  assert.equal(statusOf('in_progress').label, 'En proceso');
  assert.equal(statusOf('unknown_value').label, 'Unknown value');
});

test('priorityOf maps priorities', () => {
  assert.equal(priorityOf('high').label, 'Alta');
  assert.equal(priorityOf('low').label, 'Baja');
});
