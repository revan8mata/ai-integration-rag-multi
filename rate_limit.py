import os
import redis
from fastapi import HTTPException

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
)

def record_token_usage(user_id: int, token_count: int, window_seconds: int):
    key = f"token_limit:{user_id}:chat"
    current = r.incrby(key ,token_count)

    if current == token_count:
        r.expire(key, window_seconds)
# first 

def check_token_limit(user_id: int, max_tokens: int):
    key = f"token_limit:{user_id}:chat"
    current = r.get(key)
    current = int(current) if current else 0
    if current >= max_tokens:
        raise HTTPException(status_code=429, detail="token limit exceeded")

def check_rate_limit(user_id: int, endpoint: str, max_requests: int, window_seconds: int):
    key = f"rate_limit:{user_id}:{endpoint}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)

    if count > max_requests:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
