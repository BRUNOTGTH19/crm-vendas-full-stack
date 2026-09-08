from datetime import datetime, timedelta, timezone

import redis
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from models.user import User
from redis_client import redis_client
from schemas.user import UserCreate, TokenResponse, UserResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_TTL_SECONDS = settings.access_token_expire_minutes * 60  # 8 horas (doc 2.2 / 4.2)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode({**data, "exp": expire}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# Sessão no Redis (doc oficial 2.2 passo 5 e 4.2: session:{user_id}, TTL 8h.
# O logout invalida a chave imediatamente, revogando o token antes de expirar.)
# ---------------------------------------------------------------------------

def _session_key(user_id: int) -> str:
    return f"session:{user_id}"


def create_session(user_id: int, access_token: str, refresh_token: str = "") -> None:
    """Salva a sessão no Redis com TTL de 8 horas."""
    try:
        redis_client.hset(
            _session_key(user_id),
            mapping={"access_token": access_token, "refresh_token": refresh_token},
        )
        redis_client.expire(_session_key(user_id), SESSION_TTL_SECONDS)
    except redis.RedisError:
        # Redis indisponível: autenticação continua funcionando (fail-open).
        pass


def revoke_session(user_id: int) -> None:
    """Invalida a sessão imediatamente (logout)."""
    try:
        redis_client.delete(_session_key(user_id))
    except redis.RedisError:
        pass


def _session_field_valid(user_id: int, field: str, token: str) -> bool:
    try:
        saved = redis_client.hget(_session_key(user_id), field)
    except redis.RedisError:
        return True  # fail-open: sem Redis, confia apenas no JWT
    return bool(saved) and saved == token


def access_session_valid(user_id: int, access_token: str) -> bool:
    return _session_field_valid(user_id, "access_token", access_token)


def refresh_session_valid(user_id: int, refresh_token: str) -> bool:
    return _session_field_valid(user_id, "refresh_token", refresh_token)


def register_user(db: Session, data: UserCreate) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise ValueError("E-mail já cadastrado")

    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Credenciais inválidas")

    payload = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)
    create_session(user.id, access_token, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


def refresh_tokens(db: Session, refresh_token: str) -> dict:
    """Valida o refresh token contra a sessão no Redis e emite novos tokens."""
    try:
        payload = jwt.decode(refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise ValueError("Refresh token inválido ou expirado")

    if not refresh_session_valid(user_id, refresh_token):
        raise ValueError("Sessão revogada ou expirada. Faça login novamente.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("Usuário não encontrado")

    new_payload = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(new_payload)
    new_refresh = create_refresh_token(new_payload)
    create_session(user.id, access_token, new_refresh)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


def get_current_user(db: Session, token: str) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise ValueError("Token inválido ou expirado")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("Usuário não encontrado")

    if not access_session_valid(user_id, token):
        raise ValueError("Sessão revogada (logout). Faça login novamente.")
    return user