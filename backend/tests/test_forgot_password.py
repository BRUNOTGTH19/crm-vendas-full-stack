"""Testes da recuperação de senha por e-mail (self-service) e do serviço de SMTP.

Cobrem: configuração exposta sem revelar contas, resposta genérica para e-mail
existente ou não, token guardado apenas como hash, envio em segundo plano e
falha de SMTP sem derrubar a requisição. Banco SQLite em memória; nenhum e-mail
é enviado de verdade.
"""
from __future__ import annotations

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from config import settings
from database import SessionLocal
from main import app
from middleware.rate_limit import PASSWORD_RESET_MAX_ATTEMPTS, reset_rate_limit
from models.password_reset_token import PasswordResetToken
from models.user import User
from services import mail_service
from services.auth_service import hash_password

client = TestClient(app)
PASSWORD_HASH = hash_password("12345678")
GENERIC_MESSAGE = (
    "Se o e-mail estiver cadastrado, você receberá as instruções em instantes."
)


@pytest.fixture(autouse=True)
def clean_rate_limit():
    reset_rate_limit()
    yield
    reset_rate_limit()


@pytest.fixture()
def make_user():
    def _make(role: str = "user") -> dict[str, object]:
        suffix = uuid.uuid4().hex
        email = f"{role}_{suffix}@example.com"
        with SessionLocal() as db:
            user = User(
                name=f"Usuario {suffix[:8]}",
                email=email,
                password_hash=PASSWORD_HASH,
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return {"id": user.id, "email": email}

    return _make


def _tokens_for(user_id: int) -> list[PasswordResetToken]:
    with SessionLocal() as db:
        return (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user_id)
            .all()
        )


def test_config_reports_self_service_disabled_without_smtp(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from", "")

    response = client.get("/auth/password-reset/config")

    assert response.status_code == 200
    assert response.json() == {"self_service": False}


def test_config_reports_self_service_when_smtp_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "nao-responda@example.com")

    response = client.get("/auth/password-reset/config")

    assert response.json() == {"self_service": True}


def test_unknown_email_gets_the_same_generic_answer(monkeypatch):
    monkeypatch.setattr(mail_service, "is_email_configured", lambda: True)
    sent: list[tuple] = []
    monkeypatch.setattr(
        mail_service,
        "send_password_reset_email",
        lambda *args: sent.append(args) or True,
    )

    response = client.post(
        "/auth/forgot-password", json={"email": "ninguem@example.com"}
    )

    assert response.status_code == 202
    assert response.json() == {"message": GENERIC_MESSAGE}
    assert sent == []


def test_existing_email_creates_hashed_token_and_sends(monkeypatch, make_user):
    user = make_user()
    monkeypatch.setattr(mail_service, "is_email_configured", lambda: True)
    sent: list[tuple] = []
    monkeypatch.setattr(
        mail_service,
        "send_password_reset_email",
        lambda *args: sent.append(args) or True,
    )

    response = client.post("/auth/forgot-password", json={"email": user["email"]})

    assert response.status_code == 202
    assert response.json() == {"message": GENERIC_MESSAGE}
    assert len(sent) == 1
    email, token, expires_minutes = sent[0]
    assert email == user["email"]
    assert expires_minutes > 0

    rows = _tokens_for(user["id"])
    assert len(rows) == 1
    assert rows[0].token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in rows[0].token_hash


def test_new_request_invalidates_the_previous_token(monkeypatch, make_user):
    user = make_user()
    monkeypatch.setattr(mail_service, "is_email_configured", lambda: True)
    monkeypatch.setattr(
        mail_service, "send_password_reset_email", lambda *args: True
    )

    client.post("/auth/forgot-password", json={"email": user["email"]})
    client.post("/auth/forgot-password", json={"email": user["email"]})

    rows = _tokens_for(user["id"])
    assert len(rows) == 2
    pending = [row for row in rows if row.used_at is None]
    assert len(pending) == 1


def test_without_smtp_no_token_is_created(monkeypatch, make_user):
    user = make_user()
    monkeypatch.setattr(mail_service, "is_email_configured", lambda: False)

    response = client.post("/auth/forgot-password", json={"email": user["email"]})

    assert response.status_code == 202
    assert _tokens_for(user["id"]) == []


def test_rate_limit_blocks_after_the_limit():
    payload = {"email": "ninguem@example.com"}
    for _ in range(PASSWORD_RESET_MAX_ATTEMPTS):
        assert client.post("/auth/forgot-password", json=payload).status_code == 202

    response = client.post("/auth/forgot-password", json=payload)

    assert response.status_code == 429


def test_mail_service_is_inert_without_smtp(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    assert mail_service.is_email_configured() is False
    assert mail_service.send_password_reset_email("a@b.com", "token", 15) is False


def test_reset_link_uses_the_public_frontend_url(monkeypatch):
    monkeypatch.setattr(settings, "app_public_url", "https://app.example.com/")

    assert (
        mail_service.reset_link("abc123")
        == "https://app.example.com/#/reset-password?token=abc123"
    )
    monkeypatch.setattr(settings, "app_public_url", "")
    assert mail_service.reset_link("abc123") == ""


def test_mail_service_sends_token_once_without_logging_it(monkeypatch, caplog):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "nao-responda@example.com")
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "app_public_url", "https://app.example.com")
    captured: dict[str, str] = {}

    class FakeSmtp:
        def __init__(self, host, port, timeout):  # noqa: ARG002
            captured["host"] = host
            captured["port"] = str(port)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            captured["starttls"] = "sim"

        def login(self, user, password):  # pragma: no cover - sem usuário no teste
            captured["login"] = user

        def send_message(self, message):
            captured["body"] = message.get_content()
            captured["to"] = message["To"]

    monkeypatch.setattr(mail_service.smtplib, "SMTP", FakeSmtp)

    assert mail_service.send_password_reset_email("cliente@example.com", "TOKEN-SECRETO", 15)
    assert captured["host"] == "smtp.example.com"
    assert captured["to"] == "cliente@example.com"
    assert "TOKEN-SECRETO" in captured["body"]
    assert "https://app.example.com/#/reset-password?token=TOKEN-SECRETO" in captured["body"]
    assert "TOKEN-SECRETO" not in caplog.text


def test_mail_service_swallows_smtp_errors(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "nao-responda@example.com")

    class BrokenSmtp:
        def __init__(self, host, port, timeout):
            raise OSError("sem rede")

    monkeypatch.setattr(mail_service.smtplib, "SMTP", BrokenSmtp)

    assert mail_service.send_password_reset_email("cliente@example.com", "t", 15) is False
