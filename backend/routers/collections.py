from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import resolve_data_owner
from schemas.collection import CollectionMessage, CollectionReminder
from services import collection_service
from services.sale_service import get_sale

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("/reminders", response_model=list[CollectionReminder])
def list_reminders(
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Central de cobranças: vendas vencidas ou que vencem hoje (escopo do dono)."""
    return collection_service.list_due_reminders(db, owner_id=owner_id)


@router.get("/message/{sale_id}", response_model=CollectionMessage)
def get_collection_message(
    sale_id: int,
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Mensagem de cobrança personalizada + link wa.me de uma venda do escopo."""
    sale = get_sale(db, sale_id, owner_id=owner_id)
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venda não encontrada"
        )
    return collection_service.build_collection_message(db, sale)