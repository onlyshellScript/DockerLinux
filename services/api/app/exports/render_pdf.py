"""Renderizado PDF institucional (reportlab/platypus).

- A4 vertical u horizontal segun el ancho de la tabla (o lo que fije la plantilla).
- Membrete en cada pagina: marca SIGOS, titulo, codigo de documento, fecha/hora y usuario.
- Pie en cada pagina: organizacion, plantilla/version y "Pagina X de Y".
- Tabla con encabezado repetido (repeatRows) y filas que no se parten entre paginas (splitInRow=0).
- Celdas con Paragraph: el texto largo hace salto de linea en lugar de desbordar.
"""
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import BaseDocTemplate, CondPageBreak, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from app.exports.render_common import BRAND, align_for, format_value

C = {k: colors.HexColor(v) for k, v in BRAND.items()}
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 14 * mm, 30 * mm, 16 * mm

ST = {
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=7.8, leading=9.6, textColor=C["text"]),
    "cell_r": ParagraphStyle("cell_r", fontName="Helvetica", fontSize=7.8, leading=9.6, textColor=C["text"], alignment=TA_RIGHT),
    "head": ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=7.6, leading=9.2, textColor=C["nav"]),
    "head_r": ParagraphStyle("head_r", fontName="Helvetica-Bold", fontSize=7.6, leading=9.2, textColor=C["nav"], alignment=TA_RIGHT),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=C["nav"], spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.5, leading=11, textColor=C["muted"]),
    "kpi_l": ParagraphStyle("kpi_l", fontName="Helvetica", fontSize=7.5, leading=9, textColor=C["muted"]),
    "kpi_v": ParagraphStyle("kpi_v", fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=C["text"]),
    "empty": ParagraphStyle("empty", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=C["muted"], alignment=TA_LEFT),
}


class NumberedCanvas(rl_canvas.Canvas):
    """Canvas que conoce el total de paginas para escribir 'Pagina X de Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        w, _ = self._pagesize
        self.setFont("Helvetica", 7.5)
        self.setFillColor(C["muted"])
        self.drawRightString(w - MARGIN_X, 9 * mm, f"Página {self._pageNumber} de {total}")


def _decorate(ds):
    m = ds.meta

    def on_page(cv, doc):
        w, h = doc.pagesize
        cv.saveState()
        # Marca
        cv.setFillColor(C["nav"])
        cv.roundRect(MARGIN_X, h - 19 * mm, 9 * mm, 9 * mm, 1.6 * mm, fill=1, stroke=0)
        cv.setFillColor(colors.white)
        cv.setFont("Helvetica-Bold", 12)
        cv.drawCentredString(MARGIN_X + 4.5 * mm, h - 16.2 * mm, "S")
        cv.setFillColor(C["nav"])
        cv.setFont("Helvetica-Bold", 13)
        cv.drawString(MARGIN_X + 12 * mm, h - 13.6 * mm, m["title"])
        cv.setFont("Helvetica", 8)
        cv.setFillColor(C["muted"])
        cv.drawString(MARGIN_X + 12 * mm, h - 18 * mm, f"{m['org']} · Módulo {m['module']}")
        cv.drawRightString(w - MARGIN_X, h - 13.6 * mm, m["doc_code"])
        cv.drawRightString(w - MARGIN_X, h - 18 * mm, f"Generado {m['generated_at']:%d/%m/%Y %H:%M} · {m['user'] or '—'}")
        cv.setStrokeColor(C["primary"])
        cv.setLineWidth(1.2)
        cv.line(MARGIN_X, h - 22 * mm, w - MARGIN_X, h - 22 * mm)
        # Pie
        cv.setStrokeColor(C["border"])
        cv.setLineWidth(0.5)
        cv.line(MARGIN_X, 13 * mm, w - MARGIN_X, 13 * mm)
        cv.setFont("Helvetica", 7.5)
        cv.drawString(MARGIN_X, 9 * mm, f"SIGOS · {m['template_id']} v{m['template_version']} · Documento generado automáticamente")
        cv.restoreState()

    return on_page


def _choose_pagesize(ds):
    o = ds.template.orientation
    if o == "portrait":
        return A4
    if o == "landscape":
        return landscape(A4)
    return landscape(A4) if sum(c.width for c in ds.columns) > 9 or len(ds.columns) > 7 else A4


def _summary_block(ds, avail_w):
    if not ds.summary:
        return []
    cells = [[Paragraph(escape(label), ST["kpi_l"]), Paragraph(escape(format_value(v, t)), ST["kpi_v"])] for label, v, t in ds.summary]
    per_row = 4 if avail_w > 200 * mm else 3
    rows = []
    for i in range(0, len(cells), per_row):
        chunk = cells[i:i + per_row]
        chunk += [["", ""]] * (per_row - len(chunk))
        rows.append([[c[0], c[1]] for c in chunk])
    col_w = avail_w / per_row
    data = [[Table([[c[0]], [c[1]]], colWidths=[col_w - 6 * mm], style=[("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]) for c in r] for r in rows]
    t = Table(data, colWidths=[col_w] * per_row)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, C["border"]),
        ("BACKGROUND", (0, 0), (-1, -1), C["zebra"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [Paragraph("Resumen", ST["h2"]), t, Spacer(1, 4 * mm)]


def _data_table(ds, rows, avail_w):
    cols = ds.columns
    if ds.groups and ds.template.group_by and len(cols) > 1:
        # en tablas agrupadas la columna de agrupacion ya figura en el subtitulo del grupo
        cols = [c for c in cols if c.key != ds.template.group_by]
    total_w = sum(c.width for c in cols)
    widths = [avail_w * c.width / total_w for c in cols]
    head = [Paragraph(escape(c.label), ST["head_r" if align_for(c) == "right" else "head"]) for c in cols]
    body = [[Paragraph(escape(format_value(r.get(c.key), c.type)), ST["cell_r" if align_for(c) == "right" else "cell"]) for c in cols] for r in rows]
    t = Table([head] + body, colWidths=widths, repeatRows=1, splitInRow=0)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C["head"]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, C["primary"]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, C["border"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    for i in range(2, len(body) + 1, 2):
        style.append(("BACKGROUND", (0, i), (-1, i), C["zebra"]))
    t.setStyle(TableStyle(style))
    return t


def render_pdf(ds):
    buf = io.BytesIO()
    pagesize = _choose_pagesize(ds)
    doc = BaseDocTemplate(buf, pagesize=pagesize, leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
                          title=ds.meta["title"], author=f"SIGOS ({ds.meta['user']})", subject=ds.meta["doc_code"], creator="SIGOS")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=_decorate(ds))])
    story = [Paragraph(escape(ds.meta["description"]), ST["body"]),
             Paragraph(f"<b>Filtros:</b> {escape(ds.meta['filters_text'])} · <b>Registros:</b> {ds.total}", ST["body"]),
             Spacer(1, 3 * mm)]
    story += _summary_block(ds, doc.width)
    if not ds.rows:
        story.append(Paragraph("No hay registros para los filtros seleccionados.", ST["empty"]))
    elif ds.groups:
        for name, rows in ds.groups.items():
            # el subtitulo nunca queda huerfano al pie de pagina
            story.append(CondPageBreak(30 * mm))
            story.append(KeepTogether([Paragraph(f"{escape(str(name))} <font color='#626A77' size='8'>({len(rows)})</font>", ST["h2"])]))
            story.append(_data_table(ds, rows, doc.width))
            story.append(Spacer(1, 3 * mm))
    else:
        story.append(_data_table(ds, ds.rows, doc.width))
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()
