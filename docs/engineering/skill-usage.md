# SIGOS — Uso de skills y herramientas

## 1. Skills disponibles relevantes
- `architect`: diseño técnico y diagramas.
- `developer`: implementación de código.
- `qa`: pruebas y validación.
- `product-owner`: requisitos.
- `security-code-review`: seguridad.
- `ui-ux-pro-max`: UI/UX para apps/dashboards.
- `design-taste-frontend`: diseño web/landing (no aplicable a dashboard desktop por regla; solo si se diseña landing).
- `impeccable`: auditoría/pulido UI.
- `redesign-existing-projects`: rediseño de proyectos existentes.
- `repomix` (MCP): contexto consolidado de repositorio.
- `graphify`: relaciones entre módulos (skill disponible).
- `ponytail`: simplificación/YAGNI.

## 2. Lo utilizado en esta auditoría
- Lectura directa de archivos del repositorio (README, manifiestos, código, pruebas, OpenAPI, compose, CI).
- Extracción de texto y estructura del PDF con Python/pypdf.
- Extracción de imágenes del PDF y análisis de color dominante con Pillow.
- Ejecución de pruebas existentes (API, desktop, mobile).

## 3. No utilizado / no disponible
- Repomix no se ejecutó porque la auditoría se realizó con lecturas dirigidas; puede usarse en fases posteriores para contexto consolidado.
- Graphify no se ejecutó; no se generó grafo.
- Figma editable no disponible; referencia visual es el PDF.
- OCR no disponible para leer texto dentro de imágenes del PDF.
