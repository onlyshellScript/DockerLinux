# SIGOS — Plan de validación de diseño

## 1. Comandos base
- API: `cd services/api && python -m pytest tests/ -v`
- Desktop: `cd apps/desktop && npm test`
- Mobile: `cd apps/mobile && flutter test`

## 2. Validaciones por fase
- Tokens: revisar contraste y consistencia visual.
- Componentes: pruebas unitarias/widget donde existan frameworks.
- Pantallas: flujo completo contra endpoints reales.
- Accesibilidad: teclado, foco, semántica, contraste.
- Responsive: móvil/tablet/desktop.
- Offline móvil: push/pull y estados fallidos.

## 3. Criterios de aceptación
- No se considera completo solo porque inicia.
- Cada pantalla debe consumir datos reales.
- Errores HTTP y red deben mostrarse.
- Pruebas ejecutadas y resultados documentados.

## 4. Diferencias contra PDF
- Documentar en cada entrega pantallas pendientes, funcionalidades no implementadas y discrepancias de nombres/códigos.
