"""Limpa os dados de teste criados durante a execucao dos testes.

A ordem de exclusao respeita as FKs (sem `ON DELETE`):

    audit_logs, push_subscriptions, payments, sale_items -> sales -> clients -> users

Os itens «payments», «push_subscriptions» e «audit_logs» nao eram limpos, e a
exclusao do usuario estourava
``IntegrityError: Cannot delete or update a parent row`` — deixando usuarios e
clientes de teste presos no banco (e o nome deles colidindo com o indice unico
global de ``clients.name_normalized`` nas execucoes seguintes).

É idempotente: pode rodar quantas vezes for preciso.
"""
from sqlalchemy import or_

from database import SessionLocal
from models.audit_log import AuditLog
from models.client import Client
from models.push_subscription import PushSubscription
from models.payment import Payment
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User

# Usuarios de teste: nomes conhecidos + padroes usados pelos smoke tests.
# Cobrir esses padroes permite remover residuos de teste (inclusive sondagens
# de diagnostico em producao) sem tocar em dados reais.
TEST_EMAIL_PATTERNS = (
    "smoke_%@crm.com",
    "sales_smoke_%@crm.com",
    "e2e_%@test.com",
    "faseA_%@test.com",
    "diag%@test.com",
    "e2e_probe_%@example.com",
    "e2e_%@example.com",
    "probe_%@example.com",
    "diag_%@example.com",
)
TEST_EMAILS = ("teste1@crm.com",)


def test_user_filter():
    """Filtro ORM dos usuários criados por testes/sondagens."""
    conditions = [User.email.like(pattern) for pattern in TEST_EMAIL_PATTERNS]
    conditions += [User.email == email for email in TEST_EMAILS]
    return or_(*conditions)


def cleanup() -> dict[str, int]:
    """Remove os resíduos de teste e devolve o total de linhas apagadas."""
    db = SessionLocal()
    deleted = {
        "users": 0,
        "clients": 0,
        "sales": 0,
        "sale_items": 0,
        "payments": 0,
        "push_subscriptions": 0,
        "audit_logs": 0,
    }
    try:
        user_ids = [u.id for u in db.query(User).filter(test_user_filter()).all()]
        if not user_ids:
            return deleted

        client_ids = [
            c.id
            for c in db.query(Client).filter(Client.created_by_id.in_(user_ids)).all()
        ]
        sale_ids = [
            s.id
            for s in db.query(Sale)
            .filter(or_(Sale.user_id.in_(user_ids), Sale.client_id.in_(client_ids or [0])))
            .all()
        ]

        if sale_ids:
            deleted["payments"] = (
                db.query(Payment)
                .filter(Payment.sale_id.in_(sale_ids))
                .delete(synchronize_session=False)
            )
            deleted["sale_items"] = (
                db.query(SaleItem)
                .filter(SaleItem.sale_id.in_(sale_ids))
                .delete(synchronize_session=False)
            )
            deleted["sales"] = (
                db.query(Sale)
                .filter(Sale.id.in_(sale_ids))
                .delete(synchronize_session=False)
            )
        if client_ids:
            deleted["clients"] = (
                db.query(Client)
                .filter(Client.id.in_(client_ids))
                .delete(synchronize_session=False)
            )

        deleted["push_subscriptions"] = (
            db.query(PushSubscription)
            .filter(PushSubscription.user_id.in_(user_ids))
            .delete(synchronize_session=False)
        )
        deleted["audit_logs"] = (
            db.query(AuditLog)
            .filter(AuditLog.user_id.in_(user_ids))
            .delete(synchronize_session=False)
        )
        deleted["users"] = (
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        )
        db.commit()
        return deleted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def totals() -> dict[str, int]:
    db = SessionLocal()
    try:
        return {
            "users": db.query(User).count(),
            "clients": db.query(Client).count(),
            "sales": db.query(Sale).count(),
            "items": db.query(SaleItem).count(),
        }
    finally:
        db.close()


if __name__ == "__main__":
    removed = cleanup()
    print("removidos:", ", ".join(f"{k}={v}" for k, v in removed.items() if v))
    print("restantes:", totals())
