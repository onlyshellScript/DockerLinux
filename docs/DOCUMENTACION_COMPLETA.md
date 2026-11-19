**DOCUMENTACIÓN COMPLETA — SIGOS 2.0**

**Portada**

| Campo | Valor |
|---|---|
| Proyecto | SIGOS 2.0 |
| Organización | [PENDIENTE] |
| Autores | [PENDIENTE] |
| Versión del documento | 1.0 |
| Fecha de última modificación | 06/11/2026 |
| Repositorio | Monorepositorio SIGOS 2.0 |

> **Actualización 17/11/2026.** Este documento describe el estado al 06/11/2026. Los cambios posteriores están en:
>
> | Tema | Documento |
> |---|---|
> | Revisión técnica, resultados de pruebas y pendientes priorizados | `docs/revision-2026-11-17.md` |
> | Esquema en español (las tablas de §3.1 usan hoy nombres en español: `users → Usuarios`, …) y estado de migraciones | `docs/database/esquema-espanol-y-orm.md` |
> | Administración de usuarios, autenticación y autorización (endpoints nuevos de §3.2) | `docs/architecture/usuarios-y-seguridad.md` |
> | Motor de exportaciones PDF/XLSX y asistente (endpoints `/exports/*`) | `docs/architecture/exportaciones.md` |
> | Sistema de diseño, layout y accesibilidad del desktop | `docs/design/sistema-de-diseno.md` |
> | Guía de desarrollo y pruebas | `docs/development/guia-desarrollo-y-pruebas.md` |


# 1. Introducción y guía de inicio

## 1.1 Descripción del sistema

SIGOS 2.0 es un monorepositorio para la gestión de órdenes de servicio técnico con backend Flask, cliente de escritorio Electron y cliente móvil Flutter, sobre SQL Server.

## 1.2 Componentes del repositorio

| Componente | Tecnología | Carpeta | Propósito |
|---|---|---|---|
| API | Python / Flask 3.0.3 | `services/api/` | Backend REST, persistencia, reglas de negocio |
| Escritorio | Electron | `apps/desktop/` | UI de gestión para administradores y técnicos |
| Móvil | Flutter / Dart | `apps/mobile/` | UI móvil con sincronización offline |

## 1.3 Requisitos previos

- Python 3.12+
- ODBC Driver 18 for SQL Server
- SQL Server 2022+ o SQL Server Express
- Node.js 20+
- Flutter stable

## 1.4 Instalación y primer uso

1. Clonar el repositorio.
2. Crear la base de datos y el usuario (ver Sección 5.3).
3. Backend:
   ```powershell
   cd services/api
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   $env:DB_URL = "mssql+pyodbc://sigos:<password>@localhost:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
   $env:FLASK_APP = "wsgi.py"
   .venv\Scripts\flask db upgrade
   .venv\Scripts\python seed.py
   ```
4. Escritorio:
   ```powershell
   cd apps/desktop
   npm install
   ```
5. Móvil:
   ```powershell
   cd apps/mobile
   flutter pub get
   ```
6. Ejecutar API:
   ```powershell
   cd services/api
   $env:DB_URL = "mssql+pyodbc://sigos:<password>@localhost:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
   $env:FLASK_APP = "wsgi.py"
   .venv\Scripts\flask run --port 5000
   ```
7. Verificar:
   ```powershell
   Invoke-RestMethod http://localhost:5000/api/v1/health
   ```

## 1.5 Resultado esperado

Respuesta JSON: `{"checks":{"application":"UP","database":"UP"},"status":"UP"}` (verificado localmente).

---
PY
# 2. Arquitectura y diseño de alto nivel


**Proyecto:** SIGOS 2.0
**Fecha:** 06/11/2026
**Autor:** [PENDIENTE]

## 2.1 Vista de contexto (C4 nivel 1)

### Actores y sistemas externos

| Actor / Elemento | Tipo / Rol | Descripción de la interacción |
|---|---|---|
| Administrador | Usuario (rol `admin`) | Gestiona usuarios, órdenes, materiales, configuración (`services/api/seed.py`, `app/identity`) |
| Despachador | Usuario (rol `dispatcher`) | Crea y asigna órdenes |
| Técnico | Usuario (rol `technician`) | Ejecuta órdenes, consume materiales, sube evidencias (`app/evidence`, `app/materials`) |
| App de escritorio | Contenedor Electron | Consume API REST vía `SIGOS_API_BASE_URL` (`apps/desktop/src/main/index.js`, `src/renderer/app.js`) |
| App móvil | Contenedor Flutter | Consume API REST; sincronización offline (`apps/mobile/lib/core/sync/sync_service.dart`) |
| SQL Server | Sistema externo (BD) | Persistencia principal (`services/api/app/config.py`) |
| SMTP | Sistema externo (correo) | Envío de notificaciones (`app/notifications/senders.py`) |
| WhatsApp API | Sistema externo | Envío de notificaciones (`app/notifications/senders.py`) |
| Almacenamiento de archivos | Sistema externo (disco/volumen) | Evidencias (`app/evidence/storage.py`, `UPLOAD_DIR`) |

![Diagrama 1](diagrams/diagrama1.png)

## 2.2 Contenedores y componentes (C4 nivel 2)

### Frontend / Clientes

| Contenedor | Tecnología | Responsabilidad | Carpeta |
|---|---|---|---|
| Escritorio | Electron + JS/HTML/CSS | UI de gestión, calendario, evidencias | `apps/desktop/` |
| Móvil | Flutter + Dart | UI móvil, offline, sync | `apps/mobile/` |

### Backend

| Componente | Carpeta | Responsabilidad |
|---|---|---|
| App factory | `services/api/app/__init__.py` | Registra blueprints bajo `/api/v1` |
| Identidad | `app/identity/` | Login, JWT, usuarios, roles, audit |
| Órdenes | `app/workorders/` | CRUD, estados, historial, programación, asignación |
| Materiales | `app/materials/` | Catálogo, stock, movimientos, transferencias, solicitudes |
| Evidencias | `app/evidence/` | Subida, revisión, firmas, checklist, eventos |
| Calendario | `app/calendar/` | Eventos, disponibilidad, validación |
| Notificaciones | `app/notifications/` | Cola y envío (email/WhatsApp) |
| Sincronización | `app/sync/` | Push/pull offline |
| Dashboard | `app/dashboard/` | Resúmenes |
| Técnicos | `app/technicians/` | Perfiles, disponibilidad, activación |
| Catálogos | `app/catalogs/` | Países, ciudades, zonas, especialidades, tipos de instalación, sectores |
| Configuración | `app/settings/` | Organización, operaciones, seguridad, notificaciones, audit log |

### Base de datos

| Elemento | Detalle |
|---|---|
| Motor | Microsoft SQL Server 2022+ (`infra/docker/compose.yaml`) |
| ORM | Flask-SQLAlchemy 3.1.1 |
| Migraciones | Alembic/Flask-Migrate (`services/api/migrations/`) |
| Tablas | 41 (introspección SQLAlchemy) |

![Diagrama 2](diagrams/diagrama2.png)

## 2.3 Registros de decisiones de arquitectura (ADR)

| ID ADR | Decisión tecnológica | Justificación / Beneficios | Alternativas descartadas | Estatus |
|---|---|---|---|---|
| ADR-01 | Backend Flask | Evidencia: `services/api/requirements.txt`, `app/__init__.py` | [PENDIENTE: confirmar motivo con el equipo] | Por confirmar |
| ADR-02 | SQL Server como BD | Evidencia: `Sección 1`, `infra/docker/compose.yaml`, `config.py` | [PENDIENTE: confirmar motivo con el equipo] | Por confirmar |
| ADR-03 | JWT para autenticación | Evidencia: `app/identity/tokens.py`, `config.py` (expiración 15 min / 7 días) | [PENDIENTE: confirmar motivo con el equipo] | Por confirmar |
| ADR-04 | Electron para escritorio | Evidencia: `apps/desktop/package.json` | [PENDIENTE: confirmar motivo con el equipo] | Por confirmar |
| ADR-05 | Flutter para móvil | Evidencia: `apps/mobile/pubspec.yaml` | [PENDIENTE: confirmar motivo con el equipo] | Por confirmar |
| ADR-06 | Alembic para migraciones | Evidencia: `services/api/migrations/`, `extensions.py` | [PENDIENTE: confirmar motivo con el equipo] | Por confirmar |
| ADR-07 | Almacenamiento local de evidencias (`UPLOAD_DIR`) | Evidencia: `app/evidence/storage.py`, `config_prod.py` | [PENDIENTE: confirmar motivo con el equipo] | Por confirmar |

---


# 3. Diseño detallado y de datos

## 3.1 Modelo entidad-relación (41 tablas)

Fuente: introspección de SQLAlchemy (`services/api/app/*/models.py`).

### audit_events

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| actor_id | INTEGER  FK->users.id |
| target_user_id | INTEGER  FK->users.id |
| action | VARCHAR(40) NOT NULL |
| changes | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function AuditEvent.<lambda> at 0x00000209BD0FA8E0>) |

