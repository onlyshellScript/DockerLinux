import json
from datetime import datetime, timezone

from app.extensions import db
from app.sync.models import SyncOperation, SYNC_SYNCED, SYNC_FAILED
from app.workorders.service import change_status, get_work_order
from app.identity.models import User


def push_operations(user_id, operations):
    results = []
    for op in operations:
        client_op_id = op.get("client_operation_id")
        op_type = op.get("operation_type")
        payload = op.get("payload", {})

        if not client_op_id or not op_type:
            results.append({"client_operation_id": client_op_id, "status": "error", "message": "missing fields"})
            continue

        existing = SyncOperation.query.filter_by(client_operation_id=client_op_id).first()
        if existing:
            results.append({"client_operation_id": client_op_id, "status": "duplicate", "server_status": existing.status})
            continue

        sync_op = SyncOperation(
            client_operation_id=client_op_id,
            operation_type=op_type,
            payload=json.dumps(payload),
            user_id=user_id,
        )
        db.session.add(sync_op)
        db.session.flush()

        try:
            if op_type == "change_status":
                wo_id = payload.get("work_order_id")
                to_status = payload.get("to_status")
                notes = payload.get("notes")
                user = db.session.get(User, user_id)
                wo, error = change_status(wo_id, to_status, user, notes)
                if error:
                    sync_op.status = SYNC_FAILED
                    sync_op.result = json.dumps({"error": error})
                    results.append({"client_operation_id": client_op_id, "status": "failed", "message": error})
                else:
                    sync_op.status = SYNC_SYNCED
                    sync_op.synced_at = datetime.now(timezone.utc)
                    sync_op.result = json.dumps({"work_order_id": wo.id, "status": wo.status})
                    results.append({"client_operation_id": client_op_id, "status": "synced"})
            elif op_type == "add_observation":
                from app.evidence.service import create_evidence
                wo_id = payload.get("work_order_id")
                description = payload.get("description")
                ev, error = create_evidence(wo_id, user_id, "observation", description=description)
                if error:
                    sync_op.status = SYNC_FAILED
                    sync_op.result = json.dumps({"error": error})
                    results.append({"client_operation_id": client_op_id, "status": "failed", "message": error})
                else:
                    sync_op.status = SYNC_SYNCED
                    sync_op.synced_at = datetime.now(timezone.utc)
                    sync_op.result = json.dumps({"evidence_id": ev.id})
                    results.append({"client_operation_id": client_op_id, "status": "synced"})
            else:
                sync_op.status = SYNC_FAILED
                sync_op.result = json.dumps({"error": "unknown operation_type"})
                results.append({"client_operation_id": client_op_id, "status": "failed", "message": "unknown operation_type"})
        except Exception as e:
            db.session.rollback()
            sync_op.status = SYNC_FAILED
            sync_op.result = json.dumps({"error": str(e)})
            results.append({"client_operation_id": client_op_id, "status": "failed", "message": str(e)})

    db.session.commit()
    return results


def pull_changes(user_id, since=None):
    from app.workorders.models import WorkOrder
    from app.materials.models import Material

    q = WorkOrder.query
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            q = q.filter(WorkOrder.updated_at > since_dt)
        except ValueError:
            pass
    work_orders = q.all()

    materials = Material.query.filter_by(is_active=True).all()

    now = datetime.now(timezone.utc).isoformat()
    return {
        "server_time": now,
        "work_orders": [w.to_dict() for w in work_orders],
        "materials": [m.to_dict() for m in materials],
    }
