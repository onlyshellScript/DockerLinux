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


def _now():
    return datetime.now(timezone.utc)


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
        # compatibility columns
        file_name=name,
        stored_name=storage_key,
        file_type=mime_type,
        file_size=size_bytes,
        created_at=_now(),
    )
    db.session.add(ev)
    db.session.flush()
    _record_event(work_order_id, ev.id, uploaded_by_id, "EVIDENCE_ADDED", EVIDENCE_DRAFT, EVIDENCE_DRAFT, f"category={category}")
    db.session.commit()
    return ev, None


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


def list_evidences(work_order_id):
    return VisitEvidence.query.filter_by(work_order_id=work_order_id).order_by(VisitEvidence.received_at.desc(), VisitEvidence.id.desc()).all()


def get_evidence(ev_id):
    return db.session.get(VisitEvidence, ev_id)


def delete_evidence(ev_id, roles=None, actor_id=None):
    ev = db.session.get(VisitEvidence, ev_id)
    if not ev:
        return False, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return False, "forbidden"
    if ev.storage_key or ev.stored_name:
        storage = get_storage()
        storage.delete(ev.storage_key or ev.stored_name)
    db.session.delete(ev)
    db.session.commit()
    return True, None


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


def submit_evidence(evidence_id, actor_id, roles=None, notes=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    wo = get_work_order(ev.work_order_id)
    if roles is not None and not can_create_evidence(actor_id, roles, wo):
        return None, "forbidden"
    return _transition(ev, EVIDENCE_SUBMITTED, actor_id, "SUBMIT", notes)


def start_review(evidence_id, actor_id, roles=None, notes=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    return _transition(ev, EVIDENCE_UNDER_REVIEW, actor_id, "REVIEW_STARTED", notes)


def request_correction(evidence_id, actor_id, notes=None, roles=None):
    ev = db.session.get(VisitEvidence, evidence_id)
    if ev is None:
        return None, "not_found"
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    if not notes:
        return None, "notes_required"
    return _transition(ev, EVIDENCE_CORRECTION_REQUIRED, actor_id, "CORRECTION_REQUESTED", notes)


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


def resubmit_expediente(work_order_id, actor_id, roles=None, operation_id=None):
    # requires correction state
    corrected = VisitEvidence.query.filter_by(work_order_id=work_order_id, status=EVIDENCE_CORRECTION_REQUIRED).all()
    out = []
    for ev in corrected:
        r, err = resubmit_evidence(ev.id, actor_id, roles=roles)
        if r:
            out.append(r)
    if out:
        _record_event(work_order_id, None, actor_id, "EXPEDIENTE_RESUBMITTED", None, EVIDENCE_RESUBMITTED, f"count={len(out)};operation={operation_id}")
        db.session.commit()
    return out, None if out else (None, "invalid_state")


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


# Signatures
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


def list_signatures(work_order_id):
    return VisitSignature.query.filter_by(work_order_id=work_order_id).order_by(VisitSignature.received_at.desc()).all()


def get_signature(sig_id):
    return db.session.get(VisitSignature, sig_id)


# Checklist
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


def list_checklist_items(work_order_id):
    return VisitChecklistItem.query.filter_by(work_order_id=work_order_id).order_by(VisitChecklistItem.id).all()


# Reviews
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


def list_reviews(evidence_id):
    return EvidenceReview.query.filter_by(evidence_id=evidence_id).order_by(EvidenceReview.created_at).all()


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


def list_user_evidences(user_id, roles):
    roles = set(roles or [])
    if "admin" in roles or "dispatcher" in roles:
        return VisitEvidence.query.order_by(VisitEvidence.received_at.desc()).all()
    from app.workorders.models import WorkOrder
    wo_ids = [w.id for w in WorkOrder.query.filter_by(assigned_to_id=user_id).all()]
    if not wo_ids:
        return []
    return VisitEvidence.query.filter(VisitEvidence.work_order_id.in_(wo_ids)).order_by(VisitEvidence.received_at.desc()).all()


def get_default_policy(work_order=None):
    return {
        "required_categories": [],
        "min_photos": 1,
        "signature_required": True,
        "allow_signature_refusal": True,
        "required_checklist": [],
    }


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
    if ev_statuses and not ev_statuses.issubset({EVIDENCE_DRAFT, EVIDENCE_CORRECTION_REQUIRED, EVIDENCE_RESUBMITTED}):
        errors.append("invalid_state")
    return errors


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
        overall = "DRAFT"
        if statuses:
            if "CORRECTION_REQUIRED" in statuses:
                overall = "CORRECTION_REQUIRED"
            elif "REJECTED" in statuses:
                overall = "REJECTED"
            elif "SUBMITTED" in statuses or "UNDER_REVIEW" in statuses or "RESUBMITTED" in statuses:
                overall = "SUBMITTED"
            elif statuses == {"APPROVED"}:
                overall = "APPROVED"
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


def get_admin_detail(work_order_id):
    from app.workorders.models import WorkOrder
    wo = get_work_order(work_order_id)
    if not wo:
        return None
    status = get_expediente_status(work_order_id)
    # strip sensitive keys
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


def start_review_admin(work_order_id, actor_id, roles=None, operation_id=None):
    if roles is not None and not can_review_evidence(roles):
        return None, "forbidden"
    _lock_row("visit_evidences", extra="work_order_id = :wo", params={"wo": work_order_id})
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


def request_correction_admin(work_order_id, actor_id, *, notes=None, items=None, roles=None, operation_id=None):
    if roles is not None and "admin" not in set(roles or []):
        return None, "forbidden"
    if not notes:
        return None, "notes_required"
    _lock_row("visit_evidences", extra="work_order_id = :wo", params={"wo": work_order_id})
    evs = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if not evs:
        return None, "not_found"
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


def approve_expediente(work_order_id, actor_id, roles=None, operation_id=None):
    if roles is not None and "admin" not in set(roles or []):
        return None, "forbidden"
    _lock_row("visit_evidences", extra="work_order_id = :wo", params={"wo": work_order_id})
    evs = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if not evs:
        return None, "not_found"
    if all(e.status == EVIDENCE_APPROVED for e in evs):
        return evs, None
    if not all(e.status in (EVIDENCE_UNDER_REVIEW, EVIDENCE_SUBMITTED, EVIDENCE_RESUBMITTED) for e in evs):
        return None, "invalid_state"
    for ev in evs:
        ev.status = EVIDENCE_APPROVED
        db.session.add(EvidenceReview(evidence_id=ev.id, reviewer_id=actor_id, decision=EVIDENCE_APPROVED, notes=None, created_at=datetime.now(timezone.utc)))
    _record_event(work_order_id, None, actor_id, "APPROVED", None, EVIDENCE_APPROVED, f"operation={operation_id}")
    db.session.commit()
    return evs, None


def reject_expediente(work_order_id, actor_id, *, reason=None, roles=None, operation_id=None):
    if roles is not None and "admin" not in set(roles or []):
        return None, "forbidden"
    if not reason:
        return None, "reason_required"
    _lock_row("visit_evidences", extra="work_order_id = :wo", params={"wo": work_order_id})
    evs = VisitEvidence.query.filter_by(work_order_id=work_order_id).all()
    if not evs:
        return None, "not_found"
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


# Backwards-compatible aliases
Evidence = VisitEvidence
create_evidence = create_evidence
