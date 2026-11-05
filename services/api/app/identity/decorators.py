from functools import wraps

import jwt
from flask import request, jsonify

from app.identity.tokens import decode_token


def _password_change_required(user):
    from flask import request
    if not getattr(user, "must_change_password", False):
        return False
    path = request.path or ""
    if path.endswith("/auth/change-password") or path.endswith("/auth/logout") or path.endswith("/auth/refresh"):
        return False
    return True

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing token"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
        if payload.get("type") != "access":
            return jsonify({"error": "invalid token type"}), 401
        from app.extensions import db
        user = db.session.get(__import__("app.identity.models", fromlist=["User"]).User, int(payload["sub"]))
        if user and _password_change_required(user):
            return jsonify({"error": "PASSWORD_CHANGE_REQUIRED"}), 403
        request.user_id = int(payload["sub"])
        request.user_roles = payload.get("roles", [])
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing token"}), 401
            token = auth_header.split(" ", 1)[1]
            try:
                payload = decode_token(token)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "invalid token"}), 401
            if payload.get("type") != "access":
                return jsonify({"error": "invalid token type"}), 401
            user_roles = payload.get("roles", [])
            if not any(r in user_roles for r in roles):
                return jsonify({"error": "insufficient permissions"}), 403
            request.user_id = int(payload["sub"])
            request.user_roles = user_roles
            return f(*args, **kwargs)
        return decorated
    return decorator
