"""Ferramentas de leitura do CRM usadas pelo assistente de IA.

Regras de segurança:

- o escopo (``owner_id``) nunca é aceito como argumento de ferramenta: ele vem
  do JWT/``resolve_data_owner`` pelo router e é aplicado em toda consulta;
- as ferramentas são fixas e não geram SQL livre; não há escrita, exclusão nem
  execução de ação;
- os schemas usam ``extra="forbid"``, então um ``user_id`` enviado pelo modelo
  é rejeitado;
- ferramentas administrativas exigem ``is_admin``.

As ferramentas de web ficam em ``ai_web`` e são despachadas por
``execute_tool_async``; ``execute_tool`` só executa ferramentas de banco.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    model_validator,
)
from sqlalchemy import case, func
from sqlalchemy.orm import Session

import cache
from clock import local_today
from models.client import Client
from models.payment import Payment
from models.sale import Sale, SaleStatus
from models.sale_item import SaleItem
from models.user import User
from services.ai_config import AIToolError
from services.ai_web import FetchUrlArgs, WebSearchArgs, fetch_url, web_search
from services.client_service import normalize_name
from services.scope import scoped

MAX_OVERDUE_ROWS = 20
MAX_SUMMARY_RANGE_DAYS = 366
MAX_LIST_RANGE_DAYS = 3660

SUMMARY_CACHE_TTL = 180
OVERDUE_CACHE_TTL = 60
SALE_STATUS_CACHE_TTL = 60
LIST_CACHE_TTL = 60
REPORT_CACHE_TTL = 180
PROFILE_CACHE_TTL = 120
ADMIN_CACHE_TTL = 120


@dataclass(frozen=True)
class ToolScope:
    """Escopo efetivo de dados aplicado a todas as ferramentas de CRM.

    ``is_admin=False`` ignora ``owner_id`` e força o próprio ``user_id``.
    ``is_admin=True`` com ``owner_id=None`` significa escopo global.
    """

    user_id: int
    is_admin: bool = False
    owner_id: int | None = None

    @property
    def scope_id(self) -> int | None:
        return self.owner_id if self.is_admin else self.user_id

    @property
    def scope_key(self) -> str:
        return "global" if self.scope_id is None else str(self.scope_id)


def _validate_period(
    start: date | None,
    end: date | None,
    *,
    max_days: int = MAX_LIST_RANGE_DAYS,
) -> None:
    if start is not None and end is not None:
        if end < start:
            raise ValueError("A data final deve ser maior ou igual à inicial.")
        if (end - start).days > max_days:
            raise ValueError("Período máximo excedido.")


def _resolve_period(start: date | None, end: date | None) -> tuple[date, date]:
    today = local_today()
    if start is None and end is None:
        return today.replace(day=1), today
    if start is None:
        start = end.replace(day=1) if end else today.replace(day=1)
    if end is None:
        end = today
    _validate_period(start, end)
    return start, end


class SalesSummaryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inicio: date
    fim: date

    @model_validator(mode="after")
    def validate_range(self) -> SalesSummaryArgs:
        if self.fim < self.inicio:
            raise ValueError("fim deve ser maior ou igual a inicio")
        if (self.fim - self.inicio).days > MAX_SUMMARY_RANGE_DAYS:
            raise ValueError("período máximo excedido")
        return self


class DashboardOverviewArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CashflowArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")

    @model_validator(mode="after")
    def validate_month(self) -> CashflowArgs:
        if self.month is not None:
            year, month = (int(part) for part in self.month.split("-"))
            if not 1 <= month <= 12:
                raise ValueError("mês inválido")
            if not 2000 <= year <= 2100:
                raise ValueError("ano inválido")
        return self


class ListOverdueArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SaleStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_id: StrictInt = Field(gt=0)


class SearchClientsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=100)
    limit: StrictInt = Field(default=10, ge=1, le=20)


class ClientDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: StrictInt = Field(gt=0)


class ListSalesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["paid", "pending"] | None = None
    client_id: StrictInt | None = Field(default=None, gt=0)
    start: date | None = None
    end: date | None = None
    limit: StrictInt = Field(default=20, ge=1, le=30)

    @model_validator(mode="after")
    def validate_range(self) -> ListSalesArgs:
        _validate_period(self.start, self.end)
        return self


class SaleDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_id: StrictInt = Field(gt=0)


class ListPaymentsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_id: StrictInt | None = Field(default=None, gt=0)
    start: date | None = None
    end: date | None = None
    limit: StrictInt = Field(default=20, ge=1, le=30)

    @model_validator(mode="after")
    def validate_range(self) -> ListPaymentsArgs:
        _validate_period(self.start, self.end)
        return self


class TopProductsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: date | None = None
    end: date | None = None
    limit: StrictInt = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_range(self) -> TopProductsArgs:
        _validate_period(self.start, self.end)
        return self


class ClientRankingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: date | None = None
    end: date | None = None
    limit: StrictInt = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_range(self) -> ClientRankingArgs:
        _validate_period(self.start, self.end)
        return self


class GlobalSearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=100)
    limit: StrictInt = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def strip_query(self) -> GlobalSearchArgs:
        self.query = self.query.strip()
        if not self.query:
            raise ValueError("Consulta vazia.")
        return self


class MyProfileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListUsersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserSummaryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: StrictInt = Field(gt=0)
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def validate_range(self) -> UserSummaryArgs:
        _validate_period(self.start, self.end)
        return self


DB_TOOL_MODELS: dict[str, type[BaseModel]] = {
    "get_sales_summary": SalesSummaryArgs,
    "get_dashboard_overview": DashboardOverviewArgs,
    "get_cashflow": CashflowArgs,
    "list_overdue": ListOverdueArgs,
    "get_sale_status": SaleStatusArgs,
    "search_clients": SearchClientsArgs,
    "get_client_details": ClientDetailsArgs,
    "list_sales": ListSalesArgs,
    "get_sale_details": SaleDetailsArgs,
    "list_payments": ListPaymentsArgs,
    "top_products": TopProductsArgs,
    "client_ranking": ClientRankingArgs,
    "global_search": GlobalSearchArgs,
    "get_my_profile": MyProfileArgs,
    "list_users": ListUsersArgs,
    "get_user_summary": UserSummaryArgs,
}

ADMIN_TOOL_NAMES = frozenset({"list_users", "get_user_summary"})
WEB_TOOL_NAMES = frozenset({"web_search", "fetch_url"})


def _parse_tool_arguments(raw_arguments: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        parsed = json.loads(raw_arguments or "{}")
    except (TypeError, ValueError) as exc:
        raise AIToolError("Argumentos da ferramenta não são JSON válido.") from exc
    if not isinstance(parsed, dict):
        raise AIToolError("Argumentos da ferramenta devem ser um objeto.")
    return parsed


def _validation_message(exc: ValidationError) -> str:
    fields: set[str] = set()
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "argumentos"
        fields.add(location)
    return "Argumentos inválidos para a ferramenta: " + ", ".join(sorted(fields)) + "."


def _cache_key(scope: ToolScope, tool_name: str, arguments: BaseModel) -> str:
    payload = json.dumps(arguments.model_dump(mode="json"), sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"ai:tool:{scope.scope_key}:{tool_name}:{digest}"


# ---------------------------------------------------------------------------
# Consultas de CRM (somente leitura, sempre com escopo)
# ---------------------------------------------------------------------------


def _scoped_sales(query, scope: ToolScope):
    return scoped(query, Sale.user_id, scope.scope_id)


def _scoped_clients(query, scope: ToolScope):
    return scoped(query, Client.created_by_id, scope.scope_id)


def _sales_summary(db: Session, scope: ToolScope, args: SalesSummaryArgs) -> dict[str, Any]:
    paid_total = func.coalesce(
        func.sum(case((Sale.status == SaleStatus.paid, Sale.total), else_=0)), 0
    )
    pending_total = func.coalesce(
        func.sum(case((Sale.status == SaleStatus.pending, Sale.remaining), else_=0)), 0
    )
    query = db.query(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.total), 0),
        paid_total,
        pending_total,
    ).filter(
        Sale.sale_date >= args.inicio,
        Sale.sale_date <= args.fim,
    )
    row = _scoped_sales(query, scope).one()
    return {
        "period": {"inicio": args.inicio.isoformat(), "fim": args.fim.isoformat()},
        "scope": scope.scope_key,
        "sales_count": int(row[0] or 0),
        "total": float(row[1] or 0),
        "paid_total": float(row[2] or 0),
        "pending_total": float(row[3] or 0),
    }


def _month_bounds(month: str | None) -> tuple[date, date]:
    """Primeiro e último dia do mês informado (padrão: mês atual)."""
    today = local_today()
    if month is None:
        year, mon = today.year, today.month
    else:
        year, mon = (int(part) for part in month.split("-"))
    first = date(year, mon, 1)
    following = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return first, following - timedelta(days=1)


def _dashboard_overview(
    db: Session, scope: ToolScope, _args: DashboardOverviewArgs
) -> dict[str, Any]:
    today = local_today()
    first_day_month = today.replace(day=1)

    total_clients = _scoped_clients(db.query(func.count(Client.id)), scope).scalar() or 0
    total_sales = _scoped_sales(db.query(func.count(Sale.id)), scope).scalar() or 0
    revenue_paid = (
        _scoped_sales(
            db.query(func.coalesce(func.sum(Sale.total), 0)).filter(
                Sale.status == SaleStatus.paid
            ),
            scope,
        ).scalar()
        or 0
    )
    revenue_pending = (
        _scoped_sales(
            db.query(func.coalesce(func.sum(Sale.remaining), 0)).filter(
                Sale.status == SaleStatus.pending
            ),
            scope,
        ).scalar()
        or 0
    )
    pending_count = (
        _scoped_sales(
            db.query(func.count(Sale.id)).filter(Sale.status == SaleStatus.pending),
            scope,
        ).scalar()
        or 0
    )
    overdue_count = (
        _scoped_sales(
            db.query(func.count(Sale.id)).filter(
                Sale.status == SaleStatus.pending,
                Sale.due_date < today,
            ),
            scope,
        ).scalar()
        or 0
    )
    revenue_month = (
        _scoped_sales(
            db.query(func.coalesce(func.sum(Sale.total), 0)).filter(
                Sale.status == SaleStatus.paid,
                Sale.sale_date >= first_day_month,
            ),
            scope,
        ).scalar()
        or 0
    )
    recent_sales = (
        _scoped_sales(db.query(Sale), scope)
        .order_by(Sale.created_at.desc(), Sale.id.desc())
        .limit(5)
        .all()
    )
    top_products = (
        _scoped_sales(
            db.query(
                SaleItem.product_name,
                func.sum(SaleItem.quantity).label("total_quantity"),
                func.sum(SaleItem.subtotal).label("total_revenue"),
            ).join(Sale, Sale.id == SaleItem.sale_id),
            scope,
        )
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(5)
        .all()
    )

    return {
        "today": today.isoformat(),
        "scope": scope.scope_key,
        "total_clients": int(total_clients),
        "total_sales": int(total_sales),
        "revenue_paid": float(revenue_paid),
        "revenue_pending": float(revenue_pending),
        "revenue_month": float(revenue_month),
        "pending_count": int(pending_count),
        "overdue_count": int(overdue_count),
        "recent_sales": [
            {
                "sale_id": sale.id,
                "client_id": sale.client_id,
                "client_name": sale.client.full_name if sale.client else None,
                "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
                "status": getattr(sale.status, "value", str(sale.status)),
                "total": float(sale.total or 0),
                "remaining": float(sale.remaining or 0),
            }
            for sale in recent_sales
        ],
        "top_products": [
            {
                "product_name": row.product_name,
                "total_quantity": int(row.total_quantity or 0),
                "total_revenue": float(row.total_revenue or 0),
            }
            for row in top_products
        ],
    }


def _cashflow(db: Session, scope: ToolScope, args: CashflowArgs) -> dict[str, Any]:
    first, last = _month_bounds(args.month)
    stats = _scoped_sales(
        db.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total), 0),
            func.coalesce(
                func.sum(case((Sale.status == SaleStatus.paid, Sale.total), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((Sale.status == SaleStatus.pending, Sale.remaining), else_=0)),
                0,
            ),
        ).filter(Sale.sale_date >= first, Sale.sale_date <= last),
        scope,
    ).one()
    received = (
        _scoped_sales(
            db.query(func.coalesce(func.sum(Payment.amount_paid), 0))
            .join(Sale, Sale.id == Payment.sale_id)
            .filter(Payment.payment_date >= first, Payment.payment_date <= last),
            scope,
        ).scalar()
        or 0
    )
    return {
        "period": {
            "month": f"{first:%Y-%m}",
            "start": first.isoformat(),
            "end": last.isoformat(),
        },
        "scope": scope.scope_key,
        "sales_count": int(stats[0] or 0),
        "sales_total": float(stats[1] or 0),
        "paid_total": float(stats[2] or 0),
        "pending_remaining": float(stats[3] or 0),
        "received_total": float(received or 0),
    }


def _overdue(db: Session, scope: ToolScope, _args: ListOverdueArgs) -> dict[str, Any]:
    today = local_today()
    filters = (
        Sale.status == SaleStatus.pending,
        Sale.due_date < today,
    )
    total_count = _scoped_sales(
        db.query(func.count(Sale.id)).filter(*filters), scope
    ).scalar() or 0
    rows = _scoped_sales(
        db.query(
            Sale.id,
            Sale.due_date,
            Sale.remaining,
            Client.full_name,
        )
        .outerjoin(Client, Client.id == Sale.client_id)
        .filter(*filters),
        scope,
    ).order_by(Sale.due_date.asc(), Sale.id.asc()).limit(MAX_OVERDUE_ROWS).all()
    return {
        "today": today.isoformat(),
        "scope": scope.scope_key,
        "total_count": int(total_count),
        "returned_count": len(rows),
        "sales": [
            {
                "sale_id": int(row[0]),
                "client_name": row[3],
                "due_date": row[1].isoformat() if row[1] else None,
                "remaining": float(row[2] or 0),
                "days_overdue": (today - row[1]).days if row[1] else None,
            }
            for row in rows
        ],
    }


def _sale_status(db: Session, scope: ToolScope, args: SaleStatusArgs) -> dict[str, Any]:
    sale = _scoped_sales(db.query(Sale), scope).filter(Sale.id == args.sale_id).first()
    if sale is None:
        return {"found": False, "sale_id": args.sale_id}
    return {
        "found": True,
        "sale_id": sale.id,
        "client_id": sale.client_id,
        "client_name": sale.client.full_name if sale.client else None,
        "status": getattr(sale.status, "value", str(sale.status)),
        "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
        "due_date": sale.due_date.isoformat() if sale.due_date else None,
        "total": float(sale.total or 0),
        "amount_paid": float(sale.amount_paid or 0),
        "remaining": float(sale.remaining or 0),
        "items_count": len(sale.items),
        "payments_count": len(sale.payments),
    }


def _search_clients(db: Session, scope: ToolScope, args: SearchClientsArgs) -> dict[str, Any]:
    query = (
        db.query(
            Client.id,
            Client.full_name,
            Client.whatsapp,
            Client.created_at,
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total), 0).label("total_revenue"),
        )
        .outerjoin(Sale, Sale.client_id == Client.id)
    )
    query = _scoped_clients(query, scope)
    if args.query and args.query.strip():
        query = query.filter(
            Client.name_normalized.contains(normalize_name(args.query), autoescape=True)
        )
    rows = (
        query.group_by(Client.id, Client.full_name, Client.whatsapp, Client.created_at)
        .order_by(Client.full_name.asc())
        .limit(args.limit)
        .all()
    )
    return {
        "scope": scope.scope_key,
        "count": len(rows),
        "clients": [
            {
                "client_id": row.id,
                "full_name": row.full_name,
                "whatsapp": row.whatsapp,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "sales_count": int(row.sales_count or 0),
                "total_revenue": float(row.total_revenue or 0),
            }
            for row in rows
        ],
    }


def _client_details(db: Session, scope: ToolScope, args: ClientDetailsArgs) -> dict[str, Any]:
    client = _scoped_clients(db.query(Client), scope).filter(Client.id == args.client_id).first()
    if client is None:
        return {"found": False, "client_id": args.client_id}

    today = local_today()
    totals = _scoped_sales(
        db.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total), 0),
            func.coalesce(func.sum(Sale.remaining), 0),
            func.coalesce(
                func.sum(case((Sale.due_date < today, 1), else_=0)), 0
            ),
            func.max(Sale.sale_date),
        ).filter(Sale.client_id == client.id),
        scope,
    ).one()
    recent = _scoped_sales(db.query(Sale), scope).filter(Sale.client_id == client.id).order_by(
        Sale.sale_date.desc(), Sale.id.desc()
    ).limit(5).all()
    return {
        "found": True,
        "client_id": client.id,
        "full_name": client.full_name,
        "whatsapp": client.whatsapp,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "sales_count": int(totals[0] or 0),
        "total_revenue": float(totals[1] or 0),
        "pending_remaining": float(totals[2] or 0),
        "overdue_count": int(totals[3] or 0),
        "last_sale_date": totals[4].isoformat() if totals[4] else None,
        "recent_sales": [
            {
                "sale_id": sale.id,
                "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
                "status": getattr(sale.status, "value", str(sale.status)),
                "total": float(sale.total or 0),
                "remaining": float(sale.remaining or 0),
                "due_date": sale.due_date.isoformat() if sale.due_date else None,
            }
            for sale in recent
        ],
    }


def _list_sales(db: Session, scope: ToolScope, args: ListSalesArgs) -> dict[str, Any]:
    query = db.query(Sale, Client.full_name).outerjoin(Client, Client.id == Sale.client_id)
    query = _scoped_sales(query, scope)
    if args.status:
        query = query.filter(Sale.status == SaleStatus(args.status))
    if args.client_id:
        query = query.filter(Sale.client_id == args.client_id)
    if args.start:
        query = query.filter(Sale.sale_date >= args.start)
    if args.end:
        query = query.filter(Sale.sale_date <= args.end)
    rows = query.order_by(Sale.sale_date.desc(), Sale.id.desc()).limit(args.limit).all()
    return {
        "scope": scope.scope_key,
        "count": len(rows),
        "sales": [
            {
                "sale_id": sale.id,
                "user_id": sale.user_id,
                "client_id": sale.client_id,
                "client_name": client_name,
                "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
                "status": getattr(sale.status, "value", str(sale.status)),
                "total": float(sale.total or 0),
                "amount_paid": float(sale.amount_paid or 0),
                "remaining": float(sale.remaining or 0),
                "due_date": sale.due_date.isoformat() if sale.due_date else None,
            }
            for sale, client_name in rows
        ],
    }


def _sale_details(db: Session, scope: ToolScope, args: SaleDetailsArgs) -> dict[str, Any]:
    sale = _scoped_sales(db.query(Sale), scope).filter(Sale.id == args.sale_id).first()
    if sale is None:
        return {"found": False, "sale_id": args.sale_id}
    return {
        "found": True,
        "sale_id": sale.id,
        "user_id": sale.user_id,
        "client_id": sale.client_id,
        "client_name": sale.client.full_name if sale.client else None,
        "client_whatsapp": sale.client.whatsapp if sale.client else None,
        "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
        "status": getattr(sale.status, "value", str(sale.status)),
        "total": float(sale.total or 0),
        "amount_paid": float(sale.amount_paid or 0),
        "remaining": float(sale.remaining or 0),
        "due_date": sale.due_date.isoformat() if sale.due_date else None,
        "items": [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price or 0),
                "subtotal": float(item.subtotal or 0),
            }
            for item in sale.items
        ],
        "payments": [
            {
                "payment_id": payment.id,
                "amount_paid": float(payment.amount_paid or 0),
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "new_due_date": payment.new_due_date.isoformat() if payment.new_due_date else None,
                "notes": payment.notes,
            }
            for payment in sale.payments
        ],
    }


def _list_payments(db: Session, scope: ToolScope, args: ListPaymentsArgs) -> dict[str, Any]:
    query = (
        db.query(Payment, Sale, Client.full_name)
        .join(Sale, Sale.id == Payment.sale_id)
        .outerjoin(Client, Client.id == Sale.client_id)
    )
    query = _scoped_sales(query, scope)
    if args.sale_id:
        query = query.filter(Payment.sale_id == args.sale_id)
    if args.start:
        query = query.filter(Payment.payment_date >= args.start)
    if args.end:
        query = query.filter(Payment.payment_date <= args.end)
    rows = query.order_by(Payment.payment_date.desc(), Payment.id.desc()).limit(args.limit).all()
    return {
        "scope": scope.scope_key,
        "count": len(rows),
        "payments": [
            {
                "payment_id": payment.id,
                "sale_id": payment.sale_id,
                "client_name": client_name,
                "amount_paid": float(payment.amount_paid or 0),
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "new_due_date": payment.new_due_date.isoformat() if payment.new_due_date else None,
                "notes": payment.notes,
            }
            for payment, _sale, client_name in rows
        ],
    }


def _top_products(db: Session, scope: ToolScope, args: TopProductsArgs) -> dict[str, Any]:
    query = (
        db.query(
            SaleItem.product_name,
            func.sum(SaleItem.quantity).label("total_quantity"),
            func.sum(SaleItem.subtotal).label("total_revenue"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
    )
    query = _scoped_sales(query, scope)
    if args.start:
        query = query.filter(Sale.sale_date >= args.start)
    if args.end:
        query = query.filter(Sale.sale_date <= args.end)
    rows = (
        query.group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(args.limit)
        .all()
    )
    return {
        "scope": scope.scope_key,
        "products": [
            {
                "product_name": row.product_name,
                "total_quantity": int(row.total_quantity or 0),
                "total_revenue": float(row.total_revenue or 0),
            }
            for row in rows
        ],
    }


def _client_ranking(db: Session, scope: ToolScope, args: ClientRankingArgs) -> dict[str, Any]:
    query = (
        db.query(
            Client.id,
            Client.full_name,
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total), 0).label("total_revenue"),
            func.max(Sale.sale_date).label("last_sale_date"),
        )
        .join(Sale, Sale.client_id == Client.id)
    )
    query = _scoped_sales(query, scope)
    if args.start:
        query = query.filter(Sale.sale_date >= args.start)
    if args.end:
        query = query.filter(Sale.sale_date <= args.end)
    rows = (
        query.group_by(Client.id, Client.full_name)
        .order_by(func.sum(Sale.total).desc())
        .limit(args.limit)
        .all()
    )
    return {
        "scope": scope.scope_key,
        "clients": [
            {
                "client_id": row.id,
                "full_name": row.full_name,
                "sales_count": int(row.sales_count or 0),
                "total_revenue": float(row.total_revenue or 0),
                "last_sale_date": row.last_sale_date.isoformat() if row.last_sale_date else None,
            }
            for row in rows
        ],
    }


def _global_search(db: Session, scope: ToolScope, args: GlobalSearchArgs) -> dict[str, Any]:
    term = args.query.strip()
    normalized = normalize_name(term)

    clients_query = (
        db.query(Client.id, Client.full_name, Client.whatsapp)
        .filter(Client.name_normalized.contains(normalized, autoescape=True))
    )
    clients = _scoped_clients(clients_query, scope).order_by(Client.full_name.asc()).limit(args.limit).all()

    products_query = (
        db.query(SaleItem.product_name, func.sum(SaleItem.quantity).label("qty"))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(func.lower(SaleItem.product_name).contains(term.lower(), autoescape=True))
    )
    products = (
        _scoped_sales(products_query, scope)
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(args.limit)
        .all()
    )

    sales_query = db.query(Sale, Client.full_name).outerjoin(Client, Client.id == Sale.client_id)
    if term.isdigit():
        sales_query = sales_query.filter(Sale.id == int(term))
    else:
        sales_query = sales_query.join(SaleItem, SaleItem.sale_id == Sale.id).filter(
            func.lower(SaleItem.product_name).contains(term.lower(), autoescape=True)
        )
    sales = _scoped_sales(sales_query, scope).order_by(Sale.sale_date.desc(), Sale.id.desc()).limit(args.limit).all()

    return {
        "query": term,
        "scope": scope.scope_key,
        "clients": [
            {"client_id": row.id, "full_name": row.full_name, "whatsapp": row.whatsapp}
            for row in clients
        ],
        "products": [
            {"product_name": row.product_name, "total_quantity": int(row.qty or 0)}
            for row in products
        ],
        "sales": [
            {
                "sale_id": sale.id,
                "client_name": client_name,
                "sale_date": sale.sale_date.isoformat() if sale.sale_date else None,
                "status": getattr(sale.status, "value", str(sale.status)),
                "total": float(sale.total or 0),
                "remaining": float(sale.remaining or 0),
            }
            for sale, client_name in sales
        ],
    }


def _my_profile(db: Session, scope: ToolScope, _args: MyProfileArgs) -> dict[str, Any]:
    user = db.get(User, scope.user_id)
    if user is None:
        return {"found": False, "user_id": scope.user_id}
    clients_count = db.query(func.count(Client.id)).filter(Client.created_by_id == user.id).scalar() or 0
    sales_count = db.query(func.count(Sale.id)).filter(Sale.user_id == user.id).scalar() or 0
    revenue = db.query(func.coalesce(func.sum(Sale.total), 0)).filter(Sale.user_id == user.id).scalar() or 0
    return {
        "found": True,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": getattr(user.role, "value", str(user.role)),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "clients_count": int(clients_count),
        "sales_count": int(sales_count),
        "sales_total": float(revenue),
        "active_scope": scope.scope_key,
    }


def _list_users(db: Session, scope: ToolScope, _args: ListUsersArgs) -> dict[str, Any]:
    if not scope.is_admin:
        raise AIToolError("Ferramenta não permitida.")

    clients_sub = (
        db.query(Client.created_by_id.label("user_id"), func.count(Client.id).label("clients_count"))
        .group_by(Client.created_by_id)
        .subquery()
    )
    sales_sub = (
        db.query(
            Sale.user_id.label("user_id"),
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total), 0).label("sales_total"),
        )
        .group_by(Sale.user_id)
        .subquery()
    )
    rows = (
        db.query(
            User,
            func.coalesce(clients_sub.c.clients_count, 0),
            func.coalesce(sales_sub.c.sales_count, 0),
            func.coalesce(sales_sub.c.sales_total, 0),
        )
        .outerjoin(clients_sub, clients_sub.c.user_id == User.id)
        .outerjoin(sales_sub, sales_sub.c.user_id == User.id)
        .order_by(User.id.asc())
        .all()
    )
    return {
        "count": len(rows),
        "users": [
            {
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "role": getattr(user.role, "value", str(user.role)),
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "clients_count": int(clients_count or 0),
                "sales_count": int(sales_count or 0),
                "sales_total": float(sales_total or 0),
            }
            for user, clients_count, sales_count, sales_total in rows
        ],
    }


def _user_summary(db: Session, scope: ToolScope, args: UserSummaryArgs) -> dict[str, Any]:
    if not scope.is_admin:
        raise AIToolError("Ferramenta não permitida.")
    user = db.get(User, args.user_id)
    if user is None:
        return {"found": False, "user_id": args.user_id}

    start, end = _resolve_period(args.start, args.end)
    paid_total = func.coalesce(
        func.sum(case((Sale.status == SaleStatus.paid, Sale.total), else_=0)), 0
    )
    pending_total = func.coalesce(
        func.sum(case((Sale.status == SaleStatus.pending, Sale.remaining), else_=0)), 0
    )
    row = (
        db.query(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total), 0),
            paid_total,
            pending_total,
        )
        .filter(
            Sale.user_id == user.id,
            Sale.sale_date >= start,
            Sale.sale_date <= end,
        )
        .one()
    )
    return {
        "found": True,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": getattr(user.role, "value", str(user.role)),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "sales_count": int(row[0] or 0),
        "total": float(row[1] or 0),
        "paid_total": float(row[2] or 0),
        "pending_total": float(row[3] or 0),
    }


_DB_HANDLERS: dict[str, Callable[[Session, ToolScope, Any], dict[str, Any]]] = {
    "get_sales_summary": _sales_summary,
    "get_dashboard_overview": _dashboard_overview,
    "get_cashflow": _cashflow,
    "list_overdue": _overdue,
    "get_sale_status": _sale_status,
    "search_clients": _search_clients,
    "get_client_details": _client_details,
    "list_sales": _list_sales,
    "get_sale_details": _sale_details,
    "list_payments": _list_payments,
    "top_products": _top_products,
    "client_ranking": _client_ranking,
    "global_search": _global_search,
    "get_my_profile": _my_profile,
    "list_users": _list_users,
    "get_user_summary": _user_summary,
}

_TOOL_TTLS = {
    "get_sales_summary": SUMMARY_CACHE_TTL,
    "get_dashboard_overview": SUMMARY_CACHE_TTL,
    "get_cashflow": REPORT_CACHE_TTL,
    "list_overdue": OVERDUE_CACHE_TTL,
    "get_sale_status": SALE_STATUS_CACHE_TTL,
    "get_client_details": LIST_CACHE_TTL,
    "get_sale_details": LIST_CACHE_TTL,
    "list_payments": LIST_CACHE_TTL,
    "list_sales": LIST_CACHE_TTL,
    "search_clients": LIST_CACHE_TTL,
    "global_search": LIST_CACHE_TTL,
    "top_products": REPORT_CACHE_TTL,
    "client_ranking": REPORT_CACHE_TTL,
    "get_my_profile": PROFILE_CACHE_TTL,
    "list_users": ADMIN_CACHE_TTL,
    "get_user_summary": ADMIN_CACHE_TTL,
}


def execute_tool(
    db: Session,
    user_id: int,
    tool_name: str,
    raw_arguments: str | dict[str, Any],
    *,
    is_admin: bool = False,
    owner_id: int | None = None,
) -> dict[str, Any]:
    """Executa uma tool de CRM fixa, sempre no escopo resolvido.

    O escopo nunca vem dos argumentos do modelo: ``user_id`` é o dono do JWT e
    ``owner_id`` só tem efeito para administradores. Os schemas usam
    ``extra="forbid"``, então um ``user_id`` enviado pelo modelo é rejeitado.
    """
    if user_id <= 0:
        raise AIToolError("Escopo de usuário inválido.")
    if tool_name in WEB_TOOL_NAMES:
        raise AIToolError("Ferramenta de web exige execução assíncrona.")
    if tool_name in ADMIN_TOOL_NAMES and not is_admin:
        raise AIToolError("Ferramenta não permitida.")

    model_class = DB_TOOL_MODELS.get(tool_name)
    if model_class is None:
        raise AIToolError("Ferramenta não permitida.")

    parsed = _parse_tool_arguments(raw_arguments)
    try:
        model = model_class.model_validate(parsed)
    except ValidationError as exc:
        raise AIToolError(_validation_message(exc)) from exc

    scope = ToolScope(user_id=user_id, is_admin=is_admin, owner_id=owner_id)
    cache_key = _cache_key(scope, tool_name, model)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    result = _DB_HANDLERS[tool_name](db, scope, model)
    cache.set_json(cache_key, result, _TOOL_TTLS.get(tool_name, LIST_CACHE_TTL))
    return result


async def execute_tool_async(
    db: Session,
    scope: ToolScope,
    tool_name: str,
    raw_arguments: str | dict[str, Any],
) -> dict[str, Any]:
    """Despacha tools de banco (síncronas) e de web (assíncronas)."""
    if tool_name in WEB_TOOL_NAMES:
        parsed = _parse_tool_arguments(raw_arguments)
        if tool_name == "web_search":
            try:
                search_args = WebSearchArgs.model_validate(parsed)
            except ValidationError as exc:
                raise AIToolError(_validation_message(exc)) from exc
            return await web_search(search_args.query, search_args.max_results)
        try:
            fetch_args = FetchUrlArgs.model_validate(parsed)
        except ValidationError as exc:
            raise AIToolError(_validation_message(exc)) from exc
        return await fetch_url(fetch_args.url)

    return execute_tool(
        db,
        scope.user_id,
        tool_name,
        raw_arguments,
        is_admin=scope.is_admin,
        owner_id=scope.owner_id,
    )
