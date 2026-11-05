import threading
from datetime import datetime, timezone

from app.extensions import db
from app.notifications.models import (
    Notification, CHANNEL_EMAIL, CHANNEL_WHATSAPP,
    STATUS_PENDING, STATUS_SENT, STATUS_FAILED, MAX_RETRIES,
)
from app.notifications.senders import send_notification

_worker_running = False


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
    global _worker_running
    if _worker_running:
        return 0
    _worker_running = True
    processed = 0
    try:
        pending = Notification.query.filter_by(status=STATUS_PENDING).order_by(Notification.created_at).limit(limit).all()
        for n in pending:
            success, error = send_notification(n.channel, n.recipient, n.subject, n.message)
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
    finally:
        _worker_running = False
    return processed


def start_worker(interval_seconds=30):
    def _loop():
        while True:
            import time
            process_pending()
            time.sleep(interval_seconds)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t


def list_notifications(user_id=None, status=None):
    q = Notification.query
    if user_id:
        q = q.filter_by(user_id=user_id)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(Notification.created_at.desc()).all()


def get_notification(notif_id):
    return db.session.get(Notification, notif_id)
