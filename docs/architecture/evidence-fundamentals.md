# Fundamentos de evidencias — E1

## Decisión de dominio

No existe una entidad `Visit` independiente en el modelo actual. La visita técnica se representa operativamente por `WorkOrder` (orden asignada/ejecutada). Para evitar duplicar información de la orden, las evidencias se vinculan a `work_order_id` mediante `VisitEvidence`; no se convierte `WorkOrder` en `Visit`.

## Entidades

- `VisitEvidence`: metadatos de fotografías/archivos y estado de validación.
- `VisitSignature`: aceptación o negativa del cliente.
- `EvidenceReview`: decisión administrativa.
- `EvidenceEvent`: historial de acciones.
- `VisitChecklistItem`: actividades y resultados.

## Estados de validación

`DRAFT -> SUBMITTED -> UNDER_REVIEW -> (CORRECTION_REQUIRED -> RESUBMITTED -> UNDER_REVIEW) | APPROVED | REJECTED`.

Transiciones protegidas por `EVIDENCE_TRANSITIONS` en `app/evidence/models.py`.

## Almacenamiento

`LocalStorage` guarda bytes fuera de directorios públicos bajo `originals/` y `derivatives/`, con clave aleatoria, validación por contenido (magic bytes + Pillow para imágenes), SHA-256, límite configurable y descarga autorizada por backend. No se almacenan bytes en SQL Server.

## Permisos

- Técnico: acceso a órdenes asignadas.
- Administrador/dispatcher: revisión y decisión.
- Validación en cada lectura/descarga.

## Identidad de la visita (E2)

Una `WorkOrder` representa una única visita técnica de servicio. El expediente de evidencias se vincula a `work_order_id`; no se crea una entidad `Visit` adicional. Si una intervención distinta requiere otro expediente, debe crearse otra orden de trabajo. Esta regla evita que dos intervenciones compartan el mismo expediente.

## Contratos preliminares (E2/E3)

- `POST /api/v1/work-orders/{id}/evidences`
- `GET /api/v1/work-orders/{id}/evidences`
- `GET /api/v1/evidences/{id}/download`
- `POST /api/v1/work-orders/{id}/signatures`
- `POST /api/v1/work-orders/{id}/checklist`
- Estados y transiciones según este documento.
