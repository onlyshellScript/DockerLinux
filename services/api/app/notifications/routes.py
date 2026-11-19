from flask import Blueprint, request, jsonify

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.identity.models import User
from app.notifications.models import ALL_CHANNELS, ALL_STATUSES
from app.notifications.service import enqueue_notification, process_pending, list_notifications, get_notification

blueprint = Blueprint("notifications", __name__)


# POST /notifications (roles: admin, dispatcher): notifications create; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/notifications")
@require_role("admin", "dispatcher")
def notifications_create():
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400
    user_id = data.get("user_id")
    channel = data.get("channel")
    recipient = data.get("recipient")
    message = data.get("message")
    if not user_id or not channel or not recipient or not message:
        return jsonify({"error": "user_id, channel, recipient and message required"}), 400
    if channel not in ALL_CHANNELS:
        return jsonify({"error": "invalid channel"}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "user not found"}), 400
    n = enqueue_notification(user_id, channel, recipient, data.get("subject"), message)
    return jsonify(n.to_dict()), 201


# GET /notifications (roles: autenticado): notifications list; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/notifications")
@require_auth
def notifications_list():
    status = request.args.get("status")
    if status and status not in ALL_STATUSES:
        return jsonify({"error": "invalid status"}), 400
    user_id = None
    if "admin" not in request.user_roles:
        user_id = request.user_id
    notifications = list_notifications(user_id=user_id, status=status)
    return jsonify([n.to_dict() for n in notifications]), 200


# POST /notifications/process (roles: admin): notifications process; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.post("/notifications/process")
@require_role("admin")
def notifications_process():
    processed = process_pending()
    return jsonify({"processed": processed}), 200
