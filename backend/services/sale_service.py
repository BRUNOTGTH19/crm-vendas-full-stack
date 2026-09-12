from decimal import Decimal

import cache
from sqlalchemy.orm import Session

from models.client import Client
from models.sale import Sale, SaleStatus
from models.sale_item import SaleItem
from schemas.sale import SaleCreate


def create_sale(db: Session, data: SaleCreate, user_id: int) -> Sale:
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise ValueError("Cliente não encontrado")

    total = Decimal("0.00")
    items = []
    for item_data in data.items:
        subtotal = (item_data.unit_price * item_data.quantity).quantize(Decimal("0.01"))
        total += subtotal
        items.append(
            SaleItem(
                product_name=item_data.product_name,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                subtotal=subtotal,
            )
        )

    sale = Sale(
        client_id=data.client_id,
        user_id=user_id,
        sale_date=data.sale_date,
        status=data.status,
        total=total,
        remaining=total,
        due_date=data.due_date,
        items=items,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)

    # Invalida caches (doc oficial 2.3 passo 5)
    cache.invalidate_dashboard_cache()
    cache.invalidate_client_sales_cache(data.client_id)
    return sale


def get_sale(db: Session, sale_id: int) -> Sale | None:
    return db.query(Sale).filter(Sale.id == sale_id).first()


def list_sales(
    db: Session,
    client_id: int | None = None,
    status_filter: SaleStatus | None = None,
) -> list[Sale]:
    query = db.query(Sale)
    if client_id:
        query = query.filter(Sale.client_id == client_id)
    if status_filter:
        query = query.filter(Sale.status == status_filter)
    return query.order_by(Sale.sale_date.desc(), Sale.id.desc()).all()


def mark_sale_paid(db: Session, sale_id: int) -> Sale:
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise ValueError("Venda não encontrada")
    sale.status = SaleStatus.paid
    sale.amount_paid = sale.total
    sale.remaining = Decimal("0.00")
    sale.due_date = None
    db.commit()
    db.refresh(sale)

    # Invalida caches (doc oficial 2.3 passo 5)
    cache.invalidate_dashboard_cache()
    cache.invalidate_client_sales_cache(sale.client_id)
    return sale