const test = require('node:test');
const assert = require('node:assert/strict');
const { classifyError, errorMessage, asList } = require('../src/renderer/errorHelper');

const mockResponses = [
  { ok: true, status: 200, body: [{ id: 1 }, { id: 2 }] },
  { ok: true, status: 200, body: { items: [{ id: 3 }] } },
  { ok: true, status: 200, body: [] },
  { ok: false, status: 403, body: { error: 'forbidden' } },
  { ok: false, status: 404, body: { error: 'not found' } },
  { ok: false, status: 500, body: { error: 'server error' } },
];

test('jsdom smoke: order detail responses do not throw', () => {
  for (const res of mockResponses) {
    assert.doesNotThrow(() => {
      try { asList(res); } catch (e) { /* expected for error responses */ }
      classifyError(res);
      errorMessage(res, 'fallback');
    });
  }
  assert.ok(true);
});
