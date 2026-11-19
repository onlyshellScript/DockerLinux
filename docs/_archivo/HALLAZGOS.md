# Hallazgos

**Proyecto:** SIGOS 2.0
**Versión del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## Inconsistencias

| ID | Descripción | Archivos | Severidad |
|---|---|---|---|
| H-01 | `.env.example` no declara variables usadas en código: `UPLOAD_DIR`, `EVIDENCE_UPLOAD_DIR`, `EVIDENCE_MAX_FILE_SIZE`, `EVIDENCE_ALLOWED_MIME_TYPES`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `WHATSAPP_API_URL`, `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `LOG_LEVEL`, `LOG_FORMAT`, `ENABLE_NOTIFICATION_WORKER`, `NOTIFICATION_WORKER_INTERVAL`, `TEST_DB_URL`, `SERVER_PORT` | `.env.example` vs `services/api/app/config_prod.py`, `services/api/app/evidence/storage.py`, `services/api/app/notifications/senders.py`, `services/api/app/logging_config.py` | MEDIUM |
| H-02 | Documentación de BD previa (`docs/database/database-design.md`) lista 11 tablas; el ORM define 41 | `docs/database/database-design.md` vs introspección SQLAlchemy | HIGH |
| H-03 | Identificadores de BD documentados en español; implementación en inglés | `docs/database/database-design.md` §10 | LOW |
| H-04 | README contiene credenciales de desarrollo en texto plano (`<contraseña de desarrollo, ya rotada>`, `Admin123!`) | `README.md` | MEDIUM |
| H-05 | `Config` (dev) incluye credenciales por defecto en código (`services/api/app/config.py:11-13`) | `services/api/app/config.py` | MEDIUM |
| H-06 | `TestConfig` usa SQLite en memoria mientras la producción usa SQL Server; tests de concurrencia SQL Server se omiten sin `TEST_DB_URL` | `services/api/app/config.py:24-29`, `services/api/tests/conftest.py` | LOW |
| H-07 | `services/api/requirements.txt` no fija versiones de `Flask-Migrate`? sí fija; faltan `python-dotenv` usada? presente. `gunicorn` presente. | — | INFO |

## Secretos detectados

No se copian valores. Variables con valores reales en README/`.env.example`: `DB_URL` con password `<contraseña de desarrollo, ya rotada>`; `JWT_SECRET_KEY=change-me`. Reportar al equipo para rotación en producción.

## Bugs / riesgos reportados (no corregidos)

| ID | Descripción | Fuente |
|---|---|---|
| B-01 | `AuditEvent` y `AuditLog` coexisten; posible duplicación de auditoría | `services/api/app/identity/models.py:57`, `services/api/app/settings/models.py:85` |
| B-02 | Múltiples rutas de evidencia duplicadas (`/work-orders/<id>/evidences/...` y `/evidences/<id>/...`) | `services/api/app/evidence/routes.py` |
| B-03 | `NotificationSettings` y `UserNotificationPreference` solapados | `services/api/app/settings/models.py:64-84` |
| B-04 | `OrganizationSettings` singleton sin constraint visible | `services/api/app/settings/models.py:8` |

## Áreas sin pruebas

- Endpoints de settings, catalogs, technicians, dashboard, calendar ya cubiertos parcialmente; cobertura por módulo [PENDIENTE: medir con coverage].
- No hay tests de carga/rendimiento.
- No hay tests E2E del flujo completo Electron↔API.
