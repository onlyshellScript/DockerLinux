# SIGOS — Matriz de trazabilidad

## 1. Convención
`EP → HU → RF/RNF → pantalla/componente → endpoint → prueba`

Los identificadores `EP` y `HU` no están definidos en los documentos revisados; se marcan como pendientes. Los códigos `RF/RNF` provienen de `Proyecto SIGOS.pdf`. Las pantallas usan IDs de `docs/design/screen-inventory.md`. Los endpoints provienen del código y OpenAPI.

## 2. Requerimientos funcionales
| EP | HU | RF/RNF | Pantalla/Componente | Endpoint | Prueba |
|---|---|---|---|---|---|
| Pendiente | Pendiente | RF-01 | S-03 / OrderForm | POST /api/v1/work-orders | tests/test_workorders.py |
| Pendiente | Pendiente | RF-02 | S-04 / OrderEdit | PUT /api/v1/work-orders/{id} | tests/test_workorders.py |
| Pendiente | Pendiente | RF-03 | S-03 / OrderFilterBar | GET /api/v1/work-orders | tests/test_workorders.py |
| Pendiente | Pendiente | RF-04 | S-04 / CancelDialog | POST /api/v1/work-orders/{id}/status | tests/test_workorders.py |
| Pendiente | Pendiente | RF-05 | S-04 / EvidenceUpload | POST /api/v1/work-orders/{id}/evidences | tests/test_evidence.py |
| Pendiente | Pendiente | RF-06 | S-05 / TechnicianSelector | PUT /api/v1/work-orders/{id} | tests/test_workorders.py |
| Pendiente | Pendiente | RF-07 | S-05 / TechnicianSelector | PUT /api/v1/work-orders/{id} | tests/test_workorders.py |
| Pendiente | Pendiente | RF-08 | S-07 / AvailabilityCard | GET /api/v1/technician-profiles | tests/test_materials.py |
| Pendiente | Pendiente | RF-09 | S-06 / ScheduleForm | PUT /api/v1/work-orders/{id} | Pendiente |
| Pendiente | Pendiente | RF-10 | S-06 / CalendarView | GET /api/v1/work-orders | Pendiente |
| Pendiente | Pendiente | RF-11 | S-12 / NotificationItem | POST /api/v1/notifications | tests/test_notifications.py |
| Pendiente | Pendiente | RF-12 | S-04 / StatusChanger | POST /api/v1/work-orders/{id}/status | tests/test_workorders.py |
| Pendiente | Pendiente | RF-13 | S-04 / Timeline | GET /api/v1/work-orders/{id}/history | tests/test_workorders.py |
| Pendiente | Pendiente | RF-14 | S-04 / Timeline | GET /api/v1/work-orders/{id}/history | Pendiente |
| Pendiente | Pendiente | RF-15 | S-08 / MaterialUsageForm | POST /api/v1/materials/{id}/movements | tests/test_materials.py |
| Pendiente | Pendiente | RF-16 | S-08 / StockBadge | POST /api/v1/materials/{id}/movements | tests/test_materials.py |
| Pendiente | Pendiente | RF-17 | S-08 / MaterialList | GET /api/v1/materials | tests/test_materials.py |
| Pendiente | Pendiente | RF-18 | S-12 / AlertBadge | GET /api/v1/materials | Pendiente |
| Pendiente | Pendiente | RF-19 | S-09 / EvidenceUpload | POST /api/v1/work-orders/{id}/evidences | tests/test_evidence.py |
| Pendiente | Pendiente | RF-20 | S-09 / SignatureCapture | Pendiente (no endpoint) | Pendiente |
| Pendiente | Pendiente | RF-21 | S-09 / EvidenceViewer | GET /api/v1/work-orders/{id}/evidences | tests/test_evidence.py |
| Pendiente | Pendiente | RF-22 | S-10 / ReportTable | Pendiente (no endpoint) | Pendiente |
| Pendiente | Pendiente | RF-23 | S-02 / KpiCard | Pendiente (no endpoint) | Pendiente |
| Pendiente | Pendiente | RF-24 | S-10 / ExportButton | Pendiente (no endpoint) | Pendiente |
| Pendiente | Pendiente | RF-25 | S-02 / KpiCard | Pendiente (no endpoint) | Pendiente |
| Pendiente | Pendiente | RF-26 | S-11 / UserForm | GET/POST/PUT /api/v1/users | tests/test_auth.py |
| Pendiente | Pendiente | RF-27 | S-11 / RoleChip | GET/POST/PUT /api/v1/users | tests/test_auth.py |
| Pendiente | Pendiente | RF-28 | S-01 / LoginForm | POST /api/v1/auth/login | tests/test_auth.py |
| Pendiente | Pendiente | RF-29 | S-01 / RecoverPassword | Pendiente (no endpoint) | Pendiente |
| Pendiente | Pendiente | RF-30 | S-12 / NotificationItem | POST /api/v1/notifications | tests/test_notifications.py |

## 3. Requerimientos no funcionales
| EP | HU | RF/RNF | Pantalla/Componente | Endpoint | Prueba |
|---|---|---|---|---|---|
| Pendiente | Pendiente | RNF-01 | Toda la app | Todos | Medición manual |
| Pendiente | Pendiente | RNF-02 | Toda la app | Todos | Pendiente |
| Pendiente | Pendiente | RNF-03 | Toda la app | Health | tests/test_health.py |
| Pendiente | Pendiente | RNF-04 | S-01 | POST /api/v1/auth/login | tests/test_auth.py |
| Pendiente | Pendiente | RNF-05 | Toda la app | Decoradores require_role | tests/test_auth.py |
| Pendiente | Pendiente | RNF-06 | API | Config/DB | Pendiente |
| Pendiente | Pendiente | RNF-07 | API | Auditoría no implementada | Pendiente |
| Pendiente | Pendiente | RNF-08 | UI | Todas | Pendiente |
| Pendiente | Pendiente | RNF-09 | S-13 | Mobile | Pendiente |
| Pendiente | Pendiente | RNF-10 | Arquitectura | Todos | N/A |
| Pendiente | Pendiente | RNF-11 | UI | Todos | Manual |
| Pendiente | Pendiente | RNF-12 | Repo | Docs/tests | N/A |
| Pendiente | Pendiente | RNF-13 | Infra | Backups | Manual |
| Pendiente | Pendiente | RNF-14 | Infra | Backups | Manual |
| Pendiente | Pendiente | RNF-15 | S-10 | Pendiente (no endpoint) | Pendiente |
| Pendiente | Pendiente | RNF-16 | API | Validación sectorial | Pendiente |

## 4. Discrepancias detectadas
- El PDF `Proyecto SIGOS.pdf` repite las filas RF-14 a RF-18 en la matriz de trazabilidad; se documenta la duplicación sin resolverla.
- Algunos requisitos del PDF no tienen endpoint en el código actual (RF-20, RF-22, RF-23, RF-24, RF-25, RF-29).
