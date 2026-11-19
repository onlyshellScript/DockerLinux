# Reconocimiento del repositorio — SIGOS 2.0

**Proyecto:** SIGOS 2.0
**Versión del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## Stack detectado

| Capa | Tecnología | Versión | Origen |
|---|---|---|---|
| Backend | Python / Flask | 3.0.3 (`services/api/requirements.txt:1`) | `services/api/requirements.txt` |
| ORM | Flask-SQLAlchemy | 3.1.1 | `services/api/requirements.txt:2` |
| Migraciones | Flask-Migrate (Alembic) | 4.0.7 | `services/api/requirements.txt:3` |
| BD | Microsoft SQL Server | 2022+ | `README.md`, `infra/docker/compose.yaml` |
| Driver | pyodbc | 5.1.0 | `services/api/requirements.txt:4` |
| Auth | PyJWT | 2.9.0 | `services/api/requirements.txt:8` |
| Exportación | openpyxl, reportlab | 3.1.5 / 4.2.5 | `services/api/requirements.txt:10-11` |
| Escritorio | Electron | [PENDIENTE: versión exacta] | `apps/desktop/package.json` |
| Móvil | Flutter / Dart | stable | `apps/mobile/pubspec.yaml` |
| CI | GitHub Actions | — | `.github/workflows/ci.yml` |

## Estructura principal

| Carpeta | Contenido |
|---|---|
| `apps/desktop/` | Electron + JS/HTML/CSS |
| `apps/mobile/` | Flutter (Android) |
| `services/api/` | Flask + modelos + migraciones + tests |
| `contracts/` | OpenAPI (`contracts/openapi.yaml`) |
| `infra/docker/` | Compose local y producción |
| `docs/` | Documentación existente (arquitectura, diseño, auditorías, trazabilidad) |
| `scripts/` | Backups PowerShell |

## Puntos de entrada

| Componente | Archivo |
|---|---|
| API dev | `services/api/wsgi.py` (`from app import create_app`) |
| API prod | `services/api/wsgi_prod.py` |
| App factory | `services/api/app/__init__.py:create_app` |
| Electron main | `apps/desktop/src/main/index.js` |
| Flutter main | `apps/mobile/lib/main.dart` |

## Modelos y tablas

41 tablas en `db.metadata` (extraídas por introspección de SQLAlchemy con `TestConfig`/SQLite). Ver `docs/02-diseno-detallado.md` § Modelo de datos.

## Endpoints

131 rutas registradas en `services/api/app/*/routes.py` (`@blueprint.<método>(...)`). Ver `docs/02-diseno-detallado.md` § API REST.

## Pruebas

- API: pytest (14 archivos, 75 pasadas, 10 omitidas en esta corrida).
- Desktop: Node test (27 pasadas).
- Móvil: Flutter test (4 pasadas).

## Huecos detectados

Ver `docs/HALLAZGOS.md`. Resumen: variables de entorno usadas en código ausentes en `.env.example` (`UPLOAD_DIR`, `EVIDENCE_*`, `SMTP_*`, `WHATSAPP_*`, `LOG_*`); tabla de BD documentada en `docs/database/database-design.md` (11 tablas) no coincide con las 41 tablas del ORM; `docs/database/database-design.md` usa identificadores en español mientras el código usa inglés.
