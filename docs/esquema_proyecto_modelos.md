# Esquema de los modelos del proyecto (SQLAlchemy metadata)

Fuente: modelos ORM del proyecto. Tablas en ingles (snake_case).

## Tabla: audit_events

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| actor_id | INTEGER | True |
| target_user_id | INTEGER | True |
| action | VARCHAR(40) | False |
| changes | TEXT | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: actor_id -> users.id, target_user_id -> users.id

---

## Tabla: audit_log

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| created_at | DATETIME | True |
| user_id | INTEGER | True |
| section | VARCHAR(40) | False |
| field | VARCHAR(80) | True |
| old_value | TEXT | True |
| new_value | TEXT | True |
| result | VARCHAR(20) | False |
| request_id | VARCHAR(40) | True |
| username | VARCHAR(80) | True |

PK: ['id']
FKs: user_id -> users.id

---

## Tabla: cities

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| country_id | INTEGER | False |
| department_name | VARCHAR(120) | True |
| dane_code | VARCHAR(5) | False |
| name | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | False |
| active | BOOLEAN | False |

PK: ['id']
FKs: country_id -> countries.id

---

## Tabla: countries

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| iso2 | VARCHAR(2) | False |
| name | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | False |
| active | BOOLEAN | False |

PK: ['id']
FKs: (ninguna)

---

## Tabla: departments

| Columna | Tipo | Nullable |
|---|---|---|
| code | VARCHAR(2) | False |
| name | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | True |

PK: ['code']
FKs: (ninguna)

---

## Tabla: evidence_events

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| work_order_id | INTEGER | True |
| evidence_id | INTEGER | True |
| actor_id | INTEGER | True |
| action | VARCHAR(40) | False |
| from_status | VARCHAR(30) | True |
| to_status | VARCHAR(30) | True |
| details | TEXT | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: actor_id -> users.id, work_order_id -> work_orders.id, evidence_id -> visit_evidences.id

---

## Tabla: evidence_reviews

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| evidence_id | INTEGER | False |
| reviewer_id | INTEGER | False |
| decision | VARCHAR(30) | False |
| notes | TEXT | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: evidence_id -> visit_evidences.id, reviewer_id -> users.id

---

## Tabla: installation_types

| Columna | Tipo | Nullable |
|---|---|---|
| code | VARCHAR(60) | False |
| label | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | False |
| active | BOOLEAN | False |

PK: ['code']
FKs: (ninguna)

---

## Tabla: material_catalog

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| category_id | INTEGER | False |
| code | VARCHAR(40) | False |
| name | VARCHAR(200) | False |
| name_norm | VARCHAR(200) | False |
| unit_id | INTEGER | False |
| measure | VARCHAR(60) | True |
| stage | VARCHAR(60) | True |
| applies_to | VARCHAR(40) | True |
| is_active | BOOLEAN | False |

PK: ['id']
FKs: category_id -> material_categories.id, unit_id -> material_units.id

---

## Tabla: material_categories

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| code | VARCHAR(40) | False |
| name | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | False |
| is_active | BOOLEAN | False |

PK: ['id']
FKs: (ninguna)

---

## Tabla: material_request_deliveries

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| request_id | INTEGER | False |
| actor_id | INTEGER | False |
| operation_id | VARCHAR(36) | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: actor_id -> users.id, request_id -> material_requests.id

---

## Tabla: material_request_delivery_items

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| delivery_id | INTEGER | False |
| request_item_id | INTEGER | False |
| quantity_delivered | FLOAT | False |
| movement_id | INTEGER | True |

PK: ['id']
FKs: movement_id -> stock_movements.id, request_item_id -> material_request_items.id, delivery_id -> material_request_deliveries.id

---

## Tabla: material_request_events

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| request_id | INTEGER | False |
| actor_id | INTEGER | True |
| action | VARCHAR(40) | False |
| from_status | VARCHAR(30) | True |
| to_status | VARCHAR(30) | True |
| payload | TEXT | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: actor_id -> users.id, request_id -> material_requests.id

---

