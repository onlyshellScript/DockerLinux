const test = require('node:test');
const assert = require('node:assert/strict');
const {
  eventPosition, snapMinutes, snapTime, crossesDay, crossesMonth,
  coordToTime, layoutOverlapColumns, optimisticApply, optimisticRevert, sameDayEvents,
} = require('../src/common/calendarMath');

test('eventPosition: 09:00-10:00 a 48px de alto', () => {
  const p = eventPosition('2026-11-04T09:00:00', '2026-11-04T10:00:00');
  assert.equal(p.top, 96);
  assert.equal(p.height, 48);
});

test('snapMinutes 15/30', () => {
  assert.equal(snapMinutes(14, 30), 0);
  assert.equal(snapMinutes(16, 30), 30);
  assert.equal(snapMinutes(7, 15), 0);
  assert.equal(snapMinutes(8, 15), 15);
});

test('snapTime', () => {
  assert.equal(snapTime('09:14', 30), '09:00');
  assert.equal(snapTime('09:16', 30), '09:30');
});

test('crossesDay', () => {
  assert.equal(crossesDay('2026-11-04T23:00:00', '2026-11-05T00:00:00'), true);
  assert.equal(crossesDay('2026-11-04T09:00:00', '2026-11-04T10:00:00'), false);
});

test('crossesMonth', () => {
  assert.equal(crossesMonth('2026-10-31', 1), true);
  assert.equal(crossesMonth('2026-10-15', 5), false);
});

test('coordToTime', () => {
  // 30px into 48px cell at 09:00 hour => 09:30 with 30 snap
  assert.equal(coordToTime(30, 0, 48, 7, 30), '07:30');
});

test('layoutOverlapColumns', () => {
  const evs = [
    { start: '2026-11-04T09:00:00', end: '2026-11-04T10:00:00', order_id: 1 },
    { start: '2026-11-04T09:30:00', end: '2026-11-04T10:30:00', order_id: 2 },
  ];
  const cols = layoutOverlapColumns(evs);
  assert.equal(cols.length, 2);
});

test('optimisticApply and revert', () => {
  const items = [{ order_id: 1, start: 'a', end: 'b' }];
  const r = optimisticApply(items, 1, 'x', 'y');
  assert.equal(r.items[0].start, 'x');
  const reverted = optimisticRevert(r.items, r.index, r.backup);
  assert.equal(reverted[0].start, 'a');
});

test('sameDayEvents includes 09:00-10:00', () => {
  const items = [
    { order_id: 1, start: '2026-11-04T09:00:00', end: '2026-11-04T10:00:00' },
    { order_id: 2, start: '2026-11-05T09:00:00', end: '2026-11-05T10:00:00' },
  ];
  const day = sameDayEvents(items, '2026-11-04');
  assert.equal(day.length, 1);
  assert.equal(day[0].order_id, 1);
});
