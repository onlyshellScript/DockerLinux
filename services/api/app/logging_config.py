import json
import logging
import sys
from datetime import datetime, timezone


# JsonFormatter: clase auxiliar para JsonFormatter.
class JsonFormatter(logging.Formatter):
# Gestiona format; recibe record; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        return json.dumps(log_entry)


# Gestiona setup logging; recibe app; sin efectos secundarios adicionales; devuelve el valor correspondiente.
def setup_logging(app):
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    fmt = app.config.get("LOG_FORMAT", "json")

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    app.logger.handlers = [handler]
    app.logger.setLevel(level)
    app.logger.propagate = False
