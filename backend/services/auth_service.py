import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from models.app_setting import AppSetting
from models.audit_log import AuditLog
from models.password_reset_token import PasswordResetToken
from models.user import User, UserRole
from redis_client import redis_client
from schemas.user import UserCreate

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)

SESSION_TTL_SECONDS = settings.access_token_expire_minutes * 60  # 8 horas (doc 2.2 / 4.2)
RESET_TOKEN_TTL_MINUTES = 15


def _utcnow() -> datetime:
    """Relógio único (mockável nos testes de expiração)."""
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normaliza datas lidas do SQLite (que pode devolver datetime sem tz)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_version(payload: dict) -> int:
    """Extrai o claim ``tv``; tokens antigos/sem claim são rejeitados."""
    value = payload.get("tv")
    if type(value) is not int or value < 0:
        raise ValueError("Sessão inválida. Faça login novamente.")
    return value


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _codes_match(expected: str, provided: str) -> bool:
    """Compara códigos em tempo constante e sem ``TypeError`` com não-ASCII.

    ``secrets.compare_digest`` só aceita ``str`` composto de ASCII; um acento
    no código configurado (ou colado pelo usuário) derrubava a ativação com
    500. Comparar os bytes resolve (A9 da auditoria).
    """
    return secrets.compare_digest(expected.encode("utf-8"), provided.encode("utf-8"))


