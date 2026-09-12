from decimal import Decimal

import cache
from sqlalchemy.orm import Session

from models.payment import Payment
from models.sale import Sale, SaleStatus
from schemas.payment import PaymentCreate


def _quant(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def register_payment(db: Session, sale_id: int, data: PaymentCreate) -> Payment:
    """Registra um pagamento (parcial ou total) em uma venda pendente.

    Validações feitas sempre no backend:
    - venda deve existir e não pode estar totalmente paga;
    - valor pago deve ser positivo e não exceder o saldo devedor.
    """
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise ValueError("Venda não encontrada")

    if sale.status == SaleStatus.paid:
        raise ValueError("Esta venda já está totalmente paga")

    remaining = _quant(Decimal(sale.total) - Decimal(sale.amount_paid or 0))

    if data.amount_paid <= 0:
        raise ValueError("O valor do pagamento deve ser maior que zero")

    if data.amount_paid > remaining:
        raise ValueError("O valor do pagamento não pode ser maior que o saldo devedor")

    payment = Payment(
        sale_id=sale.id,
        amount_paid=data.amount_paid,
        payment_date=data.payment_date,
        new_due_date=data.new_due_date,
        notes=data.notes,
    )
    db.add(payment)

    sale.amount_paid = _quant(Decimal(sale.amount_paid or 0) + data.amount_paid)
    sale.remaining = _quant(Decimal(sale.total) - sale.amount_paid)

    if sale.remaining <= 0:
        sale.remaining = Decimal("0.00")
        sale.status = SaleStatus.paid
        sale.due_date = None
    elif data.new_due_date is not None:
        # Mantém pendente e agenda nova data de cobrança para o saldo restante.
        sale.status = SaleStatus.pending
        sale.due_date = data.new_due_date

    db.commit()
    db.refresh(payment)

    # Invalida caches de dashboard e do histórico do cliente.
    cache.invalidate_dashboard_cache()
    if sale.client_id:
        cache.invalidate_client_sales_cache(sale.client_id)

    return payment


def get_payments_by_sale(db: Session, sale_id: int) -> list[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.sale_id == sale_id)
        .order_by(Payment.payment_date, Payment.id)
        .all()
    )
