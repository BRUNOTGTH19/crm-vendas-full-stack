"""Job real e banco isolado; nenhuma chamada a provedor push real."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from pywebpush import WebPushException

import scheduler
from config import settings
from database import Base, SessionLocal, engine
from models.client import Client
from models.push_subscription import PushSubscription
from models.sale import Sale
from models.user import User
from services import push_service


@pytest.fixture
def sample(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(settings, "reminder_days_before", 0)
    monkeypatch.setattr(settings, "reminder_timezone", "UTC")
    monkeypatch.setattr(push_service, "get_vapid_keys", Mock(return_value=("test-public", "test-private")))
    today = datetime.now(ZoneInfo("UTC")).date()
    with SessionLocal() as db:
        for owner in (1, 2):
            db.add(User(id=owner, name=f"User {owner}", email=f"u{owner}@example.com",
                        password_hash="unused", role="admin" if owner == 1 else "user"))
        db.flush()
        db.add(Client(id=1, full_name="Sintético", name_normalized="sintetico", created_by_id=1))
        db.flush()
        for index, (owner, days, status) in enumerate([
            (1, 0, "pending"), (1, -1, "pending"), (1, 1, "pending"),
            (1, 0, "paid"), (1, None, "pending"), (2, 0, "pending"),
        ], start=1):
            db.add(Sale(id=index, client_id=1, user_id=owner, sale_date=today,
                        due_date=None if days is None else today + timedelta(days=days),
                        status=status, total=10, amount_paid=0, remaining=10))
        for owner in (1, 2):
            db.add(PushSubscription(id=owner, user_id=owner,
                                   endpoint=f"https://push.example.test/{owner}", p256dh="abc", auth="def"))
        db.commit()
    return today


def test_job_to_simulated_transport(sample, caplog):
    push_service.webpush.reset_mock()
    with caplog.at_level("INFO"):
        assert scheduler.check_due_charges() == 3
    assert push_service.webpush.call_count == 2
    calls = {call.kwargs["subscription_info"]["endpoint"]: call.kwargs
             for call in push_service.webpush.call_args_list}
    first = calls["https://push.example.test/1"]
    second = calls["https://push.example.test/2"]
    payload = json.loads(first["data"])
    assert payload["title"] == "🔔 Alerta de cobranças"
    assert payload["body"] == f"2 cobrança(s) com vencimento até {sample:%d/%m/%Y}. Abra o app para ver os detalhes."
    assert json.loads(second["data"])["body"].startswith("1 cobrança(s)")
    assert payload["url"] == "/#/queue"
    assert payload["icon"] == "/icons/icon-192.png"
    assert payload["data"]["run_id"] == json.loads(second["data"])["data"]["run_id"]
    assert first["vapid_private_key"] == "test-private"
    assert first["vapid_claims"] == {"sub": settings.vapid_subject}
    assert first["timeout"] == 10 and first["ttl"] == 3600
    for stage in ("reminder_started", "reminder_found", "reminder_notify", "push_attempt", "push_accepted", "reminder_finished"):
        assert stage in caplog.text
    assert "https://push.example.test" not in caplog.text


@pytest.mark.parametrize("status", [404, 410, 401, 403, 503])
def test_provider_failure_continues(sample, monkeypatch, status, caplog):
    failure = WebPushException("sensitive endpoint", response=SimpleNamespace(status_code=status))
    send = Mock(side_effect=[failure, None])
    monkeypatch.setattr(push_service, "webpush", send)
    with SessionLocal() as db:
        assert push_service.send_push_to_all(db, "title", "body") == 1
        assert (db.get(PushSubscription, 1) is None) == (status in (404, 410))
    assert send.call_count == 2
    assert "sensitive endpoint" not in caplog.text


def test_network_failure_continues(sample, monkeypatch):
    monkeypatch.setattr(push_service, "webpush", Mock(side_effect=[TimeoutError(), None]))
    with SessionLocal() as db:
        assert push_service.send_push_to_all(db, "title", "body") == 1
        assert db.query(PushSubscription).count() == 2



def test_preview_window_and_empty_job(sample, monkeypatch):
    send = Mock(return_value=1)
    monkeypatch.setattr(scheduler, "send_push_to_all", send)
    monkeypatch.setattr(settings, "reminder_days_before", 1)
    result = scheduler.run_due_charges(user_id=1, dry_run=True)
    assert result["sales_found"] == 3
    assert result["cutoff"] == (sample + timedelta(days=1)).isoformat()
    assert scheduler.run_due_charges(user_id=999)["sales_found"] == 0
    send.assert_not_called()
    send.side_effect = [RuntimeError("simulated"), 1]
    result = scheduler.run_due_charges()
    assert send.call_count == 2
    assert result["users_failed"] == 1 and result["push_accepted"] == 1


def test_cron_timezone_and_next_fire():
    job = scheduler.scheduler.get_job("pending-reminders")
    start = datetime(2026, 9, 17, settings.reminder_hour, tzinfo=ZoneInfo(settings.reminder_timezone))
    assert job.trigger.get_next_fire_time(None, start) == start
    assert job.trigger.get_next_fire_time(start, start) == start + timedelta(days=1)
    assert str(job.trigger.timezone) == settings.reminder_timezone
    assert job.max_instances == 1 and job.coalesce


def test_admin_manual_job_and_audit(sample):
    from fastapi.testclient import TestClient

    from main import app
    from models.audit_log import AuditLog
    from services.auth_service import create_access_token

    client = TestClient(app)
    admin = {"Authorization": f"Bearer {create_access_token({'sub': '1'})}"}
    user = {"Authorization": f"Bearer {create_access_token({'sub': '2'})}"}
    assert client.post("/admin/reminders/run", json={}).status_code == 401
    assert client.post("/admin/reminders/run", json={}, headers=user).status_code == 403
    assert client.post("/admin/reminders/run", json={"dry_run": False}, headers=admin).status_code == 400
    assert client.post("/admin/reminders/run", json={"user_id": 999}, headers=admin).status_code == 404
    response = client.post("/admin/reminders/run", json={"user_id": 1}, headers=admin)
    assert response.status_code == 200 and response.json()["dry_run"] is True
    response = client.post("/admin/reminders/run", json={"user_id": 1, "dry_run": False, "confirm": True}, headers=admin)
    assert response.status_code == 200
    result = response.json()
    assert result["push_accepted"] == 1 and result["source"] == "manual"
    with SessionLocal() as db:
        entry = db.query(AuditLog).filter(AuditLog.action == "reminder_run_completed").order_by(AuditLog.id.desc()).first()
        assert json.loads(entry.detail)["run_id"] == result["run_id"]
    with scheduler._run_lock:
        assert client.post("/admin/reminders/run", json={}, headers=admin).status_code == 409
    push_service.webpush.reset_mock()
    response = client.post("/push/test", json={}, headers=user)
    assert response.status_code == 200 and response.json()["sent"] == 1
    push_service.webpush.assert_called_once()
    assert push_service.webpush.call_args.kwargs["subscription_info"]["endpoint"].endswith("/2")
