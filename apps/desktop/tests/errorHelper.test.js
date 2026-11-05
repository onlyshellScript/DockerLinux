const test = require('node:test');
const assert = require('node:assert/strict');
const { classifyError, errorMessage } = require('../src/renderer/errorHelper');

test('classifyError transport when no response', () => {
  const info = classifyError({ ok: false, status: 0, error: 'fetch failed' });
  assert.equal(info.kind, 'transport');
  assert.match(info.message, /conexi/i);
});

test('classifyError 401', () => {
  const info = classifyError({ ok: false, status: 401, body: { error: 'token expired' } });
  assert.equal(info.kind, 'unauthorized');
  assert.equal(info.message, 'token expired');
});

test('classifyError 403 password change', () => {
  const info = classifyError({ ok: false, status: 403, body: { code: 'PASSWORD_CHANGE_REQUIRED', message: 'change pw' } });
  assert.equal(info.kind, 'password_change');
});

test('classifyError 409/422/5xx', () => {
  assert.equal(classifyError({ ok: false, status: 409, body: { error: 'conflict' } }).kind, 'conflict');
  assert.equal(classifyError({ ok: false, status: 422, body: { error: 'invalid' } }).kind, 'validation');
  assert.equal(classifyError({ ok: false, status: 500, body: null }).kind, 'server');
});

test('errorMessage reads body.message || body.error', () => {
  assert.equal(errorMessage({ ok: false, status: 422, body: { message: 'msg' } }), 'msg');
  assert.equal(errorMessage({ ok: false, status: 422, body: { error: 'err' } }), 'err');
  assert.equal(errorMessage(null, 'fallback'), 'fallback');
});
