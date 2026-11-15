# SIGOS — Matriz de trazabilidad

## 0. Alcance del MVP (SUPUESTO — pendiente de confirmación del usuario)

No existe en la documentación revisada una definición explícita de MVP. Se propone el siguiente alcance
como **supuesto**; los RF/RNF marcados "MVP (supuesto)" siguen esta lista y deben confirmarse:

**MVP (supuesto):** flujo operativo mínimo de órdenes de trabajo para admin/dispatcher/técnico:
creación, edición, listado/filtrado, cancelación, asignación/reasignación, programación, cambio de estado,
historial/timeline, evidencias (carga, listado, descarga, firma digital se excluye), materiales y stock,
usuarios y roles, login/refresh, notificaciones, y RNF de salud, autenticación y autorización.

**Post-MVP:** disponibilidad avanzada, alertas de stock, reportes/exportación, KPIs/dashboard, firma digital,
recuperación de contraseña, offline móvil, rendimiento/UX documentados, backups y auditoría.

## 1. Convención
`EP → HU → RF/RNF → pantalla/componente → endpoint → módulo/archivo → prueba → estado → defectos conocidos`

Los identificadores `EP` y `HU` no están definidos en los documentos revisados; se marcan como pendientes.
Los códigos `RF/RNF` provienen de `Proyecto SIGOS.pdf`. Las pantallas usan IDs de `docs/design/screen-inventory.md`.
Los endpoints y módulos provienen del código actual (Flask). Las pruebas citan `tests/<archivo>::<test>` cuando existe
una prueba identificable; si no se identificó prueba dedicada se marca "Pendiente".
La columna "Defectos conocidos" referencia IDs del informe de hallazgos (seguridad/funcionales) cuando aplican;
"—" indica que no se identificó defecto conocido para ese requisito.

**Suite de regresión (Fase 2):** 257 passed, 10 skipped, 0 failed.

## 2. Requerimientos funcionales

