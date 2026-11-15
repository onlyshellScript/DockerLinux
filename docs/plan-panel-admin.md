## Estado de implementación (Fase A)
- A1: implementado (admin edita con motivo, If-Match, timeline/audit, notificación).
- A2: implementado (domingos/festivos con autorización admin; tarjetas UI pendiente).
- A3: implementado (exportación xlsx/pdf y KPIs existentes; UI reportes pendiente).
- A4: pendiente (solo UI, sin cambios de API).
- A5: en progreso.

## 0. Resumen (≤25 líneas)
SIGOS ya tiene la mayoría de los campos necesarios; faltan estados de usuario, segundo nombre/apellido y centro de costo/puesto, que conviene resolver sin migración cuando sea posible o con una migración mínima si se confirma el alcance. El bloqueo principal es el modelo de permisos: admin es solo lectura en workorders (RNF-05, `test_admin_cannot_create_work_order`, `ACCESS_RULES`). Se propone edición admin con motivo obligatorio e historial, más endpoints de usuarios (suspender/deshabilitar/eliminar lógico) y reportes (exportación xlsx/pdf y KPIs). Calendario y evidencias se resuelven con cambios de UI/API acotados. No se altera el esquema salvo decisión explícita en DECISIONES PENDIENTES.

## a) Campos existentes vs faltantes

### WorkOrder (`services/api/app/workorders/models.py:30-95`)
- Ya existen: `installation_type`, `installation_type_code`, `assigned_to_id`, `scheduled_at`, `scheduled_end`, `schedule_notes`, `version`, `materials` vía `POST /work-orders/{id}/materials`.
- Falta: motivo de edición administrativa (reusar `AuditLog` o `WorkOrderStatusHistory`).
- Sin migración: guardar motivo en `AuditLog` (`services/api/app/settings/models.py`).

### TechnicianProfile (`services/api/app/materials/models.py:175-231`)
- Ya existen: `first_name`, `last_name`, `specialty`, `specialty_code`, `document_type`, `document_number`, `document`, `is_available`, `is_active`, cobertura por ciudad/zona.
- Faltan: segundo nombre, segundo apellido, centro de costo, puesto.
- Sin migración: concatenar en `first_name`/`last_name` (degrada datos) o guardar en `legacy_zone`/`email` (no recomendado). Opción recomendada: migración mínima de 4 columnas o reutilizar `specialty`/`phone` (no recomendado).

### User (`services/api/app/identity/models.py:10-78`)
- Ya existen: `username`, `email`, `is_active`, `must_change_password`, `locked_until`, `failed_attempts`.
- Faltan: estado explícito (suspendido/deshabilitado/eliminado lógico) y motivo.
- Sin migración: `is_active=False` (deshabilitado), `locked_until` futuro (suspendido), username prefijado `deleted_` (eliminado lógico, frágil).
- Recomendado: migración con columna `status` + `deleted_at` (o reusar `locked_until` + `is_active` si se acepta ambigüedad).

### Notificaciones (`services/api/app/notifications/models.py:1-50`)
- Ya existen: `user_id`, `subject`, `message`, `status`, `is_read`.
- Falta: tipo de autorización (solo convención en `subject`/`message`).

## b) Conflicto de permisos (admin solo lectura)
- Evidencia: `test_admin_cannot_create_work_order`, `ACCESS_RULES` (`dashboard.dashboard_summary: admin, dispatcher`), RNF-05, rutas `workorders` (`require_role("dispatcher")` en create/put).
- Propuesta: nuevo permiso "admin_editor" restringido a edición (no creación) con motivo obligatorio (`reason`) y registro en `AuditLog`/historial.
- Tests que cambian: `test_admin_cannot_create_work_order` se mantiene (creación sigue solo dispatcher); añadir `test_admin_can_edit_work_order_with_reason` y `test_admin_edit_without_reason_returns_422`.
- Reglas: `require_role("admin", "dispatcher")` en PATCH/PUT de workorder, pero el servicio exige `reason` si el rol es admin; admin no puede cambiar estado a `cancelled` ni asignar sin motivo.

