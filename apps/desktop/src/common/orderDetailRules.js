function allowedTransitions(status, role) {
  const base = {
    pending: ['assigned', 'cancelled'],
    assigned: ['in_progress', 'cancelled'],
    in_progress: ['completed', 'cancelled'],
    completed: [],
    cancelled: [],
  };
  let list = base[status] || [];
  const isTech = role === 'technician';
  if (isTech) list = list.filter((s) => s !== 'cancelled' && s !== 'assigned');
  return list;
}

function visibleActions(role, status) {
  const isManager = role === 'admin' || role === 'dispatcher';
  const terminal = status === 'completed' || status === 'cancelled';
  return {
    assign: isManager,
    cancel: isManager,
    schedule: isManager,
    materials: true,
    edit: isManager && !terminal,
  };
}

function backendErrorToMessage(err) {
  const status = err && (err.status || err.statusCode);
  const msg = (err && (err.error || err.message || err.code || (typeof err === 'string' ? err : ''))) || '';
  const low = String(msg).toLowerCase();
  if (low.includes('schedule_conflict') || low.includes('solape')) return 'Solape de horario del tecnico';
  if (low.includes('sunday') || low.includes('domingo')) return 'Se requiere autorizacion de administrador para programar en domingo o festivo';
  if (low.includes('invalid_time') || low.includes('fuera de horario') || low.includes('outside')) return 'Fuera de horario laboral';
  if (low.includes('invalid_technician') || low.includes('tecnico invalido')) return 'Tecnico invalido o inactivo';
  if (low.includes('insufficient') || low.includes('stock')) return 'Stock insuficiente';
  // reason required se devuelve tal cual (422)
  if (status === 409 || status === 412 || low.includes('stale') || low.includes('version')) return 'Otra persona modifico esta orden';
  if (status === 422) return String(msg || 'Datos invalidos');
  return String(msg || 'Error');
}

function validateMaterialQty(qty) {
  return typeof qty === 'number' ? qty > 0 : Number(qty) > 0;
}

function validateRequiredFields(obj) {
  const errors = {};
  if (!obj || !String(obj.customer_name || '').trim()) errors.customer_name = 'Cliente obligatorio';
  return errors;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { allowedTransitions, visibleActions, backendErrorToMessage, validateMaterialQty, validateRequiredFields };
}
