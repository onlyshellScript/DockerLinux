from flask import Blueprint, jsonify

from app.extensions import db
from app.health.service import check_health

blueprint = Blueprint("health", __name__)


# GET /health (roles: publico): health; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/health")
def health():
    body, status_code = check_health(db.session)
    return jsonify(body), status_code
