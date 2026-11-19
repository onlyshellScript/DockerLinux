// errorHelper.js: clasificacion y mensajes de error HTTP/transporte.
// classifyError(res): clasifica classify error; sin efectos secundarios.
function classifyError(res) {
  if (!res) {
    return { kind: 'transport', status: 0, message: 'Sin conexión con el servidor.', transportError: null };
  }
  const status = Number(res.status || 0);
  const body = res.body && typeof res.body === 'object' ? res.body : null;
  const bodyMsg = body ? (body.message || body.error) : (typeof res.body === 'string' ? res.body : null);
  const transportError = res.error || null;

  if (status === 0 || transportError) {
    return { kind: 'transport', status: 0, message: bodyMsg || 'Sin conexión con el servidor.', transportError };
  }
  if (status === 401) {
    return { kind: 'unauthorized', status, message: bodyMsg || 'Sesión expirada. Inicia sesión de nuevo.', code: body && body.code };
  }
  if (status === 403) {
    if (body && body.code === 'PASSWORD_CHANGE_REQUIRED') {
      return { kind: 'password_change', status, message: bodyMsg || 'Debes cambiar tu contraseña.', code: body.code };
    }
    return { kind: 'forbidden', status, message: bodyMsg || 'No tienes permisos para esta acción.', code: body && body.code };
  }
  if (status === 404) {
    return { kind: 'not_found', status, message: bodyMsg || 'Recurso no encontrado.', code: body && body.code };
  }
  if (status === 409) {
    return { kind: 'conflict', status, message: bodyMsg || 'Conflicto de datos.', code: body && body.code };
  }
  if (status === 422) {
    return { kind: 'validation', status, message: bodyMsg || 'Datos inválidos.', code: body && body.code, field: body && body.field };
  }
  if (status >= 500) {
    return { kind: 'server', status, message: bodyMsg || 'Error del servidor.', code: body && body.code };
  }
  if (!res.ok) {
    return { kind: 'http', status, message: bodyMsg || 'Error inesperado.', code: body && body.code };
  }
  return { kind: 'ok', status, message: null, code: body && body.code };
}

// devuelve error message; sin efectos secundarios.
function errorMessage(res, fallback) {
  if (!res) return fallback || 'Sin conexión con el servidor.';
  const info = classifyError(res);
  return (info && info.message) || fallback || 'Error';
}

// asList(resp): convierte as list; sin efectos secundarios.
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
  module.exports = { classifyError, errorMessage, asList };
}
