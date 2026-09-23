"""Gestão de dados (admin): reset, exportação, importação e gestão de usuários.

Cobre as tabelas de DADOS (clients, sales, sale_items, payments,
push_subscriptions) e a tabela de USUÁRIOS (listagem e deleção).

A tabela ``users`` é PRESERVADA no reset para não deslogar o administrador
que executa a operação.

O reset usa DELETE (não TRUNCATE) respeitando a ordem das foreign keys:
sale_items e payments antes de sales; sales antes de clients.
"""
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from cache import invalidate_data_cache
from models.audit_log import AuditLog
from models.client import Client
from models.payment import Payment
from models.push_subscription import PushSubscription
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User
from schemas.admin import (
    ClientExport,
    DataTables,
    ExportPayload,
    ImportResult,
    PaymentExport,
    PushSubscriptionExport,
    SaleExport,
    SaleItemExport,
    UserListItem,
    UserDeleteResult,
)


def log_action(db: Session, user_id: int | None, action: str, detail: str) -> AuditLog:
    """Registra uma ação administrativa na tabela de auditoria."""
    entry = AuditLog(user_id=user_id, action=action, detail=detail)
    db.add(entry)
    db.flush()
    return entry


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_data(db: Session) -> ExportPayload:
    """Monta o documento consolidado com todos os registros das tabelas de dados."""
    tables = DataTables(
        clients=[
            ClientExport.model_validate(c, from_attributes=True)
            for c in db.query(Client).order_by(Client.id).all()
        ],
        sales=[
            SaleExport.model_validate(s, from_attributes=True)
            for s in db.query(Sale).order_by(Sale.id).all()
        ],
        sale_items=[
            SaleItemExport.model_validate(i, from_attributes=True)
            for i in db.query(SaleItem).order_by(SaleItem.id).all()
        ],
        payments=[
            PaymentExport.model_validate(p, from_attributes=True)
            for p in db.query(Payment).order_by(Payment.id).all()
        ],
        push_subscriptions=[
            PushSubscriptionExport.model_validate(p, from_attributes=True)
            for p in db.query(PushSubscription).order_by(PushSubscription.id).all()
        ],
    )
    return ExportPayload(version=1, exported_at=datetime.now(timezone.utc), tables=tables)


def export_to_json(db: Session) -> str:
    """Serializa a exportação para JSON (pt-BR friendly, UTF-8)."""
    payload = export_data(db)
    return payload.model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def reset_data(db: Session, user_id: int | None) -> dict[str, int]:
    """Apaga os registros das tabelas de dados, preservando ``users``.

    Retorna um dicionário tabela -> quantidade removida.
    """
    # Ordem respeitando as foreign keys (filhos antes dos pais).
    counts: dict[str, int] = {}
    counts["sale_items"] = db.query(SaleItem).delete(synchronize_session=False)
    counts["payments"] = db.query(Payment).delete(synchronize_session=False)
    counts["push_subscriptions"] = (
        db.query(PushSubscription).delete(synchronize_session=False)
    )
    counts["sales"] = db.query(Sale).delete(synchronize_session=False)
    counts["clients"] = db.query(Client).delete(synchronize_session=False)

    log_action(
        db,
        user_id,
        "database_reset",
        json.dumps({"cleared": counts, "preserved": ["users"]}, ensure_ascii=False),
    )
    db.commit()
    invalidate_data_cache()
    return counts


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_data(
    db: Session, payload: ExportPayload, mode: str = "skip", user_id: int | None = None
) -> ImportResult:
    """Reinsere os dados exportados, validados por Pydantic.

    mode="skip": ignora registros cujo id já existe.
    mode="overwrite": atualiza campos dos registros existentes.

    A ordem de inserção respeita as foreign keys: clients -> sales ->
    sale_items/payments. As push_subscriptions são independentes.
    """
    inserted = {"clients": 0, "sales": 0, "sale_items": 0, "payments": 0, "push_subscriptions": 0}
    skipped = dict(inserted)
    updated = dict(inserted)

    def apply(model, row, counters_prefix: str):
        obj = db.get(model, row.id)
        if obj is None:
            data = row.model_dump(exclude_none=True)
            db.add(model(**data))
            inserted[counters_prefix] += 1
            return
        if mode == "overwrite":
            values = row.model_dump(exclude={"id"})
            if values.get("created_at") is None:
                values.pop("created_at", None)
            for field, value in values.items():
                setattr(obj, field, value)
            updated[counters_prefix] += 1
        else:
            skipped[counters_prefix] += 1

    for row in payload.tables.clients:
        apply(Client, row, "clients")
    db.flush()

    for row in payload.tables.sales:
        apply(Sale, row, "sales")
    db.flush()

    for row in payload.tables.sale_items:
        apply(SaleItem, row, "sale_items")
    for row in payload.tables.payments:
        apply(Payment, row, "payments")
    for row in payload.tables.push_subscriptions:
        apply(PushSubscription, row, "push_subscriptions")

    db.flush()

    log_action(
        db,
        user_id,
        "database_import",
        json.dumps(
            {"mode": mode, "inserted": inserted, "skipped": skipped, "updated": updated},
            ensure_ascii=False,
        ),
    )
    db.commit()
    invalidate_data_cache()
    return ImportResult(mode=mode, inserted=inserted, skipped=skipped, updated=updated)


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------


