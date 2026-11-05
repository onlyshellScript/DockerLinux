"""Idempotent loader for the gas-natural materials catalog.

Run manually:
    python seeds/load_catalog.py
Never invoked at server startup.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.common.normalize import normalize_text
from app.materials.models import MaterialCategory, MaterialUnit, MaterialCatalog


UNIT_MAP = {
    "pza": ("unidad", "Unidad", False),
    "m": ("m", "Metro", True),
    "kg": ("kg", "Kilogramo", True),
    "lt": ("lt", "Litro", True),
    "rollo": ("rollo", "Rollo", True),
}

STAGE_MAP = {}  # passthrough


def _unit_code(raw):
    return UNIT_MAP[raw][0]


def load_into_app(app, path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    with app.app_context():
        inserted = updated = skipped = 0

        # units
        for raw, (code, name, allows) in UNIT_MAP.items():
            u = MaterialUnit.query.filter_by(code=code).first()
            if not u:
                u = MaterialUnit(code=code, name=name, name_norm=normalize_text(name), allows_decimal=allows)
                db.session.add(u)
            else:
                u.name = name
                u.name_norm = normalize_text(name)
                u.allows_decimal = allows
        db.session.commit()

        # categories
        cats = {}
        for row in data:
            cat_name = row["category"]
            cat_norm = normalize_text(cat_name)
            cat_code = cat_norm.upper().replace(" ", "_")
            cat = MaterialCategory.query.filter_by(name_norm=cat_norm).first()
            if not cat:
                cat = MaterialCategory(code=cat_code, name=cat_name, name_norm=cat_norm)
                db.session.add(cat)
                db.session.flush()
            cats[cat_name] = cat
        db.session.commit()

        # catalog items
        for row in data:
            code = row["code"]
            name = row["name"]
            name_norm = normalize_text(name)
            cat = cats[row["category"]]
            unit_code = _unit_code(row["unit"])
            unit = MaterialUnit.query.filter_by(code=unit_code).first()

            existing = MaterialCatalog.query.filter_by(code=code).first()
            if existing:
                # update mutable fields
                existing.name = name
                existing.name_norm = name_norm
                existing.category_id = cat.id
                existing.unit_id = unit.id
                existing.measure = row.get("measure")
                existing.stage = row.get("stage")
                existing.applies_to = row.get("applies_to")
                existing.is_active = True
                updated += 1
            else:
                # duplicate name_norm check
                dup = MaterialCatalog.query.filter_by(name_norm=name_norm).first()
                if dup:
                    print(f"SKIP duplicate name_norm: {name}")
                    skipped += 1
                    continue
                mc = MaterialCatalog(
                    category_id=cat.id,
                    code=code,
                    name=name,
                    name_norm=name_norm,
                    unit_id=unit.id,
                    measure=row.get("measure"),
                    stage=row.get("stage"),
                    applies_to=row.get("applies_to"),
                    is_active=True,
                )
                db.session.add(mc)
                inserted += 1
        db.session.commit()

        print(f"inserted={inserted} updated={updated} skipped={skipped} total={len(data)}")
        print(f"categories={MaterialCategory.query.count()} units={MaterialUnit.query.count()} catalog={MaterialCatalog.query.count()}")




def load(path):
    app = create_app()
    return load_into_app(app, path)

if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "seeds", "materiales_gas_natural.json")
    load(path)
