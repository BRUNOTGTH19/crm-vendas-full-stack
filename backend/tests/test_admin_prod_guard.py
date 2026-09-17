"""Testes de gestão de dados: reset em produção é bloqueado (403)."""
import pytest
from fastapi.testclient import TestClient

from config import settings
from database import SessionLocal
from main import app

client = TestClient(app)


def _make_admin(email: str) -> dict:
    r = client.post(
        "/auth/register",
        json={"name": "Admin Prod", "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text
    with SessionLocal() as db:
        from models.user import User

        user = db.query(User).filter(User.email == email).one()
        user.role = "admin"
        db.commit()
    r = client.post("/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_user(email: str) -> dict:
    r = client.post(
        "/auth/register",
        json={"name": "User Prod", "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _delete_user(email: str) -> None:
    with SessionLocal() as db:
        from models.user import User

        db.query(User).filter(User.email == email).delete(synchronize_session=False)
        db.commit()


@pytest.fixture(scope="module")
def prod_admin_headers():
    headers = _make_admin(f"prod_admin_{pytest.__dict__.get('_x', '')}{id(object())}@crm.com")
    return headers


@pytest.fixture(scope="module")
def prod_user_headers():
    return _make_user(f"prod_user_{id(object())}@crm.com")


@pytest.fixture(scope="module")
def prod_environment():
    original = settings.environment
    original_allow = settings.allow_database_reset
    settings.environment = "production"
    settings.allow_database_reset = False
    yield
    settings.environment = original
    settings.allow_database_reset = original_allow


def test_register_rejects_admin_role():
    r = client.post(
        "/auth/register",
        json={"name": "X", "email": f"esc_{id(object())}@crm.com", "password": "123456", "role": "admin"},
    )
    assert r.status_code == 422


def test_reset_blocked_in_production(prod_admin_headers, prod_environment):
    r = client.post("/admin/database/reset", json={"confirm": True}, headers=prod_admin_headers)
    assert r.status_code == 403


def test_reset_blocked_for_non_admin(prod_user_headers, prod_environment):
    r = client.post("/admin/database/reset", json={"confirm": True}, headers=prod_user_headers)
    assert r.status_code in (401, 403)


def test_export_and_import_still_available(prod_admin_headers, prod_environment):
    r = client.get("/admin/database/export", headers=prod_admin_headers)
    assert r.status_code == 200