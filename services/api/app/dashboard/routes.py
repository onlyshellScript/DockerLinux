from flask import Blueprint, request, jsonify

from app.extensions import db
from app.identity.decorators import require_role
from app.dashboard.service import build_summary

blueprint = Blueprint("dashboard", __name__)


@blueprint.get("/dashboard/summary")
@require_role("admin", "dispatcher")
def dashboard_summary():
    range_days = request.args.get("range", 7, type=int)
    zone = request.args.get("zone")
    city_id = request.args.get("city_id")
    zone_id = request.args.get("zone_id")
    technician_id = request.args.get("technician_id", type=int)
    data = build_summary(range_days=range_days, zone=zone, city_id=city_id, zone_id=zone_id, technician_id=technician_id)
    return jsonify(data), 200
