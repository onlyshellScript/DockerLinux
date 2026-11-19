from flask import Blueprint, jsonify

from app.extensions import db
from app.health.service import check_health, check_liveness

blueprint = Blueprint("health", __name__)


# GET /health (roles: publico): estado de la aplicacion y de la base de datos (200 UP / 503 DOWN).
@blueprint.get("/health")
def health():
    body, status_code = check_health(db.session)
    return jsonify(body), status_code


# GET /health/live (roles: publico): vida del proceso, independiente de SQL Server. Para healthchecks de contenedor/servicio.
@blueprint.get("/health/live")
def live():
    body, status_code = check_liveness()
    return jsonify(body), status_code
