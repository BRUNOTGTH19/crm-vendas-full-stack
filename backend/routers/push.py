from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.user import User
from services import push_service

router = APIRouter(prefix="/push", tags=["Push"])


class PushSubscribeIn(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushTestIn(BaseModel):
    title: str = "🔔 Teste de alerta"
    body: str = "Se você está lendo isso, as notificações estão funcionando!"
    url: str = "/#/queue"


@router.get("/vapid-key")
def get_vapid_key():
    """Chave pública VAPID usada pelo navegador em `applicationServerKey`."""
    if not settings.vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web Push não configurado no servidor (VAPID_PUBLIC_KEY ausente).",
        )
    return {"public_key": settings.vapid_public_key}


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(
    data: PushSubscribeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Registra/atualiza a subscrição push deste dispositivo para o usuário logado."""
    sub = push_service.save_subscription(
        db, user_id=current_user.id, endpoint=data.endpoint, p256dh=data.p256dh, auth=data.auth
    )
    return {"id": sub.id, "endpoint": sub.endpoint}


@router.post("/unsubscribe")
def unsubscribe(
    data: PushSubscribeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Remove a subscrição push deste dispositivo."""
    removed = push_service.remove_subscription(db, endpoint=data.endpoint)
    return {"removed": removed}


@router.post("/test")
def send_test(
    data: PushTestIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Envia uma notificação de teste para todos os dispositivos inscritos."""
    sent = push_service.send_push_to_all(db, title=data.title, body=data.body, url=data.url)
    return {"sent": sent}