# SIGOS — Design tokens

## 1. Fuente de referencia
- Referencia visual: PDF `SIGOS ING SW IIIIII-comprimido.pdf`, páginas de interfaces (10-13) y dashboard/login (Fig. 14-15 en `Proyecto SIGOS.pdf`).
- Los valores de color son aproximaciones extraídas de imágenes y del PDF (`0.098 0.42 0.141`). No son tokens oficiales de Figma; no se encontró archivo editable accesible.

## 2. Colores semánticos (aproximados)
| Token | Hex | RGB | Uso |
|---|---|---|---|
| `color-primary-dark` | `#103020` | `16,48,32` | Header, navegación, títulos principales |
| `color-primary` | `#207050` | `32,112,80` | Botones primarios, acentos |
| `color-primary-soft` | `#206040` | `32,96,64` | Hover/estados activos |
| `color-background` | `#F0F0E0` | `240,240,224` | Fondo general |
| `color-surface` | `#FFFFFF` | `255,255,255` | Tarjetas, paneles |
| `color-surface-muted` | `#F0F0F0` | `240,240,240` | Fondos secundarios |
| `color-border` | `#D0D0D0` | `208,208,208` | Bordes |
| `color-text` | `#1F2937` | `31,41,55` | Texto principal |
| `color-text-muted` | `#374151` | `55,65,81` | Texto secundario |
| `color-success` | `#166534` | `22,101,52` | Estados exitosos |
| `color-warning` | `#F0B050` | `240,176,80` | Alertas bajo stock |
| `color-danger` | `#991B1B` | `153,27,27` | Errores/cancelación |
| `color-info` | `#2563EB` | `37,99,235` | Enlaces/acciones secundarias |

## 3. Tipografía
- Familia base desktop: `"Segoe UI", system-ui, sans-serif` (actual).
- Familia base móvil: Material default (Roboto) hasta definir fuente corporativa.
- Escala sugerida: 12 / 14 / 16 / 20 / 24 / 28 / 32.
- Pesos: 400 regular, 600 semibold, 700 bold.
- No se identificó fuente oficial en el PDF; valores pendientes de confirmación.

## 4. Espaciado
- Base: 4px.
- Escala: 4, 8, 12, 16, 24, 32, 48.
- Márgenes de contenedor: 16 móvil, 24 tablet, 32 desktop.

## 5. Radios, bordes y elevación
- Radio pequeño: 6px.
- Radio estándar: 8px.
- Radio tarjeta: 12px.
- Borde estándar: 1px `color-border`.
- Elevación baja: `0 2px 8px rgba(0,0,0,0.06)`.
- Elevación media: `0 8px 24px rgba(0,0,0,0.08)`.

## 6. Estados
- `up`: fondo `#E7F7EE`, texto `#166534`.
- `down`: fondo `#FDE8E8`, texto `#991B1B`.
- `unknown`: fondo `#EEF2F7`, texto `#374151`.
- Prioridad: `low`, `medium`, `high`.
- Estados de orden: `pending`, `assigned`, `in_progress`, `completed`, `closed`, `cancelled`.

## 7. Iconografía
- Desktop: preferir iconos SVG o fuente de iconos ya disponible; no añadir dependencias sin justificación.
- Mobile: Material Icons (ya disponible por Flutter).
- Iconos mínimos: dashboard, órdenes, técnicos, calendario, inventario, evidencias, reportes, usuarios, notificaciones, sync, logout.

## 8. Pendientes
- Confirmar fuente corporativa y tamaños exactos con Figma si se obtiene acceso.
- Validar contraste WCAG para todos los pares de color.
