import os

from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app
from app.config_prod import ProductionConfig
from app.notifications.service import start_worker

app = create_app(ProductionConfig)

# La API solo es alcanzable a traves del proxy (Caddy), que fija X-Forwarded-*: se confia en un salto.
# PROXY_FIX_HOPS=0 lo desactiva (p. ej. si la API se expusiera sin proxy).
_hops = int(os.getenv("PROXY_FIX_HOPS", "1"))
if _hops > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_hops, x_proto=_hops, x_host=_hops)

if os.getenv("ENABLE_NOTIFICATION_WORKER", "false").lower() == "true":
    start_worker(app, interval_seconds=int(os.getenv("NOTIFICATION_WORKER_INTERVAL", "30")))
