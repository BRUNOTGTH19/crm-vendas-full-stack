import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from middleware.client_ip import client_ip
from middleware.rate_limit import (
    is_admin_activation_blocked,
    record_admin_activation_failure,
)
from models.audit_log import AuditLog
from schemas.user import (
    AdminActivationRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from services.auth_service import (
    activate_admin,
    confirm_password_reset,
    create_session,
    get_current_user,
    login_user,
    refresh_tokens,
    register_user,
    reset_password,
    revoke_session,
)

INVALID_RESET_TOKEN_MESSAGE = "Token inválido ou expirado."
LEGACY_RESET_DISABLED_MESSAGE = (
    "A redefinição por e-mail está desativada. Peça um token ao administrador."
)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)):
    try:
        user = register_user(db, data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(
    data: UserLogin,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    try:
        result = login_user(db, data.email, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user = result["user"]
    # Sessão no Redis é informativa (nada a lê para autenticar). Gravar em
    # background tira o round-trip do Upstash do caminho crítico do login.
    background_tasks.add_task(
        create_session, user.id, result["access_token"], result["refresh_token"]
    )
    logger.info(
        "login_ok user_id=%s duration_ms=%.1f",
        user.id,
        (time.perf_counter() - started) * 1000,
    )
    return result


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password_endpoint(data: PasswordResetRequest, db: Session = Depends(get_db)):
    """Redefinição simples de senha (legado) — desativada por padrão.

    Basta o e-mail cadastrado + a nova senha, então qualquer pessoa que saiba o
    e-mail pode trocar a senha (A1 da auditoria). O fluxo seguro por token
    (``/auth/reset-password/confirm``) é o recomendado. Para reativar em um
    ambiente controlado, defina ``ALLOW_LEGACY_PASSWORD_RESET=true``.
    """
    if not settings.allow_legacy_password_reset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=LEGACY_RESET_DISABLED_MESSAGE,
        )
    try:
        reset_password(db, data.email, data.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset_endpoint(
    data: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
):
    """Confirma a troca com o token de uso único gerado pelo administrador.

    Resposta genérica para token inexistente, usado ou expirado — não revela
    usuário, e-mail ou validade. O rate limit por IP é o mesmo do endpoint
    anterior (ver middleware em ``main.py``).
    """
    try:
        confirm_password_reset(db, data.token, data.new_password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_TOKEN_MESSAGE,
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Revoga a sessão no Redis, invalidando o token antes de expirar (doc 2.2)."""
    try:
        user = get_current_user(db, credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    revoke_session(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    data: RefreshRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        result = refresh_tokens(db, data.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    user_id = int(result["user_id"])
    background_tasks.add_task(
        create_session, user_id, result["access_token"], result["refresh_token"]
    )
    return result


@router.get("/me", response_model=UserResponse)
def me(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    try:
        user = get_current_user(db, credentials.credentials)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/activate-admin", response_model=UserResponse)
def activate_admin_endpoint(
    data: AdminActivationRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Torna o próprio usuário logado administrador mediante código secreto.

    O código vem de ``ADMIN_SETUP_CODE`` ou é gerado pelo backend e mostrado
    **apenas no log do servidor** na primeira vez que o app é aberto sem admin.
    """
    ip = client_ip(request)
    if is_admin_activation_blocked(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Aguarde alguns minutos e tente novamente.",
        )
    try:
        user = get_current_user(db, credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    try:
        return activate_admin(db, user, data.code)
    except ValueError as e:
        record_admin_activation_failure(ip)
        # A16: tentativas falhas passam a deixar trilha (sem registrar o código).
        if "já é administrador" not in str(e):
            db.add(
                AuditLog(
                    user_id=user.id,
                    action="admin_activation_failed",
                    detail="invalid_code",
                )
            )
            db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
