import os
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
NODE_ID = os.getenv("NODE_ID", "node-local")
WINDOW_MS = 60_000

# Atomic exact sliding-window limiter.
# KEYS[1] = per-customer sorted-set key
# ARGV[1] = now in milliseconds
# ARGV[2] = window size in milliseconds
# ARGV[3] = quota
# ARGV[4] = unique request member
#
# The decision and state mutation happen in one Redis script, so three
# stateless app nodes cannot race each other into over-admitting.
SLIDING_WINDOW_LUA = r"""
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)

if count < limit then
  redis.call('ZADD', key, now, member)
  redis.call('PEXPIRE', key, window + 5000)
  return {1, limit - count - 1, 0}
end

local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local retry = window
if oldest[2] then
  retry = math.max(1, window - (now - tonumber(oldest[2])))
end
return {0, 0, retry}
"""

app = FastAPI(title="RelayAPI Rate Limiter", version="1.0.0")
redis: Redis | None = None

TIERS = {
    "starter": 60,
    "growth": 300,
    "northwind": 300,
    "test-100-a": 100,
    "test-100-b": 100,
    "test-100-c": 100,
    "boundary-5": 5,
}

def quota_for(customer_id: str) -> int:
    # In a real deployment this comes from authoritative customer config.
    # There is deliberately no customer-specific bypass in the request path.
    return TIERS.get(customer_id, 100)

@app.on_event("startup")
async def startup():
    global redis
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis.ping()

@app.on_event("shutdown")
async def shutdown():
    if redis:
        await redis.aclose()

@app.get("/health")
async def health():
    return {"ok": True, "node": NODE_ID}

@app.get("/api/v1/ping")
async def ping(request: Request):
    customer_id = request.headers.get("X-Customer-Id")
    if not customer_id:
        return JSONResponse({"error": "missing X-Customer-Id"}, status_code=400)

    quota = quota_for(customer_id)
    now_ms = time.time_ns() // 1_000_000
    key = f"relayapi:rl:{customer_id}"
    member = f"{now_ms}-{NODE_ID}-{uuid.uuid4().hex}"

    assert redis is not None
    allowed, remaining, retry_ms = await redis.eval(
        SLIDING_WINDOW_LUA,
        1,
        key,
        now_ms,
        WINDOW_MS,
        quota,
        member,
    )

    headers = {
        "X-RateLimit-Limit": str(quota),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Algorithm": "exact-sliding-window",
        "X-Relay-Node": NODE_ID,
    }

    if int(allowed) == 0:
        retry_seconds = max(1, (int(retry_ms) + 999) // 1000)
        headers["Retry-After"] = str(retry_seconds)
        return JSONResponse(
            {"error": "rate limit exceeded", "customer_id": customer_id},
            status_code=429,
            headers=headers,
        )

    return JSONResponse(
        {"ok": True, "customer_id": customer_id, "node": NODE_ID},
        headers=headers,
    )