def create_access_token(data: dict, token_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {**data, "tv": token_version, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(data: dict, token_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode(
        {**data, "tv": token_version, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


# ---------------------------------------------------------------------------
# Sessão no Redis (best-effort, apenas informativo/auditoria).
# A AUTENTICAÇÃO É 100% JWT: a validação NÃO consulta mais o Redis.
# O Upstash free tier (evição de chaves, conexões intermitentes) causava
# falsos "Sessão revogada" — o JWT assinado e com expiração é suficiente.
# ---------------------------------------------------------------------------

def _session_key(user_id: int) -> str:
    return f"session:{user_id}"


def create_session(user_id: int, access_token: str, refresh_token: str = "") -> None:
    """Salva a sessão no Redis (best-effort, TTL 8h). Não afeta a autenticação."""
    try:
        redis_client.hset(
            _session_key(user_id),
            mapping={"access_token": access_token, "refresh_token": refresh_token},
        )
        redis_client.expire(_session_key(user_id), SESSION_TTL_SECONDS)
    except Exception:
        # Redis indisponível: login continua funcionando normalmente.
        pass


def revoke_session(user_id: int) -> None:
    """Marca a sessão como revogada no Redis (best-effort, apenas informativo)."""
    try:
        redis_client.hset(_session_key(user_id), "revoked", "1")
        redis_client.expire(_session_key(user_id), SESSION_TTL_SECONDS)
    except Exception:
        pass


def delete_session(user_id: int) -> None:
    """Remove a sessão informativa do Redis na troca de senha (best-effort)."""
    try:
        redis_client.delete(_session_key(user_id))
    except Exception:
        # A invalidação real é o token_version no banco; Redis é complementar.
        pass


def _promote_bootstrap_admin(db: Session, user: User) -> bool:
    """Promove a admin o e-mail configurado em ``ADMIN_EMAIL``.

    O cadastro público cria sempre ``user``. Este bootstrap libera a área
    administrativa sem SQL manual: é idempotente, não cria conta e só age
    quando a variável está definida. O e-mail precisa já estar cadastrado.
    """
    admin_email = (settings.admin_email or "").strip().lower()
    if not admin_email or user.role == UserRole.admin:
        return False
    if (user.email or "").strip().lower() != admin_email:
        return False
    # A11: o bootstrap por e-mail só vale para o PRIMEIRO administrador. Antes,
    # quem registrasse o e-mail de ADMIN_EMAIL virava admin no login a qualquer
    # momento — inclusive depois da configuração inicial, sem prova de posse do
    # e-mail. A recuperação passa a ser explícita (código mestra ou manage.py).
    if _admin_exists(db):
        logging.getLogger(__name__).warning(
            "admin_bootstrap_ignored reason=admin_exists user_id=%s", user.id
        )
        return False
    user.role = UserRole.admin
    db.commit()
    db.refresh(user)
    logging.getLogger(__name__).warning(
        "admin_promoted_bootstrap user_id=%s (ADMIN_EMAIL)", user.id
    )
    return True


# Texto claro do código gerado (legado, migrado na leitura).
_ADMIN_CODE_KEY = "admin_setup_code"
# A13: o código de ativação fica só como SHA-256; vazar a tabela não o revela.
_ADMIN_CODE_HASH_KEY = "admin_setup_code_hash"
_ADMIN_CONSUMED_KEY = "admin_setup_consumed"


def _setting(db: Session, key: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def _hash_admin_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _admin_exists(db: Session) -> bool:
    return db.query(User.id).filter(User.role == UserRole.admin).first() is not None


def ensure_admin_setup_code(db: Session) -> str | None:
    """Gera (uma única vez) o código de ativação e o registra no log.

    Só age quando ainda não existe administrador e ``ADMIN_SETUP_CODE`` não foi
    definido. Apenas o hash SHA-256 fica no banco; o texto claro aparece **uma
    vez** no log do servidor e nunca é devolvido pela API.
    """
    if (settings.admin_setup_code or "").strip():
        return None
    # Caminho comum depois da ativação: uma única consulta barata e retorno.
    if _admin_exists(db):
        return None
    if _setting(db, _ADMIN_CONSUMED_KEY) is not None:
        return None

    # Migração de bancos antigos: o código em texto claro vira hash.
    legacy = _setting(db, _ADMIN_CODE_KEY)
    if legacy:
        db.query(AppSetting).filter(AppSetting.key == _ADMIN_CODE_KEY).delete()
        db.add(AppSetting(key=_ADMIN_CODE_HASH_KEY, value=_hash_admin_code(legacy)))
        db.commit()
        return legacy

    if _setting(db, _ADMIN_CODE_HASH_KEY):
        return None

    code = secrets.token_urlsafe(9)
    db.add(AppSetting(key=_ADMIN_CODE_HASH_KEY, value=_hash_admin_code(code)))
    db.commit()
    logging.getLogger(__name__).warning(
        "admin_setup_code_generated code=%s (Ativar acesso admin no app)", code
    )
    return code


def activate_admin(db: Session, user: User, code: str) -> User:
    """Promove o próprio usuário logado mediante o código de ativação.

    Com ``ADMIN_SETUP_CODE`` definido, o código do operador funciona como uma
    chave mestra: vale a qualquer momento, mesmo que já exista administrador
    (útil para recuperar o acesso). Sem a variável, o código gerado é de uso
    único: é apagado após a promoção e a ativação fica encerrada para os demais.
    """
    if user.role == UserRole.admin:
        raise ValueError("Você já é administrador.")

    env_code = (settings.admin_setup_code or "").strip()
    provided = (code or "").strip()

    if env_code:
        # Chave mestra do operador: não depende de existir/ não existir admin.
        if not provided or not _codes_match(env_code, provided):
            raise ValueError("Código de ativação inválido.")
    else:
        # Código gerado automaticamente: uso único e encerrado após o 1º admin.
        if _admin_exists(db) or _setting(db, _ADMIN_CONSUMED_KEY) is not None:
            raise ValueError("A ativação por código já foi utilizada.")
        expected_hash = _setting(db, _ADMIN_CODE_HASH_KEY)
        if not expected_hash:
            # Gera agora (ou migra o legado em texto claro).
            ensure_admin_setup_code(db)
            expected_hash = _setting(db, _ADMIN_CODE_HASH_KEY)
        if (
            not expected_hash
            or not provided
            or not secrets.compare_digest(_hash_admin_code(provided), expected_hash)
        ):
            raise ValueError("Código de ativação inválido.")

        # Consome o código e registra que a ativação já foi usada.
        db.query(AppSetting).filter(
            AppSetting.key.in_([_ADMIN_CODE_KEY, _ADMIN_CODE_HASH_KEY])
        ).delete(synchronize_session=False)
        db.add(AppSetting(key=_ADMIN_CONSUMED_KEY, value=str(user.id)))

    user.role = UserRole.admin
    db.add(AuditLog(user_id=user.id, action="admin_activated", detail=f"email={user.email}"))
    db.commit()
    db.refresh(user)
    logging.getLogger(__name__).info("admin_activated user_id=%s", user.id)
    return user


def rotate_admin_setup_code(db: Session) -> str:
    """Invalida o código atual e gera um novo (A4).

    A rotação é o que limita o dano de um vazamento: o código antigo deixa de
    valer imediatamente. Com ``ADMIN_SETUP_CODE`` definido, a variável de
    ambiente é a fonte da verdade — altere-a no provedor e reinicie.
    """
    if (settings.admin_setup_code or "").strip():
        raise ValueError(
            "ADMIN_SETUP_CODE está definido no ambiente; altere a variável e "
            "reinicie o serviço para rotacionar."
        )
    db.query(AppSetting).filter(
        AppSetting.key.in_([_ADMIN_CODE_KEY, _ADMIN_CODE_HASH_KEY, _ADMIN_CONSUMED_KEY])
    ).delete(synchronize_session=False)
    code = secrets.token_urlsafe(12)
    db.add(AppSetting(key=_ADMIN_CODE_HASH_KEY, value=_hash_admin_code(code)))
    db.commit()
    logging.getLogger(__name__).warning(
        "admin_setup_code_rotated (novo código exibido apenas no comando)"
    )
    return code


def expire_admin_setup_code(db: Session) -> None:
    """Encerra a ativação por código gerado (mantém a chave mestra do ambiente)."""
    db.query(AppSetting).filter(
        AppSetting.key.in_([_ADMIN_CODE_KEY, _ADMIN_CODE_HASH_KEY])
    ).delete(synchronize_session=False)
    db.add(AppSetting(key=_ADMIN_CONSUMED_KEY, value="expired"))
    db.commit()
    logging.getLogger(__name__).info("admin_setup_code_expired")


def register_user(db: Session, data: UserCreate) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise ValueError("E-mail já cadastrado")

    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, email: str, new_password: str) -> None:
    """Redefinição simples de senha pelo e-mail cadastrado (sem link/código).

    Decisão de produto: disponível na tela de login para quem esqueceu a senha.
    O endpoint que chama esta função é protegido por rate limit por IP.
    Qualquer troca de senha incrementa ``token_version`` e derruba os tokens
    emitidos antes dela.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise ValueError("E-mail não cadastrado")

    user.password_hash = hash_password(new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    delete_session(user.id)
    logging.getLogger(__name__).info("password_reset user_id=%s", user.id)


def create_password_reset_token(
    db: Session, admin_id: int, target_user_id: int
) -> dict[str, object]:
    """Gera um token de uso único e persiste apenas o hash SHA-256."""
    if admin_id == target_user_id:
        raise ValueError("Um administrador não pode gerar token para si mesmo.")

    target = db.get(User, target_user_id)
    if target is None:
        raise LookupError("Usuário não encontrado.")

    now = _utcnow()
    expires_at = now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
    token = secrets.token_urlsafe(32)

    # Um novo token invalida imediatamente os anteriores ainda pendentes.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == target_user_id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)

    db.add(
        PasswordResetToken(
            user_id=target_user_id,
            token_hash=_hash_reset_token(token),
            expires_at=expires_at,
        )
    )
    db.commit()
    logging.getLogger(__name__).info(
        "reset_token_created admin_id=%s target_user_id=%s", admin_id, target_user_id
    )
    return {"token": token, "expires_at": expires_at}


def confirm_password_reset(db: Session, token: str, new_password: str) -> None:
    """Troca a senha e invalida sessões na mesma transação.

    Qualquer falha (inexistente, usado ou expirado) resulta na mesma mensagem
    genérica, sem revelar se o token ou o usuário existem.
    """
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == _hash_reset_token(token.strip()))
        .first()
    )
    now = _utcnow()
    if row is None or row.used_at is not None or _as_utc(row.expires_at) <= now:
        raise ValueError("Token inválido ou expirado.")

    user = db.get(User, row.user_id)
    if user is None:
        raise ValueError("Token inválido ou expirado.")

    user.password_hash = hash_password(new_password)
    user.token_version = int(user.token_version or 0) + 1
    # Consome também qualquer outro token pendente do usuário.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now}, synchronize_session=False)
    db.commit()
    delete_session(user.id)
    logging.getLogger(__name__).info("password_reset_confirmed user_id=%s", user.id)


def login_user(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise ValueError("Credenciais inválidas")

    # ``verify_and_update`` re-hasheia senhas antigas (custo 12 do passlib) para
    # o custo configurado, sem exigir que o usuário troque a senha. O verify em
    # si é o trecho mais caro do login; o custo 11 responde ~2x mais rápido.
    valid, new_hash = pwd_context.verify_and_update(password, user.password_hash)
    if not valid:
        raise ValueError("Credenciais inválidas")
    if new_hash:
        user.password_hash = new_hash
        db.commit()

    _promote_bootstrap_admin(db, user)
    if user.role != UserRole.admin:
        ensure_admin_setup_code(db)

    payload = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(payload, user.token_version)
    refresh_token = create_refresh_token(payload, user.token_version)
    # A sessão no Redis é apenas informativa (nada a lê para autenticar). Quem
    # grava é o router, em background, para não somar latência ao login.

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


def refresh_tokens(db: Session, refresh_token: str) -> dict:
    """Valida o refresh token (JWT + token_version) e emite novos tokens."""
    try:
        payload = jwt.decode(refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
        token_version = _token_version(payload)
    except (JWTError, TypeError, ValueError):
        raise ValueError("Refresh token inválido ou expirado")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or token_version != user.token_version:
        raise ValueError("Refresh token inválido ou expirado")

    new_payload = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(new_payload, user.token_version)
    new_refresh = create_refresh_token(new_payload, user.token_version)
    # Sessão informativa gravada pelo router em background (não bloqueia).

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        # Interno: o router usa para gravar a sessão informativa em background.
        # O response_model (RefreshResponse) não expõe este campo.
        "user_id": user.id,
    }


def get_current_user(db: Session, token: str) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
        token_version = _token_version(payload)
    except (JWTError, TypeError, ValueError):
        raise ValueError("Token inválido ou expirado")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("Usuário não encontrado")

    if token_version != user.token_version:
        raise ValueError("Sessão invalidada. Faça login novamente.")

    # A consulta do usuário já era necessária; o "tv" é comparado na mesma linha.
    # ``ensure_admin_setup_code`` saiu daqui: era escrita no caminho de leitura
    # (A15) e custava uma consulta extra em TODA requisição autenticada. A
    # geração acontece no login, quando faz sentido.
    _promote_bootstrap_admin(db, user)
    return user
