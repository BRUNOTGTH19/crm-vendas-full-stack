"""Endpoints do assistente de IA.

O token JWT é obrigatório em ambas as rotas. O escopo dos dados vem de
``resolve_data_owner`` (usuário comum = próprio id; admin = global ou usuário
selecionado via ``X-View-User``); nenhum argumento do modelo é aceito como
escopo de dados. Cada usuário tem uma cota de mensagens por hora
(``AI_MAX_MESSAGES_PER_HOUR``), porque cada chamada pode acionar o provedor
externo várias vezes.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from middleware.auth_middleware import (
    get_current_user_dependency,
    resolve_data_owner,
)
from middleware.rate_limit import is_ai_blocked, record_ai_message
from models.user import User, UserRole
from schemas.ai import (
    ChatRequest,
    ChatResponse,
    StatusMessageRequest,
    StatusMessageResponse,
)
from services import ai_service

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger(__name__)

UNAVAILABLE_MESSAGE = "Assistente de IA indisponível no momento."
RATE_LIMIT_MESSAGE = (
    "O limite temporário do provedor de IA foi atingido. "
    "Tente novamente em alguns minutos."
)
PROVIDER_ERROR_MESSAGE = (
    "Não foi possível consultar a IA agora. Tente novamente em instantes."
)
AI_DISABLED_MESSAGE = "O assistente de IA está desativado neste ambiente."
AI_QUOTA_MESSAGE = (
    "Limite de mensagens do assistente atingido. Tente novamente mais tarde."
)


def _enforce_ai_quota(user: User) -> None:
    """Cota por usuário (A3): protege a fatura do provedor de IA.

    O contador é em memória (mesma limitação dos outros rate limits) e conta
    a tentativa antes da chamada — erros do provedor também consomem cota.
    """
    if settings.ai_max_messages_per_hour <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_DISABLED_MESSAGE,
        )
    key = f"ai:{user.id}"
    if is_ai_blocked(key):
        logger.warning("ai_quota_exceeded user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=AI_QUOTA_MESSAGE,
        )
    record_ai_message(key)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    data: ChatRequest,
    db: Session = Depends(get_db),  # noqa: B008 - padrão do projeto (FastAPI)
    current_user: User = Depends(get_current_user_dependency),  # noqa: B008
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Consulta dados via tools fixas no escopo resolvido para o usuário."""
    _enforce_ai_quota(current_user)
    is_admin = bool(current_user.role == UserRole.admin)
    try:
        reply = await ai_service.generate_chat_reply(
            db,
            current_user.id,
            data.message,
            history=data.history,
            is_admin=is_admin,
            owner_id=owner_id,
        )
    except ai_service.AIConfigurationError:
        # Mensagem genérica: não revela qual variável falta nem seu conteúdo.
        logger.error("ai_not_configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=UNAVAILABLE_MESSAGE,
        ) from None
    except ai_service.AIProviderRateLimitError:
        logger.warning("ai_rate_limited user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_MESSAGE,
        ) from None
    except ai_service.AIProviderError as exc:
        logger.warning("ai_provider_error user_id=%s reason=%s", current_user.id, exc)
        # Detalhe só para admin: ajuda a diagnosticar configuração do provedor
        # sem expor nada a usuários comuns. O texto vem de _provider_error_detail
        # e contém apenas status HTTP + código/tipo do erro.
        detail = PROVIDER_ERROR_MESSAGE
        if current_user.role == "admin":
            detail = f"{PROVIDER_ERROR_MESSAGE} [{exc}]"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return ChatResponse(reply=reply)


@router.post("/status-message", response_model=StatusMessageResponse)
async def status_message_endpoint(
    data: StatusMessageRequest,
    current_user: User = Depends(get_current_user_dependency),  # noqa: B008
):
    """Gera um texto curto para o usuário revisar/copiar. Não grava nem envia."""
    _enforce_ai_quota(current_user)
    try:
        message = await ai_service.generate_status_message(
            current_user.id,
            motivo=data.motivo,
            cliente=data.cliente,
            pedido=data.pedido,
        )
    except ai_service.AIConfigurationError:
        logger.error("ai_not_configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=UNAVAILABLE_MESSAGE,
        ) from None
    except ai_service.AIProviderRateLimitError:
        logger.warning("ai_rate_limited user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_MESSAGE,
        ) from None
    except ai_service.AIProviderError as exc:
        logger.warning("ai_provider_error user_id=%s reason=%s", current_user.id, exc)
        # Detalhe só para admin: ajuda a diagnosticar configuração do provedor
        # sem expor nada a usuários comuns. O texto vem de _provider_error_detail
        # e contém apenas status HTTP + código/tipo do erro.
        detail = PROVIDER_ERROR_MESSAGE
        if current_user.role == "admin":
            detail = f"{PROVIDER_ERROR_MESSAGE} [{exc}]"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return StatusMessageResponse(message=message)
