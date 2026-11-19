# -*- coding: utf-8 -*-
def _roles(roles):
    return set(roles or [])


# Gestiona can access work order; recibe user_id, roles, work_order; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def can_access_work_order(user_id, roles, work_order):
    roles = _roles(roles)
    if work_order is None:
        return False
    if "admin" in roles or "dispatcher" in roles:
        return True
    return work_order.assigned_to_id == user_id


# can_create_evidence: indica si el usuario puede crear evidencia para la orden, reutilizando la regla de acceso a la orden; entradas user_id, roles, work_order; salida bool; sin efectos secundarios.
def can_create_evidence(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)


# can_view_evidence: indica si el usuario puede ver evidencias de la orden, reutilizando la regla de acceso a la orden; entradas user_id, roles, work_order; salida bool; sin efectos secundarios.
def can_view_evidence(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)


# can_download_evidence: indica si el usuario puede descargar evidencias de la orden, reutilizando la regla de acceso a la orden; entradas user_id, roles, work_order; salida bool; sin efectos secundarios.
def can_download_evidence(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)


# can_review_evidence: indica si los roles pueden revisar/aprobar evidencias (admin o dispatcher); entrada roles; salida bool; sin efectos secundarios.
def can_review_evidence(roles):
    roles = _roles(roles)
    return "admin" in roles or "dispatcher" in roles


# can_manage_checklist: indica si el usuario puede gestionar el checklist de la orden, reutilizando la regla de acceso a la orden; entradas user_id, roles, work_order; salida bool; sin efectos secundarios.
def can_manage_checklist(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)