## Tabla: material_request_items

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| request_id | INTEGER | False |
| material_id | INTEGER | False |
| quantity | FLOAT | False |
| quantity_requested | FLOAT | False |
| quantity_approved | FLOAT | False |
| quantity_delivered | FLOAT | False |

PK: ['id']
FKs: material_id -> materials.id, request_id -> material_requests.id

---

## Tabla: material_request_operations

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| operation_id | VARCHAR(36) | False |
| operation_type | VARCHAR(40) | False |
| actor_id | INTEGER | True |
| request_id | INTEGER | True |
| result | TEXT | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: request_id -> material_requests.id, actor_id -> users.id

---

## Tabla: material_requests

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| requester_id | INTEGER | False |
| technician_id | INTEGER | True |
| work_order_id | INTEGER | True |
| status | VARCHAR(30) | False |
| client_operation_id | VARCHAR(36) | True |
| delivered_by_id | INTEGER | True |
| reason | TEXT | True |
| approved_by_id | INTEGER | True |
| approval_reason | TEXT | True |
| created_at | DATETIME | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: delivered_by_id -> users.id, technician_id -> technician_profiles.id, requester_id -> users.id, work_order_id -> work_orders.id, approved_by_id -> users.id

---

## Tabla: material_units

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| code | VARCHAR(20) | False |
| name | VARCHAR(60) | False |
| name_norm | VARCHAR(60) | False |
| allows_decimal | BOOLEAN | False |
| is_active | BOOLEAN | False |

PK: ['id']
FKs: (ninguna)

---

## Tabla: materials

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| name | VARCHAR(120) | False |
| code | VARCHAR(40) | True |
| description | VARCHAR(250) | True |
| unit | VARCHAR(20) | False |
| current_stock | FLOAT | False |
| min_stock | FLOAT | False |
| unit_price | NUMERIC(18, 2) | False |
| is_active | BOOLEAN | False |
| catalog_item_id | INTEGER | True |
| created_at | DATETIME | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: catalog_item_id -> material_catalog.id

---

## Tabla: municipalities

| Columna | Tipo | Nullable |
|---|---|---|
| code | VARCHAR(5) | False |
| name | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | True |
| department_code | VARCHAR(2) | True |

PK: ['code']
FKs: department_code -> departments.code

---

## Tabla: notification_settings

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| preferences | TEXT | False |
| version | INTEGER | False |
| updated_by_id | INTEGER | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: updated_by_id -> users.id

---

## Tabla: notifications

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| user_id | INTEGER | False |
| channel | VARCHAR(15) | False |
| recipient | VARCHAR(250) | False |
| subject | VARCHAR(200) | True |
| message | TEXT | False |
| status | VARCHAR(15) | False |
| retry_count | INTEGER | False |
| error_message | VARCHAR(500) | True |
| created_at | DATETIME | True |
| sent_at | DATETIME | True |

PK: ['id']
FKs: user_id -> users.id

---

## Tabla: operational_settings

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| work_days | VARCHAR(20) | False |
| work_start | VARCHAR(5) | False |
| work_end | VARCHAR(5) | False |
| default_visit_duration | INTEGER | False |
| max_visit_duration | INTEGER | False |
| min_advance_hours | INTEGER | False |
| travel_margin_minutes | INTEGER | False |
| calendar_interval | INTEGER | False |
| stock_critical_threshold | FLOAT | False |
| version | INTEGER | False |
| updated_by_id | INTEGER | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: updated_by_id -> users.id

---

## Tabla: organization_settings

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| company_name | VARCHAR(150) | False |
| nit | VARCHAR(40) | True |
| admin_email | VARCHAR(120) | False |
| contact_phone | VARCHAR(30) | True |
| address | VARCHAR(250) | True |
| city_id | INTEGER | True |
| timezone | VARCHAR(60) | False |
| version | INTEGER | False |
| updated_by_id | INTEGER | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: city_id -> cities.id, updated_by_id -> users.id

---

## Tabla: roles

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| name | VARCHAR(50) | False |
| description | VARCHAR(200) | True |

PK: ['id']
FKs: (ninguna)

