"""Testes da ativação de administrador por código secreto.

Cobrem: código gerado e registrado no log, promoção do usuário logado,
consumo único, código definido por ``ADMIN_SETUP_CODE``, bootstrap por
``ADMIN_EMAIL``, exigência de autenticação e rate limit por IP.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from config import settings
from database import SessionLocal
from main import app
from middleware.rate_limit import reset_rate_limit
from models.app_setting import AppSetting
from models.audit_log import AuditLog
from models.user import User

client = TestClient(app)

CODE_KEY = "admin_setup_code"
CONSUMED_KEY = "admin_setup_consumed"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%S%f")


def _register(name: str, email: str) -> dict:
    r = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _login(email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _activate(headers: dict, code: str):
    return client.post("/auth/activate-admin", json={"code": code}, headers=headers)


@pytest.fixture(autouse=True)
def clean_admin_state(isolated_services, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "")
    monkeypatch.setattr(settings, "admin_setup_code", "")
    reset_rate_limit()
    with SessionLocal() as db:
        db.query(AuditLog).delete()
        db.query(User).delete()
        db.query(AppSetting).delete()
        db.commit()
    yield


def test_generated_code_promotes_once_and_is_logged(caplog):
    stamp = _stamp()
    owner_email = f"dono_{stamp}@crm.com"
    other_email = f"outro_{stamp}@crm.com"
    _register("Dono", owner_email)
    _register("Outro", other_email)
    owner = _login(owner_email)

    with SessionLocal() as db:
        code = db.query(AppSetting).filter(AppSetting.key == CODE_KEY).one().value
    assert code and len(code) >= 10
    assert "admin_setup_code_generated" in caplog.text

    # Código errado não promove.
    r = _activate(owner, "codigo-errado")
    assert r.status_code == 400
    assert client.get("/admin/users", headers=owner).status_code == 403

    # Código correto promove o usuário logado.
    r = _activate(owner, code)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"
    assert client.get("/admin/users", headers=owner).status_code == 200

    with SessionLocal() as db:
        assert db.query(AppSetting).filter(AppSetting.key == CODE_KEY).count() == 0
        assert db.query(AppSetting).filter(AppSetting.key == CONSUMED_KEY).count() == 1
        assert db.query(AuditLog).filter(AuditLog.action == "admin_activated").count() == 1

    # O código é de uso único: outro usuário não consegue usá-lo.
    other = _login(other_email)
    r = _activate(other, code)
    assert r.status_code == 400
    assert client.get("/admin/users", headers=other).status_code == 403


def test_env_code_activates_only_once(monkeypatch):
    monkeypatch.setattr(settings, "admin_setup_code", "codigo-do-dono")
    stamp = _stamp()
    owner_email = f"env_dono_{stamp}@crm.com"
    other_email = f"env_outro_{stamp}@crm.com"
    _register("Dono Env", owner_email)
    _register("Outro Env", other_email)
    owner = _login(owner_email)

    # Com a variável definida, nenhum código aleatório é gerado.
    with SessionLocal() as db:
        assert db.query(AppSetting).filter(AppSetting.key == CODE_KEY).count() == 0

    assert _activate(owner, "errado").status_code == 400
    r = _activate(owner, "codigo-do-dono")
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"

    # Encerrada a ativação, nem o código do operador promove mais ninguém.
    other = _login(other_email)
    assert _activate(other, "codigo-do-dono").status_code == 400
    assert client.get("/admin/users", headers=other).status_code == 403


def test_admin_email_promotes_without_code(monkeypatch):
    stamp = _stamp()
    email = f"bootstrap_{stamp}@crm.com"
    monkeypatch.setattr(settings, "admin_email", email.upper())
    _register("Bootstrap", email)

    headers = _login(email)
    assert client.get("/admin/users", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.query(AppSetting).filter(AppSetting.key == CODE_KEY).count() == 0


def test_activation_requires_authentication():
    r = client.post("/auth/activate-admin", json={"code": "qualquer"})
    assert r.status_code in (401, 403)


def test_wrong_code_is_rate_limited():
    stamp = _stamp()
    email = f"rate_{stamp}@crm.com"
    _register("Rate", email)
    headers = _login(email)

    for _ in range(10):
        assert _activate(headers, "errado").status_code == 400
    assert _activate(headers, "errado").status_code == 429
