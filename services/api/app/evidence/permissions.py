# -*- coding: utf-8 -*-
def _roles(roles):
    return set(roles or [])


def can_access_work_order(user_id, roles, work_order):
    roles = _roles(roles)
    if work_order is None:
        return False
    if "admin" in roles or "dispatcher" in roles:
        return True
    return work_order.assigned_to_id == user_id


def can_create_evidence(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)


def can_view_evidence(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)


def can_download_evidence(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)


def can_review_evidence(roles):
    roles = _roles(roles)
    return "admin" in roles or "dispatcher" in roles


def can_manage_checklist(user_id, roles, work_order):
    return can_access_work_order(user_id, roles, work_order)
