# Reclamacion atomica de notificaciones (evita envios duplicados entre procesadores y no pierde notificaciones).
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.identity.models import User
from app.notifications import service
from app.notifications.models import (
    MAX_RETRIES, STATUS_FAILED, STATUS_PENDING, STATUS_PROCESSING, STATUS_SENT, Notification,
)


def _user(app):
    with app.app_context():
        u = User(username="claims", email="claims@test.local")
        u.set_password("Claims123!")
        db.session.add(u)
        db.session.commit()
        return u.id


def _add(app, uid, n=1, **kw):
    with app.app_context():
        ids = []
        for i in range(n):
            x = Notification(user_id=uid, channel="email", recipient=f"r{i}@test.local", subject=f"s{i}", message="m", **kw)
            db.session.add(x)
            db.session.flush()
            ids.append(x.id)
        db.session.commit()
        return ids


def _sender(monkeypatch, result=(True, None)):
    calls = []

    def fake(channel, recipient, subject, message):
        calls.append(subject)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(service, "send_notification", fake)
    return calls


def test_each_notification_is_sent_once_and_marked_sent(app, monkeypatch):
    uid = _user(app)
    ids = _add(app, uid, 3)
    calls = _sender(monkeypatch)
    with app.app_context():
        assert service.process_pending() == 3
        assert service.process_pending() == 0  # nada pendiente: no reenvia
        rows = Notification.query.filter(Notification.id.in_(ids)).all()
        assert {r.status for r in rows} == {STATUS_SENT}
        assert all(r.claimed_at is None and r.sent_at is not None for r in rows)
    assert sorted(calls) == ["s0", "s1", "s2"]


def test_notification_claimed_by_another_processor_is_not_sent(app, monkeypatch):
    uid = _user(app)
    now = datetime.now(timezone.utc)
    claimed = _add(app, uid, 1, status=STATUS_PROCESSING, claimed_at=now)[0]
    free = _add(app, uid, 1)[0]
    calls = _sender(monkeypatch)
    with app.app_context():
        assert service.process_pending() == 1
        assert db.session.get(Notification, claimed).status == STATUS_PROCESSING
        assert db.session.get(Notification, free).status == STATUS_SENT
    assert len(calls) == 1


def test_claim_is_atomic_only_one_winner(app):
    uid = _user(app)
    nid = _add(app, uid, 1)[0]
    with app.app_context():
        now = datetime.now(timezone.utc)
        assert service._claim(nid, 0, now) is True
        assert service._claim(nid, 0, now) is False  # segundo procesador: 0 filas


def test_stale_snapshot_cannot_claim_after_another_processor_retried(app):
    # B leyo la notificacion con 0 intentos; A la intento, fallo y volvio a pending con 1: B no debe reintentarla ya.
    uid = _user(app)
    nid = _add(app, uid, 1, retry_count=1)[0]
    with app.app_context():
        assert service._claim(nid, 0, datetime.now(timezone.utc)) is False
        assert db.session.get(Notification, nid).status == STATUS_PENDING


def test_abandoned_claim_returns_to_pending_and_is_not_lost(app, monkeypatch):
    uid = _user(app)
    old = datetime.now(timezone.utc) - timedelta(seconds=3600)
    nid = _add(app, uid, 1, status=STATUS_PROCESSING, claimed_at=old)[0]
    calls = _sender(monkeypatch)
    with app.app_context():
        assert service.process_pending() == 1
        assert db.session.get(Notification, nid).status == STATUS_SENT
    assert calls == ["s0"]


def test_recent_claim_is_not_released(app, monkeypatch):
    uid = _user(app)
    recent = datetime.now(timezone.utc) - timedelta(seconds=30)
    nid = _add(app, uid, 1, status=STATUS_PROCESSING, claimed_at=recent)[0]
    calls = _sender(monkeypatch)
    with app.app_context():
        assert service.process_pending() == 0
        assert db.session.get(Notification, nid).status == STATUS_PROCESSING
    assert calls == []


def test_failure_keeps_retry_rules_and_releases_claim(app, monkeypatch):
    uid = _user(app)
    nid = _add(app, uid, 1)[0]
    _sender(monkeypatch, (False, "SMTP no configurado"))
    with app.app_context():
        for attempt in range(1, MAX_RETRIES + 1):
            service.process_pending()
            n = db.session.get(Notification, nid)
            assert n.retry_count == attempt
            assert n.claimed_at is None
            assert n.status == (STATUS_FAILED if attempt >= MAX_RETRIES else STATUS_PENDING)
        assert n.error_message == "SMTP no configurado"


def test_sender_exception_counts_as_failure_and_does_not_leave_claim(app, monkeypatch):
    uid = _user(app)
    nid = _add(app, uid, 1)[0]
    _sender(monkeypatch, RuntimeError("x" * 900))
    with app.app_context():
        assert service.process_pending() == 1
        n = db.session.get(Notification, nid)
        assert n.status == STATUS_PENDING and n.retry_count == 1 and n.claimed_at is None
        assert len(n.error_message) <= 500


def test_processing_status_is_a_valid_filter(client, app):
    from app.notifications.models import ALL_STATUSES
    assert STATUS_PROCESSING in ALL_STATUSES
