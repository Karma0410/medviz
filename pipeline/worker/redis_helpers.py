import os
import redis
from redis.exceptions import TimeoutError as RedisTimeoutError
import json
from urllib.parse import urlparse

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_parsed = urlparse(_redis_url)
redis_client = redis.Redis(
    host=_parsed.hostname,
    port=_parsed.port or 6379,
    db=int(_parsed.path.lstrip("/") or 0),
)


def task_pop():
    try:
        return redis_client.blpop("tasks", timeout=5)
    except RedisTimeoutError:
        return None


def enqueue_result(task_id: str, results: dict):
    redis_client.rpush("results", json.dumps({"task_id": task_id, "results": results}))