| EP | HU | RF/RNF | Alcance | Pantalla/Componente | Endpoint (método + ruta) | Módulo/Archivo (línea) | Prueba (archivo::test) | Estado | Defectos conocidos |
|---|---|---|---|---|---|---|---|---|---|
| Pendiente | Pendiente | RF-01 | MVP (supuesto) | S-03 / OrderForm | POST /api/v1/work-orders | services/api/app/workorders/routes.py:72 | tests/test_workorders.py::test_create_work_order | Implementado | — |
| Pendiente | Pendiente | RF-02 | MVP (supuesto) | S-04 / OrderEdit | PATCH/PUT /api/v1/work-orders/{id} | services/api/app/workorders/routes.py:97,118 | tests/test_workorders.py::test_work_order_edit_patch_and_put | Implementado | — |
| Pendiente | Pendiente | RF-03 | MVP (supuesto) | S-03 / OrderFilterBar | GET /api/v1/work-orders | services/api/app/workorders/routes.py:23 | tests/test_workorders.py::test_work_orders_list_filters_and_pagination | Implementado | F5 |
| Pendiente | Pendiente | RF-04 | MVP (supuesto) | S-04 / CancelDialog | POST /api/v1/work-orders/{id}/status | services/api/app/workorders/routes.py:134 | tests/test_rf04_rf13_rf14.py::test_rf04_cancelar_exige_motivo | Implementado | — |
| Pendiente | Pendiente | RF-05 | MVP (supuesto) | S-04 / EvidenceUpload | POST /api/v1/work-orders/{id}/evidences | services/api/app/evidence/routes.py:68 | tests/test_evidence.py::test_upload_observation | Implementado | — |
| Pendiente | Pendiente | RF-06 | MVP (supuesto) | S-05 / TechnicianSelector | PUT /api/v1/work-orders/{id} | services/api/app/workorders/routes.py:118 | tests/test_workorders.py::test_assign_and_transition | Implementado | — |
| Pendiente | Pendiente | RF-07 | MVP (supuesto) | S-05 / TechnicianSelector | POST /api/v1/work-orders/{id}/assignments | services/api/app/workorders/routes.py:288 | tests/test_workorders.py::test_assign_and_transition | Implementado | — |
| Pendiente | Pendiente | RF-08 | Post-MVP | S-07 / AvailabilityCard | GET /api/v1/technician-profiles | services/api/app/materials/routes.py:381 | tests/test_materials.py::test_technician_profile | Implementado | — |
| Pendiente | Pendiente | RF-09 | MVP (supuesto) | S-06 / ScheduleForm | POST/PATCH /api/v1/work-orders/{id}/schedule | services/api/app/workorders/routes.py:208,247 | tests/test_rf09_calendar.py::test_rf09_rechaza_solape_horario | Implementado | — |
| Pendiente | Pendiente | RF-10 | MVP (supuesto) | S-06 / CalendarView | GET /api/v1/work-orders | services/api/app/workorders/routes.py:23 | tests/test_workorders.py::test_work_orders_calendar_range_and_empty_technician | Implementado | F5 |
| Pendiente | Pendiente | RF-11 | MVP (supuesto) | S-12 / NotificationItem | POST /api/v1/notifications | services/api/app/notifications/routes.py:12 | tests/test_notifications.py::test_create_notification | Implementado | — |
| Pendiente | Pendiente | RF-12 | MVP (supuesto) | S-04 / StatusChanger | POST /api/v1/work-orders/{id}/status | services/api/app/workorders/routes.py:134 | tests/test_workorders.py::test_assign_and_transition | Implementado | S7 |
| Pendiente | Pendiente | RF-13 | MVP (supuesto) | S-04 / Timeline | GET /api/v1/work-orders/{id}/history | services/api/app/workorders/routes.py:338 | tests/test_rf04_rf13_rf14.py::test_rf13_historial_por_transicion | Implementado | — |
| Pendiente | Pendiente | RF-14 | MVP (supuesto) | S-04 / Timeline | GET /api/v1/work-orders/{id}/timeline | services/api/app/workorders/routes.py:351 | tests/test_rf04_rf13_rf14.py::test_rf14_timeline_cronologico | Implementado | — |
| Pendiente | Pendiente | RF-15 | MVP (supuesto) | S-08 / MaterialUsageForm | POST /api/v1/work-orders/{id}/materials | services/api/app/workorders/routes.py:311 | tests/test_rf15_rf16_materiales.py::test_rf15_asociacion_orden_material | Implementado | — |
| Pendiente | Pendiente | RF-16 | MVP (supuesto) | S-08 / StockBadge | POST /api/v1/materials/{id}/movements | services/api/app/materials/routes.py:335 | tests/test_rf15_rf16_materiales.py::test_rf16_descuenta_stock_y_movimiento | Implementado | S19, F3 |
| Pendiente | Pendiente | RF-17 | MVP (supuesto) | S-08 / MaterialList | GET /api/v1/materials | services/api/app/materials/routes.py:130 | tests/test_materials.py::test_create_material | Implementado | — |
| Pendiente | Pendiente | RF-18 | Post-MVP | S-12 / AlertBadge | GET /api/v1/materials | services/api/app/materials/routes.py:130 | Pendiente (sin test dedicado a alertas de stock) | Parcial | — |
| Pendiente | Pendiente | RF-19 | MVP (supuesto) | S-09 / EvidenceUpload | POST /api/v1/work-orders/{id}/evidences | services/api/app/evidence/routes.py:68 | tests/test_evidence.py::test_upload_photo | Implementado | — |
| Pendiente | Pendiente | RF-20 | Post-MVP | S-09 / SignatureCapture | POST /api/v1/work-orders/{id}/signatures | services/api/app/evidence/routes.py:268 | tests/test_evidence.py::test_signature_refusal_and_submit | Implementado | — |
| Pendiente | Pendiente | RF-21 | MVP (supuesto) | S-09 / EvidenceViewer | GET /api/v1/work-orders/{id}/evidences | services/api/app/evidence/routes.py:112 | tests/test_evidence.py::test_list_evidences | Implementado | — |
| Pendiente | Pendiente | RF-22 | Post-MVP | S-10 / ReportTable | GET /api/v1/reportes/ordenes | services/api/app/reportes/routes.py:10 | tests/test_rf22_reportes.py::test_rf22_admin_ok | Implementado | — |
| Pendiente | Pendiente | RF-23 | Post-MVP | S-02 / KpiCard | Pendiente (no endpoint) | Pendiente (sin módulo) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RF-24 | Post-MVP | S-10 / ExportButton | GET /api/v1/reportes/ordenes?formato=xlsx\|pdf | services/api/app/reportes/routes.py:42 | tests/test_export_extra.py::test_pdf_bytestream_valid | Parcial (devuelve 501 "no implementado") | — |
| Pendiente | Pendiente | RF-25 | Post-MVP | S-02 / KpiCard | Pendiente (no endpoint) | Pendiente (sin módulo) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RF-26 | MVP (supuesto) | S-11 / UserForm | GET/POST/PUT /api/v1/users | services/api/app/identity/routes.py:46,53,75 | tests/test_auth.py::test_create_user | Implementado | — |
| Pendiente | Pendiente | RF-27 | MVP (supuesto) | S-11 / RoleChip | GET/POST/PUT /api/v1/users | services/api/app/identity/routes.py:46,53,75 | tests/test_auth.py::test_users_list_requires_admin | Implementado | — |
| Pendiente | Pendiente | RF-28 | MVP (supuesto) | S-01 / LoginForm | POST /api/v1/auth/login | services/api/app/identity/routes.py:10 | tests/test_auth.py::test_login_success | Implementado | — |
| Pendiente | Pendiente | RF-29 | Post-MVP | S-01 / RecoverPassword | Pendiente (no endpoint) | Pendiente (sin módulo) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RF-30 | MVP (supuesto) | S-12 / NotificationItem | POST /api/v1/notifications | services/api/app/notifications/routes.py:12 | tests/test_notifications.py::test_create_notification | Implementado | — |

