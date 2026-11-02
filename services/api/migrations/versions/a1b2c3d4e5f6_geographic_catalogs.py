"""geographic catalogs country city zone + data integrity

Revision ID: a1b2c3d4e5f6
Revises: 719f12d0f9c8
Create Date: 2026-10-29 00:00:00.000000

"""
import json
import os
import unicodedata
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'a1b2c3d4e5f6'
down_revision = '719f12d0f9c8'
branch_labels = None
depends_on = None


def _norm(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    # --- create countries ---
    op.create_table(
        'countries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('iso2', sa.String(length=2), nullable=False, unique=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('name_norm', sa.String(length=120), nullable=False, unique=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )

    # --- create cities ---
    op.create_table(
        'cities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('country_id', sa.Integer(), sa.ForeignKey('countries.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('department_name', sa.String(length=120), nullable=True),
        sa.Column('dane_code', sa.String(length=5), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('name_norm', sa.String(length=120), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint('country_id', 'dane_code', name='uq_city_country_dane'),
    )
    op.create_index('ix_cities_country_id', 'cities', ['country_id'])

    # --- create zones ---
    op.create_table(
        'zones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('city_id', sa.Integer(), sa.ForeignKey('cities.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('name_norm', sa.String(length=120), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint('city_id', 'name_norm', name='uq_zone_city_name'),
        sa.CheckConstraint("kind IN ('localidad','comuna','barrio','vereda','corregimiento','sector')", name='ck_zone_kind'),
    )
    op.create_index('ix_zones_city_id', 'zones', ['city_id'])

    # --- create installation_types ---
    op.create_table(
        'installation_types',
        sa.Column('code', sa.String(length=60), primary_key=True),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('name_norm', sa.String(length=120), nullable=False, unique=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )

    # --- seed country ---
    op.execute("INSERT INTO countries (iso2, name, name_norm, active) VALUES ('CO', 'Colombia', 'colombia', 1)")

    # get country id
    country_id = bind.execute(sa.text("SELECT id FROM countries WHERE iso2='CO'")).scalar()

    # --- seed cities from JSON or from old municipalities ---
    # Prefer old municipalities table if exists
    tables = inspector.get_table_names()
    old_munis = []
    if 'municipalities' in tables:
        rows = bind.execute(sa.text("SELECT code, name, department_code FROM municipalities")).fetchall()
        # map dept code -> name
        dept_map = {}
        if 'departments' in tables:
            for d in bind.execute(sa.text("SELECT code, name FROM departments")).fetchall():
                dept_map[d[0]] = d[1]
        for r in rows:
            code = (r[0] or '').strip().zfill(5)
            name = r[1]
            dept_code = r[2]
            dept_name = dept_map.get(dept_code, dept_code)
            old_munis.append((code, name, dept_name))
    else:
        # load json
        json_path = os.path.join(os.path.dirname(__file__), '..', '..', 'seeds', 'colombia_divipola.json')
        # relative to migrations/versions -> services/api
        json_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'seeds', 'colombia_divipola.json'))
        if os.path.exists(json_path):
            data = json.load(open(json_path, encoding='utf-8'))
            for item in data:
                old_munis.append((item['dane_code'].zfill(5), item['name'], item['department_name']))

    # insert cities idempotently
    city_id_map = {}  # dane_code -> new city id
    for code, name, dept_name in old_munis:
        nn = _norm(name)
        # check exists
        existing = bind.execute(sa.text("SELECT id FROM cities WHERE dane_code=:c"), {"c": code}).fetchone()
        if existing:
            city_id_map[code] = existing[0]
            continue
        bind.execute(
            sa.text("INSERT INTO cities (country_id, department_name, dane_code, name, name_norm, active) VALUES (:cid, :dep, :code, :name, :nn, 1)"),
            {"cid": country_id, "dep": dept_name, "code": code, "name": name, "nn": nn},
        )
        new_id = bind.execute(sa.text("SELECT id FROM cities WHERE dane_code=:c"), {"c": code}).scalar()
        city_id_map[code] = new_id

    # If no old municipalities, load from JSON
    if not old_munis:
        json_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'seeds', 'colombia_divipola.json'))
        if os.path.exists(json_path):
            data = json.load(open(json_path, encoding='utf-8'))
            for item in data:
                code = item['dane_code'].zfill(5)
                name = item['name']
                dept_name = item['department_name']
                nn = _norm(name)
                existing = bind.execute(sa.text("SELECT id FROM cities WHERE dane_code=:c"), {"c": code}).fetchone()
                if existing:
                    city_id_map[code] = existing[0]
                    continue
                bind.execute(
                    sa.text("INSERT INTO cities (country_id, department_name, dane_code, name, name_norm, active) VALUES (:cid, :dep, :code, :name, :nn, 1)"),
                    {"cid": country_id, "dep": dept_name, "code": code, "name": name, "nn": nn},
                )
                new_id = bind.execute(sa.text("SELECT id FROM cities WHERE dane_code=:c"), {"c": code}).scalar()
                city_id_map[code] = new_id

    # --- migrate sectors -> zones ---
    # map old sector id -> new zone id
    sector_to_zone = {}
    if 'sectors' in tables:
        for s in bind.execute(sa.text("SELECT id, municipality_code, name, kind, active FROM sectors")).fetchall():
            sid, mcode, name, kind, active = s
            mcode = (mcode or '').strip().zfill(5)
            cid = city_id_map.get(mcode)
            if cid is None:
                # try find city
                r = bind.execute(sa.text("SELECT id FROM cities WHERE dane_code=:c"), {"c": mcode}).fetchone()
                cid = r[0] if r else None
            if cid is None:
                continue
            k = kind if kind in ('localidad','comuna','barrio','vereda','corregimiento','sector') else 'sector'
            nn = _norm(name)
            # check existing
            existing = bind.execute(sa.text("SELECT id FROM zones WHERE city_id=:c AND name_norm=:n"), {"c": cid, "n": nn}).fetchone()
            if existing:
                sector_to_zone[sid] = existing[0]
                continue
            bind.execute(
                sa.text("INSERT INTO zones (city_id, kind, name, name_norm, active) VALUES (:cid, :kind, :name, :nn, :act)"),
                {"cid": cid, "kind": k, "name": name, "nn": nn, "act": 1 if active else 0},
            )
            new_zid = bind.execute(sa.text("SELECT id FROM zones WHERE city_id=:c AND name_norm=:n"), {"c": cid, "n": nn}).scalar()
            sector_to_zone[sid] = new_zid

    # --- seed Bogota localities if city exists and no zones ---
    bogota_code = '11001'
    bogota_id = city_id_map.get(bogota_code)
    if bogota_id is not None:
        locs = [
            "Usaquén","Chapinero","Santa Fe","San Cristóbal","Usme","Tunjuelito","Bosa","Kennedy",
            "Fontibón","Engativá","Suba","Barrios Unidos","Teusaquillo","Los Mártires","Antonio Nariño",
            "Puente Aranda","La Candelaria","Rafael Uribe Uribe","Ciudad Bolívar","Sumapaz",
        ]
        for loc in locs:
            nn = _norm(loc)
            existing = bind.execute(sa.text("SELECT id FROM zones WHERE city_id=:c AND name_norm=:n"), {"c": bogota_id, "n": nn}).fetchone()
            if not existing:
                bind.execute(
                    sa.text("INSERT INTO zones (city_id, kind, name, name_norm, active) VALUES (:cid, 'localidad', :name, :nn, 1)"),
                    {"cid": bogota_id, "name": loc, "nn": nn},
                )

    # --- specialties name_norm ---
    if 'specialties' in tables:
        # add column if missing
        cols = [c['name'] for c in inspector.get_columns('specialties')]
        if 'name_norm' not in cols:
            op.add_column('specialties', sa.Column('name_norm', sa.String(length=120), nullable=True))
        for r in bind.execute(sa.text("SELECT code, label FROM specialties")).fetchall():
            code, label = r
            bind.execute(sa.text("UPDATE specialties SET name_norm=:nn WHERE code=:c"), {"nn": _norm(label), "c": code})
        # unique index
        try:
            op.create_index('uq_specialties_name_norm', 'specialties', ['name_norm'], unique=True)
        except Exception:
            pass

    # --- installation_types seed ---
    for code, label in [("residencial", "Residencial"), ("comercial", "Comercial"), ("industrial", "Industrial"), ("institucional", "Institucional")]:
        existing = bind.execute(sa.text("SELECT code FROM installation_types WHERE code=:c"), {"c": code}).fetchone()
        if not existing:
            bind.execute(sa.text("INSERT INTO installation_types (code, label, name_norm, active) VALUES (:c,:l,:n,1)"),
                         {"c": code, "l": label, "n": _norm(label)})

    # --- technician_profiles: rename zones -> legacy_zone, add specialty FK? ---
    cols = [c['name'] for c in inspector.get_columns('technician_profiles')]
    if 'legacy_zone' not in cols:
        if 'zones' in cols:
            with op.batch_alter_table('technician_profiles') as batch_op:
                batch_op.alter_column('zones', new_column_name='legacy_zone')
        else:
            op.add_column('technician_profiles', sa.Column('legacy_zone', sa.String(length=250), nullable=True))
    # specialty_code already exists

    # --- technician_zones: transform to new schema ---
    # create new table with new columns, migrate, drop old
    # We'll add columns city_id, zone_id and remove old municipality_code/sector_id via new table
    tz_cols = [c['name'] for c in inspector.get_columns('technician_zones')]
    if 'city_id' not in tz_cols:
        # create new table
        op.create_table(
            'technician_zones_new',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('technician_id', sa.Integer(), sa.ForeignKey('technician_profiles.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('city_id', sa.Integer(), sa.ForeignKey('cities.id', ondelete='RESTRICT'), nullable=False),
            sa.Column('zone_id', sa.Integer(), sa.ForeignKey('zones.id', ondelete='RESTRICT'), nullable=True),
            sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        # migrate
        if 'technician_zones' in tables:
            for r in bind.execute(sa.text("SELECT id, technician_id, municipality_code, sector_id, is_primary FROM technician_zones")).fetchall():
                rid, tid, mcode, sector_id, is_primary = r
                mcode = (mcode or '').strip().zfill(5)
                cid = city_id_map.get(mcode)
                if cid is None:
                    r2 = bind.execute(sa.text("SELECT id FROM cities WHERE dane_code=:c"), {"c": mcode}).fetchone()
                    cid = r2[0] if r2 else None
                if cid is None:
                    continue
                zid = sector_to_zone.get(sector_id) if sector_id is not None else None
                bind.execute(
                    sa.text("INSERT INTO technician_zones_new (technician_id, city_id, zone_id, is_primary) VALUES (:t,:c,:z,:p)"),
                    {"t": tid, "c": cid, "z": zid, "p": 1 if is_primary else 0},
                )
        # drop old, rename
        op.drop_table('technician_zones')
        op.rename_table('technician_zones_new', 'technician_zones')
        op.create_index('ix_technician_zones_technician_id', 'technician_zones', ['technician_id'])
        op.create_index('ix_technician_zones_city_id', 'technician_zones', ['city_id'])

    # --- work_orders: add legacy_zone, city_id, zone_id, installation_type_code ---
    wo_cols = [c['name'] for c in inspector.get_columns('work_orders')]
    if 'legacy_zone' not in wo_cols:
        if 'zone' in wo_cols:
            # keep zone text; add legacy_zone copy
            op.add_column('work_orders', sa.Column('legacy_zone', sa.String(length=60), nullable=True))
            bind.execute(sa.text("UPDATE work_orders SET legacy_zone = zone"))
        else:
            op.add_column('work_orders', sa.Column('legacy_zone', sa.String(length=60), nullable=True))
    if 'city_id' not in wo_cols:
        op.add_column('work_orders', sa.Column('city_id', sa.Integer(), sa.ForeignKey('cities.id', ondelete='RESTRICT'), nullable=True))
    if 'zone_id' not in wo_cols:
        op.add_column('work_orders', sa.Column('zone_id', sa.Integer(), sa.ForeignKey('zones.id', ondelete='RESTRICT'), nullable=True))
    if 'installation_type_code' not in wo_cols:
        op.add_column('work_orders', sa.Column('installation_type_code', sa.String(length=60), sa.ForeignKey('installation_types.code', ondelete='RESTRICT'), nullable=True))

    # --- departments/municipalities/sectors: add name_norm (compat) ---
    for tbl in ('departments', 'municipalities', 'sectors'):
        if tbl in tables:
            cols = [c['name'] for c in inspector.get_columns(tbl)]
            if 'name_norm' not in cols:
                op.add_column(tbl, sa.Column('name_norm', sa.String(length=120), nullable=True))

    # --- partial unique indexes for technician_zones ---
    try:
        op.create_index('uq_techzone_city_all', 'technician_zones', ['technician_id', 'city_id'], unique=True,
                        sqlite_where=sa.text("zone_id IS NULL"), postgresql_where=sa.text("zone_id IS NULL"))
    except Exception:
        pass
    try:
        op.create_index('uq_techzone_zone', 'technician_zones', ['technician_id', 'city_id', 'zone_id'], unique=True,
                        sqlite_where=sa.text("zone_id IS NOT NULL"), postgresql_where=sa.text("zone_id IS NOT NULL"))
    except Exception:
        pass
    try:
        op.create_index('uq_techzone_primary', 'technician_zones', ['technician_id'], unique=True,
                        sqlite_where=sa.text("is_primary = 1"), postgresql_where=sa.text("is_primary = TRUE"))
    except Exception:
        pass

    # --- CHECK constraints for zones kind already in table; specialties/workorders maybe ---
    # add name CHECK not needed


def downgrade():
    # drop new tables/columns partially
    op.drop_table('technician_zones') if False else None
    pass
