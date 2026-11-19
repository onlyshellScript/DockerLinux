# -*- coding: utf-8 -*-
from datetime import datetime, timezone

import sqlalchemy as sa

from app.extensions import db

# Validation states (independent from work order operational status)
EVIDENCE_DRAFT = "DRAFT"
EVIDENCE_SUBMITTED = "SUBMITTED"
EVIDENCE_UNDER_REVIEW = "UNDER_REVIEW"
EVIDENCE_CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
EVIDENCE_RESUBMITTED = "RESUBMITTED"
EVIDENCE_APPROVED = "APPROVED"
EVIDENCE_REJECTED = "REJECTED"

EVIDENCE_STATES = [
    EVIDENCE_DRAFT,
    EVIDENCE_SUBMITTED,
    EVIDENCE_UNDER_REVIEW,
    EVIDENCE_CORRECTION_REQUIRED,
    EVIDENCE_RESUBMITTED,
    EVIDENCE_APPROVED,
    EVIDENCE_REJECTED,
]

EVIDENCE_TRANSITIONS = {
    EVIDENCE_DRAFT: {EVIDENCE_SUBMITTED},
    EVIDENCE_SUBMITTED: {EVIDENCE_UNDER_REVIEW},
    EVIDENCE_UNDER_REVIEW: {EVIDENCE_CORRECTION_REQUIRED, EVIDENCE_APPROVED, EVIDENCE_REJECTED},
    EVIDENCE_CORRECTION_REQUIRED: {EVIDENCE_RESUBMITTED},
    EVIDENCE_RESUBMITTED: {EVIDENCE_UNDER_REVIEW},
    EVIDENCE_APPROVED: set(),
    EVIDENCE_REJECTED: set(),
}

CATEGORY_BEFORE = "BEFORE"
CATEGORY_DURING = "DURING"
CATEGORY_AFTER = "AFTER"
CATEGORY_ADDITIONAL = "ADDITIONAL"

EVIDENCE_CATEGORIES = [CATEGORY_BEFORE, CATEGORY_DURING, CATEGORY_AFTER, CATEGORY_ADDITIONAL]


# VisitEvidence: modelo de base de datos que representa la entidad VisitEvidence.
class VisitEvidence(db.Model):
    __tablename__ = "Evidencias"

    id = db.Column("IdEvidencia", db.Integer, primary_key=True)
    work_order_id = db.Column("IdOrden", db.Integer, db.ForeignKey("OrdenesTrabajo.IdOrden"), nullable=False, index=True)
    category = db.Column("TipoEvidencia", db.String(20), nullable=False, default=CATEGORY_ADDITIONAL, server_default=CATEGORY_ADDITIONAL)
    original_name = db.Column("NombreArchivo", db.String(250))
    storage_key = db.Column("NombreAlmacenado", db.String(120), unique=True, index=True)
    mime_type = db.Column("TipoArchivo", db.String(100))
    size_bytes = db.Column("TamanoArchivo", db.Integer)
    sha256 = db.Column("Sha256", db.String(64), index=True)
    declared_capture_at = db.Column("FechaCapturaDeclarada", db.DateTime(timezone=True))
    received_at = db.Column("FechaRecepcion", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    uploaded_by_id = db.Column("IdSubidoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), nullable=False)
    description = db.Column("Descripcion", db.Text)
    status = db.Column("Estado", db.String(30), nullable=False, default=EVIDENCE_DRAFT, server_default=EVIDENCE_DRAFT)
    previous_evidence_id = db.Column("EvidenciaAnteriorId", db.Integer, db.ForeignKey("Evidencias.IdEvidencia"))
    version_number = db.Column("NumeroVersion", db.Integer, nullable=False, default=1, server_default=sa.text("1"))
    duplicate_of_id = db.Column("DuplicadoDeId", db.Integer, db.ForeignKey("Evidencias.IdEvidencia"))
    client_operation_id = db.Column("OperacionClienteId", db.String(36), index=True)
    # Firma historica del tecnico: referencia a la version de FirmasTecnico vigente al registrar la evidencia,
    # mas una copia de su huella (sha256), del firmante y del momento. Se fija al insertar y nunca cambia
    # (ver _guard_evidence_signature). Las evidencias anteriores a esta funcion quedan con estos campos en NULL.
    technician_signature_id = db.Column("IdFirmaTecnico", db.Integer, db.ForeignKey("FirmasTecnico.IdFirmaTecnico"), index=True)
    technician_signature_sha256 = db.Column("FirmaTecnicoSha256", db.String(64))
    technician_signature_user_id = db.Column("IdTecnicoFirmante", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    technician_signed_at = db.Column("FechaFirmaTecnico", db.DateTime(timezone=True))

    # Compatibility columns retained for existing records/APIs
    # Alias heredados: la tabla Evidencias no tiene columnas propias para estos campos.
    file_name = sa.orm.synonym("original_name")
    stored_name = sa.orm.synonym("storage_key")
    file_type = sa.orm.synonym("mime_type")
    file_size = sa.orm.synonym("size_bytes")
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    work_order = db.relationship("WorkOrder")
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])
    technician_signature = db.relationship("TechnicianSignature", foreign_keys=[technician_signature_id])
    technician_signer = db.relationship("User", foreign_keys=[technician_signature_user_id])
    previous_evidence = db.relationship("VisitEvidence", remote_side=[id], foreign_keys=[previous_evidence_id])
    duplicate_of = db.relationship("VisitEvidence", remote_side=[id], foreign_keys=[duplicate_of_id])
    reviews = db.relationship("EvidenceReview", backref="evidence", cascade="all, delete-orphan", order_by="EvidenceReview.created_at")

# Convierte el valor al formato interno; recibe sin parametros; accede al sistema de archivos; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "category": self.category,
            "original_name": self.original_name or self.file_name,
            "storage_key": self.storage_key or self.stored_name,
            "mime_type": self.mime_type or self.file_type,
            "size_bytes": self.size_bytes if self.size_bytes is not None else self.file_size,
            "sha256": self.sha256,
            "declared_capture_at": self.declared_capture_at.isoformat() if self.declared_capture_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "uploaded_by": self.uploaded_by.to_dict() if self.uploaded_by else None,
            "uploaded_by_id": self.uploaded_by_id,
            "description": self.description,
            "status": self.status,
            "previous_evidence_id": self.previous_evidence_id,
            "version_number": self.version_number,
            "duplicate_of_id": self.duplicate_of_id,
            "file_name": self.file_name or self.original_name,
            "stored_name": self.stored_name or self.storage_key,
            "file_type": self.file_type or self.mime_type,
            "file_size": self.file_size if self.file_size is not None else self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "technician_signature": self.signature_summary(),
        }

