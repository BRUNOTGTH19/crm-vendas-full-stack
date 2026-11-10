"""Rate limiting para login, redefinição de senha, ativação de admin e IA.

Por padrão os contadores vivem na memória do processo: simples, sem
dependências, e eficaz no servidor único (uvicorn). Com vários workers ou
instâncias, cada processo teria seu próprio contador e o limite efetivo
multiplicaria — por isso ``RATE_LIMIT_BACKEND=redis`` guarda as janelas em
sorted sets no Redis, compartilhadas por todas as instâncias (A17).

O Redis é best-effort: se ele cair, o contador volta para a memória em vez de
derrubar o login. A janela continua sendo aplicada por processo.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from uuid import uuid4

import redis

from config import settings
from redis_client import redis_client

logger = logging.getLogger(__name__)

REDIS_PREFIX = "ratelimit:v1:"

# Limite por IP: 15 falhas de login em 5 minutos.
LOGIN_MAX_FAILURES = 15
LOGIN_WINDOW_SECONDS = 300

# Limite por IP: 10 redefinições de senha em 10 minutos (contam TODAS as
# chamadas, porque cada uma troca uma senha — sucesso ou não).
PASSWORD_RESET_MAX_ATTEMPTS = 10
PASSWORD_RESET_WINDOW_SECONDS = 600

# Limite por IP: 10 códigos de ativação de admin errados em 10 minutos.
ADMIN_ACTIVATION_MAX_ATTEMPTS = 10
ADMIN_ACTIVATION_WINDOW_SECONDS = 600

# Limite por usuário: mensagens do assistente de IA por hora. O limite real vem
# de ``AI_MAX_MESSAGES_PER_HOUR`` (0 desliga a IA). Cada mensagem pode gerar
# várias chamadas ao provedor, então esta cota protege a fatura/cota dele.
AI_WINDOW_SECONDS = 3600

_failures: dict[str, list[float]] = defaultdict(list)
_reset_attempts: dict[str, list[float]] = defaultdict(list)
_admin_attempts: dict[str, list[float]] = defaultdict(list)
_ai_messages: dict[str, list[float]] = defaultdict(list)

_STORES: dict[str, dict[str, list[float]]] = {
    "login": _failures,
    "password_reset": _reset_attempts,
    "admin_activation": _admin_attempts,
    "ai": _ai_messages,
}


def _redis_backend() -> redis.Redis | None:
    """Cliente Redis quando o backend compartilhado está ligado."""
    if settings.rate_limit_backend != "redis":
        return None
    return redis_client


def _redis_key(bucket: str, key: str) -> str:
    return f"{REDIS_PREFIX}{bucket}:{key}"


def _redis_count(client: redis.Redis, key: str, window: float, moment: float) -> int | None:
    """Conta eventos na janela; ``None`` quando o Redis falha."""
    try:
        client.zremrangebyscore(key, 0, moment - window)
        return int(client.zcard(key) or 0)
    except redis.RedisError:
        logger.warning("rate_limit_redis_unavailable op=count")
        return None


def _redis_add(client: redis.Redis, key: str, window: float, moment: float) -> bool:
    """Registra um evento; ``False`` quando o Redis falha."""
    try:
        client.zadd(key, {f"{moment:.6f}:{uuid4().hex}": moment})
        client.expire(key, int(window) + 60)
        return True
    except redis.RedisError:
        logger.warning("rate_limit_redis_unavailable op=add")
        return False


def _prune(store: dict[str, list[float]], key: str, now: float, window: float) -> None:
    stamps = store.get(key)
    if not stamps:
        store.pop(key, None)
        return
    stamps[:] = [t for t in stamps if now - t < window]
    if not stamps:
        store.pop(key, None)


def _is_blocked(bucket: str, key: str, limit: int, window: float,
                now: float | None = None) -> bool:
    client = _redis_backend()
    if client is not None:
        moment = time.time() if now is None else now
        count = _redis_count(client, _redis_key(bucket, key), window, moment)
        if count is not None:
            return count >= limit
        # Redis indisponível: cai para a memória (o login não para por isso).
    moment = time.monotonic() if now is None else now
    store = _STORES[bucket]
    _prune(store, key, moment, window)
    return len(store.get(key, ())) >= limit


def _record(bucket: str, key: str, window: float, now: float | None = None) -> None:
    client = _redis_backend()
    if client is not None:
        moment = time.time() if now is None else now
        if _redis_add(client, _redis_key(bucket, key), window, moment):
            return
    moment = time.monotonic() if now is None else now
    store = _STORES[bucket]
    _prune(store, key, moment, window)
    store[key].append(moment)


def is_login_blocked(key: str, now: float | None = None) -> bool:
    """True quando o IP excedeu o número de falhas na janela."""
    return _is_blocked("login", key, LOGIN_MAX_FAILURES, LOGIN_WINDOW_SECONDS, now)


def record_login_failure(key: str, now: float | None = None) -> None:
    _record("login", key, LOGIN_WINDOW_SECONDS, now)


def is_password_reset_blocked(key: str, now: float | None = None) -> bool:
    """True quando o IP excedeu o número de redefinições na janela."""
    return _is_blocked(
        "password_reset", key, PASSWORD_RESET_MAX_ATTEMPTS,
        PASSWORD_RESET_WINDOW_SECONDS, now,
    )


def record_password_reset(key: str, now: float | None = None) -> None:
    _record("password_reset", key, PASSWORD_RESET_WINDOW_SECONDS, now)


def is_admin_activation_blocked(key: str, now: float | None = None) -> bool:
    """True quando o IP excedeu as tentativas de ativação na janela."""
    return _is_blocked(
        "admin_activation", key, ADMIN_ACTIVATION_MAX_ATTEMPTS,
        ADMIN_ACTIVATION_WINDOW_SECONDS, now,
    )


def record_admin_activation_failure(key: str, now: float | None = None) -> None:
    _record("admin_activation", key, ADMIN_ACTIVATION_WINDOW_SECONDS, now)


def is_ai_blocked(key: str, now: float | None = None) -> bool:
    """True quando o usuário excedeu a cota de mensagens da IA na janela."""
    limit = settings.ai_max_messages_per_hour
    if limit <= 0:
        return False
    return _is_blocked("ai", key, limit, AI_WINDOW_SECONDS, now)


def record_ai_message(key: str, now: float | None = None) -> None:
    _record("ai", key, AI_WINDOW_SECONDS, now)


def reset_rate_limit() -> None:
    """Limpa contadores (usado pelos testes)."""
    for store in _STORES.values():
        store.clear()
    client = _redis_backend()
    if client is None:
        return
    try:
        keys = list(client.scan_iter(match=f"{REDIS_PREFIX}*"))
        if keys:
            client.delete(*keys)
    except redis.RedisError:
        logger.warning("rate_limit_redis_unavailable op=reset")
