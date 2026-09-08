from typing import Optional

import cache
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.sale import SaleStatus
from models.user import User
from schemas.sale import SaleCreate, SaleResponse
from services.sale_service import create_sale, list_sales, mark_sale_paid, get_sale

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale_endpoint(
    data: SaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    try:
        return create_sale(db, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("", response_model=list[SaleResponse])
def get_sales(
    client_id: Optional[int] = Query(None, description="Filtra por cliente"),
    status_filter: Optional[SaleStatus] = Query(None, alias="status", description="paid ou pending"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    return list_sales(db, client_id=client_id, status_filter=status_filter)


@router.get("/client/{client_id}", response_model=list[SaleResponse])
def get_client_sales(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Histórico de vendas do cliente (cache Redis de 2 min, doc 4.2)."""
    cache_key = f"sales:client:{client_id}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return JSONResponse(content=cached)

    sales = list_sales(db, client_id=client_id)
    data = jsonable_encoder(
        [SaleResponse.model_validate(s) for s in sales]
    )
    cache.set_json(cache_key, data, cache.CLIENT_SALES_TTL)
    return data


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale_endpoint(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    sale = get_sale(db, sale_id)
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venda não encontrada"
        )
    return sale


@router.patch("/{sale_id}/pay", response_model=SaleResponse)
def pay_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    try:
        return mark_sale_paid(db, sale_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc