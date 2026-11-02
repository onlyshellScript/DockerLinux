async function getHealth(baseUrl) {
  const url = new URL('/api/v1/health', baseUrl);
  const response = await fetch(url);
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  return { ok: response.ok, status: response.status, body };
}

module.exports = { getHealth };
