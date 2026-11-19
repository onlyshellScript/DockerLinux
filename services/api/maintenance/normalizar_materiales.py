# -*- coding: utf-8 -*-
"""Normalización a MAYÚSCULAS de los textos existentes del módulo de materiales.

Uso (desde services/api, con DB_URL en .env):
    python -m maintenance.normalizar_materiales            # solo informe (no escribe nada)
    python -m maintenance.normalizar_materiales --apply    # aplica la normalización en una transacción

- Reescribe únicamente textos (nombre, descripción, unidad, medida, etapa, aplica a, notas de movimientos) con la misma
  regla que usan los modelos (normalize_upper). No cambia ids, códigos, cantidades ni relaciones.
- No fusiona ni elimina duplicados: los informa con sus referencias (movimientos, solicitudes, stock de técnicos,
  ítems de catálogo) para decidir una consolidación controlada (ver docs/architecture/2026-11-18-ajustes-administrativos.md).
- Es idempotente: ejecutarlo de nuevo no cambia nada.
"""
import argparse
import collections
import sys

from app import create_app
from app.common.normalize import normalize_text, normalize_upper
from app.extensions import db

FIELDS = {
    "Material": ("name", "description", "unit"),
    "MaterialCatalog": ("name", "measure", "stage", "applies_to"),
    "MaterialCategory": ("name",),
    "MaterialUnit": ("name",),
    "StockMovement": ("notes",),
}


def _pending(obj, fields):
    return {f: getattr(obj, f) for f in fields if isinstance(getattr(obj, f), str) and getattr(obj, f) != normalize_upper(getattr(obj, f))}


def _duplicates(rows):
    groups = collections.defaultdict(list)
    for r in rows:
        key = normalize_text(r.name)
        if key:
            groups[key].append(r)
    return {k: v for k, v in groups.items() if len(v) > 1}


def run(apply=False, out=sys.stdout):
    from app.materials import models as M
    report = {"changes": {}, "duplicates": []}
    classes = {"Material": M.Material, "MaterialCatalog": M.MaterialCatalog, "MaterialCategory": M.MaterialCategory,
               "MaterialUnit": M.MaterialUnit, "StockMovement": M.StockMovement}
    for name, cls in classes.items():
        rows = cls.query.all()
        pending = [(r, _pending(r, FIELDS[name])) for r in rows]
        pending = [(r, p) for r, p in pending if p]
        report["changes"][name] = len(pending)
        print(f"{cls.__tablename__}: {len(rows)} registros, {len(pending)} por normalizar", file=out)
        for r, p in pending[:5]:
            print(f"   id={r.id}: " + ", ".join(f"{k}={v!r} -> {normalize_upper(v)!r}" for k, v in p.items()), file=out)
        if apply:
            for r, p in pending:
                for field in p:
                    setattr(r, field, getattr(r, field))  # el validador del modelo aplica normalize_upper

    # Duplicados por escritura en el inventario y sus referencias (no se tocan).
    for key, group in _duplicates(M.Material.query.all()).items():
        refs = []
        for m in group:
            refs.append({
                "id": m.id, "name": m.name, "code": m.code, "catalog_item_id": m.catalog_item_id,
                "stock": m.current_stock,
                "movements": M.StockMovement.query.filter_by(material_id=m.id).count(),
                "request_items": M.MaterialRequestItem.query.filter_by(material_id=m.id).count(),
                "technician_stock": M.TechnicianStock.query.filter_by(material_id=m.id).count(),
            })
        report["duplicates"].append({"key": key, "materials": refs})
        print(f"DUPLICADO {key!r}: " + "; ".join(f"id={r['id']} {r['name']!r} cod={r['code']} stock={r['stock']} mov={r['movements']} sol={r['request_items']} stec={r['technician_stock']}" for r in refs), file=out)
    if not report["duplicates"]:
        print("Sin duplicados por diferencias de escritura en Materiales.", file=out)

    if apply:
        db.session.commit()
        print("Normalización aplicada.", file=out)
    else:
        db.session.rollback()
        print("Modo informe: no se escribió nada. Use --apply para aplicar.", file=out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="aplica la normalización (por defecto solo informa)")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        run(apply=args.apply)


if __name__ == "__main__":
    main()
