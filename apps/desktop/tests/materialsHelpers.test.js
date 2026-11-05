const test = require('node:test');
const assert = require('node:assert/strict');
const { formatCOP, materialStatus, stockLevelPct, filterMaterials, minStockWarning } = require('../src/renderer/common/materials');

test('formatCOP es-CO', () => {
  assert.equal(formatCOP(75000), '$ 75.000');
});

test('materialStatus thresholds', () => {
  assert.equal(materialStatus(10, 10, 0.5).key, 'low');
  assert.equal(materialStatus(5, 10, 0.5).key, 'critical');
  assert.equal(materialStatus(15, 10, 0.5).key, 'ok');
  assert.equal(materialStatus(0, 0, 0.5).key, 'critical');
  assert.equal(materialStatus(5, 0, 0.5).key, 'ok');
});

test('stockLevelPct', () => {
  assert.equal(stockLevelPct(5, 10), 50);
});

test('filterMaterials by q/status/unit', () => {
  const list = [
    { name: 'Filtro', code: 'FIL', unit: 'pza', _status: 'ok' },
    { name: 'Tornillo', code: 'TOR', unit: 'pza', _status: 'low' },
  ];
  assert.equal(filterMaterials(list, 'fil', '', '').length, 1);
  assert.equal(filterMaterials(list, '', 'low', '').length, 1);
  assert.equal(filterMaterials(list, '', '', 'pza').length, 2);
});

test('minStockWarning', () => {
  assert.equal(minStockWarning(0), true);
  assert.equal(minStockWarning(5), false);
});
