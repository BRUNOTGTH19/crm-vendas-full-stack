import os
import redis
from config import settings

redis_url = os.getenv("REDIS_URL") or settings.redis_url or "redis://localhost:6379/0"
ssl = redis_url.startswith("rediss://")

redis_kwargs = {
    "decode_responses": True,
}
if ssl:
    redis_kwargs["ssl_cert_reqs"] = None

redis_client = redis.from_url(redis_url, **redis_kwargs)