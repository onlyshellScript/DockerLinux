# E5.3 Interfaz administrativa del módulo de evidencias

## Pantallas implementadas

- Vista `Bandeja Evidencias` en menú (roles admin/dispatcher).
- Bandeja con filtros, paginación y conteos.
- Detalle de expediente con fotografías, firma, checklist, historial y revisiones.
- Acciones: iniciar revisión, solicitar corrección, aprobar, rechazar.

## Componentes reutilizados

- `sigos-card`, `sigos-btn-primary`, `sigos-btn-secondary`, `sigos-input`, badges, tablas.

## Endpoints consumidos

- `GET /api/v1/evidences/inbox`
- `GET /api/v1/work-orders/{id}/evidence-detail`
- `GET /api/v1/evidences/{id}/download`
- `POST /api/v1/work-orders/{id}/evidences/start-review`
- `POST /api/v1/work-orders/{id}/evidences/request-correction`
- `POST /api/v1/work-orders/{id}/evidences/approve`
- `POST /api/v1/work-orders/{id}/evidences/reject`

## Matriz de permisos

- Bandeja y detalle: admin/dispatcher (técnico autorizado solo detalle de sus expedientes).
- Iniciar revisión: admin/dispatcher.
- Corrección, aprobación, rechazo: admin.

## Estados representados

Todos los estados del contrato E1-E4.

## Pruebas

- `npm test`: 27 pruebas pasan.
- `node --check`: sin errores.

## Limitaciones

- Validación visual real no ejecutada con automatización.
- No se implementó firma en canvas.
- E5.4 pendiente.

## Problemas encontrados

- Ninguno bloqueante.
