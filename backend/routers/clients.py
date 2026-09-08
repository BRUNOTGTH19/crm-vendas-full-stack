from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.user import User
from schemas.client import ClientCreate, ClientResponse, ClientUpdate
from services.client_service import create_client, list_clients, get_client, update_client, delete_client

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


@router.get("/{client_id}", response_model=ClientResponse)
def get_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    client = get_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
        )
    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client_endpoint(
    client_id: int,
    data: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    client = get_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
        )
    try:
        return update_client(db, client, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    client = get_client(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
        )
    try:
        delete_client(db, client)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc