"""Sonda de pruebas de SIGOS Windows: opera sobre la aplicacion real (modelos, config y BD de SIGOS_ENV_FILE).

Uso: python sql_probe.py <app_dir> <comando> [args]
  seed-user                 crea (idempotente) el usuario de prueba y devuelve su id
  enqueue <n>               encola n notificaciones de correo pendientes para ese usuario
  stats                     JSON con recuento por estado y suma/maximo de intentos
  process-once              ejecuta una vez process_pending() (como un ciclo del worker)
  ddl-denied                intenta CREATE TABLE con el usuario de la aplicacion: exit 0 si se deniega
  marker <put|count> [txt]  escribe / cuenta filas marcadoras (asunto = txt) para probar restauraciones
No imprime nunca credenciales.
"""
import json
import os
import sys

app_dir, cmd, *args = sys.argv[1:]
sys.path.insert(0, app_dir)

from sqlalchemy import func, text  # noqa: E402

from app import create_app  # noqa: E402
from app.config import ProductionConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.identity.models import User  # noqa: E402
from app.notifications.models import Notification  # noqa: E402

PROBE_USER = "wt_probe"

app = create_app(ProductionConfig)
with app.app_context():
    if cmd == "seed-user":
        u = User.query.filter_by(username=PROBE_USER).first()
        if not u:
            u = User(username=PROBE_USER, email="wt_probe@example.invalid", password_hash="!")
            db.session.add(u)
            db.session.commit()
        print(u.id)
    elif cmd == "enqueue":
        uid = User.query.filter_by(username=PROBE_USER).one().id
        prefix = args[1] if len(args) > 1 else "wt"
        for i in range(int(args[0])):
            db.session.add(Notification(user_id=uid, channel="email", recipient="nobody@example.invalid",
                                        subject=f"{prefix}-{i}", message="prueba"))
        db.session.commit()
        print(args[0])
    elif cmd == "stats":
        rows = db.session.query(Notification.status, func.count(), func.sum(Notification.retry_count),
                                func.max(Notification.retry_count)).group_by(Notification.status).all()
        print(json.dumps({s: {"n": n, "sum_retries": int(t or 0), "max_retries": int(m or 0)} for s, n, t, m in rows}))
    elif cmd == "process-once":
        # args: [latencia_envio_s] [inicio_epoch]. La latencia simula un SMTP real (el envio sin SMTP falla en
        # microsegundos y dos procesos no llegarian a solaparse); el inicio sincroniza procesos concurrentes.
        import time
        from app.notifications import service
        delay = float(args[0]) if args else 0.0
        if len(args) > 1:
            time.sleep(max(0.0, float(args[1]) - time.time()))
        real_send = service.send_notification
        send_log = os.environ.get("PROBE_SEND_LOG")

        def slow_send(channel, recipient, subject, message):
            # Registro de cada intento REAL de envio (el contador Intentos no sirve: dos procesos pueden pisarse).
            if send_log:
                with open(send_log, "a", encoding="utf-8") as fh:
                    fh.write(f"{os.getpid()}\t{subject}\n")
            if delay:
                time.sleep(delay)
            return real_send(channel, recipient, subject, message)

        service.send_notification = slow_send
        print(service.process_pending())
    elif cmd == "ddl-denied":
        try:
            db.session.execute(text("CREATE TABLE wt_ddl_probe (x INT)"))
            db.session.commit()
        except Exception as exc:  # se espera: permiso denegado
            db.session.rollback()
            print("denegado:", type(exc).__name__)
            sys.exit(0)
        db.session.execute(text("DROP TABLE wt_ddl_probe"))
        db.session.commit()
        print("PERMITIDO")
        sys.exit(1)
    elif cmd == "marker":
        uid = User.query.filter_by(username=PROBE_USER).one().id
        if args[0] == "put":
            db.session.add(Notification(user_id=uid, channel="email", recipient="m@example.invalid",
                                        subject=args[1], message="marker", status="sent"))
            db.session.commit()
        print(Notification.query.filter_by(subject=args[1]).count())
    else:
        sys.exit(f"comando desconocido: {cmd}")
