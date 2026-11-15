import pytest

from app.identity.models import User, Role
from app.extensions import db

EXEMPT = {"auth.login", "auth.refresh", "health.health", "static"}

ACCESS_RULES = {
    'auth.change_password_route': 'any',
    'auth.login': 'public',
    'auth.refresh': 'public',
    'auth.users_create': ['admin'],
    'auth.users_get': ['admin'],
    'auth.users_list': ['admin'],
    'auth.users_update': ['admin'],
    'calendar.authorize_sunday': ['admin'],
    'calendar.availability': 'any',
    'calendar.events': 'any',
    'calendar.unassigned': 'any',
    'calendar.validate': 'any',
    'catalogs.create_installation_type': ['admin'],
    'catalogs.create_specialty': ['admin'],
    'catalogs.create_zone': ['admin'],
    'catalogs.list_cities': 'any',
    'catalogs.list_countries': 'any',
    'catalogs.list_departments': 'any',
    'catalogs.list_installation_types': 'any',
    'catalogs.list_municipalities': 'any',
    'catalogs.list_sectors': 'any',
    'catalogs.list_specialties': 'any',
    'catalogs.list_zones': 'any',
    'catalogs.patch_zone': ['admin'],
    'dashboard.dashboard_summary': ['admin', 'dispatcher'],
    'dashboard.dashboard_tecnico': ['technician'],
    'tecnico.mi_dashboard': ['technician'],
    'tecnico.mis_ordenes': ['technician'],
    'tecnico.mis_orden_detalle': ['technician'],
    'tecnico.mis_orden_estado': ['technician'],
    'tecnico.mis_orden_materiales': ['technician'],
    'tecnico.mi_camioneta': ['technician'],
    'tecnico.mi_perfil': ['technician'],
    'evidence.checklist_create': 'any',
    'evidence.checklist_list': 'any',
    'evidence.checklist_patch': 'any',
    'evidence.evidence_admin_detail': 'any',
    'evidence.evidence_approve': ['admin'],
    'evidence.evidence_approve_single': ['admin'],
    'evidence.evidence_detail': 'any',
    'evidence.evidence_events_list': 'any',
    'evidence.evidence_expediente_detail': 'any',
    'evidence.evidence_inbox': ['admin', 'dispatcher'],
    'evidence.evidence_reject': ['admin'],
    'evidence.evidence_reject_single': ['admin'],
    'evidence.evidence_request_correction': ['admin'],
    'evidence.evidence_request_correction_single': ['admin'],
    'evidence.evidence_resubmit': 'any',
    'evidence.evidence_resubmit_alias': 'any',
    'evidence.evidence_review': ['admin', 'dispatcher'],
    'evidence.evidence_reviews_list': 'any',
    'evidence.evidence_send_alias': 'any',
    'evidence.evidence_start_review': ['admin', 'dispatcher'],
    'evidence.evidence_start_review_single': ['admin', 'dispatcher'],
    'evidence.evidence_status': 'any',
    'evidence.evidence_submit': 'any',
    'evidence.evidence_submit_single': 'any',
    'evidence.evidences_create': 'any',
    'evidence.evidences_delete': ['admin'],
    'evidence.evidences_download': 'any',
    'evidence.evidences_list': 'any',
    'evidence.evidences_list_mine': 'any',
    'evidence.signatures_create': 'any',
    'evidence.signatures_list': 'any',
    'health.health': 'public',
    'materials.catalog_create': ['admin'],
    'materials.catalog_list': 'any',
    'materials.categories_list': 'any',
    'materials.consume_work_order_material': ['admin', 'dispatcher', 'technician'],
    'materials.material_requests_approve': ['admin', 'dispatcher'],
    'materials.material_requests_cancel': 'any',
    'materials.material_requests_create': 'any',
    'materials.material_requests_deliver': ['admin', 'dispatcher'],
    'materials.material_requests_events': 'any',
    'materials.material_requests_get': 'any',
    'materials.material_requests_list': 'any',
    'materials.material_requests_reject': ['admin', 'dispatcher'],
    'materials.material_requests_submit': 'any',
    'materials.material_requests_update': 'any',
    'materials.materials_consume': ['admin', 'dispatcher', 'technician'],
    'materials.materials_create': ['admin', 'dispatcher'],
    'materials.materials_export': ['admin', 'dispatcher'],
    'materials.materials_export_download': ['admin', 'dispatcher'],
    'materials.materials_export_preview': ['admin', 'dispatcher'],
    'materials.materials_get': 'any',
    'materials.materials_list': 'any',
    'materials.materials_movement': ['admin', 'dispatcher'],
    'materials.materials_movements_list': 'any',
    'materials.materials_transfer': ['admin', 'dispatcher'],
    'materials.materials_update': ['admin', 'dispatcher'],
    'materials.profiles_create': ['admin'],
    'materials.profiles_get': 'any',
    'materials.profiles_list': 'any',
    'materials.profiles_update': ['admin', 'dispatcher'],
    'materials.technician_stock_list': 'any',
    'materials.units_list': 'any',
    'materials.work_order_material_requests': 'any',
    'notifications.notifications_create': ['admin', 'dispatcher'],
    'notifications.notifications_list': 'any',
    'notifications.notifications_process': ['admin'],
    'reportes.reportes_ordenes': ['admin', 'dispatcher'],
    'settings.audit_export': ['admin'],
    'settings.audit_list': ['admin'],
    'settings.get_notif': 'any',
    'settings.get_notif_me': 'any',
    'settings.get_ops': 'any',
    'settings.get_org': 'any',
    'settings.get_sec': ['admin'],
    'settings.ops_impact': ['admin'],
    'settings.patch_notif': ['admin'],
    'settings.patch_notif_me': 'any',
    'settings.patch_ops': ['admin'],
    'settings.patch_org': ['admin'],
    'settings.patch_sec': ['admin'],
    'settings.public': 'any',
    'sync.sync_pull': 'any',
    'sync.sync_push': 'any',
    'technicians.activate': ['admin'],
    'technicians.create_technician': ['admin'],
    'technicians.deactivate': ['admin'],
    'technicians.get_technician': ['admin', 'dispatcher', 'technician'],
    'technicians.list_technicians': ['admin', 'dispatcher'],
    'technicians.patch_availability': 'any',
    'technicians.patch_technician': ['admin'],
    'technicians.reset_password': ['admin'],
    'technicians.unlock': ['admin'],
    'technicians.username_available': 'any',
    'workorders.work_orders_assign': 'any',
    'workorders.work_orders_bulk': ['admin', 'dispatcher'],
    'workorders.work_orders_change_status': 'any',
    'workorders.work_orders_create': ['dispatcher'],
    'workorders.work_orders_export': 'any',
    'workorders.work_orders_get': 'any',
    'workorders.work_orders_history': 'any',
    'workorders.work_orders_list': 'any',
    'workorders.work_orders_materials': ['dispatcher', 'technician'],
    'workorders.work_orders_patch': 'any',
    'workorders.work_orders_reschedule': 'any',
    'workorders.work_orders_schedule': 'any',
    'workorders.work_orders_timeline': 'any',
    'workorders.work_orders_transition': 'any',
    'workorders.work_orders_update': ['dispatcher'],
}

