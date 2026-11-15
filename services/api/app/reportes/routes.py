from flask import Blueprint, request, jsonify, Response

from app.identity.decorators import require_role
from app.workorders.models import ALL_STATUSES
from app.reportes import service as reportes_service

blueprint = Blueprint("reportes", __name__)


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
        if formato == "xlsx":
            import io
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Reporte"
            ws.append(["ID", "Titulo", "Estado", "Prioridad", "Zona", "Tecnico", "Creado"])
            for item in data.get("items", []):
                ws.append([
                    item.get("id"),
                    item.get("title"),
                    item.get("status"),
                    item.get("priority"),
                    item.get("zone"),
                    (item.get("assigned_to") or {}).get("username"),
                    item.get("created_at"),
                ])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return Response(buf.getvalue(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=reporte.xlsx"})
        if formato == "pdf":
            import io
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
            from reportlab.lib import colors
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter)
            rows = [["ID", "Titulo", "Estado", "Prioridad"]]
            for item in data.get("items", []):
                rows.append([str(item.get("id")), str(item.get("title")), str(item.get("status")), str(item.get("priority"))])
            table = Table(rows)
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.grey), ("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
            doc.build([table])
            buf.seek(0)
            return Response(buf.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=reporte.pdf"})

    return jsonify(data), 200

