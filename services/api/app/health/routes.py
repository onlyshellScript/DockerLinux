from flask import Blueprint, jsonify

from app.extensions import db
from app.health.service import check_health

blueprint = Blueprint("health", __name__)


@blueprint.get("/health")
def health():
    body, status_code = check_health(db.session)
    return jsonify(body), status_code
