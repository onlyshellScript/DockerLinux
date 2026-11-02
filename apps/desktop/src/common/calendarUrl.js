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
module.exports = { buildCalendarEventsUrl };
