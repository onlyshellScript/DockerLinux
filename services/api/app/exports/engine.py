"""Orquestacion de exportaciones: plantilla -> parametros validados -> dataset -> render -> validacion."""
import hashlib
import io
import json
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal

from app.exports.sources import SOURCES, SUMMARIES, ExportError, org_tz
from app.exports.templates import MODULE_LABELS, get_template

MAX_ROWS = {"xlsx": 50000, "pdf": 5000}
PREVIEW_ROWS = 15


class Dataset:
    def __init__(self, template, params, columns, rows, summary, groups, meta):
        self.template, self.params, self.columns, self.rows = template, params, columns, rows
        self.summary, self.groups, self.meta = summary, groups, meta

    @property
    def total(self):
        return len(self.rows)


def _jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def data_hash(columns, rows):
    """Huella del contenido exportable (columnas visibles + valores). Detecta cambios entre vista previa y generacion."""
    keys = [c.key for c in columns]
    payload = json.dumps([[_jsonable(r.get(k)) for k in keys] for r in rows], ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _filters_text(template, params):
    parts = []
    for f in template.filters:
        v = params.get(f.key)
        if v in (None, ""):
            continue
        label = v
        if f.options:
            label = dict(f.options).get(v, v)
        elif f.source == "technicians":
            from app.exports.sources import option_values
            label = next((o["label"] for o in option_values("technicians") if o["value"] == str(v)), v)
        parts.append(f"{f.label}: {label}")
    return " · ".join(parts) or "Sin filtros"


def resolve(template_id, params, ctx, fmt=None):
    """Valida la peticion y construye el dataset. Lanza ExportError (422) o PermissionError (403)."""
    t = get_template(template_id)
    if not t:
        raise ExportError("Plantilla no encontrada", "template")
    if not any(r in t.roles for r in ctx["roles"]):
        raise PermissionError("No tiene permiso para esta plantilla")
    if fmt is not None and fmt not in t.formats:
        raise ExportError("Formato no compatible con la plantilla", "format")
    params = {k: (str(v).strip() if v is not None else "") for k, v in (params or {}).items()}
    allowed = {f.key for f in t.filters}
    clean = {k: v for k, v in params.items() if k in allowed and v != ""}
    for f in t.filters:  # valores de select restringidos a las opciones declaradas
        if f.options and f.key in clean and clean[f.key] not in dict(f.options):
            raise ExportError(f"Valor no válido para «{f.label}»", f.key)

    # Columnas: subconjunto de las de la plantilla, en el orden de la plantilla
    req_cols = params.get("columns")
    if t.allow_columns and req_cols:
        wanted = [c for c in req_cols.split(",") if c]
        unknown = set(wanted) - {c.key for c in t.columns}
        if unknown:
            raise ExportError("Columnas no válidas: " + ", ".join(sorted(unknown)), "columns")
        columns = [c for c in t.columns if c.key in wanted]
        if not columns:
            raise ExportError("Seleccione al menos una columna", "columns")
    else:
        columns = [c for c in t.columns if c.default]

    rows = SOURCES[t.source](t, clean, ctx)

    # Orden
    sort = params.get("sort") or t.default_sort
    order = params.get("order") or t.default_order
    if sort:
        if t.sorts and sort not in {k for k, _ in t.sorts}:
            raise ExportError("Orden no válido", "sort")
        if order not in ("asc", "desc"):
            raise ExportError("Dirección de orden no válida", "order")
        rows.sort(key=lambda r: (r.get(sort) is None, r.get(sort) if not isinstance(r.get(sort), str) else r.get(sort).lower()),
                  reverse=(order == "desc"))
        if order == "desc":  # mantener vacios al final tambien en descendente
            rows.sort(key=lambda r: r.get(sort) is None)

    groups = None
    if t.group_by:
        groups = {}
        for r in rows:
            groups.setdefault(r.get(t.group_by) or "—", []).append(r)

    summary = SUMMARIES[t.summary](rows, clean) if t.summary else []
    now_local = datetime.now(timezone.utc).astimezone(org_tz())
    meta = {
        "title": t.name, "description": t.description, "module": MODULE_LABELS.get(t.module, t.module),
        "template_id": t.id, "template_version": t.version,
        "generated_at": now_local.replace(tzinfo=None), "user": ctx.get("username") or "",
        "filters_text": _filters_text(t, clean), "org": _org_name(),
        "doc_code": f"SIGOS-{t.module[:3].upper()}-{now_local:%Y%m%d-%H%M%S}-{secrets.token_hex(2).upper()}",
    }
    return Dataset(t, clean, columns, rows, summary, groups, meta)


def _org_name():
    try:
        from app.settings.service import get_organization
        return get_organization().company_name or "SIGOS"
    except Exception:  # pragma: no cover
        return "SIGOS"


def filename(ds, fmt):
    stamp = ds.meta["generated_at"].strftime("%Y%m%d-%H%M")
    return f"sigos_{ds.template.module}_{ds.template.id.split('.', 1)[1]}_{stamp}.{fmt}"


def check_limits(ds, fmt):
    limit = MAX_ROWS[fmt]
    if ds.total > limit:
        raise ExportError(f"La exportación tiene {ds.total} filas y el máximo para {fmt.upper()} es {limit}. Ajuste los filtros.", "limit")


def render(ds, fmt):
    from app.exports.render_pdf import render_pdf
    from app.exports.render_xlsx import render_xlsx
    check_limits(ds, fmt)
    data = render_pdf(ds) if fmt == "pdf" else render_xlsx(ds)
    validate_output(data, fmt, ds)
    return data


def validate_output(data, fmt, ds):
    """Comprueba la integridad del archivo generado antes de entregarlo."""
    if fmt == "pdf":
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-1024:]:
            raise RuntimeError("PDF generado inválido")
        if data.count(b"/Type /Page") - data.count(b"/Type /Pages") < 1:
            raise RuntimeError("PDF sin páginas")
        return
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True)
    if "Datos" not in wb.sheetnames:
        raise RuntimeError("XLSX sin hoja de datos")
    ws = wb["Datos"]
    data_rows = sum(1 for _ in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True))
    if ds.total == 0:
        data_rows = 0  # la unica fila es el aviso "Sin registros"
    if data_rows != ds.total:
        raise RuntimeError(f"XLSX con {data_rows} filas, se esperaban {ds.total}")
    wb.close()


HEADER_ROW = 5  # fila de encabezados de la hoja Datos (render_xlsx lo respeta)


def preview_payload(ds):
    from app.exports.render_common import format_value
    return {
        "template": ds.template.id, "title": ds.meta["title"], "total": ds.total, "hash": data_hash(ds.columns, ds.rows),
        "columns": [{"key": c.key, "label": c.label, "type": c.type} for c in ds.columns],
        "rows": [[format_value(r.get(c.key), c.type) for c in ds.columns] for r in ds.rows[:PREVIEW_ROWS]],
        "summary": [{"label": l, "value": format_value(v, t)} for l, v, t in ds.summary],
        "filters_text": ds.meta["filters_text"], "groups": {k: len(v) for k, v in ds.groups.items()} if ds.groups else None,
        "limits": MAX_ROWS, "warnings": [f"{fmt.upper()}: supera el máximo de {lim} filas" for fmt, lim in MAX_ROWS.items() if ds.total > lim],
    }
