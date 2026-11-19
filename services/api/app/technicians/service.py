import os
import secrets
from datetime import datetime, timezone

from app.extensions import db
from app.identity.models import User, Role, AuditEvent
from app.identity.passwords import generate_username, normalize_username, generate_temporary_password
from app.materials.models import TechnicianProfile
from app.catalogs.models import City, Zone, TechnicianZone, Department, Municipality
from app.common.normalize import normalize_text


# Aplica la configuracion solicitada; recibe profile, coverage_list; interactua con la base de datos; devuelve el valor correspondiente.
def _apply_coverage(profile, coverage_list):
    if coverage_list is None:
        return None
    if not isinstance(coverage_list, list):
        return "invalid_coverage"
    if len(coverage_list) == 0:
        return "coverage_required"
    if len(coverage_list) > 20:
        return "too_many_coverages"
    TechnicianZone.query.filter_by(technician_id=profile.id).delete()
    primary_seen = False
    seen = set()
    for item in coverage_list:
        city_id = item.get("city_id")
        zone_ids = item.get("zone_ids", None)
        # support zone_ids list or single zone_id
        if zone_ids is None and "zone_id" in item:
            zone_ids = [item.get("zone_id")] if item.get("zone_id") is not None else None
        is_primary = bool(item.get("is_primary", False))
        city = City.query.get(city_id)
        if not city:
            return "invalid_city"
        if is_primary:
            if primary_seen:
                return "multiple_primary"
            primary_seen = True
        if zone_ids is None:
            key = (city_id, None)
            if key in seen:
                return "duplicate_coverage"
            seen.add(key)
            tz = TechnicianZone(technician_id=profile.id, city_id=city_id, zone_id=None, is_primary=is_primary)
            db.session.add(tz)
        else:
            if not isinstance(zone_ids, list):
                return "invalid_coverage"
            if len(zone_ids) == 0:
                # treat as whole city? spec uses zone_ids[]|null; empty -> whole city
                key = (city_id, None)
                if key in seen:
                    return "duplicate_coverage"
                seen.add(key)
                tz = TechnicianZone(technician_id=profile.id, city_id=city_id, zone_id=None, is_primary=is_primary)
                db.session.add(tz)
            else:
                for zid in zone_ids:
                    if zid is None:
                        continue
                    zone = Zone.query.get(zid)
                    if not zone or zone.city_id != city_id:
                        return "invalid_zone"
                    key = (city_id, zid)
                    if key in seen:
                        return "duplicate_coverage"
                    seen.add(key)
                    tz = TechnicianZone(technician_id=profile.id, city_id=city_id, zone_id=zid, is_primary=is_primary)
                    db.session.add(tz)
    if not primary_seen:
        # mark first as primary
        first = TechnicianZone.query.filter_by(technician_id=profile.id).first()
        if first:
            first.is_primary = True
    return None


# _role_technician: obtiene el rol "technician" desde la base de datos; sin parametros; salida Role o None; lee la base de datos.
def _role_technician():
    return Role.query.filter_by(name="technician").first()


# _audit: registra un evento de auditoria para un tecnico; entradas actor_id, target_user_id, action, changes; efecto secundario agrega AuditEvent a la sesion.
def _audit(actor_id, target_user_id, action, changes=None):
    ev = AuditEvent(actor_id=actor_id, target_user_id=target_user_id, action=action, changes=changes)
    db.session.add(ev)


