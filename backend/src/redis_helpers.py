import os
import redis
import json
from urllib.parse import urlparse

# redis_client = redis.from_url(
#     os.getenv("REDIS_URL"),
#     decode_responses=True
# )

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_parsed = urlparse(_redis_url)
redis_client = redis.Redis(
    host=_parsed.hostname,
    port=_parsed.port or 6379,
    db=int(_parsed.path.lstrip("/") or 0),
)

TASK_PREFIX = "task:"

def save_task(task_id: str, data: dict):
    redis_client.set(f"{TASK_PREFIX}{task_id}", json.dumps(data))

def get_task(task_id: str):
    raw = redis_client.get(f"{TASK_PREFIX}{task_id}")

    if not raw:
        return None

    return json.loads(raw)

def update_task(task_id: str, updates: dict):
    task = get_task(task_id)

    if not task:
        raise ValueError(f"Task {task_id} not found")

    task.update(updates)
    save_task(task_id, task)

def list_tasks():
    tasks = []
    for key in redis_client.scan_iter(f"{TASK_PREFIX}*"):
        key = key.decode() if isinstance(key, bytes) else key
        task_id = key.replace(TASK_PREFIX, "")
        tasks.append(get_task(task_id))
    return tasks

def enqueue_task(task_id: str, mri_path: str):
    redis_client.rpush("tasks", json.dumps({"task_id": task_id, "mri_path": mri_path }))