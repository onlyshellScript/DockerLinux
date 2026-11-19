# Sistema de diseño SIGOS (desktop)

> Fuente única: `apps/desktop/src/renderer/design-system.css` (se carga después de `sigos.css` y `app-sigos.css`)
> Componentes JS: `ui-components.js` (modal, confirmación, texto) · `export-wizard.js` (exportación)
> Sustituye como referencia a `design-tokens.md` (valores aproximados del PDF original).

## 1. Principios

- **Operar, no decorar**: interfaz de trabajo diario; jerarquía y legibilidad antes que expresión.
- **Color con significado**: verde oscuro para navegación, verde medio como acento y acción principal, neutros para
  todo lo demás. Los colores semánticos solo aparecen cuando un estado requiere atención (p. ej. «Alertas stock» > 0,
  materiales en estado bajo o crítico, badges de estado).
- **Un componente por patrón**: un modal, un diálogo de confirmación, un tipo de pestaña, un botón primario.

## 2. Tokens (`:root`)

| Grupo | Tokens |
|---|---|
| Marca | `--c-nav #163028`, `--c-nav-2`, `--c-primary #2E7A50`, `--c-primary-hover`, `--c-primary-soft`, `--c-primary-ring` |
| Neutros | `--c-bg #F7F6F3`, `--c-surface #FFF`, `--c-surface-2`, `--c-hover`, `--c-border`, `--c-border-strong`, `--c-text #1A1F27`, `--c-text-2 #3A4552`, `--c-text-3 #626A77` |
| Estados | `--c-success(-bg)`, `--c-warning(-bg)`, `--c-danger(-bg)`, `--c-info(-bg)`, `--c-neutral(-bg)` |
| Tipografía | `--font-display` Outfit, `--font-body` DM Sans, `--font-mono` JetBrains Mono; `--fs-xs` 11 … `--fs-2xl` 24 |
| Espaciado | `--sp-1` 4 … `--sp-8` 32 (base 4) |
| Forma | `--r-sm` 6, `--r-md` 8, `--r-lg` 12, `--shadow-sm`, `--shadow-md` |
| Controles | `--control-h` 36 px |
| Movimiento | `--dur-fast` 150 ms, `--dur-base` 240 ms, `--ease` |
| Layout | `--sidebar-w` 270, `--sidebar-w-min` 72, `--topbar-h` 56 |

`--c-text-3` está calibrado para ≥ 4,5:1 sobre blanco y sobre `--c-bg` (WCAG AA).

## 3. Componentes

| Componente | Clases / API |
|---|---|
| Botones | `.sigos-btn-primary`, `-secondary`, `-ghost`, `-danger`, modificador `.sigos-btn-sm` |
| Campos | `.sigos-input`, `.sigos-select`, `.fld` (+ `label[for]`), `.fld-hint`, `.fld-error`, `aria-invalid` |
| Tablas | `.tbl`, `.tbl-row`, `.table-scroll` (las tablas anchas se desplazan dentro de su contenedor) |
| Badges | `.badge-*` (estado de orden, prioridad, disponibilidad, rol) |
| Pestañas | `.ds-tabs` + `.ds-tab[aria-selected]` (navegables con flechas) |
| Alertas | `.ds-alert--info/warning/danger/success` |
| Modal | `sigosModal({title, body, footer, size, raw, dismissible, beforeClose, onClose})` → `{card, close, q}` |
| Confirmación | `await confirmDialog(mensaje, {title, confirmLabel, cancelLabel, danger})` → `boolean` |
| Entrada de texto | `await askText(mensaje, {title, multiline, placeholder, required})` → `string \| null` |
| Tooltip | atributo `data-tip` (hover y foco de teclado) |
| Indicadores | `.kpi-strip` › `.kpi-group` › `.kpi-tile` (`.is-alert` solo para valores que requieren atención) |
| Configuración | `.st-group`, `.st-days`, `.st-seg`, `.st-unit`, `.st-actions` |
| Evidencias | `.ev-head`, `.ev-layout`, `.ev-gallery`, `.ev-thumb`, `.ev-timeline`, `openEvidencePreview()` |
| Exportación | `openExportWizard(module, initialParams)`, clases `.xw-*` |

Los modales atrapan el foco, cierran con Escape/fondo/X y devuelven el foco al disparador. Las acciones destructivas
abren la confirmación con el foco en «Cancelar».

## 4. Layout

- **Sidebar** 270/72 px con transición de 240 ms, navegación por categorías (Operación, Inventario, Evidencias, Análisis,
  Sistema), marca del ítem activo y tooltips al estar minimizado. La preferencia se guarda en
  `userData/sigos-ui-prefs.json` (IPC `sigos:prefs:get/set`) con respaldo en `localStorage`.
- **Móvil (< 768 px)**: drawer superpuesto con fondo de cierre y botón ☰; rejillas inline a una columna; acciones del
  header solo con icono.
- **Header**: título y fecha, búsqueda (solo donde está conectada: Materiales), **Exportar**, notificaciones y menú de
  usuario (cambiar contraseña, cerrar sesión).

## 5. Accesibilidad

- Enlace «Saltar al contenido», región `aria-live` que anuncia la pantalla, foco devuelto al menú tras navegar con teclado.
- Todos los campos con etiqueta asociada o `aria-label`; botones con nombre accesible; imágenes con `alt`.
- Objetivos táctiles ≥ 32 px (40 px en móvil); `prefers-reduced-motion` respetado.
- Las vistas asíncronas abandonan su render si el usuario cambió de pantalla durante la carga (`content.isConnected`).

## 6. Verificación

Scripts Playwright usados en la validación (copias de trabajo fuera del repo; el proyecto incluye `tests/visual/validate.js`):
recorrido de las 12 rutas (expandido, minimizado, móvil), auditoría a11y (etiquetas, nombres, `alt`, contraste,
objetivos táctiles, desbordamiento en 1440/820/390 px), diálogos, teclado, Configuración, Bandeja de evidencias,
asistente de exportación y navegación rápida. Resultado al 17/11/2026: 0 hallazgos, 0 errores de consola.

Detector de diseño: `impeccable detect --json <archivos>` → sin hallazgos.