### audit_log

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function AuditLog.<lambda> at 0x00000209BD310180>) |
| user_id | INTEGER  FK->users.id |
| section | VARCHAR(40) NOT NULL |
| field | VARCHAR(80) |
| old_value | TEXT |
| new_value | TEXT |
| result | VARCHAR(20) NOT NULL DEFAULT ScalarElementColumnDefault('applied') |
| request_id | VARCHAR(40) |
| username | VARCHAR(80) |

Indices: INDEX ix_audit_log_section: ['section'] unique=False; INDEX ix_audit_log_section_created: ['section', 'created_at'] unique=False; INDEX ix_audit_log_created_at: ['created_at'] unique=False

### cities

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| country_id | INTEGER NOT NULL FK->countries.id |
| department_name | VARCHAR(120) |
| dane_code | VARCHAR(5) NOT NULL |
| name | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) NOT NULL |
| active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

Indices: INDEX ix_city_country_name_norm: ['country_id', 'name_norm'] unique=False; INDEX ix_cities_country_id: ['country_id'] unique=False

### countries

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| iso2 | VARCHAR(2) UK NOT NULL |
| name | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) UK NOT NULL |
| active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

### departments

| Campo | Tipo y restricciones |
|---|---|
| code | VARCHAR(2) PK NOT NULL |
| name | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) |

### evidence_events

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| work_order_id | INTEGER  FK->work_orders.id |
| evidence_id | INTEGER  FK->visit_evidences.id |
| actor_id | INTEGER  FK->users.id |
| action | VARCHAR(40) NOT NULL |
| from_status | VARCHAR(30) |
| to_status | VARCHAR(30) |
| details | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function EvidenceEvent.<lambda> at 0x00000209BD3CEF20>) |

Indices: INDEX ix_evidence_events_work_order_id: ['work_order_id'] unique=False; INDEX ix_evidence_events_evidence_id: ['evidence_id'] unique=False; INDEX ix_evidence_events_created_at: ['created_at'] unique=False

### evidence_reviews

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| evidence_id | INTEGER NOT NULL FK->visit_evidences.id |
| reviewer_id | INTEGER NOT NULL FK->users.id |
| decision | VARCHAR(30) NOT NULL |
| notes | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function EvidenceReview.<lambda> at 0x00000209BD3CDBC0>) |

Indices: INDEX ix_evidence_reviews_evidence_id: ['evidence_id'] unique=False

### installation_types

| Campo | Tipo y restricciones |
|---|---|
| code | VARCHAR(60) PK NOT NULL |
| label | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) UK NOT NULL |
| active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

### material_catalog

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| category_id | INTEGER NOT NULL FK->material_categories.id |
| code | VARCHAR(40) UK NOT NULL |
| name | VARCHAR(200) NOT NULL |
| name_norm | VARCHAR(200) UK NOT NULL |
| unit_id | INTEGER NOT NULL FK->material_units.id |
| measure | VARCHAR(60) |
| stage | VARCHAR(60) |
| applies_to | VARCHAR(40) |
| is_active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

Indices: INDEX ix_material_catalog_unit_id: ['unit_id'] unique=False; INDEX ix_material_catalog_name_norm: ['name_norm'] unique=True; INDEX ix_material_catalog_category_id: ['category_id'] unique=False; INDEX ix_material_catalog_code: ['code'] unique=True

### material_categories

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| code | VARCHAR(40) UK NOT NULL |
| name | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) UK NOT NULL |
| is_active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

Indices: INDEX ix_material_categories_code: ['code'] unique=True; INDEX ix_material_categories_name_norm: ['name_norm'] unique=True

### material_request_deliveries

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| request_id | INTEGER NOT NULL FK->material_requests.id |
| actor_id | INTEGER NOT NULL FK->users.id |
| operation_id | VARCHAR(36) |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function MaterialRequestDelivery.<lambda> at 0x00000209BD22A840>) |

Indices: INDEX ix_material_request_deliveries_created_at: ['created_at'] unique=False; INDEX ix_material_request_deliveries_request_id: ['request_id'] unique=False; INDEX ix_material_request_deliveries_operation_id: ['operation_id'] unique=False

### material_request_delivery_items

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| delivery_id | INTEGER NOT NULL FK->material_request_deliveries.id |
| request_item_id | INTEGER NOT NULL FK->material_request_items.id |
| quantity_delivered | FLOAT NOT NULL |
| movement_id | INTEGER  FK->stock_movements.id |

Indices: INDEX ix_material_request_delivery_items_request_item_id: ['request_item_id'] unique=False; INDEX ix_material_request_delivery_items_delivery_id: ['delivery_id'] unique=False

### material_request_events

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| request_id | INTEGER NOT NULL FK->material_requests.id |
| actor_id | INTEGER  FK->users.id |
| action | VARCHAR(40) NOT NULL |
| from_status | VARCHAR(30) |
| to_status | VARCHAR(30) |
| payload | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function MaterialRequestEvent.<lambda> at 0x00000209BD229440>) |

Indices: INDEX ix_material_request_events_created_at: ['created_at'] unique=False; INDEX ix_material_request_events_request_id: ['request_id'] unique=False

### material_request_items

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| request_id | INTEGER NOT NULL FK->material_requests.id |
| material_id | INTEGER NOT NULL FK->materials.id |
| quantity | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| quantity_requested | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| quantity_approved | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| quantity_delivered | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |

Indices: INDEX ix_material_request_items_request_id: ['request_id'] unique=False; INDEX ix_material_request_items_material_id: ['material_id'] unique=False

### material_request_operations

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| operation_id | VARCHAR(36) UK NOT NULL |
| operation_type | VARCHAR(40) NOT NULL |
| actor_id | INTEGER  FK->users.id |
| request_id | INTEGER  FK->material_requests.id |
| result | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function MaterialRequestOperation.<lambda> at 0x00000209BD24D120>) |

Indices: INDEX ix_material_request_operations_request_id: ['request_id'] unique=False; INDEX ix_material_request_operations_created_at: ['created_at'] unique=False; INDEX ix_material_request_operations_operation_id: ['operation_id'] unique=True; INDEX ix_material_request_operations_operation_type: ['operation_type'] unique=False

### material_requests

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| requester_id | INTEGER NOT NULL FK->users.id |
| technician_id | INTEGER  FK->technician_profiles.id |
| work_order_id | INTEGER  FK->work_orders.id |
| status | VARCHAR(30) NOT NULL DEFAULT ScalarElementColumnDefault('SUBMITTED') |
| client_operation_id | VARCHAR(36) UK |
| delivered_by_id | INTEGER  FK->users.id |
| reason | TEXT |
| approved_by_id | INTEGER  FK->users.id |
| approval_reason | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function MaterialRequest.<lambda> at 0x00000209BD1D84A0>) |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function MaterialRequest.<lambda> at 0x00000209BD1D8680>) |

Indices: INDEX ix_material_requests_requester_id: ['requester_id'] unique=False; INDEX ix_material_requests_client_operation_id: ['client_operation_id'] unique=True; INDEX ix_material_requests_work_order_id: ['work_order_id'] unique=False; INDEX ix_material_requests_technician_id: ['technician_id'] unique=False

### material_units

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| code | VARCHAR(20) UK NOT NULL |
| name | VARCHAR(60) NOT NULL |
| name_norm | VARCHAR(60) UK NOT NULL |
| allows_decimal | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(False) |
| is_active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

Indices: INDEX ix_material_units_code: ['code'] unique=True; INDEX ix_material_units_name_norm: ['name_norm'] unique=True

### materials

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| name | VARCHAR(120) NOT NULL |
| code | VARCHAR(40) UK |
| description | VARCHAR(250) |
| unit | VARCHAR(20) NOT NULL |
| current_stock | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| min_stock | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| unit_price | NUMERIC(18, 2) NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| is_active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |
| catalog_item_id | INTEGER UK FK->material_catalog.id |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function Material.<lambda> at 0x00000209BD177100>) |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function Material.<lambda> at 0x00000209BD1772E0>) |

Indices: INDEX ix_materials_code: ['code'] unique=True; INDEX ix_materials_catalog_item_id: ['catalog_item_id'] unique=True; INDEX ix_materials_name: ['name'] unique=False

### municipalities

| Campo | Tipo y restricciones |
|---|---|
| code | VARCHAR(5) PK NOT NULL |
| name | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) |
| department_code | VARCHAR(2)  FK->departments.code |

Indices: INDEX ix_municipalities_department_code: ['department_code'] unique=False

### notification_settings

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| preferences | TEXT NOT NULL DEFAULT ScalarElementColumnDefault('{}') |
| version | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| updated_by_id | INTEGER  FK->users.id |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function NotificationSettings.<lambda> at 0x00000209BD2E2660>) |

### notifications

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| user_id | INTEGER NOT NULL FK->users.id |
| channel | VARCHAR(15) NOT NULL |
| recipient | VARCHAR(250) NOT NULL |
| subject | VARCHAR(200) |
| message | TEXT NOT NULL |
| status | VARCHAR(15) NOT NULL DEFAULT ScalarElementColumnDefault('pending') |
| retry_count | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| error_message | VARCHAR(500) |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function Notification.<lambda> at 0x00000209BD4DDEE0>) |
| sent_at | DATETIME |

Indices: INDEX ix_notifications_status: ['status'] unique=False; INDEX ix_notifications_user_id: ['user_id'] unique=False

