# Calidad, pruebas y despliegue — SIGOS 2.0

**Proyecto:** SIGOS 2.0
**Versión del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## 1. Estrategia de pruebas

| Tipo | Framework | Carpeta | Comando | Resultado |
|---|---|---|---|---|
| Unitarias/integración API | pytest 8.3.2 | `services/api/tests/` | `cd services/api && .venv\Scripts\python -m pytest tests/ -v` | 75 pasadas, 10 omitidas (SQLite; tests SQL Server omitidos sin `TEST_DB_URL`) |
| Desktop | Node test | `apps/desktop/tests/` | `cd apps/desktop && npm test` | 27 pasadas |
| Móvil | Flutter test | `apps/mobile/test/` | `cd apps/mobile && flutter test` | 4 pasadas |
| Visual E2E | Playwright | `apps/desktop/tests/visual/` | [PENDIENTE: comando] | [PENDIENTE] |

Cobertura: Sin medición de cobertura configurada (`pytest.ini` no define `--cov`).

Áreas críticas sin pruebas: settings, catalogs, technicians, dashboard, workorder history, transferencias/consumo (ver `docs/HALLAZGOS.md`).

## 2. Variables de entorno

| Variable | Obligatoria | Descripción | Valor de ejemplo (ficticio) | Archivo que la lee |
|---|---|---|---|---|
| DB_URL | Sí (prod) | Cadena de conexión SQL Server | `mssql+pyodbc://user:pass@host:1433/db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes` | `services/api/app/config.py:8`, `config_prod.py:8` |
| DB_USERNAME | No (legacy) | Usuario BD | `sigos` | `.env.example` |
| DB_PASSWORD | No (legacy) | Password BD | `change-me` | `.env.example` |
| SERVER_PORT | No | Puerto API | `5000` | `.env.example` |
| JWT_SECRET_KEY | Sí (prod) | Secreto JWT | `change-me-in-production` | `services/api/app/config.py:14`, `config_prod.py:13` |
| SIGOS_API_BASE_URL | No | URL base API (desktop/móvil) | `http://localhost:5000` | `apps/desktop/src/main/index.js`, `apps/mobile` (dart-define) |
| UPLOAD_DIR | No (default `uploads`/`/app/uploads`) | Directorio de evidencias | `/app/uploads` | `services/api/app/evidence/storage.py`, `config_prod.py:17` |
| EVIDENCE_UPLOAD_DIR | No | Override del dir de evidencias | `/app/uploads` | `services/api/app/evidence/storage.py` |
| EVIDENCE_MAX_FILE_SIZE | No (default 10MB) | Tamaño máximo de archivo | `10485760` | `services/api/app/evidence/storage.py` |
| EVIDENCE_ALLOWED_MIME_TYPES | No | MIME permitidos | `image/jpeg,application/pdf` | `services/api/app/evidence/storage.py` |
| SMTP_HOST | No | Host SMTP | `smtp.example.com` | `services/api/app/notifications/senders.py` |
| SMTP_PORT | No (default 587) | Puerto SMTP | `587` | `services/api/app/notifications/senders.py` |
| SMTP_USER | No | Usuario SMTP | `user@example.com` | `services/api/app/notifications/senders.py` |
| SMTP_PASS | No | Password SMTP | `change-me` | `services/api/app/notifications/senders.py` |
| SMTP_FROM | No (default SMTP_USER) | Remitente | `noreply@sigos.local` | `services/api/app/notifications/senders.py` |
| WHATSAPP_API_URL | No | URL API WhatsApp | `https://graph.facebook.com/...` | `services/api/app/notifications/senders.py` |
| WHATSAPP_API_TOKEN | No | Token WhatsApp | `change-me` | `services/api/app/notifications/senders.py` |
| WHATSAPP_PHONE_NUMBER_ID | No | ID número WhatsApp | `123456789` | `services/api/app/notifications/senders.py` |
| LOG_LEVEL | No (default INFO) | Nivel de log | `INFO` | `services/api/app/config_prod.py:19`, `logging_config.py` |
| LOG_FORMAT | No (default json) | Formato de log | `json` | `services/api/app/config_prod.py:20`, `logging_config.py` |
| ENABLE_NOTIFICATION_WORKER | No (default false) | Activa worker de notificaciones | `true` | `services/api/wsgi_prod.py` |
| NOTIFICATION_WORKER_INTERVAL | No (default 30) | Intervalo worker (s) | `30` | `services/api/wsgi_prod.py` |
| TEST_DB_URL | No | BD para tests SQL Server | `mssql+pyodbc://.../sigos_test` | `services/api/tests/conftest.py` |

Variables usadas en código y ausentes en `.env.example` listadas en `docs/HALLAZGOS.md` (H-01).

## 3. Base de datos local

Ver `README.md` § Base de datos local. Comandos verificados localmente (`sqlcmd` disponible, BD `sigos` y `sigos_test` existentes).

## 4. Migraciones

```powershell
cd services/api
$env:DB_URL = "mssql+pyodbc://sigos:Sigos_Dev_2026!@localhost:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
$env:FLASK_APP = "wsgi.py"
.venv\Scripts\flask db upgrade
```
Revertir: `.venv\Scripts\flask db downgrade` (una revisión a la vez). Verificado `flask db upgrade` en SQL Server local (migraciones hasta `e2a3b4c5d6e7`).

## 5. Despliegue (Docker producción)

```powershell
cd infra/docker
$env:DB_URL = "mssql+pyodbc://sa:YourPassword@sqlserver:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
$env:JWT_SECRET_KEY = "your-secret-key"
$env:MSSQL_SA_PASSWORD = "YourPassword"
docker compose -f docker-compose.prod.yaml up -d
```
Servicios: `api` (gunicorn 4 workers, puerto 5000) y `sqlserver`. Healthcheck: `GET /api/v1/health`.

## 6. Verificación posterior al despliegue

- `Invoke-RestMethod http://<host>:5000/api/v1/health` debe devolver `status: UP`.
- Logs: stdout del contenedor API (formato `LOG_FORMAT`).
- Uploads: volumen `api-uploads` en `/app/uploads`.

## 7. Backups

```powershell
.\scripts\backup-db.ps1 -Server "localhost,1433" -Database "sigos" -BackupDir "C:\Backups\SIGOS"
.\scripts\backup-uploads.ps1
```
[NO VERIFICADO] en este entorno (scripts no ejecutados).
