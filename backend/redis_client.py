import os

import redis

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ``ssl_cert_reqs`` só é aceito em conexões TLS (rediss://). Em ``redis://``
# a redis-py rejeita o argumento com TypeError — e, como os helpers de cache
# só capturam ``RedisError``, o cache quebraria em vez de degradar.
_ssl_kwargs = {"ssl_cert_reqs": None} if redis_url.startswith("rediss://") else {}


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
        **_ssl_kwargs,
    )


redis_client = build_redis_client()
