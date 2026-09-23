"""Prova da redefinição simples de senha (tela de login, sem link/código).

Cobre: troca de senha pelo e-mail cadastrado, login com a senha nova, senha
antiga invalidada, e-mail inexistente (404), senha curta (422) e rate limit
por IP (429). O contador é limpo ao final para não afetar a suíte.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from main import app
from middleware.rate_limit import PASSWORD_RESET_MAX_ATTEMPTS, reset_rate_limit

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_rate_limit():
    reset_rate_limit()
    yield
    reset_rate_limit()


@pytest.fixture()
def registered_user():
    stamp = datetime.now().strftime("%H%M%S%f")
    email = f"reset_{stamp}@crm.com"
    r = client.post(
        "/auth/register",
        json={"name": "Reset Senha", "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text
    return email


def _login(email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def _reset(email: str, new_password: str):
    return client.post(
        "/auth/reset-password",
        json={"email": email, "new_password": new_password},
    )


def test_reset_changes_password_and_old_stops_working(registered_user):
    assert _reset(registered_user, "nova-senha-456").status_code == 204
    assert _login(registered_user, "123456").status_code == 401
    r = _login(registered_user, "nova-senha-456")
    assert r.status_code == 200, r.text


def test_reset_unknown_email_returns_404():
    r = _reset("nao_existe_xyz@crm.com", "qualquer-senha")
    assert r.status_code == 404


def test_reset_short_password_is_rejected(registered_user):
    r = _reset(registered_user, "123")
    assert r.status_code == 422
    # A senha original continua valendo.
    assert _login(registered_user, "123456").status_code == 200


def test_reset_rate_limited_per_ip():
    for i in range(PASSWORD_RESET_MAX_ATTEMPTS):
        r = _reset(f"sem_conta_{i}@crm.com", "senha-valida-1")
        assert r.status_code == 404  # tentativas sem sucesso também contam

    r = _reset("mais_uma@crm.com", "senha-valida-1")
    assert r.status_code == 429
    assert "Tente novamente" in r.json()["detail"]
