import time
from datetime import datetime, timedelta, timezone

import jwt

from app.extensions import db
from app.identity.models import User, Role, UserSession
from app.identity.tokens import create_access_token, create_refresh_token


_login_attempts = {}


# Verifica la condicion solicitada; recibe ip; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _check_rate_limit(ip):
    now = time.time()
    window = 300
    max_attempts = 5
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < window]
    _login_attempts[ip] = attempts
    if len(attempts) >= max_attempts:
        return False
    return True


# Registra un intento de login fallido para la IP indicada en el control de rate limit.
def _record_attempt(ip):
    _login_attempts.setdefault(ip, []).append(time.time())


# Gestiona authenticate; recibe username, password, ip; interactua con la base de datos; devuelve el valor correspondiente.
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
    session = _open_session(user, ip, now)
    db.session.commit()
    if ip:
        _login_attempts.pop(ip, None)
    return {
        "access_token": create_access_token(user, session.id),
        "refresh_token": create_refresh_token(user, session.id),
        "token_type": "Bearer",
        "user": user.to_dict(),
    }, 200


# _open_session: registra una sesion nueva (una por login); vence con el refresh token.
def _open_session(user, ip=None, now=None):
    import uuid
    from flask import current_app
    now = now or datetime.now(timezone.utc)
    session = UserSession(
        id=str(uuid.uuid4()), user_id=user.id, created_at=now,
        expires_at=now + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"],
        ip_address=(ip or None) and str(ip)[:45],
    )
    db.session.add(session)
    return session


# revoke_session: cierra una sesion; idempotente. Devuelve True si existia.
def revoke_session(sid, reason="logout"):
    session = db.session.get(UserSession, sid) if isinstance(sid, str) else None
    if session is None:
        return False
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = reason
    return True


# revoke_user_sessions: cierra todas las sesiones abiertas de un usuario (cambio o restablecimiento de contrasena,
# desactivacion). No hace commit: lo hace la operacion que la invoca. except_sid conserva la sesion actual.
def revoke_user_sessions(user_id, reason, except_sid=None):
    q = UserSession.query.filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_sid:
        q = q.filter(UserSession.id != except_sid)
    now = datetime.now(timezone.utc)
    for s in q.all():
        s.revoked_at = now
        s.revoked_reason = reason


# logout: revoca la sesion a la que pertenece el token (access o refresh). El token debe tener firma valida;
# se acepta vencido para poder cerrar una sesion cuyo access token ya expiro. Devuelve True si se revoco.
def logout(token):
    if not token:
        return False
    try:
        payload = decode_token(token, verify_exp=False)
    except jwt.InvalidTokenError:
        return False
    sid = payload.get("sid")
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return False
    session = db.session.get(UserSession, sid) if isinstance(sid, str) else None
    if session is None or session.user_id != user_id:
        return False
    revoke_session(sid, "logout")
    db.session.commit()
    return True


# Cambia la contrasena; las demas sesiones abiertas del usuario se revocan (la actual, except_sid, se conserva).
def change_password(user_id, current_password, new_password, except_sid=None):
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
    revoke_user_sessions(user.id, "password_changed", except_sid=except_sid)
    db.session.commit()
    return True, None

# Gestiona refresh access token; recibe refresh_token; interactua con la base de datos; devuelve el valor correspondiente.
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
    # Un refresh token solo renueva una sesion vigente: tras el logout (o una revocacion) deja de servir.
    sid = payload.get("sid")
    session = db.session.get(UserSession, sid) if isinstance(sid, str) else None
    if session is None or session.user_id != user.id or not session.is_active():
        return None, 401
    return {
        "access_token": create_access_token(user, session.id),
        "token_type": "Bearer",
        "user": user.to_dict(),
    }, 200


# decodifica y valida un JWT delegando en tokens.decode_token; entrada token; salida dict con claims; sin efectos secundarios adicionales.
def decode_token(token, verify_exp=True):
    from app.identity.tokens import decode_token as _decode

    return _decode(token, verify_exp=verify_exp)


# ---------- Administracion de usuarios ----------
import json as _json
import re as _re

