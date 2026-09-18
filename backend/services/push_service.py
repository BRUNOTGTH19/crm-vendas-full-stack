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
from services.vapid_service import get_vapid_keys

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


def remove_subscription(db: Session, endpoint: str, user_id: int) -> bool:
    """Remove somente uma subscrição pertencente ao usuário autenticado."""
    sub = db.query(PushSubscription).filter(
        PushSubscription.endpoint == endpoint, PushSubscription.user_id == user_id
    ).first()
    if not sub:
        return False
    db.delete(sub)
    db.commit()
    return True


def send_push_to_all(
    db: Session, title: str, body: str, url: str = "/#/queue", *,
    user_id: int | None = None, run_id: str = "direct",
) -> int:
    """Envia aos inscritos, opcionalmente apenas aos dispositivos de user_id.

    Retorna envios ACEITOS pelo provedor, não confirma exibição no celular.
    Subscrições expiradas (404/410) são removidas; outras falhas são preservadas.
    """
    # Resolve as chaves VAPID (env → banco → geração automática persistida).
    try:
        _, vapid_private_key = get_vapid_keys(db)
    except Exception as exc:  # nunca derruba o job por falha de configuração
        logger.warning("push_config_failed run_id=%s error_type=%s", run_id, type(exc).__name__)
        return 0

    payload = json.dumps({
        "title": title, "body": body, "url": url,
        "icon": "/icons/icon-192.png", "tag": "crm-alerta",
        "data": {"run_id": run_id},
    })
    query = db.query(PushSubscription)
    if user_id is not None:
        query = query.filter(PushSubscription.user_id == user_id)
    subscriptions = query.all()
    logger.info("push_targets run_id=%s user_id=%s subscriptions=%d", run_id, user_id, len(subscriptions))
    sent = 0
    for sub in subscriptions:
        sub_id, owner_id = sub.id, sub.user_id
        logger.info("push_attempt run_id=%s user_id=%s subscription_id=%s", run_id, owner_id, sub_id)
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                timeout=10,
                ttl=3600,
            )
            sent += 1
            logger.info("push_accepted run_id=%s user_id=%s subscription_id=%s", run_id, owner_id, sub_id)
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "push_failed run_id=%s user_id=%s subscription_id=%s status=%s error_type=%s",
                run_id, owner_id, sub_id, status, type(exc).__name__,
            )
            if status in (404, 410):
                try:
                    db.delete(sub)
                    db.commit()
                    logger.info("push_subscription_removed run_id=%s subscription_id=%s", run_id, sub_id)
                except Exception as cleanup_exc:
                    db.rollback()
                    logger.warning("push_cleanup_failed run_id=%s subscription_id=%s error_type=%s",
                                   run_id, sub_id, type(cleanup_exc).__name__)
        except Exception as exc:
            # Não registrar endpoint, chaves ou texto da exceção (podem conter segredos).
            logger.warning("push_failed run_id=%s user_id=%s subscription_id=%s error_type=%s",
                           run_id, owner_id, sub_id, type(exc).__name__)
    logger.info("push_finished run_id=%s user_id=%s accepted=%d failed=%d",
                run_id, user_id, sent, len(subscriptions) - sent)
    return sent