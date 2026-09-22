"""Testes do controle de reset de dados e do registro de vendas.

O reset é controlado pela flag ``ALLOW_DATABASE_RESET`` (opt-out, ligada por
padrão). Antes o backend bloqueava o reset em produção, o que impedia o
administrador de zerar os dados no ambiente real — regressão coberta aqui.
"""
import pytest
from datetime import date
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
    headers = _make_admin(f"prod_admin_{id(object())}@crm.com")
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


def test_reset_blocked_when_flag_disabled(prod_admin_headers, prod_environment):
    """Sem a flag de liberação, o reset responde 403 (proteção contra acidente)."""
    r = client.post("/admin/database/reset", json={"confirm": True}, headers=prod_admin_headers)
    assert r.status_code == 403


def test_reset_blocked_for_non_admin(prod_user_headers, prod_environment):
    r = client.post("/admin/database/reset", json={"confirm": True}, headers=prod_user_headers)
    assert r.status_code in (401, 403)


def test_export_and_import_still_available(prod_admin_headers, prod_environment):
    r = client.get("/admin/database/export", headers=prod_admin_headers)
    assert r.status_code == 200


def test_reset_allowed_with_flag_even_in_production(prod_admin_headers):
    """Com ALLOW_DATABASE_RESET=true o admin consegue zerar os dados em produção."""
    original_env, original_allow = settings.environment, settings.allow_database_reset
    settings.environment = "production"
    settings.allow_database_reset = True
    try:
        r = client.post("/admin/database/reset", json={"confirm": True}, headers=prod_admin_headers)
        assert r.status_code == 200, r.text
    finally:
        settings.environment = original_env
        settings.allow_database_reset = original_allow


# ---------------------------------------------------------------------------
# Regressão: registrar venda (usuário comum) com vencimento hoje.
# Antes, o envio de push usava ``client.name`` (inexistente) e derrubava a
# requisição com HTTP 500, exibindo "backend na porta 8000" no frontend.
# ---------------------------------------------------------------------------

def test_common_user_can_create_sale_due_today():
    from models.user import User
    from models.client import Client
    from models.sale import Sale
    from models.sale_item import SaleItem

    email = f"sale_user_{id(object())}@crm.com"
    normalized = f"cliente venda {id(object())}"
    headers = _make_user(email)
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).one()
            c = Client(
                full_name="Cliente Venda",
                name_normalized=normalized,
                created_by_id=user.id,
            )
            db.add(c)
            db.commit()
            client_id = c.id

        payload = {
            "client_id": client_id,
            "sale_date": date.today().isoformat(),
            "status": "pending",
            "due_date": date.today().isoformat(),
            "items": [
                {"product_name": "P1", "quantity": 2, "unit_price": 10.5},
            ],
        }
        r = client.post("/sales", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["client_id"] == client_id
        assert len(body["items"]) == 1
    finally:
        # Remove dependências antes do cliente/usuário (FKs).
        with SessionLocal() as db:
            client_row = db.query(Client).filter(Client.name_normalized == normalized).first()
            if client_row is not None:
                sale_ids = [s.id for s in db.query(Sale).filter(Sale.client_id == client_row.id)]
                if sale_ids:
                    db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).delete(
                        synchronize_session=False
                    )
                    db.query(Sale).filter(Sale.id.in_(sale_ids)).delete(
                        synchronize_session=False
                    )
                db.query(Client).filter(Client.id == client_row.id).delete(
                    synchronize_session=False
                )
            db.query(User).filter(User.email == email).delete(synchronize_session=False)
            db.commit()
