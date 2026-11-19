import logging
import threading
from datetime import datetime, timezone

from app.extensions import db
from app.notifications.models import (
    Notification, CHANNEL_EMAIL, CHANNEL_WHATSAPP,
    STATUS_PENDING, STATUS_SENT, STATUS_FAILED, MAX_RETRIES,
)
from app.notifications.senders import send_notification

logger = logging.getLogger(__name__)

# Control de ejecucion del worker.
_process_lock = threading.Lock()
_worker_state_lock = threading.Lock()
_worker_stop_event = threading.Event()
_worker_thread = None


def enqueue_notification(user_id, channel, recipient, subject, message):
    if channel not in (CHANNEL_EMAIL, CHANNEL_WHATSAPP):
        return None

    n = Notification(
        user_id=user_id,
        channel=channel,
        recipient=recipient,
        subject=subject,
        message=message,
    )
    db.session.add(n)
    db.session.commit()
    return n


def process_pending(limit=50):
    # Evita que el worker y el endpoint manual procesen simultaneamente.
    if not _process_lock.acquire(blocking=False):
        return 0

    processed = 0
    try:
        pending = (
            Notification.query
            .filter_by(status=STATUS_PENDING)
            .order_by(Notification.created_at)
            .limit(limit)
            .all()
        )

        for n in pending:
            success, error = send_notification(
                n.channel, n.recipient, n.subject, n.message
            )

            if success:
                n.status = STATUS_SENT
                n.sent_at = datetime.now(timezone.utc)
                n.error_message = None
            else:
                n.retry_count += 1
                n.error_message = error
                if n.retry_count >= MAX_RETRIES:
                    n.status = STATUS_FAILED

            processed += 1

        db.session.commit()

    except Exception:
        db.session.rollback()
        logger.exception("Error procesando notificaciones pendientes")

    finally:
        _process_lock.release()

    return processed


def start_worker(app, interval_seconds=30):
    """Inicia un unico worker asociado a una aplicacion Flask."""
    global _worker_thread

    if app is None:
        raise ValueError("Se requiere una instancia de Flask para iniciar el worker.")

    if interval_seconds < 1:
        raise ValueError("interval_seconds debe ser mayor o igual a 1.")

    with _worker_state_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            if _worker_stop_event.is_set():
                raise RuntimeError("El worker anterior todavia se esta deteniendo.")
            return _worker_thread

        _worker_stop_event.clear()

        def _loop():
            logger.info(
                "Worker de notificaciones iniciado. Intervalo: %s segundos.",
                interval_seconds,
            )

            while not _worker_stop_event.is_set():
                try:
                    with app.app_context():
                        processed = process_pending()
                        if processed:
                            logger.info(
                                "Notificaciones procesadas: %s", processed
                            )
                except Exception:
                    logger.exception("Error en el ciclo del worker de notificaciones")

                _worker_stop_event.wait(interval_seconds)

            logger.info("Worker de notificaciones detenido.")

        _worker_thread = threading.Thread(
            target=_loop,
            name="sigos-notification-worker",
            daemon=True,
        )
        _worker_thread.start()
        return _worker_thread


def stop_worker(timeout=10):
    """Solicita la detencion del worker y espera su finalizacion."""
    global _worker_thread

    with _worker_state_lock:
        thread = _worker_thread
        if thread is None:
            return True
        _worker_stop_event.set()

    if thread is not threading.current_thread():
        thread.join(timeout=timeout)

    if thread.is_alive():
        logger.warning(
            "El worker no se detuvo dentro del tiempo limite de %s segundos.",
            timeout,
        )
        return False

    with _worker_state_lock:
        if _worker_thread is thread:
            _worker_thread = None

    return True


def list_notifications(user_id=None, status=None):
    q = Notification.query
    if user_id:
        q = q.filter_by(user_id=user_id)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(Notification.created_at.desc()).all()


def get_notification(notif_id):
    return db.session.get(Notification, notif_id)


def create_in_app_notification(user_id, title, message):
    from app.identity.models import User

    user = db.session.get(User, user_id)
    recipient = user.email if user and user.email else ""

    n = Notification(
        user_id=user_id,
        channel="in_app",
        recipient=recipient,
        subject=title,
        message=message,
        status=STATUS_PENDING,
    )
    db.session.add(n)
    return n


def notify_technician_change(wo, user, message):
    try:
        if getattr(wo, "assigned_to_id", None):
            create_in_app_notification(
                wo.assigned_to_id, "Cambio en orden", message
            )
    except Exception:
        logger.exception("No se pudo crear la notificacion interna del tecnico")

    return None
