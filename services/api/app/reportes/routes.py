from flask import Blueprint, request, jsonify, Response

from app.identity.decorators import require_role
from app.workorders.models import ALL_STATUSES
from app.reportes import service as reportes_service

blueprint = Blueprint("reportes", __name__)


# GET /reportes/ordenes (roles: admin, dispatcher): reportes ordenes; entrada path/query/body segun endpoint; salida JSON; delega la logica en el servicio.
@blueprint.get("/reportes/ordenes")
@require_role("admin", "dispatcher")
def reportes_ordenes():
    estado = request.args.get("estado")
    tecnico_id = request.args.get("tecnico_id")
    zona = request.args.get("zona")
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 10, type=int)
    campo_fecha = request.args.get("campo_fecha", "created_at")
    formato = request.args.get("formato")

    if estado and estado not in ALL_STATUSES:
        return jsonify({"error": "estado invalido"}), 400

    try:
        data = reportes_service.build_report(
            estado=estado,
            tecnico_id=tecnico_id,
            zona=zona,
            desde=desde,
            hasta=hasta,
            pagina=pagina,
            por_pagina=por_pagina,
            campo_fecha=campo_fecha,
            for_user_id=request.user_id,
            for_user_roles=request.user_roles,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if formato in ("xlsx", "pdf"):
        # Compatibilidad: delega en el motor centralizado (plantilla orders.general); sin generadores propios.
        from app.exports import engine
        from app.exports.sources import ExportError
        from app.identity.models import User
        from app.extensions import db
        user = db.session.get(User, request.user_id)
        ctx = {"user_id": request.user_id, "roles": request.user_roles, "username": user.username if user else ""}
        params = {"status": estado or "", "technician_id": tecnico_id or "", "zone": zona or "",
                  "date_from": (desde or "")[:10], "date_to": (hasta or "")[:10], "date_field": campo_fecha or "created_at"}
        try:
            ds = engine.resolve("orders.general", params, ctx, formato)
            content = engine.render(ds, formato)
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except ExportError as exc:
            return jsonify({"error": exc.message, "field": exc.field}), 422
        mime = "application/pdf" if formato == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        name = engine.filename(ds, formato)
        return Response(content, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Export-Filename": name})

    return jsonify(data), 200
