# E5.2 Interfaz del técnico para evidencias

## Pantallas implementadas

- Vista `Evidencias` en el menú principal (`NAV` key `evidence`).
- Selector de orden de trabajo asignada.
- Panel de fotografías por categoría.
- Registro de negativa de firma.
- Checklist.
- Acciones de envío y reenvío.
- Historial resumido.

## Componentes reutilizados

- `sigos-card`, `sigos-btn-primary`, `sigos-btn-secondary`, `sigos-input`.
- Badges de estado.
- Icono `evidence` existente.

## Servicios y endpoints consumidos

- `GET /api/v1/work-orders`
- `GET /api/v1/work-orders/{id}/evidence-status`
- `POST /api/v1/work-orders/{id}/evidences`
- `GET /api/v1/evidences/{id}/download`
- `POST /api/v1/work-orders/{id}/signatures`
- `POST/GET /api/v1/work-orders/{id}/checklist`
- `POST /api/v1/work-orders/{id}/evidences/submit`
- `POST /api/v1/work-orders/{id}/evidences/resubmit`

## Estados representados

`DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `CORRECTION_REQUIRED`, `RESUBMITTED`, `APPROVED`, `REJECTED`.

## Pruebas

- `npm test`: 27 pruebas pasan.
- `node --check src/renderer/app.js`: sin errores de sintaxis.

## Limitaciones

- No se implementó firma dibujada; solo negativa justificada (el backend soporta archivo de firma, pero la UI actual no captura canvas).
- Validación visual real no ejecutada con navegador automatizado.
- Administración queda para E5.3.

## Pendientes

- Integración visual con E5.3.
- Pruebas de interacción end-to-end.