# Lista los registros que cumplen los filtros indicados; recibe q, status, zone, city_id, zone_id, specialty, active, page, page_size; interactua con la base de datos; devuelve el valor correspondiente.
def list_technicians(q=None, status=None, zone=None, city_id=None, zone_id=None, specialty=None, active=None, page=1, page_size=20):
    query = TechnicianProfile.query
    if active is not None:
        query = query.filter(TechnicianProfile.is_active == active)
    if status:
        query = query.filter(TechnicianProfile.is_available == (status == "available"))
    if city_id or zone_id:
        from app.catalogs.models import TechnicianZone
        sub = TechnicianZone.query
        if city_id:
            sub = sub.filter(TechnicianZone.city_id == int(city_id))
        if zone_id:
            sub = sub.filter(TechnicianZone.zone_id == int(zone_id))
        ids = [r.technician_id for r in sub.all()]
        query = query.filter(TechnicianProfile.id.in_(ids if ids else [-1]))
    if zone:
        query = query.filter(TechnicianProfile.legacy_zone.ilike(f"%{zone}%"))
    if specialty:
        query = query.filter(db.or_(TechnicianProfile.specialty_code == specialty, TechnicianProfile.specialty == specialty))
    if q:
        like = f"%{q}%"
        query = query.join(User).filter(
            db.or_(
                TechnicianProfile.first_name.ilike(like),
                TechnicianProfile.last_name.ilike(like),
                User.username.ilike(like),
                TechnicianProfile.phone.ilike(like),
                TechnicianProfile.specialty.ilike(like),
            )
        )
    total = query.count()
    items = query.order_by(TechnicianProfile.id).offset((page - 1) * page_size).limit(page_size).all()
    # open orders count per tech
    from app.workorders.models import WorkOrder
    for t in items:
        t.open_orders = WorkOrder.query.filter(
            WorkOrder.assigned_to_id == (t.user_id),
            WorkOrder.status.in_(["pending", "assigned", "in_progress"]),
        ).count()
    counts = {
        "available": TechnicianProfile.query.filter_by(is_available=True, is_active=True).count(),
        "busy": 0,
        "off_duty": TechnicianProfile.query.filter_by(is_available=False, is_active=True).count(),
        "total": TechnicianProfile.query.filter_by(is_active=True).count(),
    }
    # busy = available false but active? approximate
    return {"items": items, "total": total, "counts": counts}


# Gestiona concat names; recibe first, second; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def _concat_names(first, second):
    first = (first or "").strip()
    second = (second or "").strip()
    if second:
        return (first + " " + second).strip()
    return first

# Crea el registro solicitado con los datos recibidos; recibe data, actor_id; interactua con la base de datos; accede al sistema de archivos; devuelve el valor correspondiente.
def create_technician(data, actor_id):
    first_name = _concat_names(data.get("first_name"), data.get("second_name") or data.get("middle_name") or data.get("segundo_nombre"))
    last_name = _concat_names(data.get("last_name"), data.get("second_last_name") or data.get("second_surname") or data.get("segundo_apellido"))
    if not first_name or not last_name:
        return None, "missing_fields"
    document_type = data.get("document_type")
    document_number = data.get("document_number") or data.get("document")
    if not document_type or not document_number:
        return None, "missing_document"
    allowed_doc_types = {"CC", "CE", "TI", "PPT", "PASAPORTE"}
    if document_type not in allowed_doc_types:
        return None, "invalid_document_type"
    if TechnicianProfile.query.filter_by(document_type=document_type, document_number=document_number).first():
        return None, "document_taken"
    spec_code = data.get("specialty_code") or data.get("specialty")
    from app.catalogs.models import Specialty
    spec_label = None
    if spec_code:
        sp = Specialty.query.get(spec_code) or Specialty.query.filter_by(label=spec_code).first()
        if not sp:
            return None, "invalid_specialty"
        spec_code = sp.code
        spec_label = sp.label
    dep_code = data.get("department_code") or data.get("department")
    mun_code = data.get("municipality_code") or data.get("municipality")
    legacy_zone = data.get("legacy_zone") or data.get("zones")
    if dep_code or mun_code:
        if not dep_code or not mun_code:
            return None, "invalid_zone"
        dep = Department.query.get(dep_code)
        mun = Municipality.query.get(mun_code)
        if not dep:
            return None, "invalid_department"
        if not mun:
            return None, "invalid_municipality"
        if mun.department_code != dep.code:
            return None, "municipality_not_in_department"
        legacy_zone = f"{dep.code}-{mun.code}"
    existing = {u.username for u in User.query.all()}
    if data.get("username"):
        username = data["username"].lower()
        if username in existing:
            return None, "username_taken"
    else:
        username = generate_username(first_name, last_name, existing)
    email = data.get("email") or f"{username}@sigos.local"
    if User.query.filter_by(email=email).first():
        email = f"{username}@sigos.local"
    initial_password = os.getenv("TECH_INITIAL_PASSWORD")
    if not initial_password:
        return None, "initial_password_not_configured"
    user = User(username=username, email=email, is_active=True, must_change_password=True)
    user.set_password(initial_password)
    role = _role_technician()
    if role:
        user.roles.append(role)
    db.session.add(user)
    db.session.flush()
    profile = TechnicianProfile(
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        phone=data.get("phone"),
        email=email,
        specialty=spec_label,
        specialty_code=spec_code,
        legacy_zone=legacy_zone,
        document_type=document_type,
        document_number=document_number,
        is_available=data.get("is_available", True),
        is_active=True,
        created_by_id=actor_id,
    )
    db.session.add(profile)
    db.session.flush()
    err = _apply_coverage(profile, data.get("coverage") or data.get("coverages"))
    if err:
        db.session.rollback()
        return None, err
    _audit(actor_id, user.id, "create", f"first_name={first_name};last_name={last_name}")
    db.session.commit()
    return {"profile": profile, "user": user, "username": username}, None