# signature_summary: datos de la firma historica del tecnico (sin la clave de almacenamiento); None si no tiene.
    def signature_summary(self):
        if not self.technician_signature_id:
            return None
        signer = self.technician_signer
        return {
            "signature_id": self.technician_signature_id,
            "technician_id": self.technician_signature_user_id,
            "technician_username": signer.username if signer else None,
            "signed_at": self.technician_signed_at.isoformat() if self.technician_signed_at else None,
            "sha256": self.technician_signature_sha256,
            "version": self.technician_signature.version if self.technician_signature else None,
        }


# TechnicianSignature: firma de perfil de un usuario (tecnico). Cada registro es una version inmutable:
# registrar una firma nueva crea otra fila y desactiva la anterior, nunca sobrescribe su archivo ni su huella.
# Asi las evidencias que referencian una version antigua conservan exactamente la firma con la que se firmaron.
class TechnicianSignature(db.Model):
    __tablename__ = "FirmasTecnico"

    id = db.Column("IdFirmaTecnico", db.Integer, primary_key=True)
    user_id = db.Column("IdUsuario", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), nullable=False, index=True)
    storage_key = db.Column("ClaveAlmacenamiento", db.String(120), nullable=False, unique=True)
    mime_type = db.Column("TipoArchivo", db.String(100), nullable=False)
    size_bytes = db.Column("TamanoArchivo", db.Integer, nullable=False)
    sha256 = db.Column("Sha256", db.String(64), nullable=False)
    version = db.Column("Version", db.Integer, nullable=False, default=1, server_default=sa.text("1"))
    is_active = db.Column("EsActiva", db.Boolean, nullable=False, default=True, server_default=sa.text("1"))
    created_at = db.Column("CreadaEn", db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    replaced_at = db.Column("ReemplazadaEn", db.DateTime(timezone=True))

    user = db.relationship("User")

# to_dict: metadatos publicos de la firma (sin la clave de almacenamiento).
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "version": self.version,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "replaced_at": self.replaced_at.isoformat() if self.replaced_at else None,
        }


# ImmutableRecordError: intento de modificar o borrar datos de firma que deben conservarse tal cual.
class ImmutableRecordError(Exception):
    pass


_EVIDENCE_SIGNATURE_FIELDS = ("technician_signature_id", "technician_signature_sha256", "technician_signature_user_id", "technician_signed_at")
_SIGNATURE_IMMUTABLE_FIELDS = ("user_id", "storage_key", "mime_type", "size_bytes", "sha256", "version", "created_at")


# Barrera en la capa de datos (ademas de la del servicio): ninguna ruta, presente o futura, puede reescribir la firma
# historica de una evidencia ni el contenido de una version de firma, ni borrar una version de firma.
@sa.event.listens_for(VisitEvidence, "before_update")
def _guard_evidence_signature(mapper, connection, target):
    state = sa.inspect(target)
    for field in _EVIDENCE_SIGNATURE_FIELDS:
        # Se fija solo al insertar: ni se reemplaza, ni se borra, ni se agrega despues a una evidencia ya registrada.
        if state.attrs[field].history.has_changes():
            raise ImmutableRecordError(f"la firma de la evidencia {target.id} es inmutable")


