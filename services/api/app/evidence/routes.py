from flask import Blueprint, request, jsonify, send_file

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.identity.models import User
from app.evidence.models import ALL_TYPES
from app.evidence.service import create_evidence, list_evidences, get_evidence, delete_evidence
from app.evidence.storage import get_storage
from app.workorders.service import get_work_order

blueprint = Blueprint("evidence", __name__)


@blueprint.post("/work-orders/<int:wo_id>/evidences")
@require_auth
def evidences_create(wo_id):
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404

    is_admin = "admin" in request.user_roles
    is_dispatcher = "dispatcher" in request.user_roles
    is_assigned = wo.assigned_to_id == request.user_id
    if not (is_admin or is_dispatcher or is_assigned):
        return jsonify({"error": "insufficient permissions"}), 403

    evidence_type = request.form.get("evidence_type", "observation")
    if evidence_type not in ALL_TYPES:
        return jsonify({"error": "invalid evidence_type"}), 400

    file = request.files.get("file")
    if evidence_type in ("photo", "document") and not file:
        return jsonify({"error": "file required for photo or document"}), 400

    ev, error = create_evidence(
        wo_id, request.user_id, evidence_type,
        file=file, description=request.form.get("description"),
    )
    if error == "invalid_extension":
        return jsonify({"error": "file type not allowed"}), 400
    if error == "file_too_large":
        return jsonify({"error": "file too large (max 10MB)"}), 400
    return jsonify(ev.to_dict()), 201


@blueprint.get("/work-orders/<int:wo_id>/evidences")
@require_auth
def evidences_list(wo_id):
    wo = get_work_order(wo_id)
    if not wo:
        return jsonify({"error": "work order not found"}), 404
    evidences = list_evidences(wo_id)
    return jsonify([e.to_dict() for e in evidences]), 200


@blueprint.get("/evidences/<int:ev_id>/download")
@require_auth
def evidences_download(ev_id):
    ev = get_evidence(ev_id)
    if not ev:
        return jsonify({"error": "evidence not found"}), 404
    if not ev.stored_name:
        return jsonify({"error": "no file to download"}), 400
    storage = get_storage()
    path = storage.load(ev.stored_name)
    if not path:
        return jsonify({"error": "file not found on storage"}), 404
    return send_file(path, mimetype=ev.file_type, download_name=ev.file_name, as_attachment=True)


@blueprint.delete("/evidences/<int:ev_id>")
@require_role("admin")
def evidences_delete(ev_id):
    deleted = delete_evidence(ev_id)
    if not deleted:
        return jsonify({"error": "evidence not found"}), 404
    return jsonify({"message": "deleted"}), 200