from sqlalchemy import func as _func

USERNAME_RE = _re.compile(r"^[a-z0-9._-]{3,80}$")
EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# UserAdminError: error de validacion o de regla de negocio; code es estable para la API, field indica el campo afectado.
class UserAdminError(Exception):
    def __init__(self, code, message, field=None, status=422):
        super().__init__(message)
        self.code, self.message, self.field, self.status = code, message, field, status


# _audit_user: registra en AuditoriaEventos quien hizo que cambio sobre que usuario (nunca contrasenas).
def _audit_user(actor_id, target_user_id, action, changes=None):
    from app.identity.models import AuditEvent
    db.session.add(AuditEvent(
        actor_id=actor_id, target_user_id=target_user_id, action=action,
        changes=_json.dumps(changes, ensure_ascii=False, default=str) if changes else None,
    ))


# _clean_username: normaliza y valida el formato del nombre de usuario.
def _clean_username(value):
    from app.common.normalize import normalize_text
    v = normalize_text(value or "")
    if not USERNAME_RE.match(v):
        raise UserAdminError("invalid_username", "Usuario de 3 a 80 caracteres: letras minusculas, numeros, punto, guion o guion bajo", "username")
    return v


# _clean_email: normaliza y valida el formato del correo.
def _clean_email(value):
    from app.common.normalize import normalize_text
    v = normalize_text(value or "")
    if len(v) > 120 or not EMAIL_RE.match(v):
        raise UserAdminError("invalid_email", "Correo electronico invalido", "email")
    return v


# _ensure_unique: evita duplicados de usuario o correo (sin distinguir mayusculas) excluyendo al propio usuario.
def _ensure_unique(username=None, email=None, exclude_id=None):
    if username is not None:
        q = User.query.filter(_func.lower(User.username) == username.lower())
        if exclude_id:
            q = q.filter(User.id != exclude_id)
        if q.first():
            raise UserAdminError("duplicate_username", "El nombre de usuario ya existe", "username", 409)
    if email is not None:
        q = User.query.filter(_func.lower(User.email) == email.lower())
        if exclude_id:
            q = q.filter(User.id != exclude_id)
        if q.first():
            raise UserAdminError("duplicate_email", "El correo electronico ya esta registrado", "email", 409)


# _resolve_roles: solo se aceptan roles existentes; exige al menos uno.
def _resolve_roles(role_names):
    names = [r for r in (role_names or []) if isinstance(r, str)]
    if not names:
        raise UserAdminError("role_required", "Debe asignar un rol", "role_names")
    roles = Role.query.filter(Role.name.in_(names)).all()
    if len(roles) != len(set(names)):
        raise UserAdminError("invalid_role", "Rol no valido", "role_names")
    return roles


# _active_admin_count: administradores activos, opcionalmente excluyendo uno.
def _active_admin_count(exclude_id=None):
    q = User.query.filter(User.is_active.is_(True), User.roles.any(Role.name == "admin"))
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    return q.count()


# Crea un usuario; si no se envia contrasena se genera una temporal (devuelta una sola vez) y se exige cambio en el primer acceso.
def create_user(data, actor_id=None):
    from app.identity.passwords import validate_password_policy, generate_temporary_password
    username = _clean_username(data.get("username"))
    email = _clean_email(data.get("email"))
    roles = _resolve_roles(data.get("role_names"))
    _ensure_unique(username=username, email=email)
    password = data.get("password") or None
    temp_password = None
    if password:
        ok, msg = validate_password_policy(password, username)
        if not ok:
            raise UserAdminError("weak_password", msg, "password")
    else:
        password = temp_password = generate_temporary_password()
    user = User(username=username, email=email)
    user.set_password(password)
    user.roles = roles
    user.is_active = bool(data.get("is_active", True))
    user.must_change_password = True if temp_password else bool(data.get("must_change_password", False))
    db.session.add(user)
    db.session.flush()
    _audit_user(actor_id, user.id, "user_created", {"username": username, "email": email, "roles": [r.name for r in roles], "is_active": user.is_active})
    db.session.commit()
    return user, temp_password


