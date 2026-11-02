# SIGOS — Catálogo de componentes

## 1. Regla de arquitectura
- Electron y Flutter no comparten código visual.
- Comparten criterios visuales: tokens, jerarquía, estados, espaciado y comportamiento.
- Los componentes se implementan según las convenciones de cada plataforma.

## 2. Componentes base requeridos
| Componente | Desktop (Electron) | Mobile (Flutter) | Fuente de verdad |
|---|---|---|---|
| Botón primario | `button.primary` | `ElevatedButton` tematizado | PDF login/dashboard |
| Botón secundario | `button.secondary` | `OutlinedButton` | PDF |
| Campo de texto | `input` | `TextFormField` | Formularios |
| Tarjeta | `card` | `Card` | Dashboard |
| Tabla/lista | `table` / `list` | `ListView` + `DataTable` | Órdenes/materiales |
| Badge de estado | `status-badge` | `Chip` | Estados de orden |
| Alerta | `alert` | `SnackBar` / `AlertDialog` | Errores/validaciones |
| Diálogo | `dialog` | `AlertDialog` | Confirmaciones |
| Navegación lateral | `sidebar` | `Drawer`/`BottomNavigationBar` | Dashboard |
| Barra superior | `topbar` | `AppBar` | Dashboard |
| Indicador de carga | spinner | `CircularProgressIndicator` | API |
| Estado vacío | `empty-state` | widget personalizado | Listas |
| Estado offline | no aplica desktop | banner/widget | Sync móvil |

## 3. Componentes por módulo
- Órdenes: `OrderCard`, `OrderStatusBadge`, `OrderFilterBar`, `OrderTimeline`.
- Técnicos: `TechnicianAvailabilityCard`, `TechnicianSelector`.
- Materiales: `MaterialRow`, `StockBadge`, `MovementForm`.
- Evidencias: `EvidenceThumbnail`, `EvidenceUpload`, `EvidenceViewer`.
- Reportes: `KpiCard`, `ChartPlaceholder`, `ExportButton`.
- Usuarios: `UserForm`, `RoleChip`.

## 4. Pendientes
- Crear componentes reales en las apps solo después de cerrar tokens y layout principal.
- No sustituir funcionalidad real por placeholders.
