from datetime import datetime, timezone

import jwt
from flask import current_app


# Crea el access token de la sesion indicada; recibe user y sid (id de SesionesUsuario); sin efectos secundarios; devuelve el JWT.
def create_access_token(user, sid):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "sid": sid,
        "username": user.username,
        "roles": [r.name for r in user.roles],
        "type": "access",
        "iat": now,
        "exp": now + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


# Crea el refresh token de la sesion indicada; recibe user y sid; sin efectos secundarios; devuelve el JWT.
def create_refresh_token(user, sid):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "sid": sid,
        "type": "refresh",
        "iat": now,
        "exp": now + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


# decode_token: decodifica y valida un JWT con la clave secreta de la app; entrada token; salida dict de claims; lanza excepcion de jwt si es invalido o expirado; sin efectos secundarios.
# verify_exp=False solo se usa en el cierre de sesion (revocar una sesion cuyo access token ya vencio); la firma siempre se verifica.
def decode_token(token, verify_exp=True):
    return jwt.decode(
        token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"],
        options={"verify_exp": verify_exp},
    )
