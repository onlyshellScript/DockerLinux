from functools import wraps

import jwt
from flask import request, jsonify

from app.identity.tokens import decode_token


# Gestiona password change required; recibe user; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _password_change_required(user):
    if not getattr(user, "must_change_password", False):
        return False
    path = request.path or ""
    if path.endswith("/auth/change-password") or path.endswith("/auth/logout") or path.endswith("/auth/refresh"):
        return False
    # Allow reading own technician profile before the mandatory password change.
    if request.method == "GET" and (path.startswith("/api/v1/technicians/") or path.endswith("/mi-perfil")):
        return False
    return True


# _authenticate: valida el access token de la peticion en el servidor, en cada peticion:
#   firma y vencimiento del JWT, tipo "access", sesion (claim sid) vigente y no revocada, usuario existente y activo.
# Devuelve (user, payload, None) o (None, None, respuesta_de_error). Los roles salen de la base, no del token.
def _authenticate():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None, (jsonify({"error": "missing token"}), 401)
    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        return None, None, (jsonify({"error": "token expired"}), 401)
    except jwt.InvalidTokenError:
        return None, None, (jsonify({"error": "invalid token"}), 401)
    if payload.get("type") != "access":
        return None, None, (jsonify({"error": "invalid token type"}), 401)
    from app.extensions import db
    from app.identity.models import User, UserSession
    sid = payload.get("sid")
    session = db.session.get(UserSession, sid) if isinstance(sid, str) else None
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None, None, (jsonify({"error": "invalid token"}), 401)
    # Sin sesion vigente (cerrada, revocada o token emitido antes de existir sesiones) el token no sirve.
    if session is None or session.user_id != user_id or not session.is_active():
        return None, None, (jsonify({"error": "session revoked", "code": "session_revoked"}), 401)
    user = db.session.get(User, user_id)
    if not user or not getattr(user, "is_active", False):
        return None, None, (jsonify({"error": "user not found or inactive"}), 401)
    if _password_change_required(user):
        return None, None, (jsonify({"error": "PASSWORD_CHANGE_REQUIRED"}), 403)
    return user, payload, None


# _bind_request: deja en la peticion el usuario autenticado y sus roles vigentes en la base.
def _bind_request(user, payload):
    request.user_id = user.id
    request.session_id = payload.get("sid")
    # Roles vigentes en la base (no los del token): un cambio de rol aplica de inmediato tambien
    # en las rutas que validan permisos manualmente con request.user_roles.
    request.user_roles = [r.name for r in user.roles]


# Gestiona require auth; recibe f; exige un access token valido de una sesion activa; responde 401/403 si no.
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user, payload, error = _authenticate()
        if error:
            return error
        _bind_request(user, payload)
        return f(*args, **kwargs)
    return decorated


# Gestiona require role; recibe *roles; como require_auth y ademas exige alguno de los roles (leidos de la base).
def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user, payload, error = _authenticate()
            if error:
                return error
            user_roles = [r.name for r in user.roles]
            if not any(r in user_roles for r in roles):
                return jsonify({"error": "insufficient permissions"}), 403
            _bind_request(user, payload)
            return f(*args, **kwargs)
        return decorated
    return decorator
