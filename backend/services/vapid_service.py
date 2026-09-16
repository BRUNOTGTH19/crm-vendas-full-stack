"""Resolução das chaves VAPID para Web Push.

Ordem de prioridade:
1. Variáveis de ambiente (``VAPID_PUBLIC_KEY`` / ``VAPID_PRIVATE_KEY``) — ideal
   para produção, onde se configura explicitamente no painel do provedor.
2. Chaves persistidas na tabela ``app_settings`` (geradas automaticamente na
   primeira execução).
3. Derivação determinística a partir do ``JWT_SECRET_KEY`` — fallback quando o
   banco não está acessível (ex.: migration ``app_settings`` não executada).

Persistir no banco garante que as chaves permaneçam estáveis entre reinícios
do servidor. Isso é essencial para o Web Push: se a chave pública mudar, as
subscrições já existentes nos navegadores deixam de funcionar.
"""
import base64
import hashlib
import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session

from config import settings
from models.app_setting import AppSetting

logger = logging.getLogger(__name__)

_PUBLIC_KEY_NAME = "vapid_public_key"
_PRIVATE_KEY_NAME = "vapid_private_key"

# Ordem do grupo da curva P-256 (SECP256R1), usada para derivar um escalar válido.
_P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def generate_vapid_keypair() -> tuple[str, str]:
    """Gera um par de chaves VAPID (P-256) em base64url.

    Retorna ``(public_key, private_key)`` no formato aceito pelo pywebpush e
    pelo navegador (``applicationServerKey``).
    """
    private_key = ec.generate_private_key(ec.SECP256R1())

    private_der = private_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return _b64url(public_raw), _b64url(private_der)


def _serialize_keypair(private_key: ec.EllipticCurvePrivateKey) -> tuple[str, str]:
    """Serializa um par de chaves P-256 em base64url (público, privado)."""
    private_der = private_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return _b64url(public_raw), _b64url(private_der)


def _derive_from_secret() -> tuple[str, str]:
    """Deriva um par VAPID determinístico a partir do ``JWT_SECRET_KEY``.

    Usado como último recurso quando o banco não está acessível (ex.: a
    migration ``app_settings`` ainda não foi executada). Como o
    ``JWT_SECRET_KEY`` é estável em produção, as chaves permanecem as mesmas
    entre reinícios — mantendo as subscrições válidas.
    """
    seed = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    scalar = (int.from_bytes(seed, "big") % (_P256_ORDER - 1)) + 1
    private_key = ec.derive_private_key(scalar, ec.SECP256R1())
    return _serialize_keypair(private_key)


def _get_setting(db: Session, key: str) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


def get_vapid_keys(db: Session) -> tuple[str, str]:
    """Retorna ``(public_key, private_key)``, gerando/persistindo se necessário.

    Ordem: variáveis de ambiente → banco (``app_settings``) → derivação
    determinística do ``JWT_SECRET_KEY`` (fallback se o banco falhar).
    """
    # 1. Variáveis de ambiente têm prioridade.
    if settings.vapid_public_key and settings.vapid_private_key:
        return settings.vapid_public_key, settings.vapid_private_key

    # 2. Chaves persistidas no banco (ou geração + persistência).
    try:
        public_key = _get_setting(db, _PUBLIC_KEY_NAME)
        private_key = _get_setting(db, _PRIVATE_KEY_NAME)
        if public_key and private_key:
            return public_key, private_key

        public_key, private_key = generate_vapid_keypair()
        _set_setting(db, _PUBLIC_KEY_NAME, public_key)
        _set_setting(db, _PRIVATE_KEY_NAME, private_key)
        logger.info("Par de chaves VAPID gerado e persistido automaticamente.")
        return public_key, private_key
    except Exception as exc:
        # 3. Fallback: banco indisponível (ex.: migration não executada).
        logger.warning(
            "Não foi possível persistir as chaves VAPID no banco (%s). "
            "Usando chaves derivadas do JWT_SECRET_KEY.",
            exc,
        )
        return _derive_from_secret()