# Lista usuarios con busqueda por usuario/correo y filtros por rol y estado (active|inactive).
def list_users(q=None, role=None, status=None):
    query = User.query
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.filter(db.or_(_func.lower(User.username).like(like), _func.lower(User.email).like(like)))
    if role:
        query = query.filter(User.roles.any(Role.name == role))
    if status == "active":
        query = query.filter(User.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active.is_(False))
    return query.order_by(User.username).all()


# get_user: obtiene un usuario por su id; entrada user_id; salida User o None; lee la base de datos.
def get_user(user_id):
    return db.session.get(User, user_id)


# Actualiza usuario, correo, rol y estado aplicando las protecciones de cuentas administrativas.
def update_user(user_id, data, actor_id=None):
    user = db.session.get(User, user_id)
    if not user:
        return None
    if "password" in data:
        raise UserAdminError("use_reset", "La contrasena se cambia con la accion de restablecimiento", "password")
    changes = {}
    if "username" in data:
        username = _clean_username(data["username"])
        if username != user.username:
            _ensure_unique(username=username, exclude_id=user.id)
            changes["username"] = [user.username, username]
            user.username = username
    if "email" in data:
        email = _clean_email(data["email"])
        if email != user.email:
            _ensure_unique(email=email, exclude_id=user.id)
            changes["email"] = [user.email, email]
            user.email = email
    if "role_names" in data:
        roles = _resolve_roles(data["role_names"])
        new_names = sorted(r.name for r in roles)
        old_names = sorted(r.name for r in user.roles)
        if new_names != old_names:
            if "admin" in old_names and "admin" not in new_names:
                if user.id == actor_id:
                    raise UserAdminError("self_demotion", "No puede quitarse a si mismo el rol de administrador", "role_names", 409)
                if user.is_active and _active_admin_count(exclude_id=user.id) == 0:
                    raise UserAdminError("last_admin", "Debe existir al menos un administrador activo", "role_names", 409)
            changes["roles"] = [old_names, new_names]
            user.roles = roles
    if "is_active" in data:
        active = data["is_active"]
        if not isinstance(active, bool):
            raise UserAdminError("invalid_status", "Estado invalido", "is_active")
        if active != user.is_active:
            if not active:
                if user.id == actor_id:
                    raise UserAdminError("self_deactivation", "No puede desactivar su propia cuenta", "is_active", 409)
                if any(r.name == "admin" for r in user.roles) and _active_admin_count(exclude_id=user.id) == 0:
                    raise UserAdminError("last_admin", "No se puede desactivar al ultimo administrador activo", "is_active", 409)
            changes["is_active"] = [user.is_active, active]
            user.is_active = active
            if not active:
                revoke_user_sessions(user.id, "user_deactivated")
    if changes:
        _audit_user(actor_id, user.id, "user_updated", changes)
    db.session.commit()
    return user


# Restablece la contrasena con una temporal segura: se devuelve una sola vez, solo se guarda el hash,
# se exige cambio en el siguiente acceso (las sesiones abiertas quedan bloqueadas por PASSWORD_CHANGE_REQUIRED) y se audita.
def reset_user_password(user_id, actor_id=None):
    from app.identity.passwords import generate_temporary_password
    user = db.session.get(User, user_id)
    if not user:
        return None, None
    if user.id == actor_id:
        raise UserAdminError("self_reset", "Para su propia cuenta use 'Cambiar contrasena'", None, 409)
    temp = generate_temporary_password()
    user.set_password(temp)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)
    user.failed_attempts = 0
    user.locked_until = None
    revoke_user_sessions(user.id, "password_reset")
    _audit_user(actor_id, user.id, "password_reset", {"method": "temporary_password"})
    db.session.commit()
    return user, temp


# Historial de auditoria de un usuario (mas reciente primero).
def user_audit(user_id, limit=20):
    from app.identity.models import AuditEvent
    return AuditEvent.query.filter(AuditEvent.target_user_id == user_id).order_by(AuditEvent.created_at.desc()).limit(limit).all()
