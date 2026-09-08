from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.client import Client
from models.sale import Sale, SaleStatus
from models.user import User
from models.sale_item import SaleItem

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/sales")
def sales_report(
    start: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end: date = Query(..., description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Resumo de vendas no período."""
    sales = (
        db.query(Sale)
        .filter(Sale.sale_date >= start, Sale.sale_date <= end)
        .order_by(Sale.sale_date, Sale.id)
        .all()
    )
    total = sum(s.total for s in sales)
    paid_total = sum(s.total for s in sales if s.status == SaleStatus.paid)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "sales_count": len(sales),
        "total": float(total),
        "paid_total": float(paid_total),
        "pending_total": float(total - paid_total),
        "sales": [
            {
                "id": s.id,
                "client_id": s.client_id,
                "client_name": s.client.full_name,
                "sale_date": s.sale_date.isoformat(),
                "status": s.status.value,
                "total": float(s.total),
            }
            for s in sales
        ],
    }


@router.get("/clients")
def clients_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Total de vendas e faturamento por cliente."""
    rows = (
        db.query(
            Client.id,
            Client.full_name,
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total), 0).label("total_revenue"),
        )
        .outerjoin(Sale, Sale.client_id == Client.id)
        .group_by(Client.id, Client.full_name)
        .order_by(func.sum(Sale.total).desc())
        .all()
    )
    return [
        {
            "client_id": r.id,
            "client_name": r.full_name,
            "sales_count": r.sales_count,
            "total_revenue": float(r.total_revenue),
        }
        for r in rows
    ]


@router.get("/products")
def products_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Produtos mais vendidos."""
    rows = (
        db.query(
            SaleItem.product_name,
            func.sum(SaleItem.quantity).label("total_quantity"),
            func.sum(SaleItem.subtotal).label("total_revenue"),
        )
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .all()
    )
    return [
        {
            "product_name": r.product_name,
            "total_quantity": int(r.total_quantity),
            "total_revenue": float(r.total_revenue),
        }
        for r in rows
    ]

