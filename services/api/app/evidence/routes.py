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
    list_admin_inbox,
    get_admin_detail,
    start_review_admin,
    request_correction_admin,
    approve_expediente,
    reject_expediente,
    list_evidence_orders,
)
from app.evidence.signatures import (
    SignatureError,
    get_active_signature,
    register_profile_signature,
    load_signature_bytes,
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

# Errores de las acciones de revisión -> (HTTP, mensaje). El código estable va en "code".
REVIEW_ERRORS = {
    "forbidden": (403, "No tiene permisos para revisar evidencias"),
    "not_found": (404, "La orden no tiene evidencias registradas"),
    "own_evidence": (403, "No puede revisar un expediente con evidencias registradas por usted"),
    "pending_drafts": (409, "Hay evidencias que el técnico todavía no envió a revisión"),
    "correction_pending": (409, "El expediente está esperando las correcciones del técnico"),
    "already_rejected": (409, "El expediente ya fue rechazado"),
    "invalid_state": (409, "El expediente no está en un estado que permita esta acción"),
    "notes_required": (422, "Indique qué debe corregir el técnico"),
    "reason_required": (422, "Indique el motivo del rechazo"),
}


def _review_error(error):
    status, message = REVIEW_ERRORS.get(error, (400, error))
    return jsonify({"error": message, "code": error}), status


# _wo_or_404: obtiene la orden de trabajo por id y devuelve 404 si no existe; entrada wo_id; salida (wo, error_response); lee la base de datos.
def _wo_or_404(wo_id):
    wo = get_work_order(wo_id)
    if not wo:
        return None, (jsonify({"error": "work order not found"}), 404)
    return wo, None


# verifica si el usuario autenticado tiene acceso a la orden de trabajo dada; entradas wo, roles; salida bool; sin efectos secundarios adicionales.
def _access(wo, roles):
    return can_access_work_order(request.user_id, roles, wo)


# POST /work-orders/<int:wo_id>/evidences (roles: autenticado): evidences create; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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
        return jsonify({"error": "invalid evidence_type"}), 400

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
    if error == "technician_signature_required":
        return jsonify({
            "error": "Registre su firma en 'Mi firma' antes de adjuntar evidencias",
            "code": "technician_signature_required",
        }), 409
    if error == "forbidden":
        return jsonify({"error": "insufficient permissions"}), 403
    if error:
        return jsonify({"error": error}), 400
    return jsonify(ev.to_dict()), 201


# GET /work-orders/<int:wo_id>/evidences (roles: autenticado): evidences list; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /evidences/<int:ev_id> (roles: autenticado): evidence detail; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /evidences (roles: autenticado): evidences list mine; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/evidences")
@require_auth
def evidences_list_mine():
    roles = request.user_roles
    items = list_user_evidences(request.user_id, roles)
    return jsonify([e.to_dict() for e in items]), 200


# GET /evidences/<int:ev_id>/download (roles: autenticado): evidences download; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# DELETE /evidences/<int:ev_id> (roles: admin): evidences delete; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.delete("/evidences/<int:ev_id>")
@require_role("admin")
def evidences_delete(ev_id):
    deleted, error = delete_evidence(ev_id, roles=["admin"], actor_id=request.user_id)
    if error == "signed_evidence_immutable":
        return jsonify({"error": "La evidencia esta firmada por el tecnico y no puede eliminarse", "code": error}), 409
    if not deleted:
        return jsonify({"error": error or "not found"}), 404
    return jsonify({"message": "deleted"}), 200


# GET /work-orders/<int:wo_id>/evidence-status (roles: autenticado): evidence status; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /work-orders/<int:wo_id>/evidence (roles: autenticado): evidence expediente detail; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/work-orders/<int:wo_id>/evidence")
@require_auth
def evidence_expediente_detail(wo_id):
    return evidence_status(wo_id)


# POST /work-orders/<int:wo_id>/evidences/submit (roles: autenticado): evidence submit; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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
    errors = validate_submission(wo_id, policy=data.get("policy"))
    if errors:
        return jsonify({"error": "incomplete_expediente", "details": errors}), 400
    items, error = submit_expediente(wo_id, request.user_id, roles=roles, operation_id=data.get("operation_id"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"submitted": len(items), "status": "SUBMITTED"}), 200


# POST /work-orders/<int:wo_id>/evidences/send (roles: autenticado): evidence send alias; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/work-orders/<int:wo_id>/evidences/send")
@require_auth
def evidence_send_alias(wo_id):
    return evidence_submit(wo_id)


# POST /evidences/<int:ev_id>/submit (roles: autenticado): evidence submit single; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# POST /work-orders/<int:wo_id>/evidences/resubmit (roles: autenticado): evidence resubmit; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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
        return jsonify({"error": "No hay evidencias pendientes de corrección para reenviar", "code": error}), 409
    return jsonify({"status": "RESUBMITTED"}), 200


# POST /work-orders/<int:wo_id>/resubmit (roles: autenticado): evidence resubmit alias; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/work-orders/<int:wo_id>/resubmit")
@require_auth
def evidence_resubmit_alias(wo_id):
    return evidence_resubmit(wo_id)


# POST /work-orders/<int:wo_id>/signatures (roles: autenticado): signatures create; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /work-orders/<int:wo_id>/signatures (roles: autenticado): signatures list; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# POST /work-orders/<int:wo_id>/checklist (roles: autenticado): checklist create; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /work-orders/<int:wo_id>/checklist (roles: autenticado): checklist list; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# PATCH /checklist/<int:item_id> (roles: autenticado): checklist patch; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /work-orders/<int:wo_id>/evidence-events (roles: autenticado): evidence events list; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# POST /evidences/<int:ev_id>/review (roles: admin, dispatcher): evidence review; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /evidences/<int:ev_id>/reviews (roles: autenticado): evidence reviews list; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
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


# GET /evidences/inbox (roles: admin, dispatcher): evidence inbox; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.

@blueprint.get("/evidences/inbox")
@require_role("admin", "dispatcher")
def evidence_inbox():
    roles = request.user_roles
    data = list_admin_inbox(
        status=request.args.get("status"),
        technician_id=request.args.get("technician_id", type=int),
        client=request.args.get("client"),
        work_order_id=request.args.get("work_order_id", type=int),
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        visit_date_from=request.args.get("visit_date_from"),
        visit_date_to=request.args.get("visit_date_to"),
        evidence_type=request.args.get("evidence_type") or request.args.get("type"),
        q=request.args.get("q"),
        page=request.args.get("page", 1, type=int),
        page_size=request.args.get("page_size", 20, type=int),
        sort=request.args.get("sort", "received_at"),
        order=request.args.get("order", "desc"),
        roles=roles,
    )
    return jsonify(data), 200


# GET /work-orders/<int:wo_id>/evidence-detail (roles: autenticado): evidence admin detail; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/work-orders/<int:wo_id>/evidence-detail")
@require_auth
def evidence_admin_detail(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    roles = request.user_roles
    if not _access(wo, roles) and "admin" not in roles and "dispatcher" not in roles:
        return jsonify({"error": "insufficient permissions"}), 403
    detail = get_admin_detail(wo_id)
    if not detail:
        return jsonify({"error": "not found"}), 404
    return jsonify(detail), 200


# POST /work-orders/<int:wo_id>/evidences/start-review (roles: admin, dispatcher): evidence start review; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/work-orders/<int:wo_id>/evidences/start-review")
@require_role("admin", "dispatcher")
def evidence_start_review(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    data = request.get_json() or {}
    res, error = start_review_admin(wo_id, request.user_id, roles=request.user_roles, operation_id=data.get("operation_id"))
    if error:
        return _review_error(error)
    return jsonify({"status": "UNDER_REVIEW"}), 200


# POST /work-orders/<int:wo_id>/evidences/request-correction (roles: admin): evidence request correction; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/work-orders/<int:wo_id>/evidences/request-correction")
@require_role("admin")
def evidence_request_correction(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    data = request.get_json() or {}
    notes = data.get("notes") or data.get("reason") or data.get("motivo")
    res, error = request_correction_admin(wo_id, request.user_id, notes=notes, items=data.get("items"), roles=request.user_roles, operation_id=data.get("operation_id"))
    if error:
        return _review_error(error)
    return jsonify({"status": "CORRECTION_REQUIRED"}), 200


# POST /work-orders/<int:wo_id>/evidences/approve (roles: admin): evidence approve; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/work-orders/<int:wo_id>/evidences/approve")
@require_role("admin")
def evidence_approve(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    data = request.get_json() or {}
    res, error = approve_expediente(wo_id, request.user_id, roles=request.user_roles, operation_id=data.get("operation_id"))
    if error:
        return _review_error(error)
    return jsonify({"status": "APPROVED"}), 200


# POST /work-orders/<int:wo_id>/evidences/reject (roles: admin): evidence reject; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/work-orders/<int:wo_id>/evidences/reject")
@require_role("admin")
def evidence_reject(wo_id):
    wo, err = _wo_or_404(wo_id)
    if err:
        return err
    data = request.get_json() or {}
    reason = data.get("reason") or data.get("notes") or data.get("motivo")
    res, error = reject_expediente(wo_id, request.user_id, reason=reason, roles=request.user_roles, operation_id=data.get("operation_id"))
    if error:
        return _review_error(error)
    return jsonify({"status": "REJECTED"}), 200


# POST /evidences/<int:ev_id>/start-review (roles: admin, dispatcher): evidence start review single; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/evidences/<int:ev_id>/start-review")
@require_role("admin", "dispatcher")
def evidence_start_review_single(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    return evidence_start_review(ev.work_order_id)


# POST /evidences/<int:ev_id>/request-correction (roles: admin): evidence request correction single; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/evidences/<int:ev_id>/request-correction")
@require_role("admin")
def evidence_request_correction_single(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    return evidence_request_correction(ev.work_order_id)


# POST /evidences/<int:ev_id>/approve (roles: admin): evidence approve single; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/evidences/<int:ev_id>/approve")
@require_role("admin")
def evidence_approve_single(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    return evidence_approve(ev.work_order_id)


# POST /evidences/<int:ev_id>/reject (roles: admin): evidence reject single; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/evidences/<int:ev_id>/reject")
@require_role("admin")
def evidence_reject_single(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    return evidence_reject(ev.work_order_id)


# _png_response: imagen de firma sin cache (la politica no-store se aplica a toda la API).
def _png_response(data):
    from flask import Response
    resp = Response(data, mimetype="image/png")
    resp.headers["Content-Disposition"] = "inline; filename=firma.png"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# GET /evidences/orders (roles: autenticado): ordenes con resumen de evidencias, paginado y sin archivos.
# El alcance lo decide el servidor: un tecnico solo ve sus ordenes asignadas (technician_id se ignora para el).
@blueprint.get("/evidences/orders")
@require_auth
def evidence_orders_list():
    try:
        data = list_evidence_orders(
            request.user_id, request.user_roles,
            q=request.args.get("q"),
            technician_id=request.args.get("technician_id", type=int),
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
            with_evidence=request.args.get("with_evidence") in ("1", "true", "yes"),
            order=request.args.get("order", "desc"),
            page=request.args.get("page", 1, type=int),
            page_size=request.args.get("page_size", 20, type=int),
        )
    except ValueError:
        return jsonify({"error": "fecha invalida", "code": "invalid_date"}), 400
    return jsonify(data), 200


# GET /evidences/<id>/technician-signature (roles: autenticado con acceso a la orden): imagen de la firma historica
# con la que se registro la evidencia. Se verifica que el archivo coincida con la huella copiada en la evidencia.
@blueprint.get("/evidences/<int:ev_id>/technician-signature")
@require_auth
def evidence_technician_signature(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    wo = get_work_order(ev.work_order_id)
    if not can_view_evidence(request.user_id, request.user_roles, wo):
        return jsonify({"error": "insufficient permissions"}), 403
    if not ev.technician_signature_id:
        return jsonify({"error": "La evidencia no tiene firma del tecnico", "code": "no_signature"}), 404
    data, error = load_signature_bytes(ev.technician_signature, expected_sha256=ev.technician_signature_sha256)
    if error == "signature_integrity_error":
        return jsonify({"error": "La firma no coincide con la registrada", "code": error}), 409
    if error:
        return jsonify({"error": "Archivo de firma no disponible", "code": error}), 404
    return _png_response(data)


# GET /me/signature (roles: tecnico): metadatos de la firma de perfil vigente del usuario autenticado.
@blueprint.get("/me/signature")
@require_role("technician")
def my_signature():
    sig = get_active_signature(request.user_id)
    return jsonify({"signature": sig.to_dict() if sig else None}), 200


# GET /me/signature/image (roles: tecnico): imagen de la firma de perfil vigente (vista previa).
@blueprint.get("/me/signature/image")
@require_role("technician")
def my_signature_image():
    sig = get_active_signature(request.user_id)
    if not sig:
        return jsonify({"error": "Sin firma registrada", "code": "no_signature"}), 404
    data, error = load_signature_bytes(sig)
    if error:
        return jsonify({"error": "Archivo de firma no disponible", "code": error}), 409 if error == "signature_integrity_error" else 404
    return _png_response(data)


# POST /me/signature (roles: tecnico): registra una nueva version de la firma del usuario autenticado.
# Cuerpo JSON {"image": "data:image/png;base64,..."} generado por el recuadro de dibujo. El propietario es siempre
# el usuario del token; cualquier user_id del cuerpo se ignora. Las versiones anteriores se conservan intactas.
@blueprint.post("/me/signature")
@require_role("technician")
def my_signature_register():
    import base64
    import binascii
    data = request.get_json(silent=True)
    raw = data.get("image") if isinstance(data, dict) else None
    if not isinstance(raw, str) or not raw:
        return jsonify({"error": "Firma requerida", "code": "signature_empty"}), 400
    prefix = "data:image/png;base64,"
    if raw.startswith("data:"):
        if not raw.startswith(prefix):
            return jsonify({"error": "La firma debe capturarse en el recuadro de dibujo (PNG)", "code": "signature_invalid_format"}), 400
        raw = raw[len(prefix):]
    try:
        png = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return jsonify({"error": "Firma con formato invalido", "code": "signature_invalid_format"}), 400
    try:
        sig = register_profile_signature(request.user_id, png)
    except SignatureError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), exc.status
    return jsonify({"signature": sig.to_dict()}), 201
