import redis

r = redis.Redis.from_url(
    "rediss://chat-bot-cg2xct.serverless.aps1.cache.amazonaws.com:6379",
    ssl_cert_reqs=None
)

print("trying")
print(r.ping())
print("Redis connection successful!")