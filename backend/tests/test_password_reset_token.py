"""Testes do token de redefinição gerado pelo admin e da invalidação de sessões.

Cobrem: autorização, hash persistido, uso único, expiração, invalidação do
token anterior, escopo por usuário, access/refresh antigos, tokens sem ``tv``,
rate limit e logs sem segredos. Banco SQLite em memória e Redis mockado pelo
``conftest.py``; nenhum serviço externo é chamado.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from config import settings
from database import SessionLocal
from main import app
from middleware.rate_limit import PASSWORD_RESET_MAX_ATTEMPTS, reset_rate_limit
from models.password_reset_token import PasswordResetToken
from models.user import User
from services import auth_service
from services.auth_service import hash_password

client = TestClient(app)
PASSWORD = "12345678"
PASSWORD_HASH = hash_password(PASSWORD)


@pytest.fixture(autouse=True)
def clean_rate_limit():
    reset_rate_limit()
    yield
    reset_rate_limit()


@pytest.fixture()
def make_user():
    """Cria usuários direto no banco (sem passar pelo cadastro público)."""

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
            return {"id": user.id, "email": email, "password": PASSWORD}

    return _make


def _login(email: str, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin(make_user) -> dict[str, object]:
    account = make_user("admin")
    response = _login(str(account["email"]))
    assert response.status_code == 200, response.text
    return {**account, "headers": _headers(response.json()["access_token"])}


def _issue(admin_headers: dict[str, str], user_id: int) -> dict[str, str]:
    response = client.post(
        f"/admin/users/{user_id}/reset-token",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _confirm(token: str, new_password: str = "nova-senha-456"):
    return client.post(
        "/auth/reset-password/confirm",
        json={"token": token, "new_password": new_password},
    )


# ---------------------------------------------------------------------------
# Geração pelo admin
# ---------------------------------------------------------------------------
def test_admin_generates_token_and_only_hash_is_stored(make_user):
    admin = _admin(make_user)
    target = make_user()
    data = _issue(admin["headers"], target["id"])

    assert isinstance(data["token"], str) and len(data["token"]) >= 32
    assert "expires_at" in data

    with SessionLocal() as db:
        row = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == target["id"])
            .one()
        )
        assert row.token_hash == hashlib.sha256(data["token"].encode()).hexdigest()
        assert row.token_hash != data["token"]
        assert row.used_at is None


def test_common_user_cannot_generate_token(make_user):
    common = make_user()
    login = _login(str(common["email"]))
    target = make_user()
    response = client.post(
        f"/admin/users/{target['id']}/reset-token",
        headers=_headers(login.json()["access_token"]),
    )
    assert response.status_code == 403


def test_admin_cannot_generate_token_for_self(make_user):
    admin = _admin(make_user)
    response = client.post(
        f"/admin/users/{admin['id']}/reset-token",
        headers=admin["headers"],
    )
    assert response.status_code == 400


def test_unknown_target_returns_404(make_user):
    admin = _admin(make_user)
    response = client.post(
        "/admin/users/999999/reset-token",
        headers=admin["headers"],
    )
    assert response.status_code == 404


def test_endpoint_requires_authentication(make_user):
    target = make_user()
    response = client.post(f"/admin/users/{target['id']}/reset-token")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Confirmação e invalidação
# ---------------------------------------------------------------------------
def test_valid_confirmation_changes_password_and_revokes_old_tokens(
    make_user, isolated_services
):
    admin = _admin(make_user)
    user = make_user()
    old_login = _login(str(user["email"]))
    assert old_login.status_code == 200
    old_access = old_login.json()["access_token"]
    old_refresh = old_login.json()["refresh_token"]

    data = _issue(admin["headers"], user["id"])
    isolated_services.delete.reset_mock()
    response = _confirm(data["token"])

    assert response.status_code == 204
    assert (
        client.get("/auth/me", headers=_headers(old_access)).status_code == 401
    )
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": old_refresh}
        ).status_code
        == 401
    )
    assert _login(str(user["email"])).status_code == 401
    assert _login(str(user["email"]), "nova-senha-456").status_code == 200
    isolated_services.delete.assert_any_call(f"session:{user['id']}")

    with SessionLocal() as db:
        db_user = db.get(User, user["id"])
        assert db_user is not None and db_user.token_version == 1
        row = db.query(PasswordResetToken).filter_by(user_id=user["id"]).one()
        assert row.used_at is not None


def test_reused_token_returns_generic_400(make_user):
    admin = _admin(make_user)
    user = make_user()
    data = _issue(admin["headers"], user["id"])

    assert _confirm(data["token"]).status_code == 204
    response = _confirm(data["token"])
    assert response.status_code == 400
    assert response.json()["detail"] == "Token inválido ou expirado."


def test_expired_token_is_rejected(make_user, monkeypatch):
    admin = _admin(make_user)
    user = make_user()
    data = _issue(admin["headers"], user["id"])
    expires_at = datetime.fromisoformat(data["expires_at"])
    monkeypatch.setattr(
        auth_service,
        "_utcnow",
        lambda: expires_at + timedelta(seconds=1),
    )

    response = _confirm(data["token"])
    assert response.status_code == 400
    assert response.json()["detail"] == "Token inválido ou expirado."
    assert _login(str(user["email"])).status_code == 200


def test_new_token_invalidates_previous(make_user):
    admin = _admin(make_user)
    user = make_user()
    first = _issue(admin["headers"], user["id"])
    second = _issue(admin["headers"], user["id"])

    assert _confirm(first["token"]).status_code == 400
    assert _confirm(second["token"]).status_code == 204


def test_token_resets_only_its_own_user(make_user):
    admin = _admin(make_user)
    user_a = make_user()
    user_b = make_user()
    data = _issue(admin["headers"], user_a["id"])

    assert _confirm(data["token"]).status_code == 204
    assert _login(str(user_a["email"])).status_code == 401
    assert _login(str(user_a["email"]), "nova-senha-456").status_code == 200
    assert _login(str(user_b["email"])).status_code == 200
    with SessionLocal() as db:
        assert db.get(User, user_b["id"]).token_version == 0


def test_access_token_without_tv_is_rejected(make_user):
    user = make_user()
    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 401


def test_refresh_token_without_tv_is_rejected(make_user):
    user = make_user()
    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.post("/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


def test_confirm_is_rate_limited(make_user):
    for index in range(PASSWORD_RESET_MAX_ATTEMPTS):
        response = _confirm(f"token-invalido-{index}")
        assert response.status_code == 400

    response = _confirm("mais-um-token-invalido")
    assert response.status_code == 429
    assert "Tente novamente" in response.json()["detail"]


def test_public_reset_also_revokes_sessions(make_user):
    user = make_user()
    old_login = _login(str(user["email"]))
    old_access = old_login.json()["access_token"]
    old_refresh = old_login.json()["refresh_token"]

    response = client.post(
        "/auth/reset-password",
        json={"email": user["email"], "new_password": "outra-senha-789"},
    )
    assert response.status_code == 204
    assert (
        client.get("/auth/me", headers=_headers(old_access)).status_code == 401
    )
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": old_refresh}
        ).status_code
        == 401
    )
    assert _login(str(user["email"]), "outra-senha-789").status_code == 200


def test_logs_do_not_contain_token_password_or_jwt(make_user, caplog):
    admin = _admin(make_user)
    user = make_user()
    old_login = _login(str(user["email"]))
    old_access = old_login.json()["access_token"]

    caplog.set_level(logging.INFO, logger="services.auth_service")
    data = _issue(admin["headers"], user["id"])
    assert _confirm(data["token"]).status_code == 204

    assert "reset_token_created" in caplog.text
    assert "password_reset_confirmed" in caplog.text
    assert data["token"] not in caplog.text
    assert "nova-senha-456" not in caplog.text
    assert PASSWORD_HASH not in caplog.text
    assert old_access not in caplog.text