## c) Estados de usuario
- Integración con S5: `require_auth`/`require_role` ya verifican existencia y `is_active` (`services/api/app/identity/decorators.py`).
- Propuesta de estados: `active`, `suspended`, `disabled`, `deleted` (lógico).
- Mapeo sin migración: `active=is_active True y locked_until None`; `suspended=locked_until futuro`; `disabled=is_active False`; `deleted=is_active False + username prefijado` (frágil).
- Sync: `pull_changes` y `change_status` ya validan usuario activo; añadir rechazo si estado != active.

## d) Autorización de domingos
- Mecanismo: `calendar/service.py` valida días laborales (`work_days`) y horario. Para domingo, si el solicitante no es admin, crear `Notification` para admin con `subject="Autorización domingo"` y devolver `403` + código `sunday_authorization_required`.
- Admin puede aprobar con endpoint `POST /api/v1/calendar/authorize-sunday` (nuevo) o reenviar la misma solicitud con `authorize_sunday=true` (solo admin).
- Festivos: no hay calendario de festivos en el código; opción sin migración: lista estática en settings/config o JSON; opción recomendada: tabla de festivos (migración) o JSON estático en `seeds/`.

## e) Selector departamento/municipio
- Ya existen `Department`/`Municipality` y endpoints `/catalogs/departments`, `/catalogs/municipalities?department=XX` (`services/api/app/catalogs/routes.py:162-175`).
- Frontend: dropdown dependiente (departamento -> municipio) consumiendo esos endpoints.
- Guardado sin migración: usar `TechnicianProfile.legacy_zone` (string "DEP-MUN") o cobertura existente (`TechnicianZone` city/zone). Recomendado: cobertura existente; `legacy_zone` solo como fallback.

## f) Endpoints nuevos o modificados
- `PATCH/PUT /api/v1/work-orders/{id}` (admin o dispatcher): edición con `reason` obligatorio para admin.
- `POST /api/v1/work-orders/{id}/materials` (ya existe): admin puede usarlo.
- `GET/POST/PUT /api/v1/technician-profiles` (ya existen): añadir campos si se migra; sin migración, reusar existentes.
- `GET /catalogs/departments`, `GET /catalogs/municipalities` (ya existen).
- `GET/POST/PATCH /api/v1/users` (ya existen): añadir `suspend`, `disable`, `delete` (lógico) y `GET /users/{id}` con datos.
- `GET /api/v1/reportes/ordenes?formato=xlsx|pdf`: implementar exportación (hoy 501).
- `GET /api/v1/dashboard/summary` o nuevo `/dashboard/kpis`: RF-23/RF-25.
- `POST /api/v1/calendar/authorize-sunday`: nuevo (admin).
- `POST /api/v1/work-orders/{id}/evidences`: sin cambios de API (solo UI).

## g) Orden de implementación (test-first)
1. Permisos admin edición (tests + rutas + motivo/historial). Riesgo: romper RNF-05; mitigar con tests de regresión.
2. Estados de usuario (tests + validación S5 + sync). Riesgo: migración; decidir primero.
3. Técnicos (campos + selector dinámico + clave inicial por env). Riesgo: datos parciales; usar campos existentes primero.
4. Calendario (domingos + festivos + notificación). Riesgo: lógica de días; tests de borde.
5. Reportes (exportación + KPIs). Riesgo: dependencias openpyxl/reportlab ya instaladas.
6. Evidencias UI (sin API).
7. Usuarios (suspender/deshabilitar/eliminar + detalle).

Esfuerzo estimado: 2-3 semanas, tests primero en cada fase.

## h) DECISIONES PENDIENTES
1. ¿Agregar columnas de segundo nombre/apellido, centro de costo y puesto a TechnicianProfile o reusar campos existentes? Recomendado: migración mínima si se confirma el alcance; si no, reusar `specialty`/`legacy_zone` (no recomendado).
2. ¿Estados de usuario requieren columna `status` o se reutilizan `is_active`/`locked_until`? Recomendado: columna `status` (claridad y auditoría).
3. ¿Festivos se gestionan con JSON estático o tabla? Recomendado: JSON estático primero, migración después si se necesita administración.
4. ¿La autorización de domingos es manual por admin (notificación) o automática con rol? Recomendado: notificación + aprobación admin (trazabilidad).
5. ¿Admin puede editar cualquier orden o solo las asignadas? Recomendado: cualquier orden con motivo obligatorio e historial.