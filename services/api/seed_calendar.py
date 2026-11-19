from datetime import datetime, timezone


from wsgi import app
from app.extensions import db
from app.workorders.models import WorkOrder
from app.calendar import service


with app.app_context():
    orders = WorkOrder.query.order_by(WorkOrder.id).all()
    for wo, hora in zip(orders, (14, 16, 18)):
        wo.scheduled_at = datetime(2026, 11, 3, hora, 0, tzinfo=timezone.utc)
        wo.scheduled_end = datetime(2026, 11, 3, hora + 1, 0, tzinfo=timezone.utc)
    db.session.commit()

    print("--- Guardado ---")
    for wo in WorkOrder.query.order_by(WorkOrder.id).all():
        print(wo.id, wo.scheduled_at, wo.scheduled_end)

    print("--- Calendario: 2026-11-03 ---")
    items, err = service.list_events("2026-11-03T00:00:00", "2026-11-04T00:00:00")
    print("error:", err)
    for i in items:
        print(i["order_code"], i["start"], i["status"], i["technicians"])

    print("--- Calendario: 2026-11-02 (debe estar vacío) ---")
    items, err = service.list_events("2026-11-02T00:00:00", "2026-11-03T00:00:00")
    print("error:", err, "| items:", len(items))
