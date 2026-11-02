from flask import Blueprint, request, jsonify

from app.extensions import db
from app.identity.decorators import require_auth, require_role
from app.catalogs.models import (
    Country, City, Zone, Specialty, InstallationType,
    Department, Municipality, Sector,
)
from app.common.normalize import normalize_text

blueprint = Blueprint("catalogs", __name__)


@blueprint.get("/catalogs/countries")
@require_auth
def list_countries():
    items = Country.query.filter_by(active=True).order_by(Country.name).all()
    return jsonify([c.to_dict() for c in items]), 200


@blueprint.get("/catalogs/cities")
@require_auth
def list_cities():
    country = request.args.get("country")  # iso2 or id
    q = request.args.get("q")
    query = City.query.filter_by(active=True)
    if country:
        # accept iso2 or numeric id
        if country.isdigit():
            query = query.filter_by(country_id=int(country))
        else:
            c = Country.query.filter_by(iso2=country.upper()).first()
            if c:
                query = query.filter_by(country_id=c.id)
            else:
                query = query.filter(City.country_id.is_(None))
    if q:
        nq = normalize_text(q)
        query = query.filter(City.name_norm.like(f"%{nq}%"))
    items = query.order_by(City.name).all()
    return jsonify([c.to_dict() for c in items]), 200


@blueprint.get("/catalogs/zones")
@require_auth
def list_zones():
    city = request.args.get("city")
    query = Zone.query.filter_by(active=True)
    if city:
        query = query.filter_by(city_id=int(city))
    items = query.order_by(Zone.name).all()
    return jsonify([z.to_dict() for z in items]), 200


@blueprint.get("/catalogs/specialties")
@require_auth
def list_specialties():
    items = Specialty.query.filter_by(active=True).order_by(Specialty.label).all()
    return jsonify([{"code": s.code, "label": s.label} for s in items]), 200


@blueprint.get("/catalogs/installation-types")
@require_auth
def list_installation_types():
    items = InstallationType.query.filter_by(active=True).order_by(InstallationType.label).all()
    return jsonify([{"code": i.code, "label": i.label} for i in items]), 200


@blueprint.post("/catalogs/zones")
@require_role("admin")
def create_zone():
    data = request.get_json() or {}
    city_id = data.get("city_id")
    name = data.get("name")
    kind = data.get("kind")
    if not city_id or not name or not kind:
        return jsonify({"error": "city_id, name, kind required"}), 422
    city = City.query.get(city_id)
    if not city:
        return jsonify({"error": "invalid city"}), 422
    if kind not in ("localidad", "comuna", "barrio", "vereda", "corregimiento", "sector"):
        return jsonify({"error": "invalid kind"}), 422
    clean_name = " ".join(str(name).split())
    nn = normalize_text(clean_name)
    if not nn:
        return jsonify({"error": "name required"}), 422
    existing = Zone.query.filter_by(city_id=city_id, name_norm=nn).first()
    if existing:
        return jsonify({"error": "zone already exists", "zone": existing.to_dict()}), 409
    z = Zone(city_id=city_id, name=clean_name, kind=kind, name_norm=nn, active=True)
    db.session.add(z)
    db.session.commit()
    return jsonify(z.to_dict()), 201


@blueprint.patch("/catalogs/zones/<int:zid>")
@require_role("admin")
def patch_zone(zid):
    z = Zone.query.get(zid)
    if not z:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    if "active" in data:
        z.active = bool(data["active"])
    if "name" in data:
        clean_name = " ".join(str(data["name"]).split())
        nn = normalize_text(clean_name)
        if not nn:
            return jsonify({"error": "name required"}), 422
        dup = Zone.query.filter(Zone.city_id == z.city_id, Zone.name_norm == nn, Zone.id != z.id).first()
        if dup:
            return jsonify({"error": "zone already exists", "zone": dup.to_dict()}), 409
        z.name = clean_name
        z.name_norm = nn
    if "kind" in data:
        if data["kind"] not in ("localidad", "comuna", "barrio", "vereda", "corregimiento", "sector"):
            return jsonify({"error": "invalid kind"}), 422
        z.kind = data["kind"]
    db.session.commit()
    return jsonify(z.to_dict()), 200


@blueprint.post("/catalogs/specialties")
@require_role("admin")
def create_specialty():
    data = request.get_json() or {}
    code = data.get("code")
    label = data.get("label")
    if not code or not label:
        return jsonify({"error": "code, label required"}), 422
    nn = normalize_text(label)
    if Specialty.query.get(code):
        return jsonify({"error": "code exists"}), 409
    if Specialty.query.filter_by(name_norm=nn).first():
        return jsonify({"error": "specialty already exists"}), 409
    s = Specialty(code=code, label=label.strip(), name_norm=nn, active=True)
    db.session.add(s)
    db.session.commit()
    return jsonify({"code": s.code, "label": s.label}), 201


@blueprint.post("/catalogs/installation-types")
@require_role("admin")
def create_installation_type():
    data = request.get_json() or {}
    code = data.get("code")
    label = data.get("label")
    if not code or not label:
        return jsonify({"error": "code, label required"}), 422
    nn = normalize_text(label)
    if InstallationType.query.get(code):
        return jsonify({"error": "code exists"}), 409
    if InstallationType.query.filter_by(name_norm=nn).first():
        return jsonify({"error": "already exists"}), 409
    i = InstallationType(code=code, label=label.strip(), name_norm=nn, active=True)
    db.session.add(i)
    db.session.commit()
    return jsonify({"code": i.code, "label": i.label}), 201


# legacy endpoints kept for compatibility (departments/municipalities/sectors)
@blueprint.get("/catalogs/departments")
@require_auth
def list_departments():
    items = Department.query.order_by(Department.name).all()
    return jsonify([{"code": d.code, "name": d.name} for d in items]), 200


@blueprint.get("/catalogs/municipalities")
@require_auth
def list_municipalities():
    dep = request.args.get("department")
    q = Municipality.query
    if dep:
        q = q.filter_by(department_code=dep)
    items = q.order_by(Municipality.name).all()
    return jsonify([{"code": m.code, "name": m.name, "department_code": m.department_code} for m in items]), 200


@blueprint.get("/catalogs/sectors")
@require_auth
def list_sectors():
    mun = request.args.get("municipality")
    q = Sector.query.filter_by(active=True)
    if mun:
        q = q.filter_by(municipality_code=mun)
    items = q.order_by(Sector.name).all()
    return jsonify([{"id": s.id, "name": s.name, "kind": s.kind, "municipality_code": s.municipality_code} for s in items]), 200