### operational_settings

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| work_days | VARCHAR(20) NOT NULL DEFAULT ScalarElementColumnDefault('1,2,3,4,5') |
| work_start | VARCHAR(5) NOT NULL DEFAULT ScalarElementColumnDefault('07:00') |
| work_end | VARCHAR(5) NOT NULL DEFAULT ScalarElementColumnDefault('18:00') |
| default_visit_duration | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(60) |
| max_visit_duration | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(480) |
| min_advance_hours | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| travel_margin_minutes | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| calendar_interval | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(30) |
| stock_critical_threshold | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0.5) |
| version | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| updated_by_id | INTEGER  FK->users.id |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function OperationalSettings.<lambda> at 0x00000209BD2E0360>) |

### organization_settings

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| company_name | VARCHAR(150) NOT NULL DEFAULT ScalarElementColumnDefault('SIGOS') |
| nit | VARCHAR(40) |
| admin_email | VARCHAR(120) NOT NULL DEFAULT ScalarElementColumnDefault('admin@sigos.local') |
| contact_phone | VARCHAR(30) |
| address | VARCHAR(250) |
| city_id | INTEGER  FK->cities.id |
| timezone | VARCHAR(60) NOT NULL DEFAULT ScalarElementColumnDefault('America/Bogota') |
| version | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| updated_by_id | INTEGER  FK->users.id |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function OrganizationSettings.<lambda> at 0x00000209BD2AEFC0>) |

### roles

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| name | VARCHAR(50) UK NOT NULL |
| description | VARCHAR(200) |

Indices: INDEX ix_roles_name: ['name'] unique=True

### sectors

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| municipality_code | VARCHAR(5)  FK->municipalities.code |
| name | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) |
| kind | VARCHAR(30) NOT NULL DEFAULT ScalarElementColumnDefault('sector') |
| active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

Indices: INDEX ix_sectors_municipality_code: ['municipality_code'] unique=False

### security_settings

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| session_inactivity_minutes | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(30) |
| session_max_hours | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(8) |
| password_min_length | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(10) |
| password_history_count | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(3) |
| lock_attempts | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(5) |
| lock_minutes | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(15) |
| temp_password_validity_days | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(7) |
| version | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| updated_by_id | INTEGER  FK->users.id |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function SecuritySettings.<lambda> at 0x00000209BD2E1580>) |

### specialties

| Campo | Tipo y restricciones |
|---|---|
| code | VARCHAR(60) PK NOT NULL |
| label | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) UK NOT NULL |
| active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

### stock_movements

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| material_id | INTEGER NOT NULL FK->materials.id |
| quantity | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| quantity_requested | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| quantity_approved | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| quantity_delivered | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| movement_type | VARCHAR(15) NOT NULL |
| work_order_id | INTEGER  FK->work_orders.id |
| user_id | INTEGER NOT NULL FK->users.id |
| notes | VARCHAR(250) |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function StockMovement.<lambda> at 0x00000209BD1B1120>) |

Indices: INDEX ix_stock_movements_material_id: ['material_id'] unique=False

### sync_operations

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| client_operation_id | VARCHAR(36) UK NOT NULL |
| operation_type | VARCHAR(50) NOT NULL |
| payload | TEXT NOT NULL |
| user_id | INTEGER NOT NULL FK->users.id |
| status | VARCHAR(15) NOT NULL DEFAULT ScalarElementColumnDefault('pending') |
| result | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function SyncOperation.<lambda> at 0x00000209BD4DC4A0>) |
| synced_at | DATETIME |

Indices: INDEX ix_sync_operations_status: ['status'] unique=False; INDEX ix_sync_operations_client_operation_id: ['client_operation_id'] unique=True

### technician_profiles

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| user_id | INTEGER UK NOT NULL FK->users.id |
| first_name | VARCHAR(80) |
| last_name | VARCHAR(80) |
| phone | VARCHAR(30) |
| email | VARCHAR(120) |
| specialty | VARCHAR(80) |
| specialty_code | VARCHAR(60)  FK->specialties.code |
| legacy_zone | VARCHAR(250) |
| document_type | VARCHAR(20) |
| document_number | VARCHAR(40) |
| document | VARCHAR(40) |
| is_available | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |
| is_active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |
| open_orders | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| created_by_id | INTEGER  FK->users.id |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function TechnicianProfile.<lambda> at 0x00000209BD1DBD80>) |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function TechnicianProfile.<lambda> at 0x00000209BD1DBF60>) |

### technician_stock

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| technician_id | INTEGER NOT NULL FK->technician_profiles.id |
| material_id | INTEGER NOT NULL FK->materials.id |
| quantity | FLOAT NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function TechnicianStock.<lambda> at 0x00000209BD1B2AC0>) |

Indices: INDEX ix_technician_stock_technician_id: ['technician_id'] unique=False; INDEX ix_technician_stock_material_id: ['material_id'] unique=False

### technician_zones

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| technician_id | INTEGER NOT NULL FK->technician_profiles.id |
| city_id | INTEGER NOT NULL FK->cities.id |
| zone_id | INTEGER  FK->zones.id |
| is_primary | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(False) |

Indices: INDEX ix_technician_zones_technician_id: ['technician_id'] unique=False; INDEX ix_technician_zones_city_id: ['city_id'] unique=False; INDEX uq_techzone_primary: ['technician_id'] unique=True; INDEX uq_techzone_zone: ['technician_id', 'city_id', 'zone_id'] unique=True; INDEX uq_techzone_city_all: ['technician_id', 'city_id'] unique=True; INDEX ix_technician_zones_zone_id: ['zone_id'] unique=False

### user_notification_preferences

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| user_id | INTEGER UK NOT NULL FK->users.id |
| preferences | TEXT NOT NULL DEFAULT ScalarElementColumnDefault('{}') |
| version | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function UserNotificationPreference.<lambda> at 0x00000209BD2E3420>) |

### user_roles

| Campo | Tipo y restricciones |
|---|---|
| user_id | INTEGER PK NOT NULL FK->users.id |
| role_id | INTEGER PK NOT NULL FK->roles.id |

### users

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| username | VARCHAR(80) UK NOT NULL |
| email | VARCHAR(120) UK NOT NULL |
| password_hash | VARCHAR(256) NOT NULL |
| is_active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |
| must_change_password | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(False) |
| password_changed_at | DATETIME |
| failed_attempts | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| locked_until | DATETIME |
| last_login | DATETIME |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function User.<lambda> at 0x00000209BD0EB7E0>) |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function User.<lambda> at 0x00000209BD0EBA60>) |

Indices: INDEX ix_users_username: ['username'] unique=True; INDEX ix_users_email: ['email'] unique=True

### visit_checklist_items

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| work_order_id | INTEGER NOT NULL FK->work_orders.id |
| label | VARCHAR(250) NOT NULL |
| result | VARCHAR(30) |
| notes | TEXT |
| checked_by_id | INTEGER  FK->users.id |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function VisitChecklistItem.<lambda> at 0x00000209BD3F0680>) |

Indices: INDEX ix_visit_checklist_items_work_order_id: ['work_order_id'] unique=False

### visit_evidences

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| work_order_id | INTEGER NOT NULL FK->work_orders.id |
| category | VARCHAR(20) NOT NULL DEFAULT ScalarElementColumnDefault('ADDITIONAL') |
| original_name | VARCHAR(250) |
| storage_key | VARCHAR(120) UK |
| mime_type | VARCHAR(100) |
| size_bytes | INTEGER |
| sha256 | VARCHAR(64) |
| declared_capture_at | DATETIME |
| received_at | DATETIME DEFAULT CallableColumnDefault(<function VisitEvidence.<lambda> at 0x00000209BD3753A0>) |
| uploaded_by_id | INTEGER NOT NULL FK->users.id |
| description | TEXT |
| status | VARCHAR(30) NOT NULL DEFAULT ScalarElementColumnDefault('DRAFT') |
| previous_evidence_id | INTEGER  FK->visit_evidences.id |
| version_number | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(1) |
| duplicate_of_id | INTEGER  FK->visit_evidences.id |
| client_operation_id | VARCHAR(36) |
| file_name | VARCHAR(250) |
| stored_name | VARCHAR(250) |
| file_type | VARCHAR(50) |
| file_size | INTEGER |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function VisitEvidence.<lambda> at 0x00000209BD3758A0>) |

Indices: INDEX ix_visit_evidences_work_order_id: ['work_order_id'] unique=False; INDEX ix_visit_evidences_sha256: ['sha256'] unique=False; INDEX ix_visit_evidences_storage_key: ['storage_key'] unique=True; INDEX ix_visit_evidences_client_operation_id: ['client_operation_id'] unique=False

### visit_signatures

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| work_order_id | INTEGER NOT NULL FK->work_orders.id |
| storage_key | VARCHAR(120) |
| signer_name | VARCHAR(120) |
| signer_role | VARCHAR(120) |
| received_at | DATETIME DEFAULT CallableColumnDefault(<function VisitSignature.<lambda> at 0x00000209BD377BA0>) |
| acceptance_text | TEXT |
| consent_version | VARCHAR(40) |
| technician_id | INTEGER  FK->users.id |
| refused | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(False) |
| refusal_reason | TEXT |
| client_operation_id | VARCHAR(36) |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function VisitSignature.<lambda> at 0x00000209BD377F60>) |

