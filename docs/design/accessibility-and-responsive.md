# SIGOS — Accesibilidad y responsive

## 1. Objetivos
- Cumplir RNF-08, RNF-09, RNF-11.
- Soportar teclado, foco visible y contraste adecuado.
- Adaptar layouts a móvil, tablet y desktop.

## 2. Breakpoints sugeridos
| Nombre | Ancho | Uso |
|---|---|---|
| mobile | < 600px | Móvil |
| tablet | 600-1023px | Tablet |
| desktop | >= 1024px | Escritorio |

## 3. Accesibilidad mínima
- Contraste AA para texto normal.
- Foco visible en controles interactivos.
- Etiquetas/aria en desktop; Semantics en Flutter.
- Mensajes de error asociados a campos.
- No depender solo del color para estados.

## 4. Responsive
- Desktop: sidebar colapsable en tablet.
- Mobile: una columna, acciones principales accesibles con pulgar.
- Tablas convertibles a cards en móvil.
- Imágenes/evidencias con tamaño máximo y zoom.

## 5. Pendientes
- Ejecutar auditoría de contraste con herramientas disponibles.
- Añadir pruebas de accesibilidad cuando existan frameworks en el repo.
