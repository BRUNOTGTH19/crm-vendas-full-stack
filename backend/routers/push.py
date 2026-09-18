from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.user import User
from services import push_service
from services.vapid_service import get_vapid_keys

router = APIRouter(prefix="/push", tags=["Push"])


class PushEndpointIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=500)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        if HttpUrl(value).scheme != "https":
            raise ValueError("O endpoint push deve usar HTTPS.")
        return value


class PushSubscribeIn(PushEndpointIn):
    p256dh: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_\-]+=*$")
    auth: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_\-]+=*$")


class PushTestIn(BaseModel):
    title: str = "🔔 Teste de alerta"
    body: str = "Se você está lendo isso, as notificações estão funcionando!"
    url: str = "/#/queue"


@router.get("/vapid-key")
def get_vapid_key(db: Session = Depends(get_db)):
    """Chave pública VAPID usada pelo navegador em `applicationServerKey`.

    As chaves vêm das variáveis de ambiente ou, se ausentes, são geradas
    automaticamente e persistidas no banco (ver ``services.vapid_service``).
    """
    try:
        public_key, _ = get_vapid_keys(db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Web Push indisponível: não foi possível obter as chaves VAPID ({exc}).",
        ) from exc
    return {"public_key": public_key}


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


@router.post("/status")
def subscription_status(
    data: PushEndpointIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    from models.push_subscription import PushSubscription

    exists = db.query(PushSubscription.id).filter(
        PushSubscription.endpoint == data.endpoint,
        PushSubscription.user_id == current_user.id,
    ).first()
    return {"subscribed": exists is not None}


@router.post("/unsubscribe")
def unsubscribe(
    data: PushEndpointIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Remove a subscrição push deste dispositivo."""
    removed = push_service.remove_subscription(db, endpoint=data.endpoint, user_id=current_user.id)
    return {"removed": removed}


@router.post("/test")
def send_test(
    data: PushTestIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Envia notificação de teste somente para os dispositivos do usuário logado."""
    run_id = uuid4().hex
    sent = push_service.send_push_to_all(
        db, title=data.title, body=data.body, url=data.url,
        user_id=current_user.id, run_id=run_id,
    )
    # "sent" = aceito pelo provedor; exibição no aparelho exige confirmação visual.
    return {"sent": sent, "run_id": run_id}