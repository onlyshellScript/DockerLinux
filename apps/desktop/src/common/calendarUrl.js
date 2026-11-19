// calendarUrl.js: construccion de URLs y rangos de dia para eventos del calendario.
// Construye la URL de consulta de eventos del calendario con filtros; entrada from, to, filters; salida str; sin efectos secundarios.
function buildCalendarEventsUrl(from, to, filters) {
  const params = new URLSearchParams();
  params.set('from', from);
  params.set('to', to);
  const f = filters || {};
  Object.keys(f).forEach((k) => {
    if (f[k] !== undefined && f[k] !== null && f[k] !== '' && f[k] !== false) {
      params.set(k, f[k]);
    }
  });
  if (f.include_cancelled) params.set('include_cancelled', 'true');
  return '/api/v1/calendar/events?' + params.toString();
}
// Construye el rango from/to para un dia dado; entrada isoDate; salida {from,to}; sin efectos secundarios.
function buildDayRange(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  const next = new Date(y, m - 1, d + 1);
  // Rellena con ceros a la izquierda; entrada n; salida str; sin efectos secundarios.
  const pad = (n) => String(n).padStart(2, '0');
  const nextStr = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
  return { from: `${isoDate}T00:00:00`, to: `${nextStr}T00:00:00` };
}

// Convierte una fecha ISO UTC a dia calendario en Bogota; entrada isoUtc; salida str; sin efectos secundarios.
function toBogotaDay(isoUtc) {
  return new Date(isoUtc).toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
}
module.exports = { buildCalendarEventsUrl, buildDayRange, toBogotaDay };
