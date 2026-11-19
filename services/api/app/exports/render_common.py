"""Formatos compartidos por vista previa y PDF (el XLSX conserva tipos y usa formatos de celda)."""
from datetime import date, datetime
from decimal import Decimal

BRAND = {"nav": "#163028", "primary": "#2E7A50", "text": "#1A1F27", "muted": "#626A77", "border": "#D9D6D0", "zebra": "#F7F6F3", "head": "#EEF2EF"}


def _thousands(n, decimals=0):
    s = f"{n:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234.567,89 (es-CO)


def format_value(v, typ):
    if v is None or v == "":
        return "—"
    if typ == "money":
        return "$ " + _thousands(float(v), 0)
    if typ == "percent":
        return _thousands(float(v) * 100, 1) + " %"
    if typ == "int":
        return _thousands(int(v), 0)
    if typ == "number":
        f = float(v)
        return _thousands(f, 0 if f == int(f) else 2)
    if typ == "datetime" and isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M")
    if typ in ("date", "datetime") and isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, Decimal):
        return _thousands(float(v), 2)
    return str(v)


def align_for(col):
    if col.align:
        return col.align
    return "right" if col.type in ("int", "number", "money", "percent") else "left"
