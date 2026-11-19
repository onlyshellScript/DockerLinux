"""API del motor de exportaciones.

GET  /exports/templates?module=&format=   catalogo de plantillas permitidas para el rol
GET  /exports/options/<source>            opciones dinamicas para filtros (technicians, categories)
POST /exports/preview                      {template, format, params} -> primeras filas + resumen + hash
POST /exports/generate                     {template, format, params, expected_hash?, accept_changes?} -> archivo
"""
import json

from flask import Blueprint, Response, jsonify, request

from app.extensions import db
from app.identity.decorators import require_role
from app.exports import engine
from app.exports.sources import ExportError, option_values
from app.exports.templates import list_templates, template_to_dict

blueprint = Blueprint("exports", __name__)
MIME = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def _ctx():
    from app.identity.models import User
    user = db.session.get(User, request.user_id)
    return {"user_id": request.user_id, "roles": request.user_roles, "username": user.username if user else ""}


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ExportError("Cuerpo de la solicitud requerido")
    fmt = (data.get("format") or "").lower()
    if fmt not in MIME:
        raise ExportError("Formato no válido (pdf o xlsx)", "format")
    params = data.get("params") or {}
    if not isinstance(params, dict):
        raise ExportError("Parámetros no válidos", "params")
    if isinstance(params.get("columns"), list):
        params["columns"] = ",".join(str(c) for c in params["columns"])
    return data, fmt, params


def _error(exc):
    body = {"error": exc.message if isinstance(exc, ExportError) else str(exc), "code": "invalid_export"}
    if isinstance(exc, ExportError) and exc.field:
        body["field"] = exc.field
    return jsonify(body), 422


@blueprint.get("/exports/templates")
@require_role("admin", "dispatcher")
def templates_list():
    module = request.args.get("module") or None
    fmt = request.args.get("format") or None
    return jsonify([template_to_dict(t) for t in list_templates(module, fmt, request.user_roles)]), 200


@blueprint.get("/exports/options/<source>")
@require_role("admin", "dispatcher")
def options(source):
    if source not in ("technicians", "categories"):
        return jsonify({"error": "fuente no válida"}), 404
    return jsonify(option_values(source)), 200


@blueprint.post("/exports/preview")
@require_role("admin", "dispatcher")
def preview():
    try:
        data, fmt, params = _body()
        ds = engine.resolve(data.get("template"), params, _ctx(), fmt)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ExportError as exc:
        return _error(exc)
    return jsonify(engine.preview_payload(ds)), 200


@blueprint.post("/exports/generate")
@require_role("admin", "dispatcher")
def generate():
    try:
        data, fmt, params = _body()
        ctx = _ctx()
        ds = engine.resolve(data.get("template"), params, ctx, fmt)
        current = engine.data_hash(ds.columns, ds.rows)
        expected = data.get("expected_hash")
        if expected and expected != current and not data.get("accept_changes"):
            return jsonify({"error": "Los datos cambiaron desde la vista previa", "code": "DATA_CHANGED",
                            "total": ds.total, "hash": current}), 409
        content = engine.render(ds, fmt)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ExportError as exc:
        return _error(exc)

    name = engine.filename(ds, fmt)
    _audit(ctx, ds, fmt, name, len(content), changed=bool(expected and expected != current))
    resp = Response(content, mimetype=MIME[fmt])
    resp.headers["Content-Disposition"] = f'attachment; filename="{name}"'
    resp.headers["X-Export-Filename"] = name
    resp.headers["X-Export-Rows"] = str(ds.total)
    resp.headers["X-Export-Document"] = ds.meta["doc_code"]
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _audit(ctx, ds, fmt, name, size, changed):
    """Registra la exportacion en la auditoria existente (seccion 'export'). Nunca bloquea la descarga."""
    try:
        from app.settings import service as settings_service
        detail = json.dumps({"template": ds.template.id, "version": ds.template.version, "format": fmt, "rows": ds.total,
                             "filters": ds.params, "columns": [c.key for c in ds.columns], "file": name, "bytes": size,
                             "document": ds.meta["doc_code"], "preview_changed": changed}, ensure_ascii=False)
        settings_service.audit(ctx["user_id"], ctx["username"], "export", ds.template.id, None, detail, "applied", request.headers.get("X-Request-Id"))
        db.session.commit()
    except Exception:  # pragma: no cover - la auditoria no debe impedir la entrega
        db.session.rollback()
