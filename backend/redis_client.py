import redis
import os

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ssl = redis_url.startswith("rediss://")

redis_client = redis.from_url(
    redis_url,
    decode_responses=True,
    ssl_cert_reqs=None if ssl else "required"
)