Indices: INDEX ix_visit_signatures_work_order_id: ['work_order_id'] unique=False; INDEX ix_visit_signatures_client_operation_id: ['client_operation_id'] unique=False

### work_order_status_history

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| work_order_id | INTEGER NOT NULL FK->work_orders.id |
| from_status | VARCHAR(20) NOT NULL |
| to_status | VARCHAR(20) NOT NULL |
| changed_by_id | INTEGER NOT NULL FK->users.id |
| notes | TEXT |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function WorkOrderStatusHistory.<lambda> at 0x00000209BD175580>) |

Indices: INDEX ix_work_order_status_history_work_order_id: ['work_order_id'] unique=False

### work_orders

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| title | VARCHAR(200) NOT NULL |
| description | TEXT |
| status | VARCHAR(20) NOT NULL DEFAULT ScalarElementColumnDefault('pending') |
| priority | VARCHAR(10) NOT NULL DEFAULT ScalarElementColumnDefault('medium') |
| customer_name | VARCHAR(120) |
| customer_phone | VARCHAR(30) |
| address | VARCHAR(250) |
| zone | VARCHAR(60) |
| legacy_zone | VARCHAR(60) |
| city_id | INTEGER  FK->cities.id |
| zone_id | INTEGER  FK->zones.id |
| installation_type | VARCHAR(80) |
| installation_type_code | VARCHAR(60)  FK->installation_types.code |
| scheduled_at | DATETIME |
| scheduled_end | DATETIME |
| schedule_notes | TEXT |
| version | INTEGER NOT NULL DEFAULT ScalarElementColumnDefault(0) |
| cancel_reason | TEXT |
| assigned_to_id | INTEGER  FK->users.id |
| created_by_id | INTEGER NOT NULL FK->users.id |
| created_at | DATETIME DEFAULT CallableColumnDefault(<function WorkOrder.<lambda> at 0x00000209BD11E980>) |
| updated_at | DATETIME DEFAULT CallableColumnDefault(<function WorkOrder.<lambda> at 0x00000209BD11EB60>) |
| completed_at | DATETIME |

Indices: INDEX ix_work_orders_legacy_zone: ['legacy_zone'] unique=False; INDEX ix_work_orders_status: ['status'] unique=False; INDEX ix_work_orders_city_id: ['city_id'] unique=False; INDEX ix_work_orders_assigned_to_id: ['assigned_to_id'] unique=False; INDEX ix_work_orders_scheduled_at: ['scheduled_at'] unique=False; INDEX ix_work_orders_zone: ['zone'] unique=False; INDEX ix_work_orders_zone_id: ['zone_id'] unique=False

### zones

| Campo | Tipo y restricciones |
|---|---|
| id | INTEGER PK NOT NULL |
| city_id | INTEGER NOT NULL FK->cities.id |
| kind | VARCHAR(30) NOT NULL |
| name | VARCHAR(120) NOT NULL |
| name_norm | VARCHAR(120) NOT NULL |
| active | BOOLEAN NOT NULL DEFAULT ScalarElementColumnDefault(True) |

Indices: INDEX ix_zones_city_id: ['city_id'] unique=False

Diagrama ER (dominio principal):

![Diagrama 3](diagrams/diagrama3.png)

## 3.2 API REST: resumen de endpoints (131)

| Método | Ruta | Auth | Origen |
|---|---|---|---|
| GET | /api/v1/calendar/events | Público | calendar\routes.py:11 |
| GET | /api/v1/calendar/unassigned | Público | calendar\routes.py:38 |
| POST | /api/v1/calendar/validate | Público | calendar\routes.py:51 |
| GET | /api/v1/technicians/<int:tid>/availability | Público | calendar\routes.py:71 |
| GET | /api/v1/catalogs/countries | Público | catalogs\routes.py:14 |
| GET | /api/v1/catalogs/cities | Público | catalogs\routes.py:21 |
| GET | /api/v1/catalogs/zones | Público | catalogs\routes.py:44 |
| GET | /api/v1/catalogs/specialties | Público | catalogs\routes.py:55 |
| GET | /api/v1/catalogs/installation-types | Público | catalogs\routes.py:62 |
| POST | /api/v1/catalogs/zones | Público | catalogs\routes.py:69 |
| PATCH | /api/v1/catalogs/zones/<int:zid> | Público | catalogs\routes.py:96 |
| POST | /api/v1/catalogs/specialties | Público | catalogs\routes.py:123 |
| POST | /api/v1/catalogs/installation-types | Público | catalogs\routes.py:142 |
| GET | /api/v1/catalogs/departments | Público | catalogs\routes.py:162 |
| GET | /api/v1/catalogs/municipalities | Público | catalogs\routes.py:169 |
| GET | /api/v1/catalogs/sectors | Público | catalogs\routes.py:180 |
| GET | /api/v1/dashboard/summary | Público | dashboard\routes.py:25 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences | Público | evidence\routes.py:68 |
| GET | /api/v1/work-orders/<int:wo_id>/evidences | Público | evidence\routes.py:112 |
| GET | /api/v1/evidences/<int:ev_id> | Público | evidence\routes.py:125 |
| GET | /api/v1/evidences | Público | evidence\routes.py:138 |
| GET | /api/v1/evidences/<int:ev_id>/download | Público | evidence\routes.py:146 |
| DELETE | /api/v1/evidences/<int:ev_id> | Público | evidence\routes.py:166 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence-status | Público | evidence\routes.py:176 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence | Público | evidence\routes.py:188 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/submit | Público | evidence\routes.py:195 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/send | Público | evidence\routes.py:221 |
| POST | /api/v1/evidences/<int:ev_id>/submit | Público | evidence\routes.py:227 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/resubmit | Público | evidence\routes.py:245 |
| POST | /api/v1/work-orders/<int:wo_id>/resubmit | Público | evidence\routes.py:261 |
| POST | /api/v1/work-orders/<int:wo_id>/signatures | Público | evidence\routes.py:268 |
| GET | /api/v1/work-orders/<int:wo_id>/signatures | Público | evidence\routes.py:309 |
| POST | /api/v1/work-orders/<int:wo_id>/checklist | Público | evidence\routes.py:322 |
| GET | /api/v1/work-orders/<int:wo_id>/checklist | Público | evidence\routes.py:347 |
| PATCH | /api/v1/checklist/<int:item_id> | Público | evidence\routes.py:359 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence-events | Público | evidence\routes.py:380 |
| POST | /api/v1/evidences/<int:ev_id>/review | Público | evidence\routes.py:393 |
| GET | /api/v1/evidences/<int:ev_id>/reviews | Público | evidence\routes.py:406 |
| GET | /api/v1/evidences/inbox | Público | evidence\routes.py:421 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence-detail | Público | evidence\routes.py:445 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/start-review | Público | evidence\routes.py:460 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/request-correction | Público | evidence\routes.py:473 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/approve | Público | evidence\routes.py:487 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/reject | Público | evidence\routes.py:500 |
| POST | /api/v1/evidences/<int:ev_id>/start-review | Público | evidence\routes.py:515 |
| POST | /api/v1/evidences/<int:ev_id>/request-correction | Público | evidence\routes.py:524 |
| POST | /api/v1/evidences/<int:ev_id>/approve | Público | evidence\routes.py:533 |
| POST | /api/v1/evidences/<int:ev_id>/reject | Público | evidence\routes.py:542 |
| GET | /api/v1/health | Público | health\routes.py:9 |
| POST | /api/v1/auth/login | Público | identity\routes.py:10 |
| POST | /api/v1/auth/refresh | Público | identity\routes.py:24 |
| POST | /api/v1/auth/change-password | Público | identity\routes.py:35 |
| GET | /api/v1/users | Público | identity\routes.py:46 |
| POST | /api/v1/users | Público | identity\routes.py:53 |
| GET | /api/v1/users/<int:user_id> | Público | identity\routes.py:66 |
| PUT | /api/v1/users/<int:user_id> | Público | identity\routes.py:75 |
| GET | /api/v1/material-categories | Público | materials\routes.py:46 |
| GET | /api/v1/material-units | Público | materials\routes.py:54 |
| GET | /api/v1/material-catalog | Público | materials\routes.py:62 |
| POST | /api/v1/material-catalog | Público | materials\routes.py:96 |
| GET | /api/v1/materials | Público | materials\routes.py:130 |
| POST | /api/v1/materials | Público | materials\routes.py:160 |
| GET | /api/v1/materials/export | Público | materials\routes.py:186 |
| GET | /api/v1/materials/export/preview | Público | materials\routes.py:236 |
| GET | /api/v1/materials/export/download | Público | materials\routes.py:262 |
| GET | /api/v1/materials/<int:mat_id> | Público | materials\routes.py:304 |
| PUT | /api/v1/materials/<int:mat_id> | Público | materials\routes.py:313 |
| POST | /api/v1/materials/<int:mat_id>/movements | Público | materials\routes.py:335 |
| GET | /api/v1/materials/<int:mat_id>/movements | Público | materials\routes.py:372 |
| GET | /api/v1/technician-profiles | Público | materials\routes.py:381 |
| POST | /api/v1/technician-profiles | Público | materials\routes.py:391 |
| GET | /api/v1/technician-profiles/<int:profile_id> | Público | materials\routes.py:404 |
| PUT | /api/v1/technician-profiles/<int:profile_id> | Público | materials\routes.py:413 |
| POST | /api/v1/materials/transfer | Público | materials\routes.py:427 |
| POST | /api/v1/materials/consume | Público | materials\routes.py:449 |
| GET | /api/v1/technician-stock | Público | materials\routes.py:468 |
| GET | /api/v1/material-requests | Público | materials\routes.py:479 |
| POST | /api/v1/material-requests | Público | materials\routes.py:496 |
| GET | /api/v1/material-requests/<int:req_id> | Público | materials\routes.py:518 |
| PATCH | /api/v1/material-requests/<int:req_id> | Público | materials\routes.py:528 |
| POST | /api/v1/material-requests/<int:req_id>/submit | Público | materials\routes.py:547 |
| POST | /api/v1/material-requests/<int:req_id>/approve | Público | materials\routes.py:565 |
| POST | /api/v1/material-requests/<int:req_id>/reject | Público | materials\routes.py:584 |
| POST | /api/v1/material-requests/<int:req_id>/deliver | Público | materials\routes.py:601 |
| POST | /api/v1/material-requests/<int:req_id>/cancel | Público | materials\routes.py:622 |
| GET | /api/v1/material-requests/<int:req_id>/events | Público | materials\routes.py:639 |
| GET | /api/v1/work-orders/<int:wo_id>/material-requests | Público | materials\routes.py:649 |
| POST | /api/v1/work-orders/<int:wo_id>/materials | Público | materials\routes.py:661 |
| POST | /api/v1/notifications | Público | notifications\routes.py:12 |
| GET | /api/v1/notifications | Público | notifications\routes.py:33 |
| POST | /api/v1/notifications/process | Público | notifications\routes.py:46 |
| GET | /api/v1/settings/organization | Público | settings\routes.py:16 |
| PATCH | /api/v1/settings/organization | Público | settings\routes.py:36 |
| GET | /api/v1/settings/operations | Público | settings\routes.py:59 |
| PATCH | /api/v1/settings/operations | Público | settings\routes.py:68 |
| POST | /api/v1/settings/operations/impact | Público | settings\routes.py:87 |
| GET | /api/v1/settings/security | Público | settings\routes.py:95 |
| PATCH | /api/v1/settings/security | Público | settings\routes.py:111 |
| GET | /api/v1/settings/notifications | Público | settings\routes.py:128 |
| PATCH | /api/v1/settings/notifications | Público | settings\routes.py:138 |
| GET | /api/v1/settings/notifications/me | Público | settings\routes.py:155 |
| PATCH | /api/v1/settings/notifications/me | Público | settings\routes.py:162 |
| GET | /api/v1/settings/public | Público | settings\routes.py:176 |
| GET | /api/v1/audit-log | Público | settings\routes.py:182 |
| GET | /api/v1/audit-log/export.csv | Público | settings\routes.py:233 |
| POST | /api/v1/sync/push | Público | sync\routes.py:9 |
| GET | /api/v1/sync/pull | Público | sync\routes.py:22 |
| GET | /api/v1/technicians | Público | technicians\routes.py:18 |
| GET | /api/v1/technicians/username-available | Público | technicians\routes.py:45 |
| POST | /api/v1/technicians | Público | technicians\routes.py:55 |
| GET | /api/v1/technicians/<int:tid> | Público | technicians\routes.py:77 |
| PATCH | /api/v1/technicians/<int:tid> | Público | technicians\routes.py:89 |
| PATCH | /api/v1/technicians/<int:tid>/availability | Público | technicians\routes.py:105 |
| POST | /api/v1/technicians/<int:tid>/deactivate | Público | technicians\routes.py:124 |
| POST | /api/v1/technicians/<int:tid>/activate | Público | technicians\routes.py:136 |
| POST | /api/v1/technicians/<int:tid>/reset-password | Público | technicians\routes.py:145 |
| POST | /api/v1/technicians/<int:tid>/unlock | Público | technicians\routes.py:154 |
| GET | /api/v1/work-orders | Público | workorders\routes.py:22 |
| POST | /api/v1/work-orders | Público | workorders\routes.py:71 |
| GET | /api/v1/work-orders/<int:wo_id> | Público | workorders\routes.py:83 |
| PATCH | /api/v1/work-orders/<int:wo_id> | Público | workorders\routes.py:96 |
| PUT | /api/v1/work-orders/<int:wo_id> | Público | workorders\routes.py:114 |
| POST | /api/v1/work-orders/<int:wo_id>/status | Público | workorders\routes.py:130 |
| POST | /api/v1/work-orders/<int:wo_id>/transitions | Público | workorders\routes.py:161 |
| POST | /api/v1/work-orders/<int:wo_id>/schedule | Público | workorders\routes.py:202 |
| PATCH | /api/v1/work-orders/<int:wo_id>/schedule | Público | workorders\routes.py:241 |
| POST | /api/v1/work-orders/<int:wo_id>/assignments | Público | workorders\routes.py:282 |
| GET | /api/v1/work-orders/<int:wo_id>/history | Público | workorders\routes.py:305 |
| GET | /api/v1/work-orders/<int:wo_id>/timeline | Público | workorders\routes.py:318 |
| POST | /api/v1/work-orders/bulk | Público | workorders\routes.py:324 |
| GET | /api/v1/work-orders/export.csv | Público | workorders\routes.py:338 |

