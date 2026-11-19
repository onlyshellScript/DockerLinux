"""Renderizado XLSX institucional con tipos de dato reales (openpyxl).

Libro:
  Resumen -> encabezado institucional, metadatos, indicadores y totales con formulas sobre la hoja Datos.
  Datos   -> encabezado institucional, tabla estructurada (filtros automaticos), encabezados inmovilizados,
             formatos de fecha/numero/moneda y anchos calculados.
"""
import io
from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from app.exports.engine import HEADER_ROW
from app.exports.render_common import align_for

NAV = "163028"
MUTED = "626A77"
HEAD_FILL = PatternFill("solid", fgColor="EEF2EF")
THIN = Side(style="thin", color="D9D6D0")
SUMMABLE = {"value", "stock", "requested", "approved", "delivered", "pending_qty", "shortage", "files", "size_kb",
            "pending", "assigned", "in_progress", "open_total", "completed", "changes", "count", "total", "active", "inactive"}
NUMBER_FORMATS = {
    "int": "#,##0", "number": "#,##0.00", "money": '"$" #,##0', "percent": "0.0%",
    "date": "dd/mm/yyyy", "datetime": "dd/mm/yyyy hh:mm",
}


def _set(cell, value, typ):
    """Asigna el valor conservando su tipo; el texto nunca se interpreta como formula."""
    if value is None or value == "":
        cell.value = None
        return
    if typ in ("int",):
        cell.value = int(value)
    elif typ in ("number", "percent"):
        cell.value = float(value)
    elif typ == "money":
        cell.value = float(value) if isinstance(value, Decimal) else value
    elif typ in ("date", "datetime") and isinstance(value, (datetime, date)):
        cell.value = value
    else:
        cell.value = str(value)
        cell.data_type = "s"  # evita inyeccion de formulas (=, +, -, @)
    if typ in NUMBER_FORMATS:
        cell.number_format = NUMBER_FORMATS[typ]


def _header_block(ws, ds, ncols):
    m = ds.meta
    ws["A1"] = m["title"]
    ws["A1"].font = Font(name="Calibri", size=16, bold=True, color=NAV)
    ws["A2"] = f"{m['org']} · Módulo {m['module']} · Documento {m['doc_code']}"
    ws["A2"].font = Font(size=10, color=MUTED)
    ws["A3"] = f"Generado el {m['generated_at']:%d/%m/%Y %H:%M} por {m['user'] or '—'} · {m['filters_text']}"
    ws["A3"].font = Font(size=10, color=MUTED)
    for r in (1, 2, 3):
        ws.cell(row=r, column=1).data_type = "s"
    ws.row_dimensions[1].height = 24


def _col_width(col, values):
    lens = [len(col.label)] + [len(str(v)) for v in values[:500] if v is not None]
    base = {"datetime": 16, "date": 11, "money": 14, "percent": 10}.get(col.type, 0)
    return max(base, min(max(lens) + 2, 60))


def render_xlsx(ds):
    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Resumen"
    ws = wb.create_sheet("Datos")
    cols = ds.columns
    n = ds.total
    first, last = HEADER_ROW + 1, HEADER_ROW + n

    # ---------------- Datos
    _header_block(ws, ds, len(cols))
    for j, c in enumerate(cols, start=1):
        cell = ws.cell(row=HEADER_ROW, column=j, value=c.label)
        cell.font = Font(bold=True, color=NAV)
        cell.fill = HEAD_FILL
        cell.border = Border(bottom=THIN)
        cell.alignment = Alignment(horizontal=align_for(c), vertical="center", wrap_text=True)
    for i, row in enumerate(ds.rows, start=first):
        for j, c in enumerate(cols, start=1):
            cell = ws.cell(row=i, column=j)
            _set(cell, row.get(c.key), c.type)
            cell.alignment = Alignment(horizontal=align_for(c), vertical="top", wrap_text=c.type == "text" and c.width >= 1.6)
    for j, c in enumerate(cols, start=1):
        ws.column_dimensions[get_column_letter(j)].width = _col_width(c, [r.get(c.key) for r in ds.rows])
    last_col = get_column_letter(len(cols))
    if n:
        tab = Table(displayName="Datos_" + ds.template.id.replace(".", "_"), ref=f"A{HEADER_ROW}:{last_col}{last}")
        tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True, showColumnStripes=False)
        ws.add_table(tab)  # la tabla incluye filtros automaticos
    else:
        ws.auto_filter.ref = f"A{HEADER_ROW}:{last_col}{HEADER_ROW}"
        ws.cell(row=first, column=1, value="Sin registros para los filtros seleccionados").font = Font(italic=True, color=MUTED)
    ws.freeze_panes = ws.cell(row=first, column=1)  # titulo + encabezados inmovilizados
    ws.sheet_view.showGridLines = False
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"
    ws.page_setup.orientation = "landscape" if len(cols) > 6 else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    # ---------------- Resumen
    s = summary_ws
    _header_block(s, ds, 2)
    r = HEADER_ROW
    s.cell(row=r, column=1, value="Indicador").font = Font(bold=True, color=NAV)
    s.cell(row=r, column=2, value="Valor").font = Font(bold=True, color=NAV)
    for c in (1, 2):
        s.cell(row=r, column=c).fill = HEAD_FILL
        s.cell(row=r, column=c).border = Border(bottom=THIN)
    r += 1
    s.cell(row=r, column=1, value="Registros exportados")
    s.cell(row=r, column=2, value=f"=COUNTA(Datos!A{first}:A{last})" if n else 0).number_format = "#,##0"
    r += 1
    for label, value, typ in ds.summary:
        if label in ("Órdenes", "Materiales", "Solicitudes", "Evidencias", "Técnicos", "Cuentas", "Expedientes") and value == n:
            continue  # ya cubierto por "Registros exportados"
        s.cell(row=r, column=1, value=label)
        _set(s.cell(row=r, column=2), value, typ)
        r += 1
    # Totales con formula para columnas monetarias y cantidades
    for j, c in enumerate(cols, start=1):
        # Solo magnitudes acumulables (nunca precios unitarios ni porcentajes)
        if n and c.key in SUMMABLE and c.type in ("int", "number", "money"):
            L = get_column_letter(j)
            s.cell(row=r, column=1, value=f"Total {c.label.lower()}")
            cell = s.cell(row=r, column=2, value=f"=SUM(Datos!{L}{first}:{L}{last})")
            cell.number_format = NUMBER_FORMATS[c.type]
            r += 1
    # Distribucion por grupo con COUNTIF sobre la hoja Datos
    if ds.groups and n:
        gcol = next((j for j, c in enumerate(cols, start=1) if c.key == ds.template.group_by), None)
        r += 1
        s.cell(row=r, column=1, value="Distribución").font = Font(bold=True, color=NAV)
        r += 1
        for g in ds.groups:
            s.cell(row=r, column=1, value=str(g)).data_type = "s"
            if gcol:
                L = get_column_letter(gcol)
                s.cell(row=r, column=2, value=f'=COUNTIF(Datos!{L}{first}:{L}{last},A{r})').number_format = "#,##0"
            else:
                s.cell(row=r, column=2, value=len(ds.groups[g])).number_format = "#,##0"
            r += 1
    s.column_dimensions["A"].width = 38
    s.column_dimensions["B"].width = 26
    s.sheet_view.showGridLines = False
    for row in s.iter_rows(min_row=HEADER_ROW + 1, max_row=r, max_col=2):
        row[1].alignment = Alignment(horizontal="right")

    wb.properties.title = ds.meta["title"]
    wb.properties.creator = f"SIGOS ({ds.meta['user']})"
    wb.properties.subject = ds.meta["doc_code"]
    wb.active = 1 if n else 0
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
