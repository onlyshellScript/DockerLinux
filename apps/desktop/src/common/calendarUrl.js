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
function buildDayRange(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  const next = new Date(y, m - 1, d + 1);
  const pad = (n) => String(n).padStart(2, '0');
  const nextStr = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
  return { from: `${isoDate}T00:00:00`, to: `${nextStr}T00:00:00` };
}

function toBogotaDay(isoUtc) {
  return new Date(isoUtc).toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
}
module.exports = { buildCalendarEventsUrl, buildDayRange, toBogotaDay };