Códigos de error: 400, 401, 403, 404, 409, 422 (validación y negocio; el cuerpo incluye `error`/`message` y, en casos de negocio, `code`).

---

# 4. Planificación y gestión del proyecto



## 4.1 Fases (reconstruidas del historial git)

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

## 4.2 Matriz de trazabilidad de requisitos

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

Requisitos sin prueba asociada listados en `Anexo D`.

---

# 5. Calidad, pruebas y despliegue



## 5.1 Estrategia de pruebas

| Tipo | Framework | Carpeta | Comando | Resultado |
|---|---|---|---|---|
| Unitarias/integración API | pytest 8.3.2 | `services/api/tests/` | `cd services/api && .venv\Scripts\python -m pytest tests/ -v` | 75 pasadas, 10 omitidas (SQLite; tests SQL Server omitidos sin `TEST_DB_URL`) |
| Desktop | Node test | `apps/desktop/tests/` | `cd apps/desktop && npm test` | 27 pasadas |
| Móvil | Flutter test | `apps/mobile/test/` | `cd apps/mobile && flutter test` | 4 pasadas |
| Visual E2E | Playwright | `apps/desktop/tests/visual/` | [PENDIENTE: comando] | [PENDIENTE] |

Cobertura: Sin medición de cobertura configurada (`pytest.ini` no define `--cov`).

Áreas críticas sin pruebas: settings, catalogs, technicians, dashboard, workorder history, transferencias/consumo (ver `Anexo D`).

## 5.2 Variables de entorno

| Variable | Obligatoria | Descripción | Valor de ejemplo (ficticio) | Archivo que la lee |
|---|---|---|---|---|
| DB_URL | Sí (prod) | Cadena de conexión SQL Server | `mssql+pyodbc://user:pass@host:1433/db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes` | `services/api/app/config.py:8`, `config_prod.py:8` |
| DB_USERNAME | No (legacy) | Usuario BD | `sigos` | `.env.example` |
| DB_PASSWORD | No (legacy) | Password BD | `change-me` | `.env.example` |
| SERVER_PORT | No | Puerto API | `5000` | `.env.example` |
| JWT_SECRET_KEY | Sí (prod) | Secreto JWT | `<jwt-secret>` | `services/api/app/config.py:14`, `config_prod.py:13` |
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

Variables usadas en código y ausentes en `.env.example` listadas en `Anexo D` (H-01).

## 5.3 Base de datos local

Ver `Sección 1` § Base de datos local. Comandos verificados localmente (`sqlcmd` disponible, BD `sigos` y `sigos_test` existentes).

## 5.4 Migraciones

```powershell
cd services/api
$env:DB_URL = "mssql+pyodbc://sigos:<password>@localhost:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
$env:FLASK_APP = "wsgi.py"
.venv\Scripts\flask db upgrade
```
Revertir: `.venv\Scripts\flask db downgrade` (una revisión a la vez). Verificado `flask db upgrade` en SQL Server local (migraciones hasta `e2a3b4c5d6e7`).

## 5.5 Despliegue (Docker producción)

```powershell
cd infra/docker
$env:DB_URL = "mssql+pyodbc://sa:YourPassword@sqlserver:1433/sigos?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
$env:JWT_SECRET_KEY = "your-secret-key"
$env:MSSQL_SA_PASSWORD = "YourPassword"
docker compose -f docker-compose.prod.yaml up -d
```
Servicios: `api` (gunicorn 4 workers, puerto 5000) y `sqlserver`. Healthcheck: `GET /api/v1/health`.

## 5.6 Verificación posterior al despliegue

- `Invoke-RestMethod http://<host>:5000/api/v1/health` debe devolver `status: UP`.
- Logs: stdout del contenedor API (formato `LOG_FORMAT`).
- Uploads: volumen `api-uploads` en `/app/uploads`.

