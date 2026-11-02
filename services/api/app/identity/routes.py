from flask import Blueprint, request, jsonify

from app.identity.service import authenticate, refresh_access_token, change_password
from app.identity.service import create_user, list_users, get_user, update_user
from app.identity.decorators import require_auth, require_role

blueprint = Blueprint("auth", __name__)


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


@blueprint.post("/auth/refresh")
def refresh():
    data = request.get_json()
    if not data or not data.get("refresh_token"):
        return jsonify({"error": "refresh_token required"}), 400
    result, status = refresh_access_token(data["refresh_token"])
    if result is None:
        return jsonify({"error": "invalid refresh token"}), 401
    return jsonify(result), 200


@blueprint.post("/auth/change-password")
@require_auth
def change_password_route():
    data = request.get_json()
    if not data or not data.get("current_password") or not data.get("new_password"):
        return jsonify({"error": "current_password and new_password required"}), 400
    ok, msg = change_password(request.user_id, data["current_password"], data["new_password"])
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"message": "password changed"}), 200

@blueprint.get("/users")
@require_role("admin")
def users_list():
    users = list_users()
    return jsonify([u.to_dict() for u in users]), 200


@blueprint.post("/users")
@require_role("admin")
def users_create():
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400
    for field in ("username", "email", "password"):
        if not data.get(field):
            return jsonify({"error": f"{field} required"}), 400
    user = create_user(data)
    return jsonify(user.to_dict()), 201


@blueprint.get("/users/<int:user_id>")
@require_role("admin")
def users_get(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify(user.to_dict()), 200


@blueprint.put("/users/<int:user_id>")
@require_role("admin")
def users_update(user_id):
    data = request.get_json()
    user = update_user(user_id, data)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify(user.to_dict()), 200
