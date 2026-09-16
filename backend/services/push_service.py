"""Web Push — notificações de alerta de prazo de vendas (100% grátis).

Fluxo:
- O navegador (PWA) cria uma subscrição via PushManager e envia ao backend
  (``POST /push/subscribe``), que persiste em ``push_subscriptions``.
- O APScheduler (ou um endpoint de teste) envia a notificação com ``pywebpush``
  assinada com as chaves VAPID (``settings.vapid_*``).
- Endpoints expirados (HTTP 404/410) são removidos automaticamente.
"""
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from config import settings
from models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def save_subscription(
    db: Session, user_id: int, endpoint: str, p256dh: str, auth: str
) -> PushSubscription:
    """Cria ou atualiza a subscrição de um dispositivo (idempotente por endpoint)."""
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if sub:
        sub.p256dh = p256dh
        sub.auth = auth
        sub.user_id = user_id
    else:
        sub = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def remove_subscription(db: Session, endpoint: str) -> bool:
    """Remove a subscrição de um dispositivo (ex.: usuário desativou alertas)."""
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if not sub:
        return False
    db.delete(sub)
    db.commit()
    return True


def send_push_to_all(db: Session, title: str, body: str, url: str = "/#/queue") -> int:
    """Envia uma notificação para todos os dispositivos inscritos.

    Retorna quantos envios foram aceitos. Subscrições inválidas/expiradas
    (404/410) são removidas do banco.
    """
    if not settings.vapid_private_key or not settings.vapid_public_key:
        logger.warning("Web Push desativado: VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY ausentes.")
        return 0

    payload = json.dumps({"title": title, "body": body, "url": url})
    sent = 0
    for sub in db.query(PushSubscription).all():
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                # Subscrição expirada/revogada: remove para não poluir o banco.
                db.delete(sub)
                db.commit()
            logger.warning("Falha ao enviar push (endpoint %s…): %s", sub.endpoint[:40], exc)
        except Exception as exc:  # cache best-effort: nunca derruba o job
            logger.warning("Erro inesperado no push: %s", exc)
    return sent