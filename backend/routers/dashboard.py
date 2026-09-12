from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

import cache
from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.client import Client
from models.sale import Sale, SaleStatus
from models.user import User
from models.sale_item import SaleItem

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Métricas gerais para a tela inicial do CRM (cache Redis de 5 min, doc 4.2)."""
    month_key = f"dashboard:{date.today():%Y-%m}"
    cached = cache.get_json(month_key)
    if cached is not None:
        return cached

    data = _compute_dashboard(db)

    cache.set_json(month_key, data, cache.DASHBOARD_TTL)
    return data


def _compute_dashboard(db: Session) -> dict:
    today = date.today()
    first_day_month = today.replace(day=1)

    total_clients = db.query(func.count(Client.id)).scalar() or 0
    total_sales = db.query(func.count(Sale.id)).scalar() or 0

    revenue_paid = (
        db.query(func.coalesce(func.sum(Sale.total), 0))
        .filter(Sale.status == SaleStatus.paid)
        .scalar()
    )
    revenue_pending = (
        db.query(func.coalesce(func.sum(Sale.remaining), 0))
        .filter(Sale.status == SaleStatus.pending)
        .scalar()
    )
    pending_count = (
        db.query(func.count(Sale.id)).filter(Sale.status == SaleStatus.pending).scalar() or 0
    )
    overdue_count = (
        db.query(func.count(Sale.id))
        .filter(
            Sale.status == SaleStatus.pending,
            Sale.due_date < today,
        )
        .scalar() or 0
    )
    revenue_month = (
        db.query(func.coalesce(func.sum(Sale.total), 0))
        .filter(
            Sale.status == SaleStatus.paid,
            Sale.sale_date >= first_day_month,
        )
        .scalar()
    )

    recent_sales = (
        db.query(Sale).order_by(Sale.created_at.desc(), Sale.id.desc()).limit(5).all()
    )
    top_products = (
        db.query(
            SaleItem.product_name,
            func.sum(SaleItem.quantity).label("total_quantity"),
            func.sum(SaleItem.subtotal).label("total_revenue"),
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

