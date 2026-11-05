function eventPosition(start, end, dayStartHour) {
  dayStartHour = dayStartHour == null ? 7 : dayStartHour;
  const s = new Date(start);
  const e = new Date(end);
  const startMin = (s.getHours() - dayStartHour) * 60 + s.getMinutes();
  const durMin = Math.max(15, (e - s) / 60000);
  return { top: (startMin / 60) * 48, height: (durMin / 60) * 48, durationMinutes: durMin };
}

function snapMinutes(minute, interval) {
  interval = interval || 30;
  return Math.max(0, Math.min(59, Math.round(minute / interval) * interval));
}

function snapTime(timeStr, interval) {
  const parts = String(timeStr || "00:00").split(":");
  const h = parseInt(parts[0], 10) || 0;
  const m = parseInt(parts[1], 10) || 0;
  const snapped = snapMinutes(m, interval);
  let hour = h;
  let minute = snapped;
  if (minute === 60) { hour += 1; minute = 0; }
  return String(hour).padStart(2, "0") + ":" + String(minute).padStart(2, "0");
}

function crossesDay(start, end) {
  const s = new Date(start);
  const e = new Date(end);
  return s.toDateString() !== e.toDateString();
}

function crossesMonth(dateStr, daysAhead) {
  const d = new Date(dateStr + "T00:00:00");
  const later = new Date(d.getTime() + (daysAhead || 0) * 86400000);
  return d.getMonth() !== later.getMonth();
}

function coordToTime(clientY, rectTop, rectHeight, dayStartHour, interval) {
  dayStartHour = dayStartHour == null ? 7 : dayStartHour;
  interval = interval || 30;
  const y = clientY - rectTop;
  const rawMin = (y / rectHeight) * 60;
  const minute = snapMinutes(rawMin, interval);
  const hourFloat = dayStartHour + rawMin / 60;
  const hour = Math.max(dayStartHour, Math.min(23, Math.floor(hourFloat)));
  return String(hour).padStart(2, "0") + ":" + String(minute).padStart(2, "0");
}

function layoutOverlapColumns(evs) {
  if (!evs || !evs.length) return [];
  const sorted = evs.slice().sort((a, b) => new Date(a.start) - new Date(b.start));
  const columns = [];
  sorted.forEach((e) => {
    let placed = false;
    for (const col of columns) {
      const last = col[col.length - 1];
      if (new Date(e.start) >= new Date(last.end)) { col.push(e); placed = true; break; }
    }
    if (!placed) columns.push([e]);
  });
  const out = columns.map((col, i) => col.map((e) => Object.assign({}, e, { index: i })));
  return out.length ? out : [[]];
}

function optimisticApply(items, eventId, newStart, newEnd) {
  const idx = (items || []).findIndex((x) => x.order_id === eventId || x.id === eventId);
  if (idx < 0) return { items: items, backup: null, index: -1 };
  const backup = JSON.parse(JSON.stringify(items[idx]));
  const next = items.map((x, i) => i === idx ? Object.assign({}, x, { start: newStart, end: newEnd }) : x);
  return { items: next, backup, index: idx };
}

function optimisticRevert(items, index, backup) {
  if (index < 0 || !backup) return items;
  const next = items.slice();
  next[index] = backup;
  return next;
}

function sameDayEvents(items, day) {
  return (items || []).filter((e) => String(e.start || "").slice(0, 10) === day)
    .slice().sort((a, b) => new Date(a.start) - new Date(b.start));
}

module.exports = {
  eventPosition, snapMinutes, snapTime, crossesDay, crossesMonth,
  coordToTime, layoutOverlapColumns, optimisticApply, optimisticRevert, sameDayEvents,
};
