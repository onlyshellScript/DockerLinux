# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from app.extensions import db
from app.evidence.models import (
    VisitEvidence,
    VisitSignature,
    EvidenceReview,
    EvidenceEvent,
    VisitChecklistItem,
    EVIDENCE_STATES,
    EVIDENCE_TRANSITIONS,
    EVIDENCE_DRAFT,
    EVIDENCE_SUBMITTED,
    EVIDENCE_UNDER_REVIEW,
    EVIDENCE_CORRECTION_REQUIRED,
    EVIDENCE_RESUBMITTED,
    EVIDENCE_APPROVED,
    EVIDENCE_REJECTED,
    EVIDENCE_CATEGORIES,
    CATEGORY_ADDITIONAL,
)
from app.evidence.storage import get_storage
from app.evidence.permissions import (
    can_access_work_order,
    can_create_evidence,
    can_view_evidence,
    can_download_evidence,
    can_review_evidence,
    can_manage_checklist,
)
from app.workorders.service import get_work_order
from app.identity.models import User
from app.materials.service import _lock_row


# _now: devuelve la fecha y hora actual en UTC; sin parametros; salida datetime; sin efectos secundarios.
def _now():
    return datetime.now(timezone.utc)


# Gestiona read file; recibe file_obj; accede al sistema de archivos; devuelve el valor correspondiente.
def _read_file(file_obj):
    if file_obj is None:
        return None, None
    if hasattr(file_obj, "read"):
        data = file_obj.read()
        if hasattr(file_obj, "seek"):
            try:
                file_obj.seek(0)
            except Exception:
                pass
        name = getattr(file_obj, "filename", None) or getattr(file_obj, "name", None) or "upload.bin"
        return data, name
    if isinstance(file_obj, (bytes, bytearray)):
        return bytes(file_obj), "upload.bin"
    return None, None


# Gestiona record event; recibe work_order_id, evidence_id, actor_id, action, from_status, to_status, details; interactua con la base de datos; devuelve el valor correspondiente.
def _record_event(work_order_id, evidence_id, actor_id, action, from_status=None, to_status=None, details=None):
    ev = EvidenceEvent(
        work_order_id=work_order_id,
        evidence_id=evidence_id,
        actor_id=actor_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        details=details,
        created_at=_now(),
    )
    db.session.add(ev)


# Agrega un nuevo elemento al sistema; recibe work_order_id, uploaded_by_id, category, file, **kwargs; interactua con la base de datos; accede al sistema de archivos; devuelve el valor correspondiente.
def add_evidence(
    work_order_id,
    uploaded_by_id,
    category=CATEGORY_ADDITIONAL,
    file=None,
    **kwargs,
):
    original_name = kwargs.pop("original_name", kwargs.pop("file_name", kwargs.pop("original_filename", None)))
    declared_mime = kwargs.pop("declared_mime", kwargs.pop("mime_type", kwargs.pop("file_type", None)))
    description = kwargs.pop("description", None)
    declared_capture_at = kwargs.pop("declared_capture_at", kwargs.pop("capture_date", kwargs.pop("taken_at", None)))
    previous_evidence_id = kwargs.pop("previous_evidence_id", kwargs.pop("previous_id", kwargs.pop("parent_evidence_id", None)))
    roles = kwargs.pop("roles", None)
    category = kwargs.pop("category", category)
    operation_id = kwargs.pop("operation_id", kwargs.pop("client_operation_id", None))
    if kwargs.pop("evidence_type", None):
        # keep compatibility; do not override explicit category
        pass
    wo = get_work_order(work_order_id)
    if not wo:
        return None, "work_order_not_found"
    if roles is not None and not can_create_evidence(uploaded_by_id, roles, wo):
        return None, "forbidden"
    if category not in EVIDENCE_CATEGORIES:
        return None, "invalid_category"
    if operation_id:
        existing = VisitEvidence.query.filter_by(client_operation_id=operation_id).first()
        if existing:
            return existing, None

    # Firma del tecnico: siempre la version vigente del perfil del usuario autenticado (uploaded_by_id).
    # Ningun dato del cliente interviene: no se acepta una imagen ni un id de firma en la peticion.
    from app.evidence.signatures import get_active_signature, signature_required_for
    signer_roles = roles
    if signer_roles is None:
        uploader = db.session.get(User, uploaded_by_id)
        signer_roles = [r.name for r in uploader.roles] if uploader else []
    profile_signature = None
    if "technician" in set(signer_roles or []):
        profile_signature = get_active_signature(uploaded_by_id)
        if profile_signature is None and signature_required_for(signer_roles):
            return None, "technician_signature_required"

    storage = get_storage()
    storage_key = None
    metadata = None
    name = original_name
    mime_type = None
    size_bytes = None
    sha256 = None

    if file is not None:
        data, detected_name = _read_file(file)
        if name is None:
            name = detected_name
        mime_type, size_bytes, sha256, error = storage.validate(data, name, declared_mime)
        if error:
            return None, error
        storage_key, metadata, error = storage.save(data, name, declared_mime)
        if error:
            return None, error
        mime_type = metadata["mime_type"]
        size_bytes = metadata["size_bytes"]
        sha256 = metadata["sha256"]
        if name is None:
            name = metadata["original_name"]

    duplicate_of_id = None
    if sha256:
        existing = VisitEvidence.query.filter_by(work_order_id=work_order_id, sha256=sha256).first()
        if existing:
            duplicate_of_id = existing.id

    parsed_capture = None
    if declared_capture_at:
        try:
            parsed_capture = datetime.fromisoformat(str(declared_capture_at).replace("Z", "+00:00"))
        except ValueError:
            parsed_capture = None

    ev = VisitEvidence(
        work_order_id=work_order_id,
        category=category,
        original_name=name,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=sha256,
        declared_capture_at=parsed_capture,
        received_at=_now(),
        uploaded_by_id=uploaded_by_id,
        description=description,
        status=EVIDENCE_DRAFT,
        previous_evidence_id=previous_evidence_id,
        version_number=1,
        duplicate_of_id=duplicate_of_id,
        client_operation_id=operation_id,
        file_name=name,
        stored_name=storage_key,
        file_type=mime_type,
        file_size=size_bytes,
        created_at=_now(),
    )
    if profile_signature is not None:
        ev.technician_signature_id = profile_signature.id
        ev.technician_signature_sha256 = profile_signature.sha256
        ev.technician_signature_user_id = uploaded_by_id
        ev.technician_signed_at = ev.received_at
    db.session.add(ev)
    db.session.flush()
    details = f"category={category}"
    if profile_signature is not None:
        details += f";signature_id={profile_signature.id};signature_sha256={profile_signature.sha256}"
    _record_event(work_order_id, ev.id, uploaded_by_id, "EVIDENCE_ADDED", EVIDENCE_DRAFT, EVIDENCE_DRAFT, details)
    db.session.commit()
    return ev, None


