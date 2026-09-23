import redis
import os

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ``ssl_cert_reqs`` só é aceito em conexões TLS (rediss://). Em ``redis://``
# a redis-py rejeita o argumento com TypeError — e, como os helpers de cache
# só capturam ``RedisError``, o cache quebraria em vez de degradar.
_ssl_kwargs = {"ssl_cert_reqs": None} if redis_url.startswith("rediss://") else {}

redis_client = redis.from_url(
    redis_url,
    decode_responses=True,
    **_ssl_kwargs,
)
