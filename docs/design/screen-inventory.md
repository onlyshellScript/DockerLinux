# SIGOS — Inventario de pantallas

## 1. Pantallas actuales en código
| App | Pantalla | Archivo | Estado | Conexión API |
|---|---|---|---|---|
| Desktop | Estado de API | `apps/desktop/src/renderer/index.html` | Implementada | `GET /api/v1/health` |
| Mobile | Estado de API | `apps/mobile/lib/features/health/health_page.dart` | Implementada | `GET /api/v1/health` |
| API | Health | `services/api/app/health/routes.py` | Implementado | DB |

## 2. Pantallas propuestas por la referencia (PDF / Proyecto SIGOS)
Evidencia explícita: PDF "SIGOS ING SW..." páginas 10-13 ("Interfases") y "Proyecto SIGOS.pdf" Fig. 14-15 y matriz de trazabilidad. Los mockups son imágenes; los nombres de pantalla provienen del documento de requerimientos.

| ID | Pantalla | Rol principal | Módulo | Requisitos asociados | Estado en código |
|---|---|---|---|---|---|
| S-01 | Inicio de sesión | Todos | Autenticación | RF-28, RF-29, RNF-04, RNF-05 | Pendiente en UI |
| S-02 | Dashboard principal | Admin/Dispatcher | Reportes/Operación | RF-03, RF-08, RF-10, RF-18, RF-23, RF-25 | Pendiente en UI |
| S-03 | Lista/consulta de órdenes | Operador/Dispatcher | Órdenes | RF-01, RF-02, RF-03, RF-04, RF-05 | Pendiente en UI |
| S-04 | Detalle de orden | Operador/Dispatcher/Técnico | Órdenes | RF-02, RF-04, RF-05, RF-06, RF-07, RF-09, RF-12, RF-13, RF-14 | Pendiente en UI |
| S-05 | Asignación/reasignación de técnicos | Coordinador/Dispatcher | Asignación | RF-06, RF-07, RF-08 | Parcial en API |
| S-06 | Calendario de visitas | Dispatcher/Técnico | Programación | RF-09, RF-10, RF-11 | Pendiente en UI |
| S-07 | Gestión de técnicos/disponibilidad | Admin/Dispatcher | Técnicos | RF-06, RF-07, RF-08 | Parcial en API |
| S-08 | Inventario de materiales | Admin/Dispatcher | Materiales | RF-15, RF-16, RF-17, RF-18 | Parcial en API |
| S-09 | Evidencias por orden | Técnico/Dispatcher | Evidencias | RF-19, RF-20, RF-21 | Parcial en API |
| S-10 | Reportes e indicadores | Admin | Reportes | RF-22, RF-23, RF-24, RF-25 | Pendiente en código |
| S-11 | Gestión de usuarios y roles | Admin | Usuarios | RF-26, RF-27 | Parcial en API |
| S-12 | Notificaciones | Admin/Dispatcher/Técnico | Notificaciones | RF-11, RF-18, RF-30 | Parcial en API |
| S-13 | Vista móvil del técnico | Técnico | Móvil/Offline | RF-12, RF-15, RF-19, RF-20, RF-21, sync | Pendiente en UI |

## 3. Estados de pantalla a cubrir
- Carga.
- Vacío.
- Error de red/API.
- Éxito.
- Sin permisos.
- Offline (solo móvil).

## 4. Notas
- El dashboard de escritorio no debe copiarse mecánicamente en móvil; la app móvil se orienta a tareas del técnico en campo.
- Los nombres de pantallas del PDF son inferencias basadas en la matriz de trazabilidad; los mockups reales son imágenes y no se pudieron leer automáticamente.