# Crea el registro solicitado con los datos recibidos; recibe work_order_id, uploaded_by_id, evidence_type, file, description, **kwargs; accede al sistema de archivos; devuelve el valor correspondiente.
def create_evidence(work_order_id, uploaded_by_id, evidence_type="observation", file=None, description=None, **kwargs):
    category = kwargs.pop("category", CATEGORY_ADDITIONAL)
    roles = kwargs.pop("roles", None)
    original_name = kwargs.pop("original_name", None)
    declared_mime = kwargs.pop("declared_mime", None)
    declared_capture_at = kwargs.pop("declared_capture_at", None)
    previous_evidence_id = kwargs.pop("previous_evidence_id", None)
    return add_evidence(
        work_order_id,
        uploaded_by_id,
        category=category,
        file=file,
        original_name=original_name or (getattr(file, "filename", None) if file is not None else None),
        declared_mime=declared_mime,
        description=description,
        declared_capture_at=declared_capture_at,
        previous_evidence_id=previous_evidence_id,
        roles=roles,
    )


# list_evidences: lista las evidencias de una orden ordenadas por fecha de recepcion descendente; entrada work_order_id; salida list; lee la base de datos.
def list_evidences(work_order_id):
    return VisitEvidence.query.filter_by(work_order_id=work_order_id).order_by(VisitEvidence.received_at.desc(), VisitEvidence.id.desc()).all()


# get_evidence: obtiene una evidencia por su id; entrada ev_id; salida VisitEvidence o None; lee la base de datos.
def get_evidence(ev_id):
    return db.session.get(VisitEvidence, ev_id)


# Elimina el registro indicado; recibe ev_id, roles, actor_id; interactua con la base de datos; devuelve el valor correspondiente.
def delete_evidence(ev_id, roles=None, actor_id=None):
    ev = db.session.get(VisitEvidence, ev_id)
    if not ev:
        return False, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return False, "forbidden"
    # Una evidencia firmada por el tecnico es un registro inmutable: no se borra por la interfaz habitual.
    if ev.technician_signature_id is not None:
        return False, "signed_evidence_immutable"
    if ev.storage_key or ev.stored_name:
        storage = get_storage()
        storage.delete(ev.storage_key or ev.stored_name)
    db.session.delete(ev)
    db.session.commit()
    return True, None


# Aplica la transicion de estado solicitada; recibe ev, to_status, actor_id, action, notes; interactua con la base de datos; devuelve el valor correspondiente.
def _transition(ev, to_status, actor_id, action, notes=None):
    if ev is None:
        return None, "not_found"
    if to_status not in EVIDENCE_TRANSITIONS.get(ev.status, set()):
        return None, "invalid_transition"
    from_status = ev.status
    ev.status = to_status
    _record_event(ev.work_order_id, ev.id, actor_id, action, from_status, to_status, notes)
    db.session.commit()
    return ev, None


