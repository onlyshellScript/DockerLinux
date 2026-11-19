// healthClient.js: consulta de salud del API desde el proceso principal.
// getHealth(baseUrl): obtiene get health; realiza peticiones de red.
async function getHealth(baseUrl) {
  const url = new URL('/api/v1/health', baseUrl);
  try {
    const response = await fetch(url);
    let body = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    return { ok: response.ok, status: response.status, body };
  } catch (error) {
    return { ok: false, status: 0, body: null, error: String(error) };
  }
}

module.exports = { getHealth };
