const test = require('node:test');
const assert = require('node:assert/strict');
const { buildCalendarEventsUrl } = require('../src/common/calendarUrl');

test('buildCalendarEventsUrl encodes + in offsets', () => {
  const url = buildCalendarEventsUrl('2026-10-26T00:00:00+00:00', '2026-11-02T00:00:00+00:00', {});
  assert.ok(!url.includes(' '), 'no spaces');
  assert.ok(url.includes('%2B') || url.includes('+') === false, 'plus encoded');
  assert.ok(url.startsWith('/api/v1/calendar/events?'));
  });

  const { buildDayRange, toBogotaDay } = require('../src/common/calendarUrl');
  test('buildDayRange cruza fin de mes', () => {
    assert.deepEqual(buildDayRange('2026-10-31'), { from: '2026-10-31T00:00:00', to: '2026-11-01T00:00:00' });
  });
  test('toBogotaDay: 02:00Z es el día anterior en Bogotá', () => {
  assert.equal(toBogotaDay('2026-10-25T02:00:00Z'), '2026-10-24');
});
