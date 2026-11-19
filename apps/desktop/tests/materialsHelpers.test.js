// materialsHelpers.test.js: pruebas de helpers de materiales.
const test = require('node:test');
const assert = require('node:assert/strict');
const { formatCOP, materialStatus, stockLevelPct, filterMaterials, minStockWarning } = require('../src/renderer/common/materials');

// formatCOP es-CO: verifica el comportamiento esperado del caso indicado.
test('formatCOP es-CO', () => {
  assert.equal(formatCOP(75000), '$ 75.000');
});

// materialStatus thresholds: verifica el comportamiento esperado del caso indicado.
test('materialStatus thresholds', () => {
  assert.equal(materialStatus(10, 10, 0.5).key, 'low');
  assert.equal(materialStatus(5, 10, 0.5).key, 'critical');
  assert.equal(materialStatus(15, 10, 0.5).key, 'ok');
  assert.equal(materialStatus(0, 0, 0.5).key, 'critical');
  assert.equal(materialStatus(5, 0, 0.5).key, 'ok');
});

// stockLevelPct: verifica el comportamiento esperado del caso indicado.
test('stockLevelPct', () => {
  assert.equal(stockLevelPct(5, 10), 50);
});

// filterMaterials by q/status/unit: verifica el comportamiento esperado del caso indicado.
test('filterMaterials by q/status/unit', () => {
  const list = [
    { name: 'Filtro', code: 'FIL', unit: 'pza', _status: 'ok' },
    { name: 'Tornillo', code: 'TOR', unit: 'pza', _status: 'low' },
  ];
  assert.equal(filterMaterials(list, 'fil', '', '').length, 1);
  assert.equal(filterMaterials(list, '', 'low', '').length, 1);
  assert.equal(filterMaterials(list, '', '', 'pza').length, 2);
});

// minStockWarning: verifica el comportamiento esperado del caso indicado.
test('minStockWarning', () => {
  assert.equal(minStockWarning(0), true);
  assert.equal(minStockWarning(5), false);
});
