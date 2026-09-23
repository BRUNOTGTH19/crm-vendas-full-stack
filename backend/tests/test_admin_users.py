"""Testes da gestão de usuários (admin): listagem e exclusão de usuários comuns.

Cobrem: autenticação/autorização, confirmação obrigatória, guardas (não
excluir outro admin, não excluir a si mesmo), alvo inexistente, cascata dos
dados do usuário (clients, sales, itens, payments, push e auditoria) e o
registro de auditoria da exclusão.

Usam SQLite em memória com foreign keys e serviços externos simulados
(conftest.py). Nenhuma conexão com o banco configurado é realizada.
"""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models.audit_log import AuditLog
from models.client import Client
from models.payment import Payment
from models.push_subscription import PushSubscription
from models.sale import Sale, SaleStatus
from models.sale_item import SaleItem
from models.user import User

client = TestClient(app)


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


def _promote_admin(email: str) -> None:
    """Administradores são provisionados fora do cadastro público."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.role = "admin"
        db.commit()


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).one().id


@pytest.fixture(scope="module")
def admin():
    email = f"adm_users_{datetime.now().strftime('%H%M%S%f')}@crm.com"
    _register("Admin Users", email)
    _promote_admin(email)
    return {"email": email, "id": _user_id(email), "headers": _login(email)}


@pytest.fixture(scope="module")
def common_user():
    email = f"common_{datetime.now().strftime('%H%M%S%f')}@crm.com"
    _register("Usuário Comum", email)
    return {"email": email, "id": _user_id(email), "headers": _login(email)}


def test_users_requires_token():
    r = client.get("/admin/users")
    assert r.status_code == 401


def test_users_requires_admin(common_user):
    r = client.get("/admin/users", headers=common_user["headers"])
    assert r.status_code == 403


def test_list_users_hides_password_hash(admin, common_user):
    r = client.get("/admin/users", headers=admin["headers"])
    assert r.status_code == 200, r.text
    emails = [u["email"] for u in r.json()]
    assert admin["email"] in emails
    assert common_user["email"] in emails
    assert all("password_hash" not in u for u in r.json())
    assert {"id", "name", "email", "role", "created_at"} <= set(r.json()[0].keys())


def test_delete_requires_confirmation(admin, common_user):
    r = client.request(
        "DELETE", f"/admin/users/{common_user['id']}", json={}, headers=admin["headers"]
    )
    assert r.status_code == 400

    r2 = client.request(
        "DELETE",
        f"/admin/users/{common_user['id']}",
        json={"confirm": False},
        headers=admin["headers"],
    )
    assert r2.status_code == 400

    with SessionLocal() as db:
        assert db.get(User, common_user["id"]) is not None


def test_delete_unknown_user_returns_404(admin):
    r = client.request(
        "DELETE", "/admin/users/999999", json={"confirm": True}, headers=admin["headers"]
    )
    assert r.status_code == 404


def test_cannot_delete_self(admin):
    r = client.request(
        "DELETE",
        f"/admin/users/{admin['id']}",
        json={"confirm": True},
        headers=admin["headers"],
    )
    assert r.status_code == 400
    with SessionLocal() as db:
        assert db.get(User, admin["id"]) is not None


def test_cannot_delete_another_admin(admin):
    email = f"adm2_{datetime.now().strftime('%H%M%S%f')}@crm.com"
    _register("Admin Dois", email)
    _promote_admin(email)
    other_id = _user_id(email)

    r = client.request(
        "DELETE",
        f"/admin/users/{other_id}",
        json={"confirm": True},
        headers=admin["headers"],
    )
    assert r.status_code == 400
    with SessionLocal() as db:
        assert db.get(User, other_id) is not None


def test_common_user_cannot_delete_anyone(common_user):
    r = client.request(
        "DELETE",
        f"/admin/users/{common_user['id']}",
        json={"confirm": True},
        headers=common_user["headers"],
    )
    assert r.status_code == 403


def test_delete_common_user_cascades_data(admin):
    stamp = datetime.now().strftime("%H%M%S%f")
    email = f"victim_{stamp}@crm.com"
    _register("Usuário Vítima", email)
    victim_id = _user_id(email)

    with SessionLocal() as db:
        c = Client(
            full_name=f"Cliente Vítima {stamp}",
            name_normalized=f"cliente vitima {stamp}",
            created_by_id=victim_id,
        )
        db.add(c)
        db.flush()
        s = Sale(
            client_id=c.id,
            user_id=victim_id,
            sale_date=date.today(),
            status=SaleStatus.pending,
            total=100,
            amount_paid=0,
            remaining=100,
        )
        db.add(s)
        db.flush()
        db.add(
            SaleItem(
                sale_id=s.id, product_name="Produto", quantity=1, unit_price=100, subtotal=100
            )
        )
        db.add(Payment(sale_id=s.id, amount_paid=50, payment_date=date.today()))
        db.add(
            PushSubscription(
                user_id=victim_id,
                endpoint=f"https://push.example/{stamp}",
                p256dh="chave-publica",
                auth="segredo",
            )
        )
        db.add(AuditLog(user_id=victim_id, action="test_seed", detail="{}"))
        db.commit()
        client_id, sale_id = c.id, s.id

    r = client.request(
        "DELETE",
        f"/admin/users/{victim_id}",
        json={"confirm": True},
        headers=admin["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted"] is True
    assert body["user_id"] == victim_id

    with SessionLocal() as db:
        assert db.get(User, victim_id) is None
        assert db.get(Client, client_id) is None
        assert db.get(Sale, sale_id) is None
        assert db.query(SaleItem).filter(SaleItem.sale_id == sale_id).count() == 0
        assert db.query(Payment).filter(Payment.sale_id == sale_id).count() == 0
        assert (
            db.query(PushSubscription)
            .filter(PushSubscription.user_id == victim_id)
            .count()
            == 0
        )
        assert db.query(AuditLog).filter(AuditLog.user_id == victim_id).count() == 0

        audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == "user_deleted", AuditLog.user_id == admin["id"])
            .all()
        )
        assert audit, "auditoria user_deleted não registrada"
        assert str(victim_id) in (audit[-1].detail or "")

        # O admin permanece intacto
        assert db.get(User, admin["id"]) is not None
