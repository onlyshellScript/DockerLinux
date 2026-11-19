// calendarMath.js: calculos de posicion, solape y snap para el calendario de ordenes.
// Devuelve top, height y durationMinutes para ubicar un evento en la grilla horaria; entrada start, end, dayStartHour; salida objeto; sin efectos secundarios.
function eventPosition(start, end, dayStartHour) {
  dayStartHour = dayStartHour == null ? 7 : dayStartHour;
  const s = new Date(start);
  const e = new Date(end);
  const startMin = (s.getHours() - dayStartHour) * 60 + s.getMinutes();
  const durMin = Math.max(15, (e - s) / 60000);
  return { top: (startMin / 60) * 48, height: (durMin / 60) * 48, durationMinutes: durMin };
}

// Redondea un minuto al intervalo mas cercano y lo limita a 0-59; entrada minute, interval; salida int; sin efectos secundarios.
function snapMinutes(minute, interval) {
  interval = interval || 30;
  return Math.max(0, Math.min(59, Math.round(minute / interval) * interval));
}

// Redondea los minutos de una hora HH:MM al intervalo indicado; entrada timeStr, interval; salida str; sin efectos secundarios.
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

// Indica si dos fechas caen en dias distintos; entrada start, end; salida bool; sin efectos secundarios.
function crossesDay(start, end) {
  const s = new Date(start);
  const e = new Date(end);
  return s.toDateString() !== e.toDateString();
}

// Indica si sumar daysAhead a dateStr cambia de mes; entrada dateStr, daysAhead; salida bool; sin efectos secundarios.
function crossesMonth(dateStr, daysAhead) {
  const d = new Date(dateStr + "T00:00:00");
  const later = new Date(d.getTime() + (daysAhead || 0) * 86400000);
  return d.getMonth() !== later.getMonth();
}

// Convierte una coordenada Y del calendario a hora HH:MM ajustada al intervalo; entrada clientY, rectTop, rectHeight, dayStartHour, interval; salida str; sin efectos secundarios.
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

// Agrupa eventos solapados en columnas para su renderizado; entrada evs; salida array de columnas; sin efectos secundarios.
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

// Aplica de forma optimista un nuevo rango a un evento en la lista y conserva backup; entrada items, eventId, newStart, newEnd; salida {items, backup, index}; sin efectos secundarios.
function optimisticApply(items, eventId, newStart, newEnd) {
  // Busca el indice del evento a actualizar dentro de items; entrada items; salida number; sin efectos secundarios.
  const idx = (items || []).findIndex((x) => x.order_id === eventId || x.id === eventId);
  if (idx < 0) return { items: items, backup: null, index: -1 };
  const backup = JSON.parse(JSON.stringify(items[idx]));
  const next = items.map((x, i) => i === idx ? Object.assign({}, x, { start: newStart, end: newEnd }) : x);
  return { items: next, backup, index: idx };
}

// Revierte un cambio optimista restaurando el backup en su indice; entrada items, index, backup; salida array; sin efectos secundarios.
function optimisticRevert(items, index, backup) {
  if (index < 0 || !backup) return items;
  const next = items.slice();
  next[index] = backup;
  return next;
}

// Filtra y ordena los eventos que ocurren en un dia; entrada items, day; salida array; sin efectos secundarios.
function sameDayEvents(items, day) {
  return (items || []).filter((e) => String(e.start || "").slice(0, 10) === day)
    .slice().sort((a, b) => new Date(a.start) - new Date(b.start));
}

module.exports = {
  eventPosition, snapMinutes, snapTime, crossesDay, crossesMonth,
  coordToTime, layoutOverlapColumns, optimisticApply, optimisticRevert, sameDayEvents,
};
