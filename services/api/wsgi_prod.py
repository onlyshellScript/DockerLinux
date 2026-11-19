import os

from app import create_app
from app.config_prod import ProductionConfig
from app.notifications.service import start_worker

app = create_app(ProductionConfig)

if os.getenv("ENABLE_NOTIFICATION_WORKER", "false").lower() == "true":
    start_worker(interval_seconds=int(os.getenv("NOTIFICATION_WORKER_INTERVAL", "30")))
