from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import resolve_data_owner
from schemas.payment import PaymentCreate, PaymentResponse
from services.payment_service import get_payments_by_sale, register_payment

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Registra um pagamento (parcial ou total) de uma venda pendente do escopo."""
    try:
        return register_payment(db, data.sale_id, data, owner_id=owner_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{sale_id}", response_model=list[PaymentResponse])
def list_payments(
    sale_id: int,
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Lista os pagamentos de uma venda do escopo (vazia se fora do escopo)."""
    return get_payments_by_sale(db, sale_id, owner_id=owner_id)