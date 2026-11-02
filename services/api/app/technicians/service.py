import secrets
from datetime import datetime, timezone

from app.extensions import db
from app.identity.models import User, Role, AuditEvent
from app.identity.passwords import generate_username, generate_temporary_password, normalize_username
from app.materials.models import TechnicianProfile
from app.catalogs.models import City, Zone, TechnicianZone
from app.common.normalize import normalize_text


def _apply_coverage(profile, coverage_list):
    if coverage_list is None:
        return None
    if not isinstance(coverage_list, list):
        return "invalid_coverage"
    if len(coverage_list) == 0:
        return "coverage_required"
    if len(coverage_list) > 20:
        return "too_many_coverages"
    # clear existing
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
            # whole city
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


def _role_technician():
    return Role.query.filter_by(name="technician").first()


def _audit(actor_id, target_user_id, action, changes=None):
    ev = AuditEvent(actor_id=actor_id, target_user_id=target_user_id, action=action, changes=changes)
    db.session.add(ev)


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


def create_technician(data, actor_id):
    first_name = data["first_name"]
    last_name = data["last_name"]
    # validate specialty code
    spec_code = data.get("specialty_code") or data.get("specialty")
    from app.catalogs.models import Specialty
    if spec_code and not Specialty.query.get(spec_code):
        # try label match
        sp = Specialty.query.filter_by(label=spec_code).first()
        spec_code = sp.code if sp else None
    if not spec_code:
        return None, "invalid_specialty"
    spec_label = Specialty.query.get(spec_code).label if Specialty.query.get(spec_code) else spec_code
    # username
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
    password = generate_temporary_password()
    user = User(username=username, email=email, is_active=True, must_change_password=True)
    user.set_password(password)
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
        legacy_zone=data.get("legacy_zone"),
        document_type=data.get("document_type"),
        document_number=data.get("document_number") or data.get("document"),
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
    return {"profile": profile, "user": user, "temporary_password": password, "username": username}, None


def get_technician(tid):
    return TechnicianProfile.query.get(tid)


def update_technician(tid, data, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile:
        return None, "not_found"
    user = profile.user
    for field in ("first_name", "last_name", "phone", "email", "legacy_zone"):
        if field in data:
            setattr(profile, field, data[field])
    if "zones" in data and "legacy_zone" not in data:
        profile.legacy_zone = data.get("zones")
    if "specialty_code" in data or "specialty" in data:
        code = data.get("specialty_code") or data.get("specialty")
        from app.catalogs.models import Specialty
        sp = Specialty.query.get(code) or Specialty.query.filter_by(label=code).first()
        if sp:
            profile.specialty_code = sp.code
            profile.specialty = sp.label
    if "document_type" in data:
        profile.document_type = data["document_type"]
    if "document_number" in data or "document" in data:
        profile.document_number = data.get("document_number") or data.get("document")
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
    _audit(actor_id, profile.user_id, "update", str({k: data[k] for k in data if k != "password"}))
    db.session.commit()
    return profile, None


def set_availability(tid, value, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile:
        return None, "not_found"
    profile.is_available = value
    _audit(actor_id, profile.user_id, "update", f"availability={value}")
    db.session.commit()
    return profile, None


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


def unlock_technician(tid, actor_id):
    profile = TechnicianProfile.query.get(tid)
    if not profile or not profile.user:
        return None, "not_found"
    profile.user.failed_attempts = 0
    profile.user.locked_until = None
    _audit(actor_id, profile.user_id, "unlock", None)
    db.session.commit()
    return profile, None


def username_available(username):
    return User.query.filter_by(username=username.lower()).first() is None