# Gestiona submit evidence; recibe evidence_id, actor_id, roles, notes; interactua con la base de datos; devuelve el valor correspondiente.
def submit_evidence(evidence_id, actor_id, roles=None, notes=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    wo = get_work_order(ev.work_order_id)
    if roles is not None and not can_create_evidence(actor_id, roles, wo):
        return None, "forbidden"
    return _transition(ev, EVIDENCE_SUBMITTED, actor_id, "SUBMIT", notes)


# Gestiona start review; recibe evidence_id, actor_id, roles, notes; interactua con la base de datos; devuelve el valor correspondiente.
def start_review(evidence_id, actor_id, roles=None, notes=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    return _transition(ev, EVIDENCE_UNDER_REVIEW, actor_id, "REVIEW_STARTED", notes)


# Gestiona request correction; recibe evidence_id, actor_id, notes, roles; interactua con la base de datos; devuelve el valor correspondiente.
def request_correction(evidence_id, actor_id, notes=None, roles=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    if not notes:
        return None, "notes_required"
    return _transition(ev, EVIDENCE_CORRECTION_REQUIRED, actor_id, "CORRECTION_REQUESTED", notes)


# Gestiona resubmit evidence; recibe evidence_id, actor_id, roles, notes, new_evidence_id; interactua con la base de datos; devuelve el valor correspondiente.
def resubmit_evidence(evidence_id, actor_id, roles=None, notes=None, new_evidence_id=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    wo = get_work_order(ev.work_order_id)
    if roles is not None and not can_create_evidence(actor_id, roles, wo):
        return None, "forbidden"
    if ev.status != EVIDENCE_CORRECTION_REQUIRED:
        return None, "invalid_transition"
    # mark original as resubmitted? Create new version instead of mutating
    if new_evidence_id:
        new_ev = db.session.get(VisitEvidence, new_evidence_id)
        if new_ev is None:
            return None, "not_found"
        new_ev.previous_evidence_id = ev.id
        new_ev.version_number = (ev.version_number or 1) + 1
        new_ev.status = EVIDENCE_RESUBMITTED
        db.session.flush()
        _record_event(ev.work_order_id, new_ev.id, actor_id, "RESUBMIT", EVIDENCE_CORRECTION_REQUIRED, EVIDENCE_RESUBMITTED, notes)
        db.session.commit()
        return new_ev, None
    return _transition(ev, EVIDENCE_RESUBMITTED, actor_id, "RESUBMIT", notes)


# Gestiona approve evidence; recibe evidence_id, actor_id, roles, notes; interactua con la base de datos; devuelve el valor correspondiente.
def approve_evidence(evidence_id, actor_id, roles=None, notes=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    result = _transition(ev, EVIDENCE_APPROVED, actor_id, "APPROVED", notes)
    if result[0] is not None:
        review = EvidenceReview(evidence_id=ev.id, reviewer_id=actor_id, decision=EVIDENCE_APPROVED, notes=notes, created_at=_now())
        db.session.add(review)
        db.session.commit()
    return result


# Gestiona reject evidence; recibe evidence_id, actor_id, notes, roles; interactua con la base de datos; devuelve el valor correspondiente.
def reject_evidence(evidence_id, actor_id, notes=None, roles=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    if not notes:
        return None, "notes_required"
    result = _transition(ev, EVIDENCE_REJECTED, actor_id, "REJECTED", notes)
    if result[0] is not None:
        review = EvidenceReview(evidence_id=ev.id, reviewer_id=actor_id, decision=EVIDENCE_REJECTED, notes=notes, created_at=_now())
        db.session.add(review)
        db.session.commit()
    return result


# Gestiona review evidence; recibe evidence_id, reviewer_id, decision, notes, roles; interactua con la base de datos; devuelve el valor correspondiente.
def review_evidence(evidence_id, reviewer_id, decision, notes=None, roles=None):
    if decision not in EVIDENCE_STATES:
        return None, "invalid_decision"
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    # map decision to transition when possible
    if decision in EVIDENCE_TRANSITIONS.get(ev.status, set()):
        ev.status = decision
    review = EvidenceReview(evidence_id=ev.id, reviewer_id=reviewer_id, decision=decision, notes=notes, created_at=_now())
    db.session.add(review)
    _record_event(ev.work_order_id, ev.id, reviewer_id, "REVIEW_DECISION", ev.status, decision, notes)
    db.session.commit()
    return review, None


# Gestiona submit expediente; recibe work_order_id, actor_id, roles, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def submit_expediente(work_order_id, actor_id, roles=None, operation_id=None):
    # idempotent: if already submitted, return current submitted items
    existing_submitted = VisitEvidence.query.filter_by(work_order_id=work_order_id, status=EVIDENCE_SUBMITTED).all()
    if existing_submitted and not VisitEvidence.query.filter_by(work_order_id=work_order_id, status=EVIDENCE_DRAFT).all():
        return existing_submitted, None
    items = VisitEvidence.query.filter_by(work_order_id=work_order_id, status=EVIDENCE_DRAFT).all()
    out = []
    for ev in items:
        r, err = submit_evidence(ev.id, actor_id, roles=roles)
        if r:
            out.append(r)
    if out:
        _record_event(work_order_id, None, actor_id, "EXPEDIENTE_SUBMITTED", None, EVIDENCE_SUBMITTED, f"count={len(out)};operation={operation_id}")
        db.session.commit()
    return out, None


# Gestiona resubmit expediente; recibe work_order_id, actor_id, roles, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def resubmit_expediente(work_order_id, actor_id, roles=None, operation_id=None):
    corrected = VisitEvidence.query.filter_by(work_order_id=work_order_id, status=EVIDENCE_CORRECTION_REQUIRED).all()
    if not corrected:
        return None, "invalid_state"
    out = []
    for ev in corrected:
        r, err = resubmit_evidence(ev.id, actor_id, roles=roles)
        if r:
            out.append(r)
    # Las evidencias agregadas durante la corrección (en borrador) viajan con el reenvío: si quedaran en borrador,
    # el expediente no podría aprobarse nunca.
    for ev in VisitEvidence.query.filter_by(work_order_id=work_order_id, status=EVIDENCE_DRAFT).all():
        r, err = submit_evidence(ev.id, actor_id, roles=roles)
        if r:
            out.append(r)
    if not out:
        return None, "invalid_state"
    _record_event(work_order_id, None, actor_id, "EXPEDIENTE_RESUBMITTED", None, EVIDENCE_RESUBMITTED, f"count={len(out)};operation={operation_id}")
    db.session.commit()
    return out, None


# Gestiona start review expediente; recibe work_order_id, actor_id, roles; interactua con la base de datos; devuelve el valor correspondiente.
def start_review_expediente(work_order_id, actor_id, roles=None):
    items = VisitEvidence.query.filter_by(work_order_id=work_order_id, status=EVIDENCE_SUBMITTED).all()
    out = []
    for ev in items:
        r, err = start_review(ev.id, actor_id, roles=roles)
        if r:
            out.append(r)
    _record_event(work_order_id, None, actor_id, "REVIEW_STARTED", None, EVIDENCE_UNDER_REVIEW, f"count={len(out)}")
    db.session.commit()
    return out, None


# Gestiona register signature; recibe work_order_id, technician_id, file, signer_name, signer_role, acceptance_text, consent_version, roles, original_name, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def register_signature(
    work_order_id,
    technician_id,
    *,
    file=None,
    signer_name=None,
    signer_role=None,
    acceptance_text=None,
    consent_version=None,
    roles=None,
    original_name=None,
    operation_id=None,
):
    wo = get_work_order(work_order_id)
    if not wo:
        return None, "work_order_not_found"
    if roles is not None and not can_create_evidence(technician_id, roles, wo):
        return None, "forbidden"
    if operation_id:
        existing = VisitSignature.query.filter_by(client_operation_id=operation_id).first()
        if existing:
            return existing, None

    storage = get_storage()
    storage_key = None
    if file is not None:
        data, detected_name = _read_file(file)
        name = original_name or detected_name
        mime_type, size_bytes, sha256, error = storage.validate(data, name, None)
        if error:
            return None, error
        storage_key, metadata, error = storage.save(data, name, None)
        if error:
            return None, error

    sig = VisitSignature(
        work_order_id=work_order_id,
        storage_key=storage_key,
        signer_name=signer_name,
        signer_role=signer_role,
        received_at=_now(),
        acceptance_text=acceptance_text,
        consent_version=consent_version,
        technician_id=technician_id,
        refused=False,
        client_operation_id=operation_id,
        created_at=_now(),
    )
    db.session.add(sig)
    db.session.flush()
    _record_event(work_order_id, None, technician_id, "SIGNATURE_REGISTERED", None, None, f"signer={signer_name}")
    db.session.commit()
    return sig, None


# Gestiona register signature refusal; recibe work_order_id, technician_id, signer_name, reason, roles; interactua con la base de datos; devuelve el valor correspondiente.
def register_signature_refusal(work_order_id, technician_id, *, signer_name=None, reason=None, roles=None):
    if not reason:
        return None, "refusal_reason_required"
    wo = get_work_order(work_order_id)
    if not wo:
        return None, "work_order_not_found"
    if roles is not None and not can_create_evidence(technician_id, roles, wo):
        return None, "forbidden"
    sig = VisitSignature(
        work_order_id=work_order_id,
        signer_name=signer_name,
        received_at=_now(),
        technician_id=technician_id,
        refused=True,
        refusal_reason=reason,
        created_at=_now(),
    )
    db.session.add(sig)
    db.session.flush()
    _record_event(work_order_id, None, technician_id, "SIGNATURE_REFUSED", None, None, f"reason={reason}")
    db.session.commit()
    return sig, None


# list_signatures: lista las firmas de una orden ordenadas por fecha de recepcion descendente; entrada work_order_id; salida list; lee la base de datos.
def list_signatures(work_order_id):
    return VisitSignature.query.filter_by(work_order_id=work_order_id).order_by(VisitSignature.received_at.desc()).all()


# get_signature: obtiene una firma por su id; entrada sig_id; salida VisitSignature o None; lee la base de datos.
def get_signature(sig_id):
    return db.session.get(VisitSignature, sig_id)


# Agrega un nuevo elemento al sistema; recibe work_order_id, label, result, notes, actor_id, roles; interactua con la base de datos; devuelve el valor correspondiente.
def add_checklist_item(work_order_id, label, *, result=None, notes=None, actor_id=None, roles=None):
    wo = get_work_order(work_order_id)
    if not wo:
        return None, "work_order_not_found"
    if roles is not None and actor_id is not None and not can_manage_checklist(actor_id, roles, wo):
        return None, "forbidden"
    item = VisitChecklistItem(
        work_order_id=work_order_id,
        label=label,
        result=result,
        notes=notes,
        checked_by_id=actor_id,
        created_at=_now(),
    )
    db.session.add(item)
    db.session.flush()
    _record_event(work_order_id, None, actor_id, "CHECKLIST_ITEM_ADDED", None, None, label)
    db.session.commit()
    return item, None


# Actualiza los campos indicados del registro; recibe item_id, result, notes, actor_id, roles; interactua con la base de datos; devuelve el valor correspondiente.
def update_checklist_item(item_id, *, result=None, notes=None, actor_id=None, roles=None):
    item = db.session.get(VisitChecklistItem, item_id)
    if not item:
        return None, "not_found"
    wo = get_work_order(item.work_order_id)
    if roles is not None and actor_id is not None and not can_manage_checklist(actor_id, roles, wo):
        return None, "forbidden"
    if result is not None:
        item.result = result
    if notes is not None:
        item.notes = notes
    if actor_id is not None:
        item.checked_by_id = actor_id
    db.session.commit()
    return item, None


# list_checklist_items: lista los items de checklist de una orden ordenados por id; entrada work_order_id; salida list; lee la base de datos.
def list_checklist_items(work_order_id):
    return VisitChecklistItem.query.filter_by(work_order_id=work_order_id).order_by(VisitChecklistItem.id).all()


# Crea el registro solicitado con los datos recibidos; recibe evidence_id, reviewer_id, decision, notes, roles; interactua con la base de datos; devuelve el valor correspondiente.
def create_review(evidence_id, reviewer_id, decision, notes=None, roles=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if not ev:
        return None, "evidence_not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    review = EvidenceReview(evidence_id=evidence_id, reviewer_id=reviewer_id, decision=decision, notes=notes, created_at=_now())
    db.session.add(review)
    db.session.flush()
    _record_event(ev.work_order_id, ev.id, reviewer_id, "EVIDENCE_REVIEWED", ev.status, decision, notes)
    db.session.commit()
    return review, None


# list_reviews: lista las revisiones de una evidencia ordenadas por fecha de creacion; entrada evidence_id; salida list; lee la base de datos.
def list_reviews(evidence_id):
    return EvidenceReview.query.filter_by(evidence_id=evidence_id).order_by(EvidenceReview.created_at).all()


# Lista los registros que cumplen los filtros indicados; recibe work_order_id, evidence_id; interactua con la base de datos; devuelve el valor correspondiente.
def list_events(work_order_id=None, evidence_id=None):
    q = EvidenceEvent.query
    if work_order_id is not None:
        q = q.filter_by(work_order_id=work_order_id)
    if evidence_id is not None:
        q = q.filter_by(evidence_id=evidence_id)
    return q.order_by(EvidenceEvent.created_at).all()


# Permissions re-export for convenience
def can_view(user_id, roles, work_order):
    return can_view_evidence(user_id, roles, work_order)


# Lista los registros que cumplen los filtros indicados; recibe user_id, roles; interactua con la base de datos; devuelve el valor correspondiente.
def list_user_evidences(user_id, roles):
    roles = set(roles or [])
    if "admin" in roles or "dispatcher" in roles:
        return VisitEvidence.query.order_by(VisitEvidence.received_at.desc()).all()
    from app.workorders.models import WorkOrder
    wo_ids = [w.id for w in WorkOrder.query.filter_by(assigned_to_id=user_id).all()]
    if not wo_ids:
        return []
    return VisitEvidence.query.filter(VisitEvidence.work_order_id.in_(wo_ids)).order_by(VisitEvidence.received_at.desc()).all()


# Obtiene un registro por su identificador; recibe work_order; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def get_default_policy(work_order=None):
    return {
        "required_categories": [],
        "min_photos": 1,
        "signature_required": True,
        "allow_signature_refusal": True,
        "required_checklist": [],
    }


# Valida los datos y reglas de negocio; recibe work_order_id, policy; interactua con la base de datos; devuelve el valor correspondiente.
def validate_submission(work_order_id, policy=None):
    if policy is None:
        wo = get_work_order(work_order_id)
        policy = get_default_policy(wo)
    errors = []
    evidences = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if len(evidences) < int(policy.get("min_photos", 0)):
        errors.append("min_photos_not_met")
    required_cats = set(policy.get("required_categories", []))
    present_cats = {e.category for e in evidences}
    for cat in required_cats:
        if cat not in present_cats:
            errors.append(f"missing_category:{cat}")
    if policy.get("signature_required", True):
        sigs = VisitSignature.query.filter_by(work_order_id=work_order_id).all()
        if not sigs:
            errors.append("signature_or_refusal_required")
        if not policy.get("allow_signature_refusal", True):
            if sigs and all(s.refused for s in sigs):
                errors.append("signature_refusal_not_allowed")
    items = VisitChecklistItem.query.filter_by(work_order_id=work_order_id).all()
    pending = [i for i in items if i.result not in ("COMPLETED", "NOT_COMPLETED")]
    if items and pending:
        errors.append("checklist_incomplete")
    for req in policy.get("required_checklist", []):
        if not any(i.label == req and i.result in ("COMPLETED", "NOT_COMPLETED") for i in items):
            errors.append(f"missing_checklist:{req}")
    ev_statuses = {e.status for e in evidences}
    # Se pueden enviar borradores nuevos aunque el expediente ya esté en revisión o aprobado (vuelve a revisión);
    # un expediente rechazado queda cerrado.
    if EVIDENCE_REJECTED in ev_statuses:
        errors.append("invalid_state")
    return errors


# Obtiene un registro por su identificador; recibe work_order_id; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def get_expediente_status(work_order_id):
    evidences = [e.to_dict() for e in list_evidences(work_order_id)]
    signatures = [s.to_dict() for s in list_signatures(work_order_id)]
    checklist = [i.to_dict() for i in list_checklist_items(work_order_id)]
    events = [e.to_dict() for e in list_events(work_order_id=work_order_id)]
    statuses = {e["status"] for e in evidences} if evidences else set()
    overall = "DRAFT"
    if statuses:
        if "SUBMITTED" in statuses or "UNDER_REVIEW" in statuses:
            overall = "SUBMITTED"
        if "APPROVED" in statuses and len(statuses) == 1:
            overall = "APPROVED"
        if "REJECTED" in statuses:
            overall = "REJECTED"
        if "CORRECTION_REQUIRED" in statuses:
            overall = "CORRECTION_REQUIRED"
    return {
        "work_order_id": work_order_id,
        "status": overall,
        "evidences": evidences,
        "signatures": signatures,
        "checklist": checklist,
        "events": events,
    }


# Lista los registros que cumplen los filtros indicados; recibe status, technician_id, client, work_order_id, date_from, date_to, visit_date_from, visit_date_to, evidence_type, q, page, page_size, sort, order, roles; interactua con la base de datos; devuelve el valor correspondiente.
def list_admin_inbox(
    *,
    status=None,
    technician_id=None,
    client=None,
    work_order_id=None,
    date_from=None,
    date_to=None,
    visit_date_from=None,
    visit_date_to=None,
    evidence_type=None,
    q=None,
    page=1,
    page_size=20,
    sort="received_at",
    order="desc",
    roles=None,
):
    from app.workorders.models import WorkOrder
    from datetime import datetime

    veq = VisitEvidence.query
    if status:
        veq = veq.filter(VisitEvidence.status == status)
    if evidence_type:
        veq = veq.filter(VisitEvidence.category == evidence_type)
    if work_order_id:
        veq = veq.filter(VisitEvidence.work_order_id == int(work_order_id))
    # technician filter via work order
    if technician_id:
        wo_ids = [w.id for w in WorkOrder.query.filter_by(assigned_to_id=int(technician_id)).all()]
        veq = veq.filter(VisitEvidence.work_order_id.in_(wo_ids if wo_ids else [-1]))
    if date_from:
        try:
            df = datetime.fromisoformat(str(date_from).replace("Z", "+00:00"))
            veq = veq.filter(VisitEvidence.received_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(str(date_to).replace("Z", "+00:00"))
            veq = veq.filter(VisitEvidence.received_at <= dt)
        except ValueError:
            pass

    candidate_wo_ids = {v.work_order_id for v in veq.all()}

    wq = WorkOrder.query
    if candidate_wo_ids:
        wq = wq.filter(WorkOrder.id.in_(candidate_wo_ids))
    else:
        wq = wq.filter(WorkOrder.id == -1)
    if client:
        like = f"%{client}%"
        wq = wq.filter(WorkOrder.customer_name.ilike(like))
    if q:
        like = f"%{q}%"
        wq = wq.filter(
            db.or_(
                WorkOrder.title.ilike(like),
                WorkOrder.customer_name.ilike(like),
                db.cast(WorkOrder.id, db.String).ilike(like),
            )
        )
    if visit_date_from:
        try:
            df = datetime.fromisoformat(str(visit_date_from).replace("Z", "+00:00"))
            wq = wq.filter(WorkOrder.scheduled_at >= df)
        except ValueError:
            pass
    if visit_date_to:
        try:
            dt = datetime.fromisoformat(str(visit_date_to).replace("Z", "+00:00"))
            wq = wq.filter(WorkOrder.scheduled_at <= dt)
        except ValueError:
            pass

    total = wq.count()
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    items = wq.order_by(WorkOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # counts by status across candidate set
    counts = {}
    for st in EVIDENCE_STATES:
        q2 = VisitEvidence.query.filter(VisitEvidence.status == st)
        if technician_id:
            wo_ids = [w.id for w in WorkOrder.query.filter_by(assigned_to_id=int(technician_id)).all()]
            q2 = q2.filter(VisitEvidence.work_order_id.in_(wo_ids if wo_ids else [-1]))
        counts[st] = q2.with_entities(VisitEvidence.work_order_id).distinct().count()

    result_items = []
    for wo in items:
        evs = VisitEvidence.query.filter_by(work_order_id=wo.id).all()
        statuses = {e.status for e in evs}
        overall = _overall_validation_status(statuses) or "DRAFT"
        result_items.append({
            "work_order": wo.to_dict(),
            "validation_status": overall,
            "evidence_count": len(evs),
            "statuses": sorted(statuses),
        })

    return {
        "items": result_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": counts,
    }


# Obtiene un registro por su identificador; recibe work_order_id; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def get_admin_detail(work_order_id):
    from app.workorders.models import WorkOrder
    wo = get_work_order(work_order_id)
    if not wo:
        return None
    status = get_expediente_status(work_order_id)
    def _clean(ev):
        ev = dict(ev)
        ev.pop("storage_key", None)
        ev.pop("stored_name", None)
        return ev
    status["evidences"] = [_clean(e) for e in status["evidences"]]
    reviews = []
    for ev in list_evidences(work_order_id):
        reviews.extend([r.to_dict() for r in list_reviews(ev.id)])
    status["reviews"] = reviews
    status["work_order"] = wo.to_dict()
    return status


# Gestiona start review admin; recibe work_order_id, actor_id, roles, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def start_review_admin(work_order_id, actor_id, roles=None, operation_id=None):
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    _lock_row("Evidencias", extra="IdOrden = :wo", params={"wo": work_order_id})
    evs = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if not evs:
        return None, "not_found"
    if all(e.status in (EVIDENCE_UNDER_REVIEW, EVIDENCE_APPROVED, EVIDENCE_REJECTED) for e in evs):
        return evs, None
    changed = False
    for ev in evs:
        if ev.status in (EVIDENCE_SUBMITTED, EVIDENCE_RESUBMITTED):
            ev.status = EVIDENCE_UNDER_REVIEW
            changed = True
    if changed:
        _record_event(work_order_id, None, actor_id, "ADMIN_REVIEW_STARTED", None, EVIDENCE_UNDER_REVIEW, f"operation={operation_id}")
        db.session.commit()
    return evs, None


# Gestiona request correction admin; recibe work_order_id, actor_id, notes, items, roles, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def request_correction_admin(work_order_id, actor_id, *, notes=None, items=None, roles=None, operation_id=None):
    if roles is not None and "admin" not in set(roles or []):
        return None, "forbidden"
    if not notes:
        return None, "notes_required"
    _lock_row("Evidencias", extra="IdOrden = :wo", params={"wo": work_order_id})
    evs = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if not evs:
        return None, "not_found"
    if any(e.uploaded_by_id == actor_id for e in evs):
        return None, "own_evidence"
    changed = False
    for ev in evs:
        if ev.status in (EVIDENCE_SUBMITTED, EVIDENCE_UNDER_REVIEW, EVIDENCE_RESUBMITTED):
            ev.status = EVIDENCE_CORRECTION_REQUIRED
            changed = True
    if not changed:
        return None, "invalid_state"
    _record_event(work_order_id, None, actor_id, "CORRECTION_REQUESTED", None, EVIDENCE_CORRECTION_REQUIRED, notes)
    db.session.commit()
    return evs, None


# _review_blocker(evs, actor_id): motivo por el que un expediente no puede aprobarse, o None.
#   own_evidence: el revisor registró alguna de las evidencias (nadie aprueba lo propio, aunque tenga varios roles).
#   pending_drafts: hay evidencias que el técnico todavía no envió a revisión.
#   correction_pending / already_rejected: el expediente está en otro punto del flujo.
def _review_blocker(evs, actor_id):
    statuses = {e.status for e in evs}
    if any(e.uploaded_by_id == actor_id for e in evs):
        return "own_evidence"
    if EVIDENCE_REJECTED in statuses:
        return "already_rejected"
    if EVIDENCE_CORRECTION_REQUIRED in statuses:
        return "correction_pending"
    if EVIDENCE_DRAFT in statuses:
        return "pending_drafts"
    return None


# Gestiona approve expediente; recibe work_order_id, actor_id, roles, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def approve_expediente(work_order_id, actor_id, roles=None, operation_id=None):
    if roles is not None and "admin" not in set(roles or []):
        return None, "forbidden"
    _lock_row("Evidencias", extra="IdOrden = :wo", params={"wo": work_order_id})
    evs = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if not evs:
        return None, "not_found"
    if all(e.status == EVIDENCE_APPROVED for e in evs):
        return evs, None  # ya aprobado: idempotente, sin registros de aprobación duplicados
    blocker = _review_blocker(evs, actor_id)
    if blocker:
        return None, blocker
    for ev in evs:
        if ev.status == EVIDENCE_APPROVED:
            continue
        ev.status = EVIDENCE_APPROVED
        db.session.add(EvidenceReview(evidence_id=ev.id, reviewer_id=actor_id, decision=EVIDENCE_APPROVED, notes=None, created_at=datetime.now(timezone.utc)))
    _record_event(work_order_id, None, actor_id, "APPROVED", None, EVIDENCE_APPROVED, f"operation={operation_id}")
    db.session.commit()
    return evs, None


# Gestiona reject expediente; recibe work_order_id, actor_id, reason, roles, operation_id; interactua con la base de datos; devuelve el valor correspondiente.
def reject_expediente(work_order_id, actor_id, *, reason=None, roles=None, operation_id=None):
    if roles is not None and "admin" not in set(roles or []):
        return None, "forbidden"
    if not reason:
        return None, "reason_required"
    _lock_row("Evidencias", extra="IdOrden = :wo", params={"wo": work_order_id})
    evs = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if not evs:
        return None, "not_found"
    if any(e.uploaded_by_id == actor_id for e in evs):
        return None, "own_evidence"
    if all(e.status == EVIDENCE_REJECTED for e in evs):
        return evs, None
    changed = False
    for ev in evs:
        if ev.status in (EVIDENCE_SUBMITTED, EVIDENCE_UNDER_REVIEW, EVIDENCE_RESUBMITTED, EVIDENCE_CORRECTION_REQUIRED):
            ev.status = EVIDENCE_REJECTED
            db.session.add(EvidenceReview(evidence_id=ev.id, reviewer_id=actor_id, decision=EVIDENCE_REJECTED, notes=reason, created_at=datetime.now(timezone.utc)))
            changed = True
    if not changed:
        return None, "invalid_state"
    _record_event(work_order_id, None, actor_id, "REJECTED", None, EVIDENCE_REJECTED, reason)
    db.session.commit()
    return evs, None


Evidence = VisitEvidence
create_evidence = create_evidence


# _overall_validation_status: estado de validacion de un expediente a partir de los estados de sus evidencias.
def _overall_validation_status(statuses):
    statuses = set(statuses or [])
    if not statuses:
        return None
    if "CORRECTION_REQUIRED" in statuses:
        return "CORRECTION_REQUIRED"
    if "REJECTED" in statuses:
        return "REJECTED"
    if statuses & {"SUBMITTED", "UNDER_REVIEW", "RESUBMITTED"}:
        return "SUBMITTED"
    if statuses == {"APPROVED"}:
        return "APPROVED"
    return "DRAFT"


def _parse_date_param(value, end_of_day=False):
    if not value:
        return None
    raw = str(value).strip()
    try:
        if len(raw) == 10:
            d = datetime.fromisoformat(raw)
            if end_of_day:
                d = d.replace(hour=23, minute=59, second=59, microsecond=999999)
            return d.replace(tzinfo=timezone.utc)
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("invalid_date")


# list_evidence_orders: listado de ordenes con el resumen de sus evidencias (cantidad, ultima fecha de registro,
# tecnico, estado), paginado y sin cargar archivos. Alcance por rol en el servidor: admin y coordinador ven todas las
# ordenes; un tecnico solo las asignadas a el (misma regla que can_access_work_order).
#   q: numero de orden ("12", "OS-0012") o texto del titulo/cliente; technician_id; date_from/date_to sobre la fecha
#   de registro de las evidencias; with_evidence: solo ordenes que tengan evidencias; order: asc|desc por fecha.
def list_evidence_orders(user_id, roles, *, q=None, technician_id=None, date_from=None, date_to=None,
                         with_evidence=False, order="desc", page=1, page_size=20):
    import re
    import sqlalchemy as sa
    from app.workorders.models import WorkOrder

    roles = set(roles or [])
    df = _parse_date_param(date_from)
    dt = _parse_date_param(date_to, end_of_day=True)

    agg = db.session.query(
        VisitEvidence.work_order_id.label("wo_id"),
        db.func.count(VisitEvidence.id).label("evidence_count"),
        db.func.max(VisitEvidence.received_at).label("last_at"),
    )
    if df:
        agg = agg.filter(VisitEvidence.received_at >= df)
    if dt:
        agg = agg.filter(VisitEvidence.received_at <= dt)
    agg = agg.group_by(VisitEvidence.work_order_id).subquery()

    query = db.session.query(WorkOrder, agg.c.evidence_count, agg.c.last_at)
    if with_evidence or df or dt:
        query = query.join(agg, agg.c.wo_id == WorkOrder.id)
    else:
        query = query.outerjoin(agg, agg.c.wo_id == WorkOrder.id)

    if not ({"admin", "dispatcher"} & roles):
        query = query.filter(WorkOrder.assigned_to_id == user_id)
    elif technician_id:
        query = query.filter(WorkOrder.assigned_to_id == int(technician_id))

    if q:
        text = str(q).strip()
        m = re.fullmatch(r"(?:os-?)?0*(\d{1,9})", text, flags=re.IGNORECASE)
        if m:
            query = query.filter(WorkOrder.id == int(m.group(1)))
        else:
            like = f"%{text}%"
            query = query.filter(db.or_(WorkOrder.title.ilike(like), WorkOrder.customer_name.ilike(like)))

    total = query.order_by(None).count()
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    # Ordenes sin evidencias siempre al final, en ambos sentidos (SQL Server ordena NULL primero en ASC).
    no_evidence_last = sa.case((agg.c.last_at.is_(None), 1), else_=0)
    date_order = agg.c.last_at.asc() if str(order).lower() == "asc" else agg.c.last_at.desc()
    rows = (
        query.order_by(no_evidence_last, date_order, WorkOrder.id.desc())
        .offset((page - 1) * page_size).limit(page_size).all()
    )

    wo_ids = [wo.id for wo, _, _ in rows]
    statuses = {}
    if wo_ids:
        for wo_id, st in (
            db.session.query(VisitEvidence.work_order_id, VisitEvidence.status)
            .filter(VisitEvidence.work_order_id.in_(wo_ids)).distinct().all()
        ):
            statuses.setdefault(wo_id, set()).add(st)

    items = []
    for wo, count, last_at in rows:
        tech = wo.assigned_to
        items.append({
            "work_order": {
                "id": wo.id,
                "code": "OS-" + str(wo.id).zfill(4),
                "title": wo.title,
                "description": wo.description,
                "customer_name": wo.customer_name,
                "status": wo.status,
            },
            "technician": {"id": tech.id, "username": tech.username} if tech else None,
            "evidence_count": int(count or 0),
            "last_evidence_at": last_at.isoformat() if last_at else None,
            "validation_status": _overall_validation_status(statuses.get(wo.id)),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