---

## Tabla: sectors

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| municipality_code | VARCHAR(5) | True |
| name | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | True |
| kind | VARCHAR(30) | False |
| active | BOOLEAN | False |

PK: ['id']
FKs: municipality_code -> municipalities.code

---

## Tabla: security_settings

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| session_inactivity_minutes | INTEGER | False |
| session_max_hours | INTEGER | False |
| password_min_length | INTEGER | False |
| password_history_count | INTEGER | False |
| lock_attempts | INTEGER | False |
| lock_minutes | INTEGER | False |
| temp_password_validity_days | INTEGER | False |
| version | INTEGER | False |
| updated_by_id | INTEGER | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: updated_by_id -> users.id

---

## Tabla: specialties

| Columna | Tipo | Nullable |
|---|---|---|
| code | VARCHAR(60) | False |
| label | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | False |
| active | BOOLEAN | False |

PK: ['code']
FKs: (ninguna)

---

## Tabla: stock_movements

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| material_id | INTEGER | False |
| quantity | FLOAT | False |
| quantity_requested | FLOAT | False |
| quantity_approved | FLOAT | False |
| quantity_delivered | FLOAT | False |
| movement_type | VARCHAR(15) | False |
| work_order_id | INTEGER | True |
| user_id | INTEGER | False |
| notes | VARCHAR(250) | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: work_order_id -> work_orders.id, material_id -> materials.id, user_id -> users.id

---

## Tabla: sync_operations

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| client_operation_id | VARCHAR(36) | False |
| operation_type | VARCHAR(50) | False |
| payload | TEXT | False |
| user_id | INTEGER | False |
| status | VARCHAR(15) | False |
| result | TEXT | True |
| created_at | DATETIME | True |
| synced_at | DATETIME | True |

PK: ['id']
FKs: user_id -> users.id

---

## Tabla: technician_profiles

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| user_id | INTEGER | False |
| first_name | VARCHAR(80) | True |
| last_name | VARCHAR(80) | True |
| phone | VARCHAR(30) | True |
| email | VARCHAR(120) | True |
| specialty | VARCHAR(80) | True |
| specialty_code | VARCHAR(60) | True |
| legacy_zone | VARCHAR(250) | True |
| document_type | VARCHAR(20) | True |
| document_number | VARCHAR(40) | True |
| document | VARCHAR(40) | True |
| is_available | BOOLEAN | False |
| is_active | BOOLEAN | False |
| open_orders | INTEGER | False |
| created_by_id | INTEGER | True |
| created_at | DATETIME | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: specialty_code -> specialties.code, user_id -> users.id, created_by_id -> users.id

---

## Tabla: technician_stock

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| technician_id | INTEGER | False |
| material_id | INTEGER | False |
| quantity | FLOAT | False |
| updated_at | DATETIME | True |

PK: ['id']
FKs: technician_id -> technician_profiles.id, material_id -> materials.id

---

## Tabla: technician_zones

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| technician_id | INTEGER | False |
| city_id | INTEGER | False |
| zone_id | INTEGER | True |
| is_primary | BOOLEAN | False |

PK: ['id']
FKs: technician_id -> technician_profiles.id, city_id -> cities.id, zone_id -> zones.id

---

## Tabla: user_notification_preferences

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| user_id | INTEGER | False |
| preferences | TEXT | False |
| version | INTEGER | False |
| updated_at | DATETIME | True |

PK: ['id']
FKs: user_id -> users.id

---

## Tabla: user_roles

| Columna | Tipo | Nullable |
|---|---|---|
| user_id | INTEGER | False |
| role_id | INTEGER | False |

PK: ['user_id', 'role_id']
FKs: user_id -> users.id, role_id -> roles.id

---

## Tabla: users

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| username | VARCHAR(80) | False |
| email | VARCHAR(120) | False |
| password_hash | VARCHAR(256) | False |
| is_active | BOOLEAN | False |
| must_change_password | BOOLEAN | False |
| password_changed_at | DATETIME | True |
| failed_attempts | INTEGER | False |
| locked_until | DATETIME | True |
| last_login | DATETIME | True |
| created_at | DATETIME | True |
| updated_at | DATETIME | True |

