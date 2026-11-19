# Administración de usuarios, autenticación y autorización

> Código: `services/api/app/identity/` · UI: módulo Usuarios en `apps/desktop/src/renderer/app.js`
> Pruebas: `tests/test_users_admin.py`, `tests/test_auth.py`, `tests/test_rnf04_security.py`, `tests/test_rnf05_access_rules.py`

## 1. Autenticación

- JWT HS256: *access* (15 min) y *refresh*; contraseñas con hash de werkzeug.
- `POST /auth/login` limita intentos por IP (5 en 5 min) y bloquea la cuenta 15 min tras 5 fallos.
- Cuentas inactivas: rechazadas en login, refresh y en **cada** petición (`require_auth` / `require_role` consultan la base).
- `must_change_password`: la API responde `403 PASSWORD_CHANGE_REQUIRED` a todo salvo cambio de contraseña, refresh y
  logout. Aplica tanto en `require_auth` como en `require_role`.

## 2. Autorización

- `require_role(...)` y `require_auth` leen **los roles vigentes en la base**, no los del token. Retirar un rol tiene efecto
  inmediato, incluso en rutas que validan manualmente con `request.user_roles`.
- Matriz de acceso declarada y verificada en `tests/test_rnf05_access_rules.py`: toda ruta nueva debe declararse o el test falla.

## 3. Endpoints de usuarios (solo admin)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/users?q=&role=&status=active\|inactive` | Lista con búsqueda y filtros |
| GET | `/roles` | Roles asignables |
| POST | `/users` | Crea; sin `password` genera una temporal (devuelta **una sola vez**) |
| GET | `/users/<id>` | Detalle + historial de auditoría de la cuenta |
| PUT | `/users/<id>` | `username`, `email`, `role_names`, `is_active` |
| POST | `/users/<id>/reset-password` | Contraseña temporal (una sola vez, `Cache-Control: no-store`) |

Errores: `{error, code, field}` con `422` (validación) o `409` (conflicto). Códigos: `invalid_username`, `invalid_email`,
`role_required`, `invalid_role`, `duplicate_username`, `duplicate_email`, `weak_password`, `use_reset`,
`self_deactivation`, `self_demotion`, `last_admin`, `self_reset`.

## 4. Reglas

- Usuario `^[a-z0-9._-]{3,80}$`; correo válido ≤120; duplicados sin distinguir mayúsculas.
- Contraseña inicial manual: política de `passwords.validate_password_policy` (≥10, mayúscula, minúscula, número).
- Un admin no puede desactivarse ni quitarse el rol admin a sí mismo, ni restablecer su propia contraseña desde este módulo.
- Siempre debe quedar al menos un administrador activo.
- La contraseña no se cambia por `PUT`; solo con el restablecimiento.
- Restablecimiento: contraseña temporal segura, solo se guarda el hash, `must_change_password = true`, desbloquea la
  cuenta; las sesiones abiertas quedan bloqueadas por `PASSWORD_CHANGE_REQUIRED` hasta el cambio.
- No hay SMTP configurado, por eso no se usa enlace de restablecimiento por correo.

## 5. Auditoría

Tabla `AuditoriaEventos` (`AuditEvent`): `user_created`, `user_updated` (con `[antes, después]` por campo),
`password_reset`. Registra el actor; nunca contraseñas.

## 6. Interfaz

Tabla con usuario, correo, rol, estado, creación y último acceso; búsqueda con espera, filtros por rol y estado;
modales de alta/edición/detalle; confirmaciones para desactivar y restablecer; contraseña temporal mostrada una vez y
borrada del campo al cerrar.

## 7. Pendientes de seguridad

Ver `docs/revision-2026-11-17.md`: los valores de **Configuración > Seguridad** no se aplican (bloqueo, longitud mínima,
historial, sesiones y vigencia están fijos en el código o no existen).
