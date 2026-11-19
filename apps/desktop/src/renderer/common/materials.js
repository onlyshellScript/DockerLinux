// materials.js: formato, estado de stock y filtros de materiales.
// formatCOP(value): formatea format cop; sin efectos secundarios.
function formatCOP(value) {
  const n = Number(value || 0);
  try {
    return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(n).replace(/\u00A0/g, ' ');
  } catch (e) {
    return '$ ' + Math.round(n).toLocaleString('es-CO');
  }
}

// devuelve material status; sin efectos secundarios.
function materialStatus(stock, minimum, threshold) {
  const s = Number(stock || 0);
  const m = Number(minimum || 0);
  const t = (threshold == null ? 0.5 : Number(threshold));
  if (m <= 0) {
    if (s <= 0) return { key: 'critical', label: 'Crítico', badge: 'badge-cancelled', bar: '#D63B3B' };
    return { key: 'ok', label: 'OK', badge: 'badge-completed', bar: '#22C55E' };
  }
  if (s <= 0 || s <= m * t) return { key: 'critical', label: 'Crítico', badge: 'badge-cancelled', bar: '#D63B3B' };
  if (s <= m) return { key: 'low', label: 'Bajo', badge: 'badge-pending', bar: '#E8A520' };
  return { key: 'ok', label: 'OK', badge: 'badge-completed', bar: '#22C55E' };
}

// devuelve stock level pct; sin efectos secundarios.
function stockLevelPct(stock, minimum) {
  const s = Number(stock || 0);
  const m = Number(minimum || 0);
  if (m <= 0) return s > 0 ? 100 : 0;
  return Math.max(0, Math.min(100, Math.round((s / m) * 100)));
}

// normalize(s): normaliza normalize; sin efectos secundarios.
function normalize(s) {
  return String(s || '').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

// filterMaterials(list, q, status, unit): filtra filter materials; sin efectos secundarios.
function filterMaterials(list, q, status, unit) {
  const nq = normalize(q);
  return (list || []).filter((m) => {
    if (status && m._status !== status) return false;
    if (unit && m.unit !== unit) return false;
    if (nq) {
      const hay = normalize((m.name || '') + ' ' + (m.code || ''));
      if (!hay.includes(nq)) return false;
    }
    return true;
  });
}

// devuelve min stock warning; sin efectos secundarios.
function minStockWarning(minimum) {
  return Number(minimum || 0) === 0;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { formatCOP, materialStatus, stockLevelPct, normalize, filterMaterials, minStockWarning };
}