ROLES = ["admin", "dispatcher", "technician"]

def _seed_users(app):
    with app.app_context():
        for name, desc in [("admin","Administrador"),("dispatcher","Despachador"),("technician","Tecnico")]:
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, description=desc))
        db.session.flush()
        for name, pwd in [("admin","Admin123!"),("dispatcher","Disp123!"),("technician","Tech123!")]:
            if not User.query.filter_by(username=name).first():
                u = User(username=name, email="{}@test.local".format(name))
                u.set_password(pwd)
                role = Role.query.filter_by(name=name).first()
                u.roles.append(role)
                db.session.add(u)
        db.session.commit()

@pytest.fixture
def tokens(app, client):
    _seed_users(app)
    out = {}
    for name, pwd in [("admin","Admin123!"),("dispatcher","Disp123!"),("technician","Tech123!")]:
        r = client.post("/api/v1/auth/login", json={"username": name, "password": pwd})
        out[name] = r.get_json()["access_token"]
    return out

def _path(rule):
    p = str(rule.rule)
    for token in ["<int:user_id>","<int:wo_id>","<int:mat_id>","<int:tid>","<int:zid>","<int:profile_id>","<int:req_id>","<int:ev_id>","<int:item_id>"]:
        p = p.replace(token, "1")
    return p

def _method(rule):
    ms = sorted(m for m in rule.methods if m not in ("HEAD","OPTIONS"))
    return ms[0] if ms else "GET"

@pytest.mark.parametrize("endpoint", sorted(ACCESS_RULES))
def test_rnf05_access_matrix(client, app, tokens, endpoint):
    assert endpoint in ACCESS_RULES, "ruta sin regla declarada: {}".format(endpoint)
    rule = next(r for r in app.url_map.iter_rules() if r.endpoint == endpoint)
    allowed = ACCESS_RULES[endpoint]
    path = _path(rule)
    method = _method(rule)
    for role in [None] + ROLES:
        headers = {}
        if role is not None:
            headers["Authorization"] = "Bearer {}".format(tokens[role])
        resp = client.open(path, method=method, headers=headers, json={})
        if allowed == "public":
            assert resp.status_code not in (401, 403), "{} {} got {}".format(endpoint, role, resp.status_code)
        elif allowed == "any":
            if role is None:
                assert resp.status_code in (401, 403), "{} {} expected 401/403 got {}".format(endpoint, role, resp.status_code)
            else:
                assert resp.status_code != 401, "{} {} got 401 (posible fuga)".format(endpoint, role)
        else:
            if role is None or role not in allowed:
                assert resp.status_code in (401, 403), "{} {} expected 401/403 got {}".format(endpoint, role, resp.status_code)
            else:
                assert resp.status_code != 401, "{} {} got 401 (posible fuga)".format(endpoint, role)

def test_rnf05_new_route_must_be_declared(app):
    for rule in app.url_map.iter_rules():
        if rule.endpoint in ("static",) or rule.endpoint.startswith("static"):
            continue
        assert rule.endpoint in ACCESS_RULES, "ruta sin regla declarada: {}".format(rule.endpoint)