## 5.7 Backups

```powershell
.\scripts\backup-db.ps1 -Server "localhost,1433" -Database "sigos" -BackupDir "C:\Backups\SIGOS"
.\scripts\backup-uploads.ps1
```
[NO VERIFICADO] en este entorno (scripts no ejecutados).

---

# 6. Requisitos no funcionales

## Requisitos no funcionales — SIGOS 2.0


## 6.1 Seguridad

- Autenticación: JWT access (15 min) + refresh (7 días) (`services/api/app/config.py:14-15`).
- Autorización: decoradores `require_auth` / `require_role(...)` en rutas (`services/api/app/identity/decorators.py`).
- Contraseñas: `set_password` con hash (algoritmo: [PENDIENTE: revisar `app/identity/passwords.py` y `models.py`] ).
- Rate limiting de login: 5 intentos / 300 s (`LOGIN_RATE_LIMIT_MAX`, `LOGIN_RATE_LIMIT_WINDOW` en `config.py:17-18`).
- Validación de entradas: validación manual en rutas (códigos 422).
- CORS: [PENDIENTE: no se encontró configuración CORS en el código].
- Secretos: `JWT_SECRET_KEY` por env en prod; dev tiene default inseguro (`config.py:14`).
- Almacenamiento de evidencias: directorio configurable, límite de tamaño y MIME (`app/evidence/storage.py`).

## 6.2 Rendimiento

- Paginación en listados (ej. `work-orders` devuelve `page`, `page_size`, `total`).
- Índices de BD: ver `Sección 3` § Modelo (índices listados por tabla).
- Caché: no implementado (no se encontró).
- Consultas costosas: no analizadas [PENDIENTE].

## 6.3 Disponibilidad y logging

- Logging: `app/logging_config.py`; niveles y formato configurables (`LOG_LEVEL`, `LOG_FORMAT`).
- Healthcheck: `GET /api/v1/health` (DB + aplicación).
- Worker de notificaciones opcional (`ENABLE_NOTIFICATION_WORKER`).

## 6.4 Compatibilidad

- Python 3.12+ (`requirements.txt`, CI).
- Node.js 20+ (CI desktop).
- Flutter stable (CI móvil).
- SQL Server 2022+ (CI usa `mcr.microsoft.com/mssql/server:2022-latest`).
- SO: Windows (instalador desktop), Android (APK móvil). Linux/macOS no documentados para desktop.

## 6.5 Lo que falta (riesgos)

- Sin rate limiting global (solo login).
- Sin CORS configurado (riesgo si se expone a navegador).
- Sin caché.
- Sin medición de cobertura.
- Auditoría duplicada (`AuditEvent` vs `AuditLog`) (H-01/H-03 en `HALLAZGOS.md`).
- Credenciales por defecto en código (riesgo en producción si no se configura env).

---

# 7. Tutoriales de casos de uso



## 7.1 Verificar que la API está viva

**Objetivo:** Confirmar instalación correcta.
**Prerrequisitos:** Backend ejecutándose en `localhost:5000`.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod http://localhost:5000/api/v1/health
   ```
**Resultado esperado:** `{"checks":{"application":"UP","database":"UP"},"status":"UP"}`.
**Errores frecuentes:** Puerto ocupado; `DB_URL` incorrecto.

## 7.2 Autenticarse y obtener token

**Objetivo:** Obtener JWT de acceso.
**Prerrequisitos:** Usuario admin existente (seed).
**Pasos:**
1. Ejecutar:
   ```powershell
   $resp = Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/v1/auth/login -ContentType "application/json" -Body '{"username":"admin","password":"<password>"}'
   $token = $resp.access_token
   ```
**Resultado esperado:** Objeto con `access_token`, `refresh_token`, `user`.
**Errores frecuentes:** 401 `invalid credentials`.

## 7.3 Crear una orden de trabajo

**Objetivo:** Crear una orden pendiente.
**Prerrequisitos:** Token de admin.
**Pasos:**
1. Ejecutar:
   ```powershell
   $h = @{ Authorization = "Bearer $token" }
   Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/v1/work-orders -Headers $h -ContentType "application/json" -Body '{"title":"Orden de prueba","description":"Prueba doc","priority":"high"}'
   ```
**Resultado esperado:** Orden con `status: "pending"` e `id` asignado.
**Errores frecuentes:** 422 si falta `title`.

## 7.4 Listar órdenes con filtros

**Objetivo:** Consultar órdenes.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:5000/api/v1/work-orders?status=pending&page=1&page_size=10" -Headers $h
   ```
**Resultado esperado:** Objeto con `items`, `total`, `page`.

## 7.5 Consultar catálogo de materiales

**Objetivo:** Listar materiales.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5000/api/v1/materials -Headers $h
   ```
**Resultado esperado:** Lista de materiales con `stock_actual`.

## 7.6 Sincronización offline (pull)

**Objetivo:** Obtener cambios desde servidor.
**Pasos:**
1. Ejecutar:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:5000/api/v1/sync/pull?since=2026-01-01T00:00:00Z" -Headers $h
   ```
**Resultado esperado:** Objeto con datos y `server_time`.
**Errores frecuentes:** 401 si token expirado.

---
# 8. Proyecto de ejemplo (`examples/api-quickstart`)

Cliente mínimo en Python (biblioteca estándar) que verifica health, autentica y crea una orden.

Comando de ejecución:

```powershell
cd examples/api-quickstart
python main.py
```

Resultado esperado:

```text
Health: {'checks': {'application': 'UP', 'database': 'UP'}, 'status': 'UP'}
Orden creada: <id> pending
```

El ejemplo usa credenciales de desarrollo definidas por `seed.py` (no se reproducen aquí).

---

# 9. Solución de problemas (FAQ)



| # | Síntoma | Causa probable | Solución |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'app'` | Ejecutar comandos fuera de `services/api` o sin `PYTHONPATH` | `cd services/api` y usar `.venv\Scripts\python` |
| 2 | `pyodbc.Error: ... Login failed` | Credenciales/BD incorrectas | Verificar `DB_URL` y que el login `sigos` exista |
| 3 | `flask db upgrade` falla por SQLite | Migraciones usan ALTER no soportado por SQLite | Usar SQL Server (no SQLite) para migraciones |
| 4 | Tests SQL Server se omiten | `TEST_DB_URL` no definido | Definir `TEST_DB_URL` y ejecutar con `-m sqlserver` |
| 5 | Puerto 5000 ocupado | Otro proceso | Cambiar `--port` o liberar puerto |
| 6 | `invalid credentials` en login | Password/usuario incorrecto o seed no ejecutado | Ejecutar `seed.py`; credenciales dev `admin`/`<password>` |
| 7 | `missing token` / `token expired` | JWT expirado (15 min) | Refrescar con `/auth/refresh` o volver a login |
| 8 | Evidencias no se guardan | `UPLOAD_DIR` inexistente o sin permisos | Crear directorio y verificar permisos |
| 9 | CORS bloquea llamadas desde navegador | CORS no configurado en backend | [PENDIENTE: implementar CORS o usar proxy] |
| 10 | Migraciones pendientes en producción | No se ejecutó `flask db upgrade` | Ejecutar migraciones antes de arrancar |
| 11 | Desktop no conecta a API | `SIGOS_API_BASE_URL` incorrecto | Definir variable de entorno |
| 12 | Build móvil falla por SDK | Flutter no instalado/versión | Instalar Flutter stable y ejecutar `flutter doctor` |

---

# 10. Validación de la documentación y mantenimiento



## 10.1 Prueba de lectura aislada

Usando únicamente `Sección 1` y `docs/`:

- (a) Instalar: posible siguiendo `Sección 1` + `Sección 5`. Verificado parcialmente en entorno local (backend).
- (b) Ejecutar primer uso: verificado (`Invoke-RestMethod http://localhost:5000/api/v1/health`).
- (c) Llamar a 3 endpoints: verificado (health, login, work-orders).
- (d) Correr pruebas: comandos documentados y ejecutados.

Puntos de fricción: credenciales en README; variables de entorno faltantes en `.env.example`; BD documentada (11 tablas) no coincide con ORM (41).

## 10.2 Checklist de revisión humana

- [ ] ¿Entendí qué hace el proyecto solo con la primera frase del README?
- [ ] ¿Pude instalarlo y ejecutar el primer ejemplo sin ayuda?
- [ ] ¿Encontré el tutorial de mi caso de uso?
- [ ] ¿La documentación de la API respondió mis dudas sin leer el código?
- [ ] ¿Entendí la arquitectura lo suficiente para hacer un cambio pequeño?
- [ ] ¿Algún comando falló o dio un resultado distinto al documentado?
- [ ] ¿Qué sección eliminaría, aclararía o ampliaría?

## 10.3 Seguimiento de revisiones

| Fecha | Revisor | Dificultad encontrada | Sección afectada | Estado |
|---|---|---|---|---|
| | | | | |

## 10.4 Proceso de mantenimiento

