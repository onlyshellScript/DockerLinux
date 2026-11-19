// orderDetailRules.js: transiciones, acciones visibles y mensajes de error del detalle de orden.
// Devuelve las transiciones de estado permitidas segun status y role; entrada status, role; salida array; sin efectos secundarios.
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

// Indica que acciones puede ver un role en un status; entrada role, status; salida objeto; sin efectos secundarios.
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

// Traduce un error de backend a mensaje legible para la UI; entrada err; salida str; sin efectos secundarios.
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

// Valida que la cantidad de material sea positiva; entrada qty; salida bool; sin efectos secundarios.
function validateMaterialQty(qty) {
  return typeof qty === 'number' ? qty > 0 : Number(qty) > 0;
}

// Valida campos obligatorios de una orden; entrada obj; salida objeto de errores; sin efectos secundarios.
function validateRequiredFields(obj) {
  const errors = {};
  if (!obj || !String(obj.customer_name || '').trim()) errors.customer_name = 'Cliente obligatorio';
  return errors;
}

// Normaliza una respuesta de API a lista; entrada resp; salida array; sin efectos secundarios.
function asList(resp) {
  if (!resp) return [];
  if (Array.isArray(resp)) return resp;
  if (resp.ok === false) {
    const err = new Error((resp.body && (resp.body.error || resp.body.message)) || 'Error de la API');
    err.status = resp.status;
    err.body = resp.body;
    throw err;
  }
  const body = (resp.body !== undefined) ? resp.body : resp;
  if (Array.isArray(body)) return body;
  if (body && Array.isArray(body.items)) return body.items;
  if (resp && Array.isArray(resp.items)) return resp.items;
  return [];
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { allowedTransitions, visibleActions, backendErrorToMessage, validateMaterialQty, validateRequiredFields, asList };
}
