import os

import redis

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _ssl_options(url: str) -> dict:
    """Opções de TLS compatíveis com o esquema da URL.

    ``ssl_cert_reqs`` só é aceito em conexões TLS (``rediss://``). Em
    ``redis://`` a redis-py rejeita o argumento com TypeError — e, como os
    helpers de cache só capturam ``RedisError``, o cache quebraria em vez de
    degradar.

    Em ``rediss://`` o certificado do servidor é VALIDADO (A6 da auditoria).
    Antes usávamos ``None``, o que aceitava qualquer certificado e abria espaço
    para MITM na rede do provedor.
    """
    return {"ssl_cert_reqs": "required"} if url.startswith("rediss://") else {}


_ssl_kwargs = _ssl_options(redis_url)

# Timeout curto: cache, sessão informativa e fila de PDF são best-effort. Sem
# limite, uma indisponibilidade do Upstash podia segurar o login (que grava a
# sessão informativa) por vários segundos.
_socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "1.5"))


def build_redis_client(decode_responses: bool = True) -> redis.Redis:
    """Cria um cliente Redis respeitando TLS (``rediss://``).

    ``decode_responses=False`` é obrigatório nos jobs de PDF, que leem bytes
    do Redis (``hgetall`` devolve ``{b"campo": ...}``). Centralizar a criação
    aqui evita repetir o erro de passar ``ssl_cert_reqs`` em URL sem TLS, que
    derrubava ``POST /queue/pdf/{sale_id}`` com 500.
    """
    return redis.from_url(
        redis_url,
        decode_responses=decode_responses,
        socket_timeout=_socket_timeout,
        socket_connect_timeout=_socket_timeout,
        **_ssl_kwargs,
    )


redis_client = build_redis_client()
