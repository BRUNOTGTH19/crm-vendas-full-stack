"""Gestão de dados (admin): reset, exportação e importação.

Cobre apenas as tabelas de DADOS (clients, sales, sale_items, payments,
push_subscriptions). A tabela ``users`` é PRESERVADA no reset para não
deslogar o administrador que executa a operação.

O reset usa DELETE (não TRUNCATE) respeitando a ordem das foreign keys:
sale_items e payments antes de sales; sales antes de clients.
"""
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.client import Client
from models.payment import Payment
from models.push_subscription import PushSubscription
from models.sale import Sale
from models.sale_item import SaleItem
from schemas.admin import (
    ClientExport,
    DataTables,
    ExportPayload,
    ImportResult,
    PaymentExport,
    PushSubscriptionExport,
    SaleExport,
    SaleItemExport,
)


def log_action(db: Session, user_id: int | None, action: str, detail: str) -> AuditLog:
    """Registra uma ação administrativa na tabela de auditoria."""
    entry = AuditLog(user_id=user_id, action=action, detail=detail)
    db.add(entry)
    db.commit()
    db.refresh(entry)
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
    db.commit()

    log_action(
        db,
        user_id,
        "database_reset",
        json.dumps({"cleared": counts, "preserved": ["users"]}, ensure_ascii=False),
    )
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
            data = row.model_dump(exclude={"created_at"})
            db.add(model(**data))
            inserted[counters_prefix] += 1
            return
        if mode == "overwrite":
            for field, value in row.model_dump(exclude={"id", "created_at"}).items():
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

    db.commit()

    log_action(
        db,
        user_id,
        "database_import",
        json.dumps(
            {"mode": mode, "inserted": inserted, "skipped": skipped, "updated": updated},
            ensure_ascii=False,
        ),
    )
    return ImportResult(mode=mode, inserted=inserted, skipped=skipped, updated=updated)