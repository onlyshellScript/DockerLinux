# Planificación — SIGOS 2.0

**Proyecto:** SIGOS 2.0
**Versión del documento:** 1.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## 1. Fases (reconstruidas del historial git)

| Fase / Sprint | Objetivos | Entregables clave | Duración estimada | Evidencia |
|---|---|---|---|---|
| H0 Fundación | Monorepo, backend, DB | Flask, Alembic, SQL Server | [PENDIENTE] | commit `34a324e` |
| Identidad | Auth JWT, roles, usuarios | `app/identity/` | [PENDIENTE] | commits iniciales |
| Órdenes | CRUD, estados, historial | `app/workorders/` | [PENDIENTE] | commits iniciales |
| Calendario | Programación, disponibilidad | `app/calendar/` | [PENDIENTE] | commits `8e402f8`... |
| Materiales | Stock, movimientos, transferencias, solicitudes | `app/materials/` | [PENDIENTE] | commits `3f5ea3a`... |
| Evidencias | Subida, revisión, firmas, checklist | `app/evidence/` | [PENDIENTE] | commits `a0dff8d`... |
| Sync offline | Push/pull | `app/sync/` | [PENDIENTE] | commits `...` |
| Notificaciones | Email/WhatsApp | `app/notifications/` | [PENDIENTE] | commits `...` |
| Producción | Docker, backups, CI | `infra/`, `.github/` | [PENDIENTE] | commits `...` |

## 2. Matriz de trazabilidad de requisitos

| ID | Descripción | Módulo / archivo | Endpoint | Prueba de verificación | Estado |
|---|---|---|---|---|---|
| RF-01 | Autenticación con JWT | `app/identity/` | `/api/v1/auth/login` | `tests/test_auth.py` | Pass |
| RF-02 | Gestión de usuarios | `app/identity/` | `/api/v1/users` | `tests/test_auth.py` | Pass |
| RF-03 | CRUD de órdenes de trabajo | `app/workorders/` | `/api/v1/work-orders` | `tests/test_workorders.py` | Pass |
| RF-04 | Historial de estados | `app/workorders/` | `/api/v1/work-orders/<id>/history` | [PENDIENTE: prueba específica] | Sin prueba |
| RF-05 | Programación y calendario | `app/calendar/` | `/api/v1/calendar/*` | `tests/test_calendar.py` | Pass |
| RF-06 | Catálogo y stock de materiales | `app/materials/` | `/api/v1/materials` | `tests/test_materials.py` | Pass |
| RF-07 | Exportación CSV/Excel/PDF | `app/materials/export.py` | `/api/v1/materials/export*` | `tests/test_export.py`, `test_export_extra.py` | Pass |
| RF-08 | Solicitudes de materiales | `app/materials/` | `/api/v1/material-requests` | `tests/test_material_requests.py` | Pass |
| RF-09 | Transferencias y consumo | `app/materials/` | `/api/v1/materials/transfer`, `/consume` | [PENDIENTE: prueba específica] | Sin prueba |
| RF-10 | Evidencias y revisión | `app/evidence/` | `/api/v1/evidences/*` | `tests/test_evidence.py` | Pass |
| RF-11 | Sincronización offline | `app/sync/` | `/api/v1/sync/*` | `tests/test_sync.py` | Pass |
| RF-12 | Notificaciones | `app/notifications/` | `/api/v1/notifications` | `tests/test_notifications.py` | Pass |
| RF-13 | Dashboard | `app/dashboard/` | `/api/v1/dashboard/summary` | [PENDIENTE: prueba específica] | Sin prueba |
| RF-14 | Catálogos geográficos | `app/catalogs/` | `/api/v1/catalogs/*` | [PENDIENTE: prueba específica] | Sin prueba |
| RF-15 | Configuración del sistema | `app/settings/` | `/api/v1/settings/*` | [PENDIENTE: prueba específica] | Sin prueba |
| RF-16 | Gestión de técnicos | `app/technicians/` | `/api/v1/technicians` | [PENDIENTE: prueba específica] | Sin prueba |

Requisitos sin prueba asociada listados en `docs/HALLAZGOS.md`.
