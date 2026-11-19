"""Worker de notificaciones como proceso independiente (servicio `worker` del compose).

Se ejecuta en un único proceso para no duplicar envíos cuando gunicorn usa varios workers.
"""
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import ProductionConfig  # noqa: E402
from app.notifications.service import process_pending  # noqa: E402

_running = True


def _stop(*_):
    global _running
    _running = False


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    interval = int(os.getenv("NOTIFICATION_WORKER_INTERVAL", "30"))
    app = create_app(ProductionConfig)
    print(f"[worker] Notificaciones cada {interval}s", flush=True)
    while _running:
        with app.app_context():
            try:
                n = process_pending()
                if n:
                    print(f"[worker] Procesadas {n} notificaciones", flush=True)
            except Exception as exc:  # el worker no debe morir por un fallo puntual
                print(f"[worker] Error: {exc}", flush=True)
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
