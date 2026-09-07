import os
import redis.asyncio as redis
from redis.exceptions import TimeoutError as RedisTimeoutError
import json
from urllib.parse import urlparse

# redis_client = redis.from_url(
#     os.getenv("REDIS_URL"),
#     decode_responses=True
# )

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0").strip()
if not _redis_url.startswith("redis://") and not _redis_url.startswith("rediss://"):
    _redis_url = f"redis://{_redis_url}:6379"

redis_client = redis.from_url(_redis_url)

TASK_PREFIX = "task:"


async def result_pop():
    try:
        return await redis_client.blpop("results", timeout=5)
    except RedisTimeoutError:
        return None


async def enqueue_task(task_id: str, mri_path: str):
    await redis_client.rpush(
        "tasks", json.dumps({"task_id": task_id, "mri_path": mri_path})
    )
