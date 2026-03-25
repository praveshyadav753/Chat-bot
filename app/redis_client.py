import redis
from app.core.config import settings
import ssl
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    db=2,
    ssl_cert_reqs=ssl.CERT_NONE,   # required for ElastiCache

    decode_responses=True
)