# get_technician: obtiene un perfil de tecnico por su id; entrada tid; salida TechnicianProfile o None; lee la base de datos.
def get_technician(tid):
    return TechnicianProfile.query.get(tid)


# Actualiza los campos indicados del registro; recibe tid, data, actor_id; interactua con la base de datos; devuelve el valor correspondiente.
def update_technician(tid, data, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile:
        return None, "not_found"
    user = profile.user
    if any(k in data for k in ("password", "new_password", "temporary_password", "initial_password")):
        return None, "password_not_allowed"
    if "first_name" in data or "second_name" in data or "middle_name" in data or "segundo_nombre" in data:
        fn = data.get("first_name", profile.first_name)
        sn = data.get("second_name") or data.get("middle_name") or data.get("segundo_nombre")
        if sn is not None:
            profile.first_name = _concat_names(fn, sn)
        elif "first_name" in data:
            profile.first_name = (data.get("first_name") or "").strip()
    if "last_name" in data or "second_last_name" in data or "second_surname" in data or "segundo_apellido" in data:
        ln = data.get("last_name", profile.last_name)
        sln = data.get("second_last_name") or data.get("second_surname") or data.get("segundo_apellido")
        if sln is not None:
            profile.last_name = _concat_names(ln, sln)
        elif "last_name" in data:
            profile.last_name = (data.get("last_name") or "").strip()
    for field in ("phone", "email", "legacy_zone"):
        if field in data:
            setattr(profile, field, data[field])
    if "zones" in data and "legacy_zone" not in data:
        profile.legacy_zone = data.get("zones")
    if "specialty_code" in data or "specialty" in data:
        code = data.get("specialty_code") or data.get("specialty")
        from app.catalogs.models import Specialty
        if code is None or code == "":
            profile.specialty_code = None
            profile.specialty = None
        else:
            sp = Specialty.query.get(code) or Specialty.query.filter_by(label=code).first()
            if sp:
                profile.specialty_code = sp.code
                profile.specialty = sp.label
    if "document_type" in data:
        dt = data["document_type"]
        allowed_doc_types = {"CC", "CE", "TI", "PPT", "PASAPORTE"}
        if dt not in allowed_doc_types:
            return None, "invalid_document_type"
        profile.document_type = dt
    if "document_number" in data or "document" in data:
        dn = data.get("document_number") or data.get("document")
        if dn is not None and dn != profile.document_number:
            if TechnicianProfile.query.filter(TechnicianProfile.id != profile.id, TechnicianProfile.document_type == (data.get("document_type") or profile.document_type), TechnicianProfile.document_number == dn).first():
                return None, "document_taken"
        profile.document_number = dn
    dep_code = data.get("department_code") or data.get("department")
    mun_code = data.get("municipality_code") or data.get("municipality")
    if dep_code or mun_code:
        if not dep_code or not mun_code:
            return None, "invalid_zone"
        dep = Department.query.get(dep_code)
        mun = Municipality.query.get(mun_code)
        if not dep:
            return None, "invalid_department"
        if not mun:
            return None, "invalid_municipality"
        if mun.department_code != dep.code:
            return None, "municipality_not_in_department"
        profile.legacy_zone = f"{dep.code}-{mun.code}"
    if "is_available" in data:
        profile.is_available = data["is_available"]
    if "is_active" in data:
        profile.is_active = data["is_active"]
        if user:
            user.is_active = data["is_active"]
    if "username" in data and user:
        new_username = data["username"].lower()
        if new_username != user.username and User.query.filter_by(username=new_username).first():
            return None, "username_taken"
        user.username = new_username
    if "coverage" in data or "coverages" in data:
        err = _apply_coverage(profile, data.get("coverage") or data.get("coverages"))
        if err:
            db.session.rollback()
            return None, err
    _audit(actor_id, profile.user_id, "update", str({k: data[k] for k in data if k not in ("password", "new_password", "temporary_password", "initial_password")}))
    db.session.commit()
    return profile, None


# Gestiona set availability; recibe tid, value, actor_id; interactua con la base de datos; devuelve el valor correspondiente.
def set_availability(tid, value, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile:
        return None, "not_found"
    profile.is_available = value
    _audit(actor_id, profile.user_id, "update", f"availability={value}")
    db.session.commit()
    return profile, None


# Gestiona deactivate technician; recibe tid, actor_id, reason; interactua con la base de datos; devuelve el valor correspondiente.
def deactivate_technician(tid, actor_id, reason=None):
    profile = TechnicianProfile.query.get(tid)
    if not profile:
        return None, "not_found"
    from app.workorders.models import WorkOrder
    open_count = WorkOrder.query.filter(
        WorkOrder.assigned_to_id == profile.user_id,
        WorkOrder.status.in_(["pending", "assigned", "in_progress"]),
    ).count()
    if open_count > 0:
        return None, "open_orders"
    profile.is_active = False
    if profile.user:
        profile.user.is_active = False
    _audit(actor_id, profile.user_id, "deactivate", reason)
    db.session.commit()
    return profile, None


# Gestiona activate technician; recibe tid, actor_id; interactua con la base de datos; devuelve el valor correspondiente.
def activate_technician(tid, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile:
        return None, "not_found"
    profile.is_active = True
    if profile.user:
        profile.user.is_active = True
    _audit(actor_id, profile.user_id, "activate", None)
    db.session.commit()
    return profile, None


# Gestiona reset password; recibe tid, actor_id; interactua con la base de datos; devuelve el valor correspondiente.
def reset_password(tid, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile or not profile.user:
        return None, "not_found"
    password = generate_temporary_password()
    profile.user.set_password(password)
    profile.user.must_change_password = True
    profile.user.failed_attempts = 0
    profile.user.locked_until = None
    _audit(actor_id, profile.user_id, "reset_password", None)
    db.session.commit()
    return password, profile.user.username


# Gestiona unlock technician; recibe tid, actor_id; interactua con la base de datos; devuelve el valor correspondiente.
def unlock_technician(tid, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile or not profile.user:
        return None, "not_found"
    profile.user.failed_attempts = 0
    profile.user.locked_until = None
    _audit(actor_id, profile.user_id, "unlock", None)
    db.session.commit()
    return profile, None


# username_available: indica si un nombre de usuario esta disponible (no existe); entrada username; salida bool; lee la base de datos.
def username_available(username):
    return User.query.filter_by(username=username.lower()).first() is None