def list_users(db: Session) -> list[UserListItem]:
    """Lista todos os usuários do sistema (nome, e-mail, papel, data de criação).

    Apenas administradores têm acesso. Não retorna password_hash.
    """
    users = db.query(User).order_by(User.id).all()
    return [
        UserListItem(
            id=u.id,
            name=u.name,
            email=u.email,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            created_at=u.created_at,
        )
        for u in users
    ]


def delete_user(db: Session, user_id: int, admin_id: int, confirm: bool) -> UserDeleteResult:
    """Deleta um usuário comum e seus dados associados.

    Regras de segurança:
    - ``confirm`` deve ser ``True``, caso contrário a operação é recusada.
    - O próprio admin não pode se deletar.
    - Admins não podem deletar outros admins.
    - Antes de deletar o usuário, remove-se suas dependências (clients, sales,
      sale_items, payments, audit_logs, push_subscriptions) respeitando as FKs.
    """
    if not confirm:
        raise ValueError("Confirmação obrigatória: envie confirm=true para excluir o usuário.")

    user = db.get(User, user_id)
    if user is None:
        raise ValueError("Usuário não encontrado")

    if user.id == admin_id:
        raise ValueError("Um administrador não pode excluir a si mesmo")

    if user.role.value == "admin":
        raise ValueError("Não é possível excluir outro administrador")

    # Remove dependências do usuário (FKs: filhos antes dos pais).
    # Ordem: sale_items -> payments -> push_subscriptions -> sales -> clients
    # -> audit_logs -> users

    # Vendas do usuário + vendas legadas presas a clientes dele (mesmo critério
    # do cleanup_test_data.py: evita órfãos de dados antigos).
    sale_ids = {s.id for s in db.query(Sale).filter(Sale.user_id == user_id)}
    client_ids = [c.id for c in db.query(Client).filter(Client.created_by_id == user_id)]
    if client_ids:
        sale_ids.update(
            s.id for s in db.query(Sale).filter(Sale.client_id.in_(client_ids))
        )
    sale_ids = list(sale_ids)

    # Sale items e payments das vendas afetadas
    if sale_ids:
        db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).delete(
            synchronize_session=False
        )
        db.query(Payment).filter(Payment.sale_id.in_(sale_ids)).delete(
            synchronize_session=False
        )

    # Push subscriptions
    db.query(PushSubscription).filter(PushSubscription.user_id == user_id).delete(
        synchronize_session=False
    )

    # Sales e clients criados pelo usuário
    if sale_ids:
        db.query(Sale).filter(Sale.id.in_(sale_ids)).delete(synchronize_session=False)
    if client_ids:
        db.query(Client).filter(Client.id.in_(client_ids)).delete(synchronize_session=False)

    # Audit logs do usuário
    db.query(AuditLog).filter(AuditLog.user_id == user_id).delete(synchronize_session=False)

    # Por fim, o próprio usuário
    db.delete(user)

    log_action(
        db,
        admin_id,
        "user_deleted",
        json.dumps({"deleted_user_id": user_id, "deleted_user_email": user.email}, ensure_ascii=False),
    )
    db.commit()
    invalidate_data_cache()

    return UserDeleteResult(
        deleted=True,
        user_id=user_id,
        preserved=["users"],
    )