- Nueva ruta → actualizar `Sección 3` (tabla de endpoints) y `Sección 4` (trazabilidad).
- Nueva variable de entorno → actualizar `Sección 5` § Variables y `.env.example`.
- Nuevo modelo/tabla → actualizar `Sección 3` § Modelo.
- Cambio de despliegue → actualizar `Sección 5`.
- Nuevo módulo → actualizar `Sección 2`.

---

# Anexo A. Referencia completa de la API (131 endpoints)

Tabla completa `Método | Ruta | Auth | Origen`. Detalle de parámetros y códigos de error: `services/api/app/*/routes.py`.

| Método | Ruta | Auth | Origen |
|---|---|---|---|
| GET | /api/v1/calendar/events | Público | calendar\routes.py:11 |
| GET | /api/v1/calendar/unassigned | Público | calendar\routes.py:38 |
| POST | /api/v1/calendar/validate | Público | calendar\routes.py:51 |
| GET | /api/v1/technicians/<int:tid>/availability | Público | calendar\routes.py:71 |
| GET | /api/v1/catalogs/countries | Público | catalogs\routes.py:14 |
| GET | /api/v1/catalogs/cities | Público | catalogs\routes.py:21 |
| GET | /api/v1/catalogs/zones | Público | catalogs\routes.py:44 |
| GET | /api/v1/catalogs/specialties | Público | catalogs\routes.py:55 |
| GET | /api/v1/catalogs/installation-types | Público | catalogs\routes.py:62 |
| POST | /api/v1/catalogs/zones | Público | catalogs\routes.py:69 |
| PATCH | /api/v1/catalogs/zones/<int:zid> | Público | catalogs\routes.py:96 |
| POST | /api/v1/catalogs/specialties | Público | catalogs\routes.py:123 |
| POST | /api/v1/catalogs/installation-types | Público | catalogs\routes.py:142 |
| GET | /api/v1/catalogs/departments | Público | catalogs\routes.py:162 |
| GET | /api/v1/catalogs/municipalities | Público | catalogs\routes.py:169 |
| GET | /api/v1/catalogs/sectors | Público | catalogs\routes.py:180 |
| GET | /api/v1/dashboard/summary | Público | dashboard\routes.py:25 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences | Público | evidence\routes.py:68 |
| GET | /api/v1/work-orders/<int:wo_id>/evidences | Público | evidence\routes.py:112 |
| GET | /api/v1/evidences/<int:ev_id> | Público | evidence\routes.py:125 |
| GET | /api/v1/evidences | Público | evidence\routes.py:138 |
| GET | /api/v1/evidences/<int:ev_id>/download | Público | evidence\routes.py:146 |
| DELETE | /api/v1/evidences/<int:ev_id> | Público | evidence\routes.py:166 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence-status | Público | evidence\routes.py:176 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence | Público | evidence\routes.py:188 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/submit | Público | evidence\routes.py:195 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/send | Público | evidence\routes.py:221 |
| POST | /api/v1/evidences/<int:ev_id>/submit | Público | evidence\routes.py:227 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/resubmit | Público | evidence\routes.py:245 |
| POST | /api/v1/work-orders/<int:wo_id>/resubmit | Público | evidence\routes.py:261 |
| POST | /api/v1/work-orders/<int:wo_id>/signatures | Público | evidence\routes.py:268 |
| GET | /api/v1/work-orders/<int:wo_id>/signatures | Público | evidence\routes.py:309 |
| POST | /api/v1/work-orders/<int:wo_id>/checklist | Público | evidence\routes.py:322 |
| GET | /api/v1/work-orders/<int:wo_id>/checklist | Público | evidence\routes.py:347 |
| PATCH | /api/v1/checklist/<int:item_id> | Público | evidence\routes.py:359 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence-events | Público | evidence\routes.py:380 |
| POST | /api/v1/evidences/<int:ev_id>/review | Público | evidence\routes.py:393 |
| GET | /api/v1/evidences/<int:ev_id>/reviews | Público | evidence\routes.py:406 |
| GET | /api/v1/evidences/inbox | Público | evidence\routes.py:421 |
| GET | /api/v1/work-orders/<int:wo_id>/evidence-detail | Público | evidence\routes.py:445 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/start-review | Público | evidence\routes.py:460 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/request-correction | Público | evidence\routes.py:473 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/approve | Público | evidence\routes.py:487 |
| POST | /api/v1/work-orders/<int:wo_id>/evidences/reject | Público | evidence\routes.py:500 |
| POST | /api/v1/evidences/<int:ev_id>/start-review | Público | evidence\routes.py:515 |
| POST | /api/v1/evidences/<int:ev_id>/request-correction | Público | evidence\routes.py:524 |
| POST | /api/v1/evidences/<int:ev_id>/approve | Público | evidence\routes.py:533 |
| POST | /api/v1/evidences/<int:ev_id>/reject | Público | evidence\routes.py:542 |
| GET | /api/v1/health | Público | health\routes.py:9 |
| POST | /api/v1/auth/login | Público | identity\routes.py:10 |
| POST | /api/v1/auth/refresh | Público | identity\routes.py:24 |
| POST | /api/v1/auth/change-password | Público | identity\routes.py:35 |
| GET | /api/v1/users | Público | identity\routes.py:46 |
| POST | /api/v1/users | Público | identity\routes.py:53 |
| GET | /api/v1/users/<int:user_id> | Público | identity\routes.py:66 |
| PUT | /api/v1/users/<int:user_id> | Público | identity\routes.py:75 |
| GET | /api/v1/material-categories | Público | materials\routes.py:46 |
| GET | /api/v1/material-units | Público | materials\routes.py:54 |
| GET | /api/v1/material-catalog | Público | materials\routes.py:62 |
| POST | /api/v1/material-catalog | Público | materials\routes.py:96 |
| GET | /api/v1/materials | Público | materials\routes.py:130 |
| POST | /api/v1/materials | Público | materials\routes.py:160 |
| GET | /api/v1/materials/export | Público | materials\routes.py:186 |
| GET | /api/v1/materials/export/preview | Público | materials\routes.py:236 |
| GET | /api/v1/materials/export/download | Público | materials\routes.py:262 |
| GET | /api/v1/materials/<int:mat_id> | Público | materials\routes.py:304 |
| PUT | /api/v1/materials/<int:mat_id> | Público | materials\routes.py:313 |
| POST | /api/v1/materials/<int:mat_id>/movements | Público | materials\routes.py:335 |
| GET | /api/v1/materials/<int:mat_id>/movements | Público | materials\routes.py:372 |
| GET | /api/v1/technician-profiles | Público | materials\routes.py:381 |
| POST | /api/v1/technician-profiles | Público | materials\routes.py:391 |
| GET | /api/v1/technician-profiles/<int:profile_id> | Público | materials\routes.py:404 |
| PUT | /api/v1/technician-profiles/<int:profile_id> | Público | materials\routes.py:413 |
| POST | /api/v1/materials/transfer | Público | materials\routes.py:427 |
| POST | /api/v1/materials/consume | Público | materials\routes.py:449 |
| GET | /api/v1/technician-stock | Público | materials\routes.py:468 |
| GET | /api/v1/material-requests | Público | materials\routes.py:479 |
| POST | /api/v1/material-requests | Público | materials\routes.py:496 |
| GET | /api/v1/material-requests/<int:req_id> | Público | materials\routes.py:518 |
| PATCH | /api/v1/material-requests/<int:req_id> | Público | materials\routes.py:528 |
| POST | /api/v1/material-requests/<int:req_id>/submit | Público | materials\routes.py:547 |
| POST | /api/v1/material-requests/<int:req_id>/approve | Público | materials\routes.py:565 |
| POST | /api/v1/material-requests/<int:req_id>/reject | Público | materials\routes.py:584 |
| POST | /api/v1/material-requests/<int:req_id>/deliver | Público | materials\routes.py:601 |
| POST | /api/v1/material-requests/<int:req_id>/cancel | Público | materials\routes.py:622 |
| GET | /api/v1/material-requests/<int:req_id>/events | Público | materials\routes.py:639 |
| GET | /api/v1/work-orders/<int:wo_id>/material-requests | Público | materials\routes.py:649 |
| POST | /api/v1/work-orders/<int:wo_id>/materials | Público | materials\routes.py:661 |
| POST | /api/v1/notifications | Público | notifications\routes.py:12 |
| GET | /api/v1/notifications | Público | notifications\routes.py:33 |
| POST | /api/v1/notifications/process | Público | notifications\routes.py:46 |
| GET | /api/v1/settings/organization | Público | settings\routes.py:16 |
| PATCH | /api/v1/settings/organization | Público | settings\routes.py:36 |
| GET | /api/v1/settings/operations | Público | settings\routes.py:59 |
| PATCH | /api/v1/settings/operations | Público | settings\routes.py:68 |
| POST | /api/v1/settings/operations/impact | Público | settings\routes.py:87 |
| GET | /api/v1/settings/security | Público | settings\routes.py:95 |
| PATCH | /api/v1/settings/security | Público | settings\routes.py:111 |
| GET | /api/v1/settings/notifications | Público | settings\routes.py:128 |
| PATCH | /api/v1/settings/notifications | Público | settings\routes.py:138 |
| GET | /api/v1/settings/notifications/me | Público | settings\routes.py:155 |
| PATCH | /api/v1/settings/notifications/me | Público | settings\routes.py:162 |
| GET | /api/v1/settings/public | Público | settings\routes.py:176 |
| GET | /api/v1/audit-log | Público | settings\routes.py:182 |
| GET | /api/v1/audit-log/export.csv | Público | settings\routes.py:233 |
| POST | /api/v1/sync/push | Público | sync\routes.py:9 |
| GET | /api/v1/sync/pull | Público | sync\routes.py:22 |
| GET | /api/v1/technicians | Público | technicians\routes.py:18 |
| GET | /api/v1/technicians/username-available | Público | technicians\routes.py:45 |
| POST | /api/v1/technicians | Público | technicians\routes.py:55 |
| GET | /api/v1/technicians/<int:tid> | Público | technicians\routes.py:77 |
| PATCH | /api/v1/technicians/<int:tid> | Público | technicians\routes.py:89 |
| PATCH | /api/v1/technicians/<int:tid>/availability | Público | technicians\routes.py:105 |
| POST | /api/v1/technicians/<int:tid>/deactivate | Público | technicians\routes.py:124 |
| POST | /api/v1/technicians/<int:tid>/activate | Público | technicians\routes.py:136 |
| POST | /api/v1/technicians/<int:tid>/reset-password | Público | technicians\routes.py:145 |
| POST | /api/v1/technicians/<int:tid>/unlock | Público | technicians\routes.py:154 |
| GET | /api/v1/work-orders | Público | workorders\routes.py:22 |
| POST | /api/v1/work-orders | Público | workorders\routes.py:71 |
| GET | /api/v1/work-orders/<int:wo_id> | Público | workorders\routes.py:83 |
| PATCH | /api/v1/work-orders/<int:wo_id> | Público | workorders\routes.py:96 |
| PUT | /api/v1/work-orders/<int:wo_id> | Público | workorders\routes.py:114 |
| POST | /api/v1/work-orders/<int:wo_id>/status | Público | workorders\routes.py:130 |
| POST | /api/v1/work-orders/<int:wo_id>/transitions | Público | workorders\routes.py:161 |
| POST | /api/v1/work-orders/<int:wo_id>/schedule | Público | workorders\routes.py:202 |
| PATCH | /api/v1/work-orders/<int:wo_id>/schedule | Público | workorders\routes.py:241 |
| POST | /api/v1/work-orders/<int:wo_id>/assignments | Público | workorders\routes.py:282 |
| GET | /api/v1/work-orders/<int:wo_id>/history | Público | workorders\routes.py:305 |
| GET | /api/v1/work-orders/<int:wo_id>/timeline | Público | workorders\routes.py:318 |
| POST | /api/v1/work-orders/bulk | Público | workorders\routes.py:324 |
| GET | /api/v1/work-orders/export.csv | Público | workorders\routes.py:338 |

