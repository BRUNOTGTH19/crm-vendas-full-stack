"""Prova do isolamento de dados por dono (escopo multiusuário).

Cobre as regras de ``resolve_data_owner``:

- usuário comum: enxerga **apenas** os próprios dados; ``X-View-User`` é
  ignorado (não é possível espiar outro usuário);
- administrador: escopo **global** sem o header e escopo do usuário
  selecionado ao enviar ``X-View-User`` (404 se o usuário não existir);
- regressão do bug original: usuário comum consegue registrar venda no
  próprio cliente.

Usa SQLite em memória com foreign keys e serviços externos simulados
(conftest.py). Nenhuma conexão com o banco configurado é realizada.
"""
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models.audit_log import AuditLog
from models.client import Client
from models.payment import Payment
from models.push_subscription import PushSubscription
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User

client = TestClient(app)


def _register(email: str) -> None:
    r = client.post(
        "/auth/register",
        json={"name": "Escopo Teste", "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text


def _login(email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).one().id


def _cleanup_user(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return
        db.query(AuditLog).filter(AuditLog.user_id == user.id).delete(
            synchronize_session=False
        )
        db.query(PushSubscription).filter(
            PushSubscription.user_id == user.id
        ).delete(synchronize_session=False)
        client_ids = [
            c.id for c in db.query(Client).filter(Client.created_by_id == user.id)
        ]
        if client_ids:
            sale_ids = [
                s.id for s in db.query(Sale).filter(Sale.client_id.in_(client_ids))
            ]
            if sale_ids:
                db.query(Payment).filter(Payment.sale_id.in_(sale_ids)).delete(
                    synchronize_session=False
                )
                db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).delete(
                    synchronize_session=False
                )
                db.query(Sale).filter(Sale.id.in_(sale_ids)).delete(
                    synchronize_session=False
                )
            db.query(Client).filter(Client.id.in_(client_ids)).delete(
                synchronize_session=False
            )
        db.delete(user)
        db.commit()


def _create_client(headers: dict, name: str) -> dict:
    r = client.post("/clients", json={"full_name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _sale_payload(client_id: int) -> dict:
    return {
        "client_id": client_id,
        "sale_date": date.today().isoformat(),
        "status": "pending",
        "due_date": (date.today() + timedelta(days=1)).isoformat(),
        "items": [{"product_name": "Produto Escopo", "quantity": 2, "unit_price": "10.00"}],
    }


# --------------------------------------------------------------------------
# Fixtures (escopo de módulo): usuário comum A, usuário comum B e admin.
# --------------------------------------------------------------------------
import pytest


@pytest.fixture(scope="module")
def user_a():
    stamp = datetime.now().strftime("%H%M%S%f")
    email = f"escopo_a_{stamp}@crm.com"
    _register(email)
    yield {"email": email, "headers": _login(email)}
    _cleanup_user(email)


@pytest.fixture(scope="module")
def user_b():
    stamp = datetime.now().strftime("%H%M%S%f")
    email = f"escopo_b_{stamp}@crm.com"
    _register(email)
    yield {"email": email, "headers": _login(email)}
    _cleanup_user(email)


@pytest.fixture(scope="module")
def admin():
    stamp = datetime.now().strftime("%H%M%S%f")
    email = f"escopo_admin_{stamp}@crm.com"
    _register(email)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.role = "admin"
        db.commit()
    yield {"email": email, "headers": _login(email)}
    _cleanup_user(email)


# --------------------------------------------------------------------------
# Usuário comum: apenas os próprios dados
# --------------------------------------------------------------------------
def test_common_user_sees_only_own_clients(user_a, user_b):
    client_a = _create_client(user_a["headers"], "Cliente Do Usuario A")
    _create_client(user_b["headers"], "Cliente Do Usuario B")

    r = client.get("/clients", headers=user_a["headers"])
    assert r.status_code == 200
    names = [c["full_name"] for c in r.json()]
    assert "Cliente Do Usuario A" in names
    assert "Cliente Do Usuario B" not in names
    assert all(c["id"] != _foreign_client_id(user_b) for c in r.json())
    assert client_a["created_by_id"] == _user_id(user_a["email"])


def _foreign_client_id(user: dict) -> int:
    r = client.get("/clients", headers=user["headers"])
    assert r.status_code == 200
    return r.json()[0]["id"]


def test_common_user_cannot_read_update_or_delete_foreign_client(user_a, user_b):
    foreign_id = _foreign_client_id(user_b)
    assert (
        client.get(f"/clients/{foreign_id}", headers=user_a["headers"]).status_code
        == 404
    )
    assert (
        client.put(
            f"/clients/{foreign_id}",
            json={"full_name": "Tentativa De Acesso"},
            headers=user_a["headers"],
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/clients/{foreign_id}", headers=user_a["headers"]).status_code
        == 404
    )


def test_common_user_view_user_header_is_ignored(user_a, user_b):
    """O header X-View-User de um usuário comum é ignorado (anti-espionagem)."""
    foreign_id = _foreign_client_id(user_b)
    r = client.get(
        "/clients",
        headers={**user_a["headers"], "X-View-User": str(foreign_id)},
    )
    assert r.status_code == 200
    assert foreign_id not in [c["id"] for c in r.json()]


def test_common_user_cannot_register_sale_on_foreign_client(user_a, user_b):
    foreign_id = _foreign_client_id(user_b)
    r = client.post(
        "/sales", json=_sale_payload(foreign_id), headers=user_a["headers"]
    )
    assert r.status_code == 400


def test_common_user_registers_sale_on_own_client(user_a):
    """Regressão: o usuário comum registra venda sem erro de backend."""
    own = _create_client(user_a["headers"], "Cliente Proprio Venda")
    r = client.post(
        "/sales", json=_sale_payload(own["id"]), headers=user_a["headers"]
    )
    assert r.status_code == 201, r.text
    assert r.json()["client_id"] == own["id"]


def test_common_user_cannot_see_or_pay_foreign_sale(user_a, user_b):
    own = _create_client(user_b["headers"], "Cliente Venda Do B")
    r = client.post("/sales", json=_sale_payload(own["id"]), headers=user_b["headers"])
    assert r.status_code == 201, r.text
    sale_id = r.json()["id"]

    # Leitura da venda de outro usuário -> 404
    assert (
        client.get(f"/sales/{sale_id}", headers=user_a["headers"]).status_code == 404
    )
    # Pagamento em venda de outro usuário -> 400
    r = client.post(
        "/payments",
        json={
            "sale_id": sale_id,
            "amount_paid": "5.00",
            "payment_date": date.today().isoformat(),
        },
        headers=user_a["headers"],
    )
    assert r.status_code == 400
    # Lista de pagamentos de venda alheia -> vazia
    r = client.get(f"/payments/{sale_id}", headers=user_a["headers"])
    assert r.status_code == 200
    assert r.json() == []


# --------------------------------------------------------------------------
# Administrador: global por padrão, escopo do usuário via X-View-User
# --------------------------------------------------------------------------
def test_admin_without_header_sees_global_scope(admin, user_a, user_b):
    _create_client(user_a["headers"], "Cliente Global A")
    _create_client(user_b["headers"], "Cliente Global B")

    r = client.get("/clients", headers=admin["headers"])
    assert r.status_code == 200
    names = [c["full_name"] for c in r.json()]
    assert "Cliente Global A" in names
    assert "Cliente Global B" in names


def test_admin_with_view_user_header_scopes_to_selected_user(admin, user_a):
    foreign_id = _foreign_client_id(user_a)
    r = client.get(
        "/clients",
        headers={**admin["headers"], "X-View-User": str(_user_id(user_a["email"]))},
    )
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert foreign_id in ids
    assert all(c["created_by_id"] == _user_id(user_a["email"]) for c in r.json())


def test_admin_view_user_unknown_returns_404(admin):
    r = client.get(
        "/clients", headers={**admin["headers"], "X-View-User": "999999999"}
    )
    assert r.status_code == 404


def test_admin_dashboard_is_global_by_default(admin):
    r = client.get("/dashboard", headers=admin["headers"])
    assert r.status_code == 200
    # Escopo global: soma os clientes de todos os usuários do teste.
    assert r.json()["total_clients"] >= 2


def test_common_user_dashboard_is_scoped(user_a):
    r = client.get("/dashboard", headers=user_a["headers"])
    assert r.status_code == 200
    with SessionLocal() as db:
        expected = (
            db.query(Client)
            .filter(Client.created_by_id == _user_id(user_a["email"]))
            .count()
        )
    assert r.json()["total_clients"] == expected