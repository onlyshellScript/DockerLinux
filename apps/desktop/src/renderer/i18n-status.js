// i18n-status.js: etiquetas y estilos de estado, prioridad, rol y tecnico.
const STATUS = {
  pending: { label: 'Pendiente', badge: 'badge-pending', color: '#E8A520', bg: '#FEF3C7', icon: 'schedule' },
  assigned: { label: 'Programada', badge: 'badge-scheduled', color: '#3B82F6', bg: '#DBEAFE', icon: 'event' },
  in_progress: { label: 'En proceso', badge: 'badge-inprogress', color: '#0EA5E9', bg: '#E0F2FE', icon: 'sync' },
  completed: { label: 'Completada', badge: 'badge-completed', color: '#22C55E', bg: '#DCFCE7', icon: 'check_circle' },
  closed: { label: 'Cerrada', badge: 'badge-completed', color: '#22C55E', bg: '#DCFCE7', icon: 'lock' },
  cancelled: { label: 'Cancelada', badge: 'badge-cancelled', color: '#D63B3B', bg: '#FEE2E2', icon: 'cancel' },
};

// devuelve status of; sin efectos secundarios.
function statusOf(value) {
  if (STATUS[value]) return STATUS[value];
  const text = String(value || '').replace(/_/g, ' ');
  const capitalized = text.charAt(0).toUpperCase() + text.slice(1);
  return { label: capitalized, badge: '', color: '#3A4552', bg: '#F1F5F9', icon: 'help' };
}

const PRIORITY = {
  high: { label: 'Alta', badge: 'badge-high', color: '#D63B3B' },
  medium: { label: 'Media', badge: 'badge-medium', color: '#E8A520' },
  low: { label: 'Baja', badge: 'badge-low', color: '#64748B' },
};

// devuelve priority of; sin efectos secundarios.
function priorityOf(value) {
  if (PRIORITY[value]) return PRIORITY[value];
  const text = String(value || '').replace(/_/g, ' ');
  const capitalized = text.charAt(0).toUpperCase() + text.slice(1);
  return { label: capitalized, badge: '', color: '#3A4552' };
}

// devuelve tech status of; sin efectos secundarios.
function techStatusOf(value) {
  const map = { available: 'Disponible', busy: 'Ocupado', offduty: 'Fuera de servicio', true: 'Disponible', false: 'Fuera de servicio' };
  let key = value;
  if (typeof value === 'boolean') key = value ? 'available' : 'offduty';
  const label = map[key] || String(value || '');
  const badge = key === 'available' || key === true ? 'badge-available' : key === 'busy' ? 'badge-busy' : 'badge-offduty';
  return { label, badge };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { STATUS, statusOf, PRIORITY, priorityOf, techStatusOf, roleOf };
}

// devuelve role of; sin efectos secundarios.
function roleOf(value) {
  const map = { admin: 'Administrador', dispatcher: 'Coordinador', technician: 'Técnico', coordinator: 'Coordinador' };
  const key = String(value || '').toLowerCase();
  const label = map[key] || (String(value || '').charAt(0).toUpperCase() + String(value || '').slice(1));
  const badge = key === 'admin' ? 'badge-admin' : key === 'dispatcher' || key === 'coordinator' ? 'badge-coordinator' : key === 'technician' ? 'badge-technician' : '';
  return { label, badge };
}
