from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

import cache
from database import get_db
from middleware.auth_middleware import resolve_data_owner
from models.client import Client
from models.sale import Sale, SaleStatus
from models.sale_item import SaleItem

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _scoped(query, column, owner_id: int | None):
    """Restringe a consulta ao dono do escopo; ``owner_id=None`` mantém o
    escopo global (visão consolidada do administrador)."""
    if owner_id is not None:
        query = query.filter(column == owner_id)
    return query


@router.get("")
def get_dashboard(
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Métricas do painel no escopo resolvido (dono, usuário selecionado ou global).

    A chave de cache inclui o escopo (``owner:<id>`` ou ``owner:global``) para
    que as métricas de um usuário NUNCA sejam reutilizadas por outro
    (doc 4.2, cache Redis 5 min).
    """
    scope = "global" if owner_id is None else owner_id
    month_key = f"dashboard:{date.today():%Y-%m}:owner:{scope}"
    cached = cache.get_json(month_key)
    if cached is not None:
        return cached

    data = _compute_dashboard(db, owner_id)

    cache.set_json(month_key, data, cache.DASHBOARD_TTL)
    return data


def _compute_dashboard(db: Session, owner_id: int | None) -> dict:
    today = date.today()
    first_day_month = today.replace(day=1)

    total_clients = (
        _scoped(db.query(func.count(Client.id)), Client.created_by_id, owner_id)
        .scalar()
        or 0
    )
    total_sales = (
        _scoped(db.query(func.count(Sale.id)), Sale.user_id, owner_id).scalar() or 0
    )

    revenue_paid = (
        _scoped(
            db.query(func.coalesce(func.sum(Sale.total), 0)).filter(
                Sale.status == SaleStatus.paid
            ),
            Sale.user_id,
            owner_id,
        ).scalar()
    )
    revenue_pending = (
        _scoped(
            db.query(func.coalesce(func.sum(Sale.remaining), 0)).filter(
                Sale.status == SaleStatus.pending
            ),
            Sale.user_id,
            owner_id,
        ).scalar()
    )
    pending_count = (
        _scoped(
            db.query(func.count(Sale.id)).filter(Sale.status == SaleStatus.pending),
            Sale.user_id,
            owner_id,
        ).scalar()
        or 0
    )
    overdue_count = (
        _scoped(
            db.query(func.count(Sale.id)).filter(
                Sale.status == SaleStatus.pending,
                Sale.due_date < today,
            ),
            Sale.user_id,
            owner_id,
        ).scalar()
        or 0
    )
    revenue_month = (
        _scoped(
            db.query(func.coalesce(func.sum(Sale.total), 0)).filter(
                Sale.status == SaleStatus.paid,
                Sale.sale_date >= first_day_month,
            ),
            Sale.user_id,
            owner_id,
        ).scalar()
    )

    recent_sales = (
        _scoped(db.query(Sale), Sale.user_id, owner_id)
        .order_by(Sale.created_at.desc(), Sale.id.desc())
        .limit(5)
        .all()
    )
    top_products = (
        _scoped(
            db.query(
                SaleItem.product_name,
                func.sum(SaleItem.quantity).label("total_quantity"),
                func.sum(SaleItem.subtotal).label("total_revenue"),
            ).join(Sale, Sale.id == SaleItem.sale_id),
            Sale.user_id,
            owner_id,
        )
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(5)
        .all()
    )

    return {
        "total_clients": total_clients,
        "total_sales": total_sales,
        "revenue_paid": float(revenue_paid),
        "revenue_pending": float(revenue_pending),
        "revenue_month": float(revenue_month),
        "pending_count": pending_count,
        "overdue_count": overdue_count,
        "recent_sales": [
            {
                "id": s.id,
                "client_id": s.client_id,
                "client_name": s.client.full_name,
                "sale_date": s.sale_date.isoformat(),
                "status": s.status.value,
                "total": float(s.total),
            }
            for s in recent_sales
        ],
        "top_products": [
            {
                "product_name": p.product_name,
                "total_quantity": int(p.total_quantity),
                "total_revenue": float(p.total_revenue),
            }
            for p in top_products
        ],
    }