# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, send_file

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.identity.models import User
from app.evidence.models import ALL_TYPES, EVIDENCE_CATEGORIES
from app.evidence.service import (
    create_evidence,
    add_evidence,
    list_evidences,
    get_evidence,
    delete_evidence,
    submit_evidence,
    start_review,
    request_correction,
    resubmit_evidence,
    approve_evidence,
    reject_evidence,
    review_evidence,
    submit_expediente,
    start_review_expediente,
    register_signature,
    register_signature_refusal,
    list_signatures,
    get_signature,
    add_checklist_item,
    update_checklist_item,
    list_checklist_items,
    create_review,
    list_reviews,
    list_events,
    list_user_evidences,
    validate_submission,
    resubmit_expediente,
    get_expediente_status,
)
from app.evidence.storage import get_storage
from app.evidence.permissions import (
    can_access_work_order,
    can_create_evidence,
    can_view_evidence,
    can_download_evidence,
    can_review_evidence,
)
from app.workorders.service import get_work_order

blueprint = Blueprint("evidence", __name__)


def _wo_or_404(wo_id):
    wo = get_work_order(wo_id)
    if not wo:
        return None, (jsonify({"error": "work order not found"}), 404)
    return wo, None


def _access(wo, roles):
    return can_access_work_order(request.user_id, roles, wo)


@blueprint.post("/work-orders/<int:wo_id>/evidences")
@require_auth
def evidences_create(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403

    evidence_type = request.form.get("evidence_type", "observation")
    category = request.form.get("category", "ADDITIONAL")
    if category not in EVIDENCE_CATEGORIES:
        category = "ADDITIONAL"
    if evidence_type not in ALL_TYPES and evidence_type not in EVIDENCE_CATEGORIES:
        pass

    file = request.files.get("file")
    if evidence_type in ("photo", "document") and not file and category in ("BEFORE", "DURING", "AFTER"):
        # file optional for category-based uploads; keep legacy requirement
        pass

    operation_id = request.form.get("operation_id") or request.form.get("client_operation_id")

    ev, error = add_evidence(
        wo_id, request.user_id,
        category=category,
        file=file,
        original_name=(file.filename if file else request.form.get("original_name")),
        declared_mime=request.form.get("mime_type"),
        description=request.form.get("description"),
        declared_capture_at=request.form.get("declared_capture_at") or request.form.get("capture_date"),
        roles=roles,
        operation_id=operation_id,
    )
    if error in ("invalid_extension", "mime_not_allowed", "unknown_content_type", "empty_file", "invalid_image", "invalid_pdf"):
        return jsonify({"error": "file type not allowed"}), 400
    if error == "file_too_large":
        return jsonify({"error": "file too large"}), 400
    if error:
        return jsonify({"error": error}), 400
    return jsonify(ev.to_dict()), 201


@blueprint.get("/work-orders/<int:wo_id>/evidences")
@require_auth
def evidences_list(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    evidences = list_evidences(wo_id)
    return jsonify([e.to_dict() for e in evidences]), 200


@blueprint.get("/evidences/<int:ev_id>")
@require_auth
def evidence_detail(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    wo = get_work_order(ev.work_order_id)
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify(ev.to_dict()), 200


@blueprint.get("/evidences")
@require_auth
def evidences_list_mine():
    roles = request.user_roles
    items = list_user_evidences(request.user_id, roles)
    return jsonify([e.to_dict() for e in items]), 200


@blueprint.get("/evidences/<int:ev_id>/download")
@require_auth
def evidences_download(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    wo = get_work_order(ev.work_order_id)
    roles = request.user_roles
    if not can_download_evidence(request.user_id, roles, wo):
        return jsonify({"error": "insufficient permissions"}), 403
    storage_key = ev.storage_key or ev.stored_name
    if not storage_key:
        return jsonify({"error": "no file to download"}), 400
    storage = get_storage()
    path = storage.load(storage_key)
    if not path:
        return jsonify({"error": "file not found on storage"}), 404
    return send_file(path, mimetype=ev.mime_type or ev.file_type, download_name=ev.original_name or ev.file_name, as_attachment=True)


@blueprint.delete("/evidences/<int:ev_id>")
@require_role("admin")
def evidences_delete(ev_id):
    deleted, error = delete_evidence(ev_id, roles=["admin"], actor_id=request.user_id)
    if not deleted:
        return jsonify({"error": error or "not found"}), 404
    return jsonify({"message": "deleted"}), 200


# Expediente status / detail
@blueprint.get("/work-orders/<int:wo_id>/evidence-status")
@require_auth
def evidence_status(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify(get_expediente_status(wo_id)), 200


@blueprint.get("/work-orders/<int:wo_id>/evidence")
@require_auth
def evidence_expediente_detail(wo_id):
    return evidence_status(wo_id)


# Submit
@blueprint.post("/work-orders/<int:wo_id>/evidences/submit")
@require_auth
def evidence_submit(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    data = request.get_json() or {}
    from app.evidence.models import VisitEvidence
    drafts = VisitEvidence.query.filter_by(work_order_id=wo_id, status="DRAFT").all()
    corrected = VisitEvidence.query.filter_by(work_order_id=wo_id, status="CORRECTION_REQUIRED").all()
    if not drafts and not corrected:
        submitted = VisitEvidence.query.filter_by(work_order_id=wo_id, status="SUBMITTED").all()
        if submitted:
            return jsonify({"submitted": 0, "status": "SUBMITTED", "idempotent": True}), 200
    errors = validate_submission(wo_id)
    if errors:
        return jsonify({"error": "incomplete_expediente", "details": errors}), 400
    items, error = submit_expediente(wo_id, request.user_id, roles=roles, operation_id=data.get("operation_id"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"submitted": len(items), "status": "SUBMITTED"}), 200


@blueprint.post("/work-orders/<int:wo_id>/evidences/send")
@require_auth
def evidence_send_alias(wo_id):
    return evidence_submit(wo_id)


@blueprint.post("/evidences/<int:ev_id>/submit")
@require_auth
def evidence_submit_single(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    wo = get_work_order(ev.work_order_id)
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    data = request.get_json() or {}
    res, error = submit_evidence(ev_id, request.user_id, roles=roles, notes=data.get("notes"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify(res.to_dict()), 200


# Resubmit after corrections
@blueprint.post("/work-orders/<int:wo_id>/evidences/resubmit")
@require_auth
def evidence_resubmit(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    data = request.get_json() or {}
    res, error = resubmit_expediente(wo_id, request.user_id, roles=roles, operation_id=data.get("operation_id"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"status": "RESUBMITTED"}), 200


@blueprint.post("/work-orders/<int:wo_id>/resubmit")
@require_auth
def evidence_resubmit_alias(wo_id):
    return evidence_resubmit(wo_id)


# Signatures
@blueprint.post("/work-orders/<int:wo_id>/signatures")
@require_auth
def signatures_create(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        file = request.files.get("file")
        data = request.form
    else:
        file = None
        data = request.get_json() or {}
    refused = str(data.get("refused", "")).lower() in ("true", "1", "yes")
    operation_id = data.get("operation_id") or data.get("client_operation_id")
    if refused:
        sig, error = register_signature_refusal(
            wo_id, request.user_id,
            signer_name=data.get("signer_name") or data.get("signer"),
            reason=data.get("reason") or data.get("refusal_reason"),
            roles=roles,
        )
    else:
        sig, error = register_signature(
            wo_id, request.user_id,
            file=file,
            signer_name=data.get("signer_name") or data.get("signer"),
            signer_role=data.get("signer_role") or data.get("role") or data.get("position"),
            acceptance_text=data.get("acceptance_text") or data.get("consent_text"),
            consent_version=data.get("consent_version"),
            roles=roles,
            original_name=(file.filename if file else None),
            operation_id=operation_id,
        )
    if error:
        return jsonify({"error": error}), 400
    return jsonify(sig.to_dict()), 201


@blueprint.get("/work-orders/<int:wo_id>/signatures")
@require_auth
def signatures_list(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify([s.to_dict() for s in list_signatures(wo_id)]), 200


# Checklist
@blueprint.post("/work-orders/<int:wo_id>/checklist")
@require_auth
def checklist_create(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    data = request.get_json() or {}
    label = data.get("label") or data.get("description") or data.get("activity")
    if not label:
        return jsonify({"error": "label required"}), 400
    item, error = add_checklist_item(
        wo_id, label,
        result=data.get("result") or data.get("status"),
        notes=data.get("notes") or data.get("observation"),
        actor_id=request.user_id,
        roles=roles,
    )
    if error:
        return jsonify({"error": error}), 400
    return jsonify(item.to_dict()), 201


@blueprint.get("/work-orders/<int:wo_id>/checklist")
@require_auth
def checklist_list(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify([i.to_dict() for i in list_checklist_items(wo_id)]), 200


@blueprint.patch("/checklist/<int:item_id>")
@require_auth
def checklist_patch(item_id):
    data = request.get_json() or {}
    item, error = update_checklist_item(
        item_id,
        result=data.get("result") or data.get("status"),
        notes=data.get("notes") or data.get("observation"),
        actor_id=request.user_id,
        roles=request.user_roles,
    )
    if error:
        return jsonify({"error": error}), 400
    # authorization: item's work order
    wo = get_work_order(item.work_order_id)
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify(item.to_dict()), 200


@blueprint.get("/work-orders/<int:wo_id>/evidence-events")
@require_auth
def evidence_events_list(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles):
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify([e.to_dict() for e in list_events(work_order_id=wo_id)]), 200


# Admin review endpoints are in E3; keep placeholders minimal
@blueprint.post("/evidences/<int:ev_id>/review")
@require_role("admin", "dispatcher")
def evidence_review(ev_id):
    data = request.get_json() or {}
    decision = data.get("decision")
    if not decision:
        return jsonify({"error": "decision required"}), 400
    review, error = create_review(ev_id, request.user_id, decision, notes=data.get("notes"), roles=request.user_roles)
    if error:
        return jsonify({"error": error}), 400
    return jsonify(review.to_dict()), 201


@blueprint.get("/evidences/<int:ev_id>/reviews")
@require_auth
def evidence_reviews_list(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    wo = get_work_order(ev.work_order_id)
    roles = request.user_roles
    if not _access(wo, roles) and "admin" not in roles and "dispatcher" not in roles:
        return jsonify({"error": "insufficient permissions"}), 403
    return jsonify([r.to_dict() for r in list_reviews(ev_id)]), 200
