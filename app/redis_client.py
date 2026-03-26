import redis
from app.core.config import settings

redis_client = redis.from_url(
    settings.REDIS_URL,         
    ssl_cert_reqs="none",        
    decode_responses=True,
)