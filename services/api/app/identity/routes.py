from flask import Blueprint, request, jsonify

from app.identity.service import authenticate, refresh_access_token, change_password, logout as logout_session
from app.extensions import db
from app.identity.models import Role
from app.identity.service import create_user, list_users, get_user, update_user, reset_user_password, user_audit, UserAdminError
from app.identity.decorators import require_auth, require_role

blueprint = Blueprint("auth", __name__)


# POST /auth/login (roles: publico): login; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/auth/login")
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password required"}), 400
    ip = request.remote_addr
    result, status = authenticate(data["username"], data["password"], ip)
    if result is None:
        if status == 429:
            return jsonify({"error": "too many attempts, try again later"}), 429
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify(result), 200


# POST /auth/refresh (roles: publico): refresh; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/auth/refresh")
def refresh():
    data = request.get_json()
    if not data or not data.get("refresh_token"):
        return jsonify({"error": "refresh_token required"}), 400
    result, status = refresh_access_token(data["refresh_token"])
    if result is None:
        return jsonify({"error": "invalid refresh token"}), 401
    return jsonify(result), 200


# POST /auth/logout (roles: publico, requiere un token de la sesion): revoca en el servidor la sesion del token.
# Acepta el access token (Authorization: Bearer) y/o el refresh token en el cuerpo; ambos pertenecen a la misma sesion.
# Responde 200 aunque la sesion ya estuviera cerrada (idempotente) para que el cliente siempre limpie su estado.
@blueprint.post("/auth/logout")
def logout():
    tokens = []
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        tokens.append(auth_header.split(" ", 1)[1])
    data = request.get_json(silent=True) or {}
    if isinstance(data, dict) and isinstance(data.get("refresh_token"), str):
        tokens.append(data["refresh_token"])
    if not tokens:
        return jsonify({"error": "token required"}), 400
    revoked = False
    for t in tokens:
        revoked = logout_session(t) or revoked
    return jsonify({"message": "logged out", "revoked": revoked}), 200


# POST /auth/change-password (roles: autenticado): change password route; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/auth/change-password")
@require_auth
def change_password_route():
    data = request.get_json()
    if not data or not data.get("current_password") or not data.get("new_password"):
        return jsonify({"error": "current_password and new_password required"}), 400
    ok, msg = change_password(request.user_id, data["current_password"], data["new_password"], except_sid=request.session_id)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"message": "password changed"}), 200

# _admin_error: traduce UserAdminError a respuesta JSON estable {error, code, field}.
def _admin_error(exc):
    db.session.rollback()
    body = {"error": exc.message, "code": exc.code}
    if exc.field:
        body["field"] = exc.field
    return jsonify(body), exc.status


# GET /users (roles: admin): lista usuarios; query q (usuario/correo), role, status=active|inactive.
@blueprint.get("/users")
@require_role("admin")
def users_list():
    status = request.args.get("status")
    if status not in (None, "", "active", "inactive"):
        return jsonify({"error": "status invalido", "code": "invalid_status"}), 400
    users = list_users(q=request.args.get("q"), role=request.args.get("role") or None, status=status or None)
    return jsonify([u.to_dict() for u in users]), 200


# GET /roles (roles: admin): roles asignables.
@blueprint.get("/roles")
@require_role("admin")
def roles_list():
    return jsonify([{"name": r.name, "description": r.description} for r in Role.query.order_by(Role.name).all()]), 200


# POST /users (roles: admin): crea usuario; sin "password" genera una temporal que se devuelve una sola vez.
@blueprint.post("/users")
@require_role("admin")
def users_create():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body required", "code": "body_required"}), 400
    try:
        user, temp = create_user(data, actor_id=request.user_id)
    except UserAdminError as exc:
        return _admin_error(exc)
    body = user.to_dict()
    if temp:
        body["temporary_password"] = temp
    return jsonify(body), 201


# GET /users/<id> (roles: admin): detalle de la cuenta con su historial de auditoria.
@blueprint.get("/users/<int:user_id>")
@require_role("admin")
def users_get(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    body = user.to_dict()
    body["audit"] = [a.to_dict() for a in user_audit(user_id)]
    return jsonify(body), 200


# PUT /users/<id> (roles: admin): modifica username, email, role_names, is_active con protecciones de administradores.
@blueprint.put("/users/<int:user_id>")
@require_role("admin")
def users_update(user_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body required", "code": "body_required"}), 400
    try:
        user = update_user(user_id, data, actor_id=request.user_id)
    except UserAdminError as exc:
        return _admin_error(exc)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify(user.to_dict()), 200


# POST /users/<id>/reset-password (roles: admin): genera contrasena temporal (mostrada una sola vez) y exige cambio.
@blueprint.post("/users/<int:user_id>/reset-password")
@require_role("admin")
def users_reset_password(user_id):
    try:
        user, temp = reset_user_password(user_id, actor_id=request.user_id)
    except UserAdminError as exc:
        return _admin_error(exc)
    if not user:
        return jsonify({"error": "user not found"}), 404
    resp = jsonify({"username": user.username, "temporary_password": temp, "must_change_password": True})
    resp.headers["Cache-Control"] = "no-store"
    return resp, 200