## 3. Requerimientos no funcionales

| EP | HU | RF/RNF | Alcance | Pantalla/Componente | Endpoint | Módulo/Archivo (línea) | Prueba (archivo::test) | Estado | Defectos conocidos |
|---|---|---|---|---|---|---|---|---|---|
| Pendiente | Pendiente | RNF-01 | Post-MVP | Toda la app | Todos | services/api/app/* (sin medición automatizada) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RNF-02 | Post-MVP | Toda la app | Todos | services/api/app/* (sin medición automatizada) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RNF-03 | MVP (supuesto) | Toda la app | GET /api/v1/health | services/api/app/health/routes.py (servicio: services/api/app/health/service.py:4) | tests/test_health.py::test_health_ok | Implementado | — |
| Pendiente | Pendiente | RNF-04 | MVP (supuesto) | S-01 | POST /api/v1/auth/login | services/api/app/identity/routes.py:10 | tests/test_rnf04_security.py::test_rnf04_login_rate_limit | Implementado | — |
| Pendiente | Pendiente | RNF-05 | MVP (supuesto) | Toda la app (nota: admin es rol de solo lectura en workorders; mutaciones exigen dispatcher o técnico asignado) | Decoradores require_role | services/api/app/identity/decorators.py:1 | tests/test_rnf05_access_rules.py::test_rnf05_admin_can_list_users; tests/test_workorders.py::test_admin_cannot_create_work_order | Implementado | — |
| Pendiente | Pendiente | RNF-06 | Post-MVP | API | Config/DB | services/api/app/config.py:14 | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RNF-07 | Post-MVP | API | Auditoría no implementada | Pendiente (sin módulo) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RNF-08 | Post-MVP | UI | Todas | apps/desktop, apps/mobile (sin auditoría automatizada) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RNF-09 | Post-MVP | S-13 | Mobile | apps/mobile/lib/core/sync/sync_service.dart:15 | Pendiente (sin test de integración) | Parcial | — |
| Pendiente | Pendiente | RNF-10 | Post-MVP | Arquitectura | Todos | services/api/app/__init__.py:23-63 | N/A | N/A | — |
| Pendiente | Pendiente | RNF-11 | Post-MVP | UI | Todos | apps/desktop, apps/mobile (manual) | Manual | Pendiente | — |
| Pendiente | Pendiente | RNF-12 | Post-MVP | Repo | Docs/tests | docs/, services/api/tests (sin métrica de cobertura) | Pendiente | Pendiente | — |
| Pendiente | Pendiente | RNF-13 | Post-MVP | Infra | Backups | scripts/backup-db.ps1, scripts/backup-uploads.ps1 | Manual | Pendiente | — |
| Pendiente | Pendiente | RNF-14 | Post-MVP | Infra | Backups | scripts/backup_sqlite.py:22 | Manual | Pendiente | — |
| Pendiente | Pendiente | RNF-15 | Post-MVP | S-10 | Pendiente (no endpoint) | services/api/app/reportes/routes.py:42 | Pendiente | Parcial (exportación 501) | — |
| Pendiente | Pendiente | RNF-16 | Post-MVP | API | Validación sectorial | services/api/app/* (sin validación sectorial implementada) | Pendiente | Pendiente | — |

## 4. Discrepancias detectadas
- El PDF `Proyecto SIGOS.pdf` repite las filas RF-14 a RF-18 en la matriz de trazabilidad; se documenta la duplicación sin resolverla.
- Algunos requisitos del PDF no tienen endpoint en el código actual (RF-23, RF-25, RF-29).
- La exportación xlsx/pdf (RF-24) existe como ruta pero responde 501 (fuera de alcance).

## 5. Brechas del MVP (RF/RNF parciales o pendientes)

Ordenadas por impacto (mayor a menor):

1. **RF-24 — Exportación xlsx/pdf** (Parcial, Post-MVP): la ruta existe pero responde 501.  
   Evidencia: `services/api/app/reportes/routes.py:42`.
2. **RNF-09 — Offline móvil** (Parcial, Post-MVP): `SyncService` implementado pero no integrado en la UI móvil.  
   Evidencia: `apps/mobile/lib/core/sync/sync_service.dart:15`.

RF-02, RF-03 y RF-10 pasaron a "Implementado" tras añadir pruebas dedicadas en
`tests/test_workorders.py` (`test_work_order_edit_patch_and_put`,
`test_work_orders_list_filters_and_pagination`,
`test_work_orders_calendar_range_and_empty_technician`), todas en verde.
No hay RF/RNF del MVP marcados como "Pendiente" sin endpoint.

Suite de regresión (Fase 2): 257 passed, 10 skipped, 0 failed.