@sa.event.listens_for(VisitEvidence, "before_delete")
def _guard_signed_evidence_delete(mapper, connection, target):
    if target.technician_signature_id is not None:
        raise ImmutableRecordError(f"la evidencia {target.id} esta firmada y no puede eliminarse")


@sa.event.listens_for(TechnicianSignature, "before_update")
def _guard_signature_content(mapper, connection, target):
    state = sa.inspect(target)
    for field in _SIGNATURE_IMMUTABLE_FIELDS:
        if state.attrs[field].history.has_changes():
            raise ImmutableRecordError(f"la version de firma {target.id} es inmutable")


@sa.event.listens_for(TechnicianSignature, "before_delete")
def _guard_signature_delete(mapper, connection, target):
    raise ImmutableRecordError(f"la version de firma {target.id} no puede eliminarse")


# VisitSignature: modelo de base de datos que representa la entidad VisitSignature.
class VisitSignature(db.Model):
    __tablename__ = "FirmasVisita"

    id = db.Column("IdFirma", db.Integer, primary_key=True)
    work_order_id = db.Column("IdOrden", db.Integer, db.ForeignKey("OrdenesTrabajo.IdOrden"), nullable=False, index=True)
    storage_key = db.Column("ClaveAlmacenamiento", db.String(120))
    signer_name = db.Column("NombreFirmante", db.String(120))
    signer_role = db.Column("RolFirmante", db.String(120))
    received_at = db.Column("FechaRecepcion", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    acceptance_text = db.Column("TextoAceptacion", db.Text)
    consent_version = db.Column("VersionConsentimiento", db.String(40))
    technician_id = db.Column("IdTecnico", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    refused = db.Column("Rechazado", db.Boolean, nullable=False, default=False, server_default=sa.text("0"))
    refusal_reason = db.Column("MotivoRechazo", db.Text)
    client_operation_id = db.Column("OperacionClienteId", db.String(36), index=True)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    work_order = db.relationship("WorkOrder")
    technician = db.relationship("User")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "storage_key": self.storage_key,
            "signer_name": self.signer_name,
            "signer_role": self.signer_role,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "acceptance_text": self.acceptance_text,
            "consent_version": self.consent_version,
            "technician_id": self.technician_id,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# EvidenceReview: modelo de base de datos que representa la entidad EvidenceReview.
class EvidenceReview(db.Model):
    __tablename__ = "RevisionesEvidencia"

    id = db.Column("IdRevision", db.Integer, primary_key=True)
    evidence_id = db.Column("IdEvidencia", db.Integer, db.ForeignKey("Evidencias.IdEvidencia"), nullable=False, index=True)
    reviewer_id = db.Column("IdRevisor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"), nullable=False)
    decision = db.Column("Decision", db.String(30), nullable=False)
    notes = db.Column("Notas", db.Text)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reviewer = db.relationship("User")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "evidence_id": self.evidence_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_username": self.reviewer.username if self.reviewer else None,
            "decision": self.decision,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# EvidenceEvent: modelo de base de datos que representa la entidad EvidenceEvent.
class EvidenceEvent(db.Model):
    __tablename__ = "EventosEvidencia"

    id = db.Column("IdEvento", db.Integer, primary_key=True)
    work_order_id = db.Column("IdOrden", db.Integer, db.ForeignKey("OrdenesTrabajo.IdOrden"), index=True)
    evidence_id = db.Column("IdEvidencia", db.Integer, db.ForeignKey("Evidencias.IdEvidencia"), index=True)
    actor_id = db.Column("IdActor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    action = db.Column("Accion", db.String(40), nullable=False)
    from_status = db.Column("EstadoAnterior", db.String(30))
    to_status = db.Column("EstadoNuevo", db.String(30))
    details = db.Column("Detalles", db.Text)
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    actor = db.relationship("User")
    evidence = db.relationship("VisitEvidence")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "evidence_id": self.evidence_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# VisitChecklistItem: modelo de base de datos que representa la entidad VisitChecklistItem.
class VisitChecklistItem(db.Model):
    __tablename__ = "ListaVerificacionVisita"

    id = db.Column("IdItem", db.Integer, primary_key=True)
    work_order_id = db.Column("IdOrden", db.Integer, db.ForeignKey("OrdenesTrabajo.IdOrden"), nullable=False, index=True)
    label = db.Column("Etiqueta", db.String(250), nullable=False)
    result = db.Column("Resultado", db.String(30))
    notes = db.Column("Notas", db.Text)
    checked_by_id = db.Column("IdVerificadoPor", db.Integer, db.ForeignKey("Usuarios.IdUsuario"))
    created_at = db.Column("CreadoEn", db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    checked_by = db.relationship("User")

# Convierte el valor al formato interno; recibe sin parametros; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def to_dict(self):
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "label": self.label,
            "result": self.result,
            "notes": self.notes,
            "checked_by_id": self.checked_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


Evidence = VisitEvidence
ALL_TYPES = ["photo", "document", "observation"]
