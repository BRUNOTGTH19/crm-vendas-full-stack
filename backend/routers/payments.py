from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.user import User
from schemas.payment import PaymentCreate, PaymentResponse
from services.payment_service import get_payments_by_sale, register_payment

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Registra um pagamento (parcial ou total) de uma venda pendente."""
    try:
        return register_payment(db, data.sale_id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/{sale_id}", response_model=list[PaymentResponse])
def list_payments(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Lista todos os pagamentos registrados para uma venda."""
    return get_payments_by_sale(db, sale_id)
