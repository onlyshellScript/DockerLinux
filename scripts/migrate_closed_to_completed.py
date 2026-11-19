import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))
from app import create_app
from app.config import Config
from app.extensions import db
from app.workorders.models import WorkOrder, WorkOrderStatusHistory

# Migra el estado 'closed' al nuevo estado 'completed' en órdenes de trabajo e historial; con --dry-run solo muestra conteos sin modificar datos; efecto secundario: actualiza filas en BD y confirma la transacción.
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    app = create_app(Config)
    with app.app_context():
        closed_orders = WorkOrder.query.filter(WorkOrder.status == "closed").count()
        closed_history_to = WorkOrderStatusHistory.query.filter(WorkOrderStatusHistory.to_status == "closed").count()
        closed_history_from = WorkOrderStatusHistory.query.filter(WorkOrderStatusHistory.from_status == "closed").count()
        print("closed work_orders:", closed_orders)
        print("history to_status=closed:", closed_history_to)
        print("history from_status=closed:", closed_history_from)
        if args.dry_run:
            return
        WorkOrder.query.filter(WorkOrder.status == "closed").update({"status": "completed"}, synchronize_session=False)
        WorkOrderStatusHistory.query.filter(WorkOrderStatusHistory.to_status == "closed").update({"to_status": "completed"}, synchronize_session=False)
        WorkOrderStatusHistory.query.filter(WorkOrderStatusHistory.from_status == "closed").update({"from_status": "completed"}, synchronize_session=False)
        db.session.commit()
        print("migrated")

if __name__ == "__main__":
    main()
