# E5.4 Integración y validación integral del módulo de evidencias

## Flujo validado

Flujo técnico-administrativo implementado en Electron y Flask:
- Consulta de órdenes.
- Acceso a expediente.
- Carga de fotografías.
- Firma en canvas o negativa justificada.
- Checklist y observaciones.
- Guardado/envío.
- Bandeja administrativa.
- Detalle y descargas privadas.
- Revisión, corrección, reenvío.
- Aprobación/rechazo.

## Endpoints utilizados

Todos los endpoints de evidencias E1-E4, incluyendo inbox, detalle, descargas, firma, checklist, submit, resubmit, start-review, request-correction, approve, reject.

## Estados comprobados

DRAFT, SUBMITTED, UNDER_REVIEW, CORRECTION_REQUIRED, RESUBMITTED, APPROVED, REJECTED.

## Permisos

- Técnico: sus expedientes.
- Admin: revisión y decisión.
- Dispatcher: consulta/inicio de revisión, sin aprobación/rechazo.

## Firma en canvas

Implementada en Electron mediante canvas HTML, exportación PNG y carga multipart al backend existente. No se presenta como firma electrónica certificada.

## Pruebas

- `npm test`: 27 pruebas pasan.
- `node --check`: sin errores.
- Backend: tests de evidencias y concurrencia SQL Server pasan.

## Validación visual

No se ejecutó automatización visual real en esta sesión. Limitación documentada.

## Limitaciones restantes

- Validación visual real pendiente.
- Reglas de obligatoriedad básicas.
- No se implementaron interfaces Flutter.
