"""Endpoints do assistente de IA.

O token JWT é obrigatório em ambas as rotas. O ``user_id`` usado nas consultas
vem exclusivamente de ``current_user.id``; nenhum argumento do modelo é aceito
como escopo de dados.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.user import User
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


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    data: ChatRequest,
    db: Session = Depends(get_db),  # noqa: B008 - padrão do projeto (FastAPI)
    current_user: User = Depends(get_current_user_dependency),  # noqa: B008
):
    """Consulta dados via tools fixas, sempre no escopo do usuário do JWT."""
    try:
        reply = await ai_service.generate_chat_reply(db, current_user.id, data.message)
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
    except ai_service.AIProviderError:
        logger.warning("ai_provider_error user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=PROVIDER_ERROR_MESSAGE,
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
    except ai_service.AIProviderError:
        logger.warning("ai_provider_error user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=PROVIDER_ERROR_MESSAGE,
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return StatusMessageResponse(message=message)
