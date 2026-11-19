// Módulo de escritorio para la vista y el proceso principal.
const test = require('node:test');
const assert = require('node:assert/strict');
const { allowedTransitions, visibleActions, backendErrorToMessage, validateMaterialQty, validateRequiredFields } = require('../src/common/orderDetailRules');

// transitions by status/role: verifica el comportamiento esperado del caso indicado.
test('transitions by status/role', () => {
  assert.deepEqual(allowedTransitions('pending', 'admin'), ['assigned', 'cancelled']);
  assert.deepEqual(allowedTransitions('pending', 'technician'), []);
  assert.deepEqual(allowedTransitions('in_progress', 'technician'), ['completed']);
});

// visible actions by role: verifica el comportamiento esperado del caso indicado.
test('visible actions by role', () => {
  assert.equal(visibleActions('technician').assign, false);
  assert.equal(visibleActions('admin').assign, true);
});

// cancel without reason blocked (message): verifica el comportamiento esperado del caso indicado.
test('cancel without reason blocked (message)', () => {
  assert.equal(backendErrorToMessage({ error: 'reason required' }), 'reason required');
});

// backend errors mapped: verifica el comportamiento esperado del caso indicado.
test('backend errors mapped', () => {
  assert.equal(backendErrorToMessage({ error: 'schedule_conflict' }), 'Solape de horario del tecnico');
  assert.equal(backendErrorToMessage({ error: 'insufficient stock' }), 'Stock insuficiente');
});

// material qty validation: verifica el comportamiento esperado del caso indicado.
test('material qty validation', () => {
  assert.equal(validateMaterialQty(0), false);
  assert.equal(validateMaterialQty(2), true);
});

// required fields validation: verifica el comportamiento esperado del caso indicado.
test('required fields validation', () => {
  assert.deepEqual(validateRequiredFields({}), { customer_name: 'Cliente obligatorio' });
  assert.deepEqual(validateRequiredFields({ customer_name: 'X' }), {});
});
