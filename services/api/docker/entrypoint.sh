#!/usr/bin/env bash
# Entrypoint del contenedor SIGOS API.
#   api     (por defecto) prepara la BD, migra y arranca gunicorn
#   worker  arranca el worker de notificaciones
#   migrate solo prepara la BD y migra
#   otro    ejecuta el comando tal cual (p. ej. bash)
set -euo pipefail

cd /app

case "${1:-api}" in
  api)
    python docker/prepare_db.py
    exec gunicorn --bind 0.0.0.0:5000 \
      --workers "${GUNICORN_WORKERS:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --access-logfile - --error-logfile - \
      wsgi_prod:app
    ;;
  worker)
    RUN_MIGRATIONS=false python docker/prepare_db.py
    exec python docker/worker.py
    ;;
  migrate)
    exec python docker/prepare_db.py
    ;;
  *)
    exec "$@"
    ;;
esac
