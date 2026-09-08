from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.user import User
from schemas.client import ClientCreate, ClientResponse
from services.client_service import create_client, list_clients

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("", response_model=list[ClientResponse])
def get_clients(
    search: Optional[str] = Query(None, description="Busca por nome do cliente"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    return list_clients(db, search)


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(
    data: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    try:
        return create_client(db, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc