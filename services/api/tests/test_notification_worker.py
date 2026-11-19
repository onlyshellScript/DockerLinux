import threading
import time

import app.notifications.service as notification_service
from flask import has_app_context


def test_worker_runs_inside_flask_app_context(app, monkeypatch):
    executed = threading.Event()
    context_detected = []

    def fake_process_pending():
        context_detected.append(has_app_context())
        executed.set()
        return 0

    monkeypatch.setattr(
        notification_service,
        "process_pending",
        fake_process_pending,
    )

    try:
        notification_service.start_worker(app, interval_seconds=1)

        assert executed.wait(timeout=3)
        assert context_detected == [True]
    finally:
        assert notification_service.stop_worker(timeout=3)


def test_start_worker_does_not_create_duplicate_threads(app, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def fake_process_pending():
        entered.set()
        release.wait(timeout=3)
        return 0

    monkeypatch.setattr(
        notification_service,
        "process_pending",
        fake_process_pending,
    )

    try:
        first_thread = notification_service.start_worker(
            app,
            interval_seconds=1,
        )

        assert entered.wait(timeout=3)

        second_thread = notification_service.start_worker(
            app,
            interval_seconds=1,
        )

        assert first_thread is second_thread
    finally:
        release.set()
        assert notification_service.stop_worker(timeout=3)


def test_stop_worker_stops_thread(app, monkeypatch):
    executed = threading.Event()

    def fake_process_pending():
        executed.set()
        return 0

    monkeypatch.setattr(
        notification_service,
        "process_pending",
        fake_process_pending,
    )

    notification_service.start_worker(app, interval_seconds=1)

    assert executed.wait(timeout=3)
    assert notification_service.stop_worker(timeout=3)

    thread = notification_service._worker_thread
    assert thread is None


def test_worker_can_restart_after_stopping(app, monkeypatch):
    executions = []
    executed_twice = threading.Event()

    def fake_process_pending():
        executions.append(True)

        if len(executions) >= 2:
            executed_twice.set()

        return 0

    monkeypatch.setattr(
        notification_service,
        "process_pending",
        fake_process_pending,
    )

    try:
        first_thread = notification_service.start_worker(
            app,
            interval_seconds=1,
        )

        assert notification_service.stop_worker(timeout=3)

        second_thread = notification_service.start_worker(
            app,
            interval_seconds=1,
        )

        assert second_thread is not first_thread
        assert executed_twice.wait(timeout=3)
    finally:
        assert notification_service.stop_worker(timeout=3)
