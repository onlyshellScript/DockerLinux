// healthClient.test.js: pruebas del cliente de salud.
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { getHealth } = require('../src/main/healthClient');

// getHealth reports available API: verifica el comportamiento esperado del caso indicado.
test('getHealth reports available API', async () => {
  const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ status: 'UP', checks: { application: 'UP', database: 'UP' } }));
  });
  await new Promise((resolve) => server.listen(0, resolve));
  const { port } = server.address();
  const result = await getHealth(`http://127.0.0.1:${port}`);
  server.close();
  assert.equal(result.ok, true);
  assert.equal(result.body.status, 'UP');
});

// getHealth reports unavailable API: verifica el comportamiento esperado del caso indicado.
test('getHealth reports unavailable API', async () => {
  const server = http.createServer((req, res) => {
    res.statusCode = 503;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ status: 'DOWN', checks: { application: 'UP', database: 'DOWN' } }));
  });
  await new Promise((resolve) => server.listen(0, resolve));
  const { port } = server.address();
  const result = await getHealth(`http://127.0.0.1:${port}`);
  server.close();
  assert.equal(result.ok, false);
  assert.equal(result.body.status, 'DOWN');
});
