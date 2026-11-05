from flask import Blueprint, request, jsonify

from app.identity.decorators import require_auth
from app.sync.service import push_operations, pull_changes

blueprint = Blueprint("sync", __name__)


@blueprint.post("/sync/push")
@require_auth
def sync_push():
    data = request.get_json()
    if not data or not isinstance(data.get("operations"), list):
        return jsonify({"error": "operations array required"}), 400
    operations = data["operations"]
    if len(operations) > 100:
        return jsonify({"error": "max 100 operations per request"}), 400
    results = push_operations(request.user_id, operations)
    return jsonify({"results": results}), 200


@blueprint.get("/sync/pull")
@require_auth
def sync_pull():
    since = request.args.get("since")
    data = pull_changes(request.user_id, since=since)
    return jsonify(data), 200
