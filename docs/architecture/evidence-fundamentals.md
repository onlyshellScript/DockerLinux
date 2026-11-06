# Fundamentos del módulo de evidencias

## Decisión de dominio

En SIGOS 2.0 no existe una entidad `Visit` independiente. La visita técnica se representa operativamente mediante una `WorkOrder` asignada y ejecutada. Para evitar duplicar datos de la orden, las evidencias se vinculan a `work_order_id` a través de `VisitEvidence`.

Esta decisión mantiene la compatibilidad con el modelo existente y evita que dos intervenciones distintas compartan un mismo expediente.

## Entidades

- `VisitEvidence`: metadatos de archivos y estado de validación.
- `VisitSignature`: aceptación o negativa del cliente.
- `EvidenceReview`: decisión administrativa.
- `EvidenceEvent`: historial de acciones.
- `VisitChecklistItem`: actividades y resultados.

## Estados de validación

`DRAFT -> SUBMITTED -> UNDER_REVIEW -> (CORRECTION_REQUIRED -> RESUBMITTED -> UNDER_REVIEW) | APPROVED | REJECTED`

Las transiciones se definen en `EVIDENCE_TRANSITIONS` dentro de `services/api/app/evidence/models.py`.

## Almacenamiento

`LocalStorage` guarda los bytes fuera de directorios públicos, bajo `originals/` y `derivatives/`. Cada archivo recibe una clave aleatoria, se valida por contenido (magic bytes y Pillow para imágenes), se calcula su SHA-256 y se aplican límites configurables. La descarga se autoriza desde el backend. No se almacenan bytes en SQL Server.

## Permisos

- El técnico accede únicamente a las órdenes asignadas.
- El administrador o dispatcher inicia la revisión.
- Solo el administrador aprueba, solicita correcciones o rechaza.
- Cada operación de lectura y descarga valida autorización en backend.

## Contratos para E2 y E3

- `POST /api/v1/work-orders/{id}/evidences`
- `GET /api/v1/work-orders/{id}/evidences`
- `GET /api/v1/evidences/{id}/download`
- `POST /api/v1/work-orders/{id}/signatures`
- `POST /api/v1/work-orders/{id}/checklist`
- `POST /api/v1/work-orders/{id}/evidences/submit`

Los estados y transiciones se definen en este documento.

## Identidad de la visita

Una `WorkOrder` representa una única visita técnica. El expediente de evidencias se vincula a `work_order_id`. Si una intervención distinta requiere otro expediente, debe crearse otra orden de trabajo.

## Contratos administrativos

- `GET /api/v1/evidences/inbox`
- `GET /api/v1/work-orders/{id}/evidence-detail`
- `POST /api/v1/work-orders/{id}/evidences/start-review`
- `POST /api/v1/work-orders/{id}/evidences/request-correction`
- `POST /api/v1/work-orders/{id}/evidences/approve`
- `POST /api/v1/work-orders/{id}/evidences/reject`

## Referencias

- `services/api/app/evidence/models.py`
- `services/api/app/evidence/service.py`
- `services/api/app/evidence/routes.py`
- `services/api/app/evidence/storage.py`
- `services/api/app/evidence/permissions.py`
