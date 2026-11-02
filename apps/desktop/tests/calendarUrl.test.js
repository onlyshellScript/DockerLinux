const test = require('node:test');
const assert = require('node:assert/strict');
const { buildCalendarEventsUrl } = require('../src/common/calendarUrl');

test('buildCalendarEventsUrl encodes + in offsets', () => {
  const url = buildCalendarEventsUrl('2026-10-26T00:00:00+00:00', '2026-11-02T00:00:00+00:00', {});
  assert.ok(!url.includes(' '), 'no spaces');
  assert.ok(url.includes('%2B') || url.includes('+') === false, 'plus encoded');
  assert.ok(url.startsWith('/api/v1/calendar/events?'));
});
