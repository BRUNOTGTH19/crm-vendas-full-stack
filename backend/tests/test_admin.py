"""Testes dos endpoints de gestão de dados (admin).

Cobrem: acesso sem permissão de admin (403), reset com/sem confirmação,
exportação e importação (modos skip/overwrite) e registro de auditoria.

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
from models.sale import Sale, SaleStatus
from models.sale_item import SaleItem
from models.user import User

client = TestClient(app)


def _register(email: str, role: str = "user") -> dict:
    r = client.post(
        "/auth/register",
        json={"name": "Teste Admin", "email": email, "password": "123456", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _login(email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_headers():
    email = f"admin_{datetime.now().strftime('%H%M%S%f')}@crm.com"
    _register(email)
    # Administradores são provisionados fora do cadastro público.
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user.role = "admin"
        db.commit()
    headers = _login(email)
    yield headers
    _cleanup_user(email)


@pytest.fixture(scope="module")
def user_headers():
    email = f"user_{datetime.now().strftime('%H%M%S%f')}@crm.com"
    _register(email, role="user")
    headers = _login(email)
    yield headers
    _cleanup_user(email)


def _cleanup_user(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Remove dependências antes do usuário (FKs).
            db.query(AuditLog).filter(AuditLog.user_id == user.id).delete(
                synchronize_session=False
            )
            client_ids = [c.id for c in db.query(Client).filter(Client.created_by_id == user.id)]
            if client_ids:
                sale_ids = [s.id for s in db.query(Sale).filter(Sale.client_id.in_(client_ids))]
                if sale_ids:
                    db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).delete(
                        synchronize_session=False
                    )
                    db.query(Sale).filter(Sale.id.in_(sale_ids)).delete(synchronize_session=False)
                db.query(Client).filter(Client.id.in_(client_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


def _seed_data(admin_headers: dict) -> int:
    """Cria cliente + venda + item direto no banco (sem depender do Redis).

    Evita o endpoint POST /sales, que invalida o cache do dashboard e exige
    Redis — mantendo o teste focado nos endpoints de admin.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == _email_from_headers(admin_headers)).first()
        assert user is not None

        c = Client(
            full_name=f"Cliente Teste {datetime.now().strftime('%H%M%S%f')}",
            name_normalized=f"cliente teste {datetime.now().strftime('%H%M%S%f')}",
            created_by_id=user.id,
        )
        db.add(c)
        db.flush()

        s = Sale(
            client_id=c.id,
            user_id=user.id,
            sale_date=date.today(),
            status=SaleStatus.pending,
            total=20,
            amount_paid=0,
            remaining=20,
            due_date=date.today(),
        )
        db.add(s)
        db.flush()

        db.add(
            SaleItem(
                sale_id=s.id,
                product_name="Produto Teste",
                quantity=2,
                unit_price=10,
                subtotal=20,
            )
        )
        db.commit()
        return c.id
    finally:
        db.close()


def _email_from_headers(headers: dict) -> str:
    """Extrai o e-mail do JWT (payload `email`) sem validar assinatura."""
    import base64
    import json

    token = headers["Authorization"].split(" ", 1)[1]
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    return payload["email"]


# ---------------------------------------------------------------------------
# Autorização
# ---------------------------------------------------------------------------

def test_reset_requires_admin(user_headers):
    r = client.post("/admin/database/reset", json={"confirm": True}, headers=user_headers)
    assert r.status_code == 403


def test_export_requires_admin(user_headers):
    r = client.get("/admin/database/export", headers=user_headers)
    assert r.status_code == 403


def test_import_requires_admin(user_headers):
    r = client.post(
        "/admin/database/import",
        files={"file": ("x.json", b"{}", "application/json")},
        headers=user_headers,
    )
    assert r.status_code == 403


def test_reset_requires_token():
    r = client.post("/admin/database/reset", json={"confirm": True})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_without_confirm_is_rejected(admin_headers):
    r = client.post("/admin/database/reset", json={"confirm": False}, headers=admin_headers)
    assert r.status_code == 400


def test_reset_with_confirm_clears_data(admin_headers):
    _seed_data(admin_headers)
    r = client.post("/admin/database/reset", json={"confirm": True}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "users" in body["preserved"]
    assert set(body["cleared"].keys()) >= {"clients", "sales", "sale_items"}

    # Após o reset, não deve haver clientes.
    r = client.get("/clients", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_reset_preserves_users(admin_headers):
    # O próprio admin continua autenticado após o reset.
    r = client.get("/auth/me", headers=admin_headers)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

def test_export_returns_json_download(admin_headers):
    _seed_data(admin_headers)
    r = client.get("/admin/database/export", headers=admin_headers)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert body["version"] == 1
    assert "tables" in body
    assert len(body["tables"]["clients"]) >= 1


def test_import_skip_and_overwrite(admin_headers):
    _seed_data(admin_headers)
    export = client.get("/admin/database/export", headers=admin_headers).json()

    # Import com skip: como os IDs já existem, tudo é pulado.
    r = client.post(
        "/admin/database/import?mode=skip",
        files={"file": ("export.json", export_json_bytes(export), "application/json")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["mode"] == "skip"
    assert result["skipped"]["clients"] >= 1

    # Import com overwrite: os registros existentes são atualizados.
    r = client.post(
        "/admin/database/import?mode=overwrite",
        files={"file": ("export.json", export_json_bytes(export), "application/json")},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "overwrite"


def test_import_invalid_file_is_rejected(admin_headers):
    r = client.post(
        "/admin/database/import",
        files={"file": ("bad.json", b'{"version": 1}', "application/json")},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_export_logs_audit(admin_headers):
    before = _count_action("database_export")
    client.get("/admin/database/export", headers=admin_headers)
    assert _count_action("database_export") == before + 1


def _count_action(action: str) -> int:
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.action == action).count()
    finally:
        db.close()


def test_audit_log_written(admin_headers):
    db = SessionLocal()
    try:
        count = db.query(AuditLog).filter(AuditLog.action == "database_reset").count()
        assert count >= 1
    finally:
        db.close()


def export_json_bytes(payload: dict) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")