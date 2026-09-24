"""Regressões de clientes: conflito de nome não pode virar 500.

O índice ``clients.name_normalized`` é GLOBAL, mas a checagem de duplicidade do
serviço é por dono. Renomear um cliente para um nome já usado por outro usuário
passava pela checagem, estourava ``IntegrityError`` no commit e a API devolvia
500 (visto no ``smoke_test_e2e.py``: ``update client: 500``).

Usa SQLite em memória com foreign keys e serviços externos simulados
(conftest.py). Nenhuma conexão com o banco configurado é realizada.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models.audit_log import AuditLog
from models.client import Client
from models.push_subscription import PushSubscription
from models.user import User

client = TestClient(app)


def _register(email: str) -> None:
    r = client.post(
        "/auth/register",
        json={"name": "Clientes Teste", "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text


def _login(email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user(prefix: str) -> dict:
    email = f"{prefix}_{datetime.now().strftime('%H%M%S%f')}@crm.com"
    _register(email)
    return {"email": email, "headers": _login(email)}


def _cleanup(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return
        db.query(AuditLog).filter(AuditLog.user_id == user.id).delete(
            synchronize_session=False
        )
        db.query(PushSubscription).filter(PushSubscription.user_id == user.id).delete(
            synchronize_session=False
        )
        db.query(Client).filter(Client.created_by_id == user.id).delete(
            synchronize_session=False
        )
        db.delete(user)
        db.commit()


@pytest.fixture
def owner():
    user = _user("clientes")
    yield user
    _cleanup(user["email"])


@pytest.fixture
def other_user():
    user = _user("clientes_outro")
    yield user
    _cleanup(user["email"])


def _create(headers: dict, name: str) -> int:
    r = client.post("/clients", json={"full_name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_update_client_with_own_name_succeeds(owner):
    cid = _create(owner["headers"], "Cliente Renomeavel")
    r = client.put(
        f"/clients/{cid}",
        json={"full_name": "Cliente Renomeado"},
        headers=owner["headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Cliente Renomeado"


def test_update_client_to_same_name_keeps_client(owner):
    """Regravar o próprio nome (sem mudança) não pode dar conflito."""
    cid = _create(owner["headers"], "Cliente Sem Mudanca")
    r = client.put(
        f"/clients/{cid}",
        json={"full_name": "Cliente Sem Mudanca"},
        headers=owner["headers"],
    )
    assert r.status_code == 200, r.text


def test_update_client_to_duplicate_name_returns_400_not_500(owner):
    _create(owner["headers"], "Cliente A")
    cid = _create(owner["headers"], "Cliente B")

    r = client.put(
        f"/clients/{cid}",
        json={"full_name": "Cliente A"},
        headers=owner["headers"],
    )
    assert r.status_code == 400, r.text
    assert "Já existe um cliente" in r.json()["detail"]


def test_update_client_to_name_of_another_owner_returns_400(owner, other_user):
    """Índice global + checagem por dono: era aqui que nascia o 500."""
    _create(other_user["headers"], "Cliente Nome Global")
    cid = _create(owner["headers"], "Cliente De Outro Dono")

    r = client.put(
        f"/clients/{cid}",
        json={"full_name": "Cliente Nome Global"},
        headers=owner["headers"],
    )
    assert r.status_code == 400, r.text
    assert "Já existe um cliente" in r.json()["detail"]


def test_create_client_with_name_of_another_owner_returns_400(owner, other_user):
    _create(other_user["headers"], "Cliente Criado Por Outro")
    r = client.post(
        "/clients",
        json={"full_name": "Cliente Criado Por Outro"},
        headers=owner["headers"],
    )
    assert r.status_code == 400, r.text
