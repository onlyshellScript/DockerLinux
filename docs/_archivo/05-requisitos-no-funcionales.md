# Requisitos no funcionales â€” SIGOS 2.0

**Proyecto:** SIGOS 2.0
**VersiÃ³n del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## 1. Seguridad

- AutenticaciÃ³n: JWT access (15 min) + refresh (7 dÃ­as) (`services/api/app/config.py:14-15`).
- AutorizaciÃ³n: decoradores `require_auth` / `require_role(...)` en rutas (`services/api/app/identity/decorators.py`).
- ContraseÃ±as: `set_password` con hash (algoritmo: [PENDIENTE: revisar `app/identity/passwords.py` y `models.py`] ).
- Rate limiting de login: 5 intentos / 300 s (`LOGIN_RATE_LIMIT_MAX`, `LOGIN_RATE_LIMIT_WINDOW` en `config.py:17-18`).
- ValidaciÃ³n de entradas: validaciÃ³n manual en rutas (cÃ³digos 422).
- CORS: [PENDIENTE: no se encontrÃ³ configuraciÃ³n CORS en el cÃ³digo].
- Secretos: `JWT_SECRET_KEY` por env en prod; dev tiene default inseguro (`config.py:14`).
- Almacenamiento de evidencias: directorio configurable, lÃ­mite de tamaÃ±o y MIME (`app/evidence/storage.py`).

## 2. Rendimiento

- PaginaciÃ³n en listados (ej. `work-orders` devuelve `page`, `page_size`, `total`).
- Ãndices de BD: ver `docs/02-diseno-detallado.md` Â§ Modelo (Ã­ndices listados por tabla).
- CachÃ©: no implementado (no se encontrÃ³).
- Consultas costosas: no analizadas [PENDIENTE].

## 3. Disponibilidad y logging

- Logging: `app/logging_config.py`; niveles y formato configurables (`LOG_LEVEL`, `LOG_FORMAT`).
- Healthcheck: `GET /api/v1/health` (DB + aplicaciÃ³n).
- Worker de notificaciones opcional (`ENABLE_NOTIFICATION_WORKER`).

## 4. Compatibilidad

- Python 3.12+ (`requirements.txt`, CI).
- Node.js 20+ (CI desktop).
- Flutter stable (CI mÃ³vil).
- SQL Server 2022+ (CI usa `mcr.microsoft.com/mssql/server:2022-latest`).
- SO: Windows (instalador desktop), Android (APK mÃ³vil). Linux/macOS no documentados para desktop.

## 5. Lo que falta (riesgos)

- Sin rate limiting global (solo login).
- Sin CORS configurado (riesgo si se expone a navegador).
- Sin cachÃ©.
- Sin mediciÃ³n de cobertura.
- AuditorÃ­a duplicada (`AuditEvent` vs `AuditLog`) (H-01/H-03 en `HALLAZGOS.md`).
- Credenciales por defecto en cÃ³digo (riesgo en producciÃ³n si no se configura env).