PK: ['id']
FKs: (ninguna)

---

## Tabla: visit_checklist_items

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| work_order_id | INTEGER | False |
| label | VARCHAR(250) | False |
| result | VARCHAR(30) | True |
| notes | TEXT | True |
| checked_by_id | INTEGER | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: work_order_id -> work_orders.id, checked_by_id -> users.id

---

## Tabla: visit_evidences

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| work_order_id | INTEGER | False |
| category | VARCHAR(20) | False |
| original_name | VARCHAR(250) | True |
| storage_key | VARCHAR(120) | True |
| mime_type | VARCHAR(100) | True |
| size_bytes | INTEGER | True |
| sha256 | VARCHAR(64) | True |
| declared_capture_at | DATETIME | True |
| received_at | DATETIME | True |
| uploaded_by_id | INTEGER | False |
| description | TEXT | True |
| status | VARCHAR(30) | False |
| previous_evidence_id | INTEGER | True |
| version_number | INTEGER | False |
| duplicate_of_id | INTEGER | True |
| client_operation_id | VARCHAR(36) | True |
| file_name | VARCHAR(250) | True |
| stored_name | VARCHAR(250) | True |
| file_type | VARCHAR(50) | True |
| file_size | INTEGER | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: previous_evidence_id -> visit_evidences.id, work_order_id -> work_orders.id, duplicate_of_id -> visit_evidences.id, uploaded_by_id -> users.id

---

## Tabla: visit_signatures

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| work_order_id | INTEGER | False |
| storage_key | VARCHAR(120) | True |
| signer_name | VARCHAR(120) | True |
| signer_role | VARCHAR(120) | True |
| received_at | DATETIME | True |
| acceptance_text | TEXT | True |
| consent_version | VARCHAR(40) | True |
| technician_id | INTEGER | True |
| refused | BOOLEAN | False |
| refusal_reason | TEXT | True |
| client_operation_id | VARCHAR(36) | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: work_order_id -> work_orders.id, technician_id -> users.id

---

## Tabla: work_order_status_history

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| work_order_id | INTEGER | False |
| from_status | VARCHAR(20) | False |
| to_status | VARCHAR(20) | False |
| changed_by_id | INTEGER | False |
| notes | TEXT | True |
| created_at | DATETIME | True |

PK: ['id']
FKs: changed_by_id -> users.id, work_order_id -> work_orders.id

---

## Tabla: work_orders

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| title | VARCHAR(200) | False |
| description | TEXT | True |
| status | VARCHAR(20) | False |
| priority | VARCHAR(10) | False |
| customer_name | VARCHAR(120) | True |
| customer_phone | VARCHAR(30) | True |
| address | VARCHAR(250) | True |
| zone | VARCHAR(60) | True |
| legacy_zone | VARCHAR(60) | True |
| city_id | INTEGER | True |
| zone_id | INTEGER | True |
| installation_type | VARCHAR(80) | True |
| installation_type_code | VARCHAR(60) | True |
| scheduled_at | DATETIME | True |
| scheduled_end | DATETIME | True |
| schedule_notes | TEXT | True |
| version | INTEGER | False |
| cancel_reason | TEXT | True |
| assigned_to_id | INTEGER | True |
| created_by_id | INTEGER | False |
| created_at | DATETIME | True |
| updated_at | DATETIME | True |
| completed_at | DATETIME | True |

PK: ['id']
FKs: created_by_id -> users.id, installation_type_code -> installation_types.code, city_id -> cities.id, assigned_to_id -> users.id, zone_id -> zones.id

---

## Tabla: zones

| Columna | Tipo | Nullable |
|---|---|---|
| id | INTEGER | False |
| city_id | INTEGER | False |
| kind | VARCHAR(30) | False |
| name | VARCHAR(120) | False |
| name_norm | VARCHAR(120) | False |
| active | BOOLEAN | False |

PK: ['id']
FKs: city_id -> cities.id

---