Ejemplos verificados (health, login, listar órdenes) ver Sección 1.4 y 7.

---

# Anexo B. Historial de cambios (changelog)

## Changelog

Todas las novedades notables de este proyecto se documentan aquí. Formato basado en Keep a Changelog.

### [Sin publicar]

## Added
- Backend Flask con identidad, órdenes, materiales, evidencias, calendario, notificaciones, sincronización offline, dashboard, técnicos, catálogos y configuración (`services/api/`).
- Cliente de escritorio Electron (`apps/desktop/`).
- Cliente móvil Flutter (`apps/mobile/`).
- Migraciones Alembic y seeds (`services/api/migrations/`, `services/api/seeds/`).
- Docker Compose local y de producción (`infra/docker/`).
- CI con GitHub Actions (`.github/workflows/ci.yml`).

## Changed
- [PENDIENTE: detallar cambios por release a partir de tags; no existen tags]

## Fixed
- Correcciones de codificación UTF-8 y validación en calendario (commits `b5ba360`, `b9239ba`, `4f71b62`).
- Ajustes de layout en módulo de evidencias (commits `d6960d0`, `456dc8a`).

## Removed
- [PENDIENTE]


---

# Anexo C. Guía de contribución

## Contribuir — SIGOS 2.0

## Entorno de desarrollo

1. Instalar requisitos (ver `Sección 1`).
2. Backend: crear venv e instalar dependencias:
   ```powershell
   cd services/api
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
3. Crear BD `sigos` y `sigos_test` (ver `Sección 5`).
4. Ejecutar migraciones y seed.

## Ejecutar pruebas

```powershell
cd services/api
.venv\Scripts\python -m pytest tests/ -v

cd ..\..\apps\desktop
npm test

cd ..\mobile
flutter test
```

Linters: [PENDIENTE: no se detectó configuración de linter en el repo].

## Convención de ramas y commits

[PENDIENTE: inferir del historial; los commits usan prefijos `feat`, `fix`, `docs`, `test`, `chore`, `refactor`].

## Pull requests

- Describir cambios y pruebas ejecutadas.
- Asegurar que CI pasa.
- Actualizar documentación afectada (ver `Sección 10` § Proceso de mantenimiento).


---

# Anexo D. Hallazgos, riesgos y pendientes

## D.1 Hallazgos

| ID | Severidad | Descripción | Ubicación | Recomendación |
|---|---|---|---|---|
| H-01 | Media | `.env.example` no declara variables usadas en código (`UPLOAD_DIR`, `EVIDENCE_*`, `SMTP_*`, `WHATSAPP_*`, `LOG_*`, `ENABLE_NOTIFICATION_WORKER`, etc.) | `.env.example` vs `services/api/app/*` | Actualizar `.env.example` |
| H-02 | Alta | Documentación previa de BD listaba 11 tablas; el ORM define 41 | `docs/_archivo/*` vs ORM | Usar las 41 tablas de la Sección 3.1 |
| H-03 | Baja | Identificadores de BD documentados en español; implementación en inglés | `docs/_archivo/database-design.md` | Usar nombres en inglés (código) |
| H-04 | Media | Credenciales de desarrollo en README y código por defecto | `Sección 1`, `services/api/app/config.py` | No versionar secretos; rotar en producción |
| H-05 | Media | `Config` (dev) incluye credenciales por defecto en código | `services/api/app/config.py:11-13` | Exigir `DB_URL`/`JWT_SECRET_KEY` por entorno |
| H-06 | Baja | Tests SQL Server se omiten sin `TEST_DB_URL` | `services/api/tests/conftest.py` | Documentar y ejecutar en CI (ya lo hace) |
| H-07 | Media | Auditoría duplicada: `AuditEvent` y `AuditLog` coexisten | `services/api/app/identity/models.py:57`, `services/api/app/settings/models.py:85` | Documentar diferencia; decidir consolidación |
| H-08 | Baja | Rutas de evidencias solapadas (ámbito orden vs evidencia) | `services/api/app/evidence/routes.py` | Documentar cuál usar; no eliminar sin análisis |
| H-09 | Media | CORS no implementado | `services/api/app/__init__.py` | Riesgo si se expone a navegador |
| H-10 | Baja | Sin medición de cobertura configurada | `services/api/pytest.ini` | Agregar `--cov` |

## D.2 Auditoría duplicada

- `AuditEvent` (`audit_events`): registra acciones de identidad (actor, target, action, changes, created_at). Origen: `services/api/app/identity/models.py:46-68`.
- `AuditLog` (`audit_log`): registra cambios de configuración (section, field, old_value, new_value, result, request_id, username). Origen: `services/api/app/settings/models.py:85-106`.
- Diferencia real: dominios distintos (identidad vs configuración). No se decidió cuál es la correcta; se registra como riesgo.

## D.3 Endpoints de evidencias solapados

Existen rutas con ámbito de orden de trabajo y rutas con ámbito de evidencia individual para operaciones similares (submit, approve, reject, review, correction). Ambas están registradas en `services/api/app/evidence/routes.py` y delegan en `services/api/app/evidence/service.py`. No se eliminaron; se documentan ambas (Anexo A).

## D.4 Variables de entorno faltantes en `.env.example`

`UPLOAD_DIR`, `EVIDENCE_UPLOAD_DIR`, `EVIDENCE_MAX_FILE_SIZE`, `EVIDENCE_ALLOWED_MIME_TYPES`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `WHATSAPP_API_URL`, `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `LOG_LEVEL`, `LOG_FORMAT`, `ENABLE_NOTIFICATION_WORKER`, `NOTIFICATION_WORKER_INTERVAL`, `TEST_DB_URL`, `SERVER_PORT` (ver Sección 5.2).

## D.5 Marcadores `[PENDIENTE]` restantes

Agrupados por sección: justificación de ADRs (Sección 2); versión exacta de Electron; cobertura de tests; comando Playwright; licencia; convención de ramas/commits; CORS; linters; tags/versiones para changelog; política de contraseñas.

## D.6 Preguntas abiertas para el equipo

1. ¿Cuáles son los motivos de los ADRs?
2. ¿Rotar credenciales de desarrollo?
3. ¿Implementar CORS?
4. ¿Medir cobertura y definir umbral?
5. ¿Unificar `AuditEvent`/`AuditLog`?
6. ¿Documentar tags/releases?
7. ¿Ejecutar Playwright en CI?
8. ¿Licencia del proyecto?
9. ¿Convención de commits oficial?
10. ¿Soporte Linux/macOS para desktop?

---
