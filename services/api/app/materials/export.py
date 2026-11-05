"""Export engine for materials inventory."""
import csv
import io
from datetime import datetime, timezone

from app.common.normalize import normalize_text
from app.extensions import db
from app.materials.service import list_materials, material_status
from app.settings import service as settings_service


ALLOWED_COLUMNS = {
    "codigo": "Código",
    "nombre": "Nombre",
    "categoria": "Categoría",
    "unidad": "Unidad",
    "stock": "Stock",
    "minimo": "Mínimo",
    "nivel": "Nivel %",
    "estado": "Estado",
    "precio": "Precio",
    "valor": "Valor",
    "activo": "Activo",
}

DEFAULT_COLUMNS = ["codigo", "nombre", "categoria", "unidad", "stock", "minimo", "estado", "precio", "valor"]


def _org_name():
    try:
        return settings_service.get_organization().company_name or "SIGOS"
    except Exception:
        return "SIGOS"


class ExportDataset:
    def __init__(self, filters=None, columns=None, user=None, limit=None):
        self.filters = filters or {}
        self.columns = [c for c in (columns or DEFAULT_COLUMNS) if c in ALLOWED_COLUMNS]
        if not self.columns:
            self.columns = list(DEFAULT_COLUMNS)
        self.user = user
        self.generated_at = datetime.now(timezone.utc)
        self.org_name = _org_name()
        self.limit = limit
        self.rows = []
        self.total_value = 0.0
        self.truncated = False
        self._build()

    def _build(self):
        f = self.filters
        is_active = f.get("is_active")
        if isinstance(is_active, str):
            is_active = is_active.lower() == "true"
        result = list_materials(
            q=f.get("q"),
            status=f.get("status"),
            unit=f.get("unit"),
            is_active=is_active,
            page=1,
            page_size=100000,
            sort=f.get("sort", "name"),
            order=f.get("order", "asc"),
        )
        items = result["items"]
        # category filter (client-side, consistent with UI)
        cat = f.get("category")
        if cat:
            items = [r for r in items if (r["material"].category if hasattr(r["material"], "category") else None) == cat or getattr(r["material"], "catalog_item", None) and getattr(r["material"].catalog_item, "category", None) and r["material"].catalog_item.category.name == cat]
        if self.limit is not None and len(items) > self.limit:
            self.truncated = True
            items = items[:self.limit]
        for r in items:
            m = r["material"]
            st = r["status"]
            stock = float(m.current_stock or 0)
            price = float(m.unit_price or 0)
            row = {
                "codigo": m.code or "",
                "nombre": m.name or "",
                "categoria": (m.category if getattr(m, "category", None) else ("Sin catálogo" if m.catalog_item_id is None else "")),
                "unidad": m.unit or "",
                "stock": stock,
                "minimo": float(m.min_stock or 0),
                "nivel": material_status(stock, m.min_stock)["key"] if False else None,
                "estado": st,
                "precio": price,
                "valor": stock * price,
                "activo": "Sí" if m.is_active else "No",
            }
            # nivel as percentage
            mn = float(m.min_stock or 0)
            if mn > 0:
                row["nivel"] = round(min(100, (stock / mn) * 100))
            else:
                row["nivel"] = 100 if stock > 0 else 0
            self.rows.append(row)
        self.total_value = sum(r["valor"] for r in self.rows)
        self.total_rows = len(self.rows)
        self.filters_applied = {k: v for k, v in f.items() if v not in (None, "", False)}

    def column_headers(self):
        return [ALLOWED_COLUMNS[c] for c in self.columns]

    def row_values(self, row):
        return [row[c] for c in self.columns]


def _sanitize_csv(value):
    # prevent formula injection
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def render_csv(dataset, separator=";"):
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=separator, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(dataset.column_headers())
    for row in dataset.rows:
        writer.writerow([_sanitize_csv(v) for v in dataset.row_values(row)])
    content = "\ufeff" + buf.getvalue()
    return content.encode("utf-8")


