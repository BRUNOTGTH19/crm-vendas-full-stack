"""Testes da ativação de administrador por código secreto.

Cobrem: código gerado e registrado no log, promoção do usuário logado,
consumo único, código definido por ``ADMIN_SETUP_CODE``, bootstrap por
``ADMIN_EMAIL``, exigência de autenticação e rate limit por IP.
"""
import re
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
CODE_HASH_KEY = "admin_setup_code_hash"
CONSUMED_KEY = "admin_setup_consumed"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%S%f")


def _register(name: str, email: str) -> dict:
    r = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "12345678"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _login(email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "12345678"})
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

    # A13: só o hash fica no banco. O texto claro aparece uma vez no log.
    with SessionLocal() as db:
        stored_hash = (
            db.query(AppSetting).filter(AppSetting.key == CODE_HASH_KEY).one().value
        )
        assert db.query(AppSetting).filter(AppSetting.key == CODE_KEY).count() == 0
    assert len(stored_hash) == 64
    match = re.search(r"admin_setup_code_generated code=(\S+)", caplog.text)
    assert match, caplog.text
    code = match.group(1)
    assert code not in stored_hash

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
        assert db.query(AppSetting).filter(AppSetting.key == CODE_HASH_KEY).count() == 0
        assert db.query(AppSetting).filter(AppSetting.key == CONSUMED_KEY).count() == 1
        assert db.query(AuditLog).filter(AuditLog.action == "admin_activated").count() == 1

    # O código é de uso único: outro usuário não consegue usá-lo.
    other = _login(other_email)
    r = _activate(other, code)
    assert r.status_code == 400
    assert client.get("/admin/users", headers=other).status_code == 403


def test_legacy_plaintext_code_is_migrated_to_hash():
    """Bancos antigos guardavam o código em texto claro; a leitura migra."""
    stamp = _stamp()
    email = f"legado_{stamp}@crm.com"
    _register("Legado", email)
    with SessionLocal() as db:
        db.add(AppSetting(key=CODE_KEY, value="codigo-legado-123"))
        db.commit()

    headers = _login(email)  # login gera/migra o código
    with SessionLocal() as db:
        assert db.query(AppSetting).filter(AppSetting.key == CODE_KEY).count() == 0
        stored = (
            db.query(AppSetting).filter(AppSetting.key == CODE_HASH_KEY).one().value
        )
    assert stored != "codigo-legado-123"
    assert _activate(headers, "codigo-legado-123").status_code == 200



def test_env_code_works_even_with_existing_admin(monkeypatch):
    """A chave mestra do operador funciona mesmo se já existe um admin.

    Antes, a checagem de "já existe admin" vinha antes da validação do código,
    o que travava a recuperação de acesso. Agora a variável é soberana.
    """
    monkeypatch.setattr(settings, "admin_setup_code", "codigo-do-dono")
    stamp = _stamp()
    owner_email = f"env_dono_{stamp}@crm.com"
    other_email = f"env_outro_{stamp}@crm.com"
    _register("Dono Env", owner_email)
    _register("Outro Env", other_email)

    # Admin pré-existente (de um uso anterior) não bloqueia a chave mestra.
    with SessionLocal() as db:
        db.add(
            User(
                name="Admin Anterior",
                email=f"anterior_{stamp}@crm.com",
                password_hash="x",
                role="admin",
            )
        )
        db.commit()

    owner = _login(owner_email)
    # Com a variável definida, nenhum código aleatório é gerado.
    with SessionLocal() as db:
        assert db.query(AppSetting).filter(AppSetting.key == CODE_KEY).count() == 0

    assert _activate(owner, "errado").status_code == 400
    r = _activate(owner, "codigo-do-dono")
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"
    assert client.get("/admin/users", headers=owner).status_code == 200

    # Sem saber a chave, ninguém mais entra.
    other = _login(other_email)
    assert _activate(other, "outra-tentativa").status_code == 400
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


def test_non_ascii_code_validates_without_crashing(monkeypatch):
    """A9: ``compare_digest`` só aceita ASCII; acento não pode gerar 500."""
    monkeypatch.setattr(settings, "admin_setup_code", "chave-secreta-ação")
    stamp = _stamp()
    email = f"acento_{stamp}@crm.com"
    _register("Acento", email)
    headers = _login(email)

    # Código errado, também com acento: erro limpo (400), não 500.
    assert _activate(headers, "chave-errada-ação").status_code == 400

    r = _activate(headers, "chave-secreta-ação")
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"


def test_failed_activation_leaves_audit_trail(monkeypatch):
    """A16: tentativa inválida é registrada (sem guardar o código digitado)."""
    monkeypatch.setattr(settings, "admin_setup_code", "codigo-de-teste")
    stamp = _stamp()
    email = f"audit_{stamp}@crm.com"
    created = _register("Auditoria", email)
    headers = _login(email)

    assert _activate(headers, "codigo-errado").status_code == 400

    with SessionLocal() as db:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "admin_activation_failed")
            .one()
        )
    assert log.user_id == created["id"]
    assert log.detail == "invalid_code"


def test_admin_email_does_not_promote_when_admin_exists(monkeypatch):
    """A11: o bootstrap por e-mail vale só para o primeiro administrador."""
    stamp = _stamp()
    monkeypatch.setattr(settings, "admin_email", f"chefe_{stamp}@crm.com")
    with SessionLocal() as db:
        db.add(
            User(
                name="Admin Existente",
                email=f"ja_admin_{stamp}@crm.com",
                password_hash="x",
                role="admin",
            )
        )
        db.commit()

    email = f"chefe_{stamp}@crm.com"
    _register("Chefe", email)
    headers = _login(email)
    assert client.get("/admin/users", headers=headers).status_code == 403


def test_rotation_invalidates_previous_code(monkeypatch, caplog):
    """A4: girar o código invalida imediatamente o anterior."""
    from services.auth_service import rotate_admin_setup_code

    monkeypatch.setattr(settings, "admin_setup_code", "")
    stamp = _stamp()
    email = f"rot_{stamp}@crm.com"
    _register("Rotacao", email)
    _login(email)  # gera o primeiro código
    old_code = re.search(r"admin_setup_code_generated code=(\S+)", caplog.text).group(1)

    with SessionLocal() as db:
        new_code = rotate_admin_setup_code(db)

    assert new_code != old_code
    headers = _login(email)
    assert _activate(headers, old_code).status_code == 400
    assert _activate(headers, new_code).status_code == 200


def test_expire_disables_generated_code(monkeypatch, caplog):
    """A4: encerrar a ativação não deixa um código novo utilizável."""
    from services.auth_service import expire_admin_setup_code

    monkeypatch.setattr(settings, "admin_setup_code", "")
    stamp = _stamp()
    email = f"exp_{stamp}@crm.com"
    _register("Expira", email)
    _login(email)
    code = re.search(r"admin_setup_code_generated code=(\S+)", caplog.text).group(1)

    with SessionLocal() as db:
        expire_admin_setup_code(db)

    headers = _login(email)
    assert _activate(headers, code).status_code == 400


