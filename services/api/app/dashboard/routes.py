from flask import Blueprint, request, jsonify

from app.identity.decorators import require_role
from app.dashboard.service import build_summary, VALID_RANGES

blueprint = Blueprint("dashboard", __name__)


def _int_arg(name):
    """None si no viene; ValueError si viene pero no es un entero."""
    raw = request.args.get(name)
    if raw is None or raw == "":
        return None
    return int(raw)


def _current_user_id():
    # AJUSTA esto a tu app: por ejemplo flask_jwt_extended.get_jwt_identity()
    # o g.current_user.id, según cómo lo exponga require_role.
    from flask import g
    user = getattr(g, "current_user", None)
    return getattr(user, "id", None)


@blueprint.get("/dashboard/summary")
@require_role("admin", "dispatcher")
def dashboard_summary():
    try:
        range_days = _int_arg("range") or 7
        city_id = _int_arg("city_id")
        zone_id = _int_arg("zone_id")
        technician_id = _int_arg("technician_id")
    except ValueError:
        return jsonify({"error": "Los parámetros range, city_id, zone_id y technician_id deben ser enteros"}), 400

    if range_days not in VALID_RANGES:
        return jsonify({"error": f"range debe ser uno de {list(VALID_RANGES)}"}), 400

    data = build_summary(
        range_days=range_days,
        zone=request.args.get("zone"),
        city_id=city_id,
        zone_id=zone_id,
        technician_id=technician_id,
        user_id=_current_user_id(),
    )
    return jsonify(data), 200