def render_excel(dataset):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Inventario"

    header_fill = PatternFill("solid", fgColor="163028")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = dataset.column_headers()
    for idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    money_cols = {"Precio", "Valor"}
    for i, row in enumerate(dataset.rows, start=2):
        for idx, val in enumerate(dataset.row_values(row), start=1):
            cell = ws.cell(row=i, column=idx, value=val)
            cell.border = border
            if headers[idx - 1] in money_cols:
                cell.number_format = '"$ "#,##0'
                cell.alignment = Alignment(horizontal="right")
    # totals row
    if dataset.rows:
        tr = len(dataset.rows) + 2
        ws.cell(row=tr, column=1, value="TOTAL").font = Font(bold=True)
        # put total value in Valor column if present
        if "Valor" in headers:
            vi = headers.index("Valor") + 1
            c = ws.cell(row=tr, column=vi, value=dataset.total_value)
            c.font = Font(bold=True)
            c.number_format = '"$ "#,##0'
        if "Stock" in headers:
            si = headers.index("Stock") + 1
            c = ws.cell(row=tr, column=si, value=sum(r["stock"] for r in dataset.rows))
            c.font = Font(bold=True)

    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(dataset.rows) + 1}"
    ws.freeze_panes = "A2"
    for idx in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(idx)].width = 16

    # Resumen sheet
    rs = wb.create_sheet("Resumen")
    rs["A1"] = "Resumen de inventario"
    rs["A1"].font = Font(bold=True, size=14)
    rs["A3"] = "Organización"
    rs["B3"] = dataset.org_name
    rs["A4"] = "Generado por"
    rs["B4"] = dataset.user.username if getattr(dataset.user, "username", None) else str(dataset.user)
    rs["A5"] = "Fecha"
    rs["B5"] = dataset.generated_at.isoformat()
    rs["A6"] = "Total materiales"
    rs["B6"] = dataset.total_rows
    rs["A7"] = "Valor del inventario"
    rs["B7"] = dataset.total_value
    rs["B7"].number_format = '"$ "#,##0'
    rs["A8"] = "Filtros"
    rs["B8"] = str(dataset.filters_applied)
    rs.column_dimensions["A"].width = 24
    rs.column_dimensions["B"].width = 40

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_pdf(dataset, orientation="landscape"):
    from reportlab.lib.pagesizes import A4, landscape, portrait
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm

    page_size = landscape(A4) if orientation == "landscape" else portrait(A4)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=page_size, leftMargin=15 * mm, rightMargin=15 * mm,
                           topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"{dataset.org_name} — Inventario de Materiales", styles["Title"]))
    story.append(Paragraph(f"Generado por: {getattr(dataset.user, 'username', dataset.user)} | Fecha: {dataset.generated_at.strftime('%d/%m/%Y %H:%M')} UTC", styles["Normal"]))
    story.append(Paragraph(f"Filtros: {dataset.filters_applied}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    headers = dataset.column_headers()
    data = [headers] + [dataset.row_values(r) for r in dataset.rows]
    # format numbers
    for row in data[1:]:
        for idx, h in enumerate(headers):
            if h in ("Precio", "Valor"):
                try:
                    row[idx] = f"$ {row[idx]:,.0f}".replace(",", ".")
                except Exception:
                    pass
            if h == "Nivel %":
                row[idx] = f"{row[idx]}%"
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163028")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Total materiales: {dataset.total_rows} | Valor del inventario: $ {dataset.total_value:,.0f}".replace(",", "."), styles["Normal"]))

    # pagination "Página X de Y"
    def make_on_page(total):
        def on_page(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.drawString(15 * mm, 10 * mm, f"Pagina {doc.page} de {total}")
            canvas.restoreState()
        return on_page

    # first pass to count pages
    buf1 = io.BytesIO()
    doc1 = SimpleDocTemplate(buf1, pagesize=page_size, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm)
    doc1.build(list(story))
    total_pages = getattr(doc1, "page", 1)

    # second pass with footer
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=page_size, leftMargin=15 * mm, rightMargin=15 * mm,
                           topMargin=20 * mm, bottomMargin=20 * mm)
    doc.build(story, onFirstPage=make_on_page(total_pages), onLaterPages=make_on_page(total_pages))
    return buf.getvalue()
