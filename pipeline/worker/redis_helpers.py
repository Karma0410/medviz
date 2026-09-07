import os
import redis
from redis.exceptions import TimeoutError as RedisTimeoutError
import json
from urllib.parse import urlparse

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0").strip()
if not _redis_url.startswith("redis://") and not _redis_url.startswith("rediss://"):
    _redis_url = f"redis://{_redis_url}:6379"

redis_client = redis.from_url(_redis_url)


def task_pop():
    try:
        return redis_client.blpop("tasks", timeout=5)
    except RedisTimeoutError:
        return None


def enqueue_result(task_id: str, results: dict):
    redis_client.rpush("results", json.dumps({"task_id": task_id, "results": results}))
