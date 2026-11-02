import time
from datetime import datetime, timedelta, timezone

import jwt

from app.extensions import db
from app.identity.models import User, Role
from app.identity.tokens import create_access_token, create_refresh_token


_login_attempts = {}


def _check_rate_limit(ip):
    now = time.time()
    window = 300
    max_attempts = 5
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < window]
    _login_attempts[ip] = attempts
    if len(attempts) >= max_attempts:
        return False
    return True


def _record_attempt(ip):
    _login_attempts.setdefault(ip, []).append(time.time())


def authenticate(username, password, ip=None):
    if ip and not _check_rate_limit(ip):
        return None, 429
    user = User.query.filter_by(username=username).first()
    if not user or not user.is_active:
        if ip:
            _record_attempt(ip)
        return None, 401
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        if ip:
            _record_attempt(ip)
        return None, 401
    if not user.check_password(password):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        if user.failed_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
        db.session.commit()
        if ip:
            _record_attempt(ip)
        return None, 401
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login = now
    db.session.commit()
    if ip:
        _login_attempts.pop(ip, None)
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "Bearer",
        "user": user.to_dict(),
    }, 200


def change_password(user_id, current_password, new_password):
    from app.identity.models import User
    from app.identity.passwords import validate_password_policy
    user = db.session.get(User, user_id)
    if not user or not user.check_password(current_password):
        return False, "current password incorrect"
    ok, msg = validate_password_policy(new_password, user.username)
    if not ok:
        return False, msg
    user.set_password(new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.now(timezone.utc)
    db.session.commit()
    return True, None

def refresh_access_token(refresh_token):
    try:
        payload = decode_token(refresh_token)
    except jwt.ExpiredSignatureError:
        return None, 401
    except jwt.InvalidTokenError:
        return None, 401
    if payload.get("type") != "refresh":
        return None, 401
    user = db.session.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        return None, 401
    return {
        "access_token": create_access_token(user),
        "token_type": "Bearer",
        "user": user.to_dict(),
    }, 200


def decode_token(token):
    from app.identity.tokens import decode_token as _decode

    return _decode(token)


def create_user(data):
    from app.common.normalize import normalize_text
    user = User(
        username=normalize_text(data["username"]),
        email=normalize_text(data["email"]),
    )
    user.set_password(data["password"])
    if data.get("role_names"):
        user.roles = Role.query.filter(Role.name.in_(data["role_names"])).all()
    db.session.add(user)
    db.session.commit()
    return user


def list_users():
    return User.query.all()


def get_user(user_id):
    return db.session.get(User, user_id)


def update_user(user_id, data):
    user = db.session.get(User, user_id)
    if not user:
        return None
    if "email" in data:
        from app.common.normalize import normalize_text
        user.email = normalize_text(data["email"])
    if "is_active" in data:
        user.is_active = data["is_active"]
    if "password" in data:
        user.set_password(data["password"])
    if "role_names" in data:
        user.roles = Role.query.filter(Role.name.in_(data["role_names"])).all()
    db.session.commit()
    return user
