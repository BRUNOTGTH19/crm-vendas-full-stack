"""Prova do rate limiting do login (anti força-bruta).

15 falhas (401) por IP em 5 minutos resultam em 429. O contador é limpo ao
final para não afetar os demais testes da suíte.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from main import app
from middleware.rate_limit import LOGIN_MAX_FAILURES, reset_rate_limit

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_rate_limit():
    reset_rate_limit()
    yield
    reset_rate_limit()


@pytest.fixture(scope="module")
def registered_user():
    stamp = datetime.now().strftime("%H%M%S%f")
    email = f"ratelimit_{stamp}@crm.com"
    r = client.post(
        "/auth/register",
        json={"name": "Rate Limit", "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text
    return email


def _login(email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_failed_logins_are_counted_and_then_blocked(registered_user):
    # Abaixo do limite: continua respondendo 401 (credenciais inválidas).
    for _ in range(LOGIN_MAX_FAILURES - 1):
        r = _login(registered_user, "senha-errada")
        assert r.status_code == 401

    # Atinge o limite -> 429, mesmo com credenciais corretas.
    r = _login(registered_user, "senha-errada")
    assert r.status_code == 401
    r = _login(registered_user, "senha-errada")
    assert r.status_code == 429
    assert "Tente novamente" in r.json()["detail"]

    r = _login(registered_user, "123456")
    assert r.status_code == 429


def test_successful_logins_do_not_count(registered_user):
    """Logins corretos nunca alimentam o contador de bloqueio."""
    for _ in range(LOGIN_MAX_FAILURES + 5):
        r = _login(registered_user, "123456")
        assert r.status_code == 200