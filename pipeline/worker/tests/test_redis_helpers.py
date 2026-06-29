import json
from unittest.mock import patch, MagicMock

import worker.redis_helpers as rh  # adapte le nom si ton fichier a un autre nom


# -----------------------------
# Fake Redis (sync version)
# -----------------------------
class FakeRedis:
    def __init__(self):
        self.queues = {"tasks": [], "results": []}

    def blpop(self, key, timeout=0):
        if self.queues.get(key):
            value = self.queues[key].pop(0)
            return (key, value)
        return None

    def rpush(self, key, value):
        self.queues.setdefault(key, []).append(value)


# -----------------------------
# task_pop
# -----------------------------
def test_task_pop_success():
    fake = FakeRedis()
    fake.queues["tasks"].append("job1")

    with patch.object(rh, "redis_client", fake):
        result = rh.task_pop()

        assert result is not None
        assert result[0] == "tasks"
        assert result[1] == "job1"


def test_task_pop_empty():
    fake = FakeRedis()

    with patch.object(rh, "redis_client", fake):
        result = rh.task_pop()

        assert result is None


# -----------------------------
# Redis timeout exception
# -----------------------------
def test_task_pop_timeout():
    fake = MagicMock()
    fake.blpop.side_effect = rh.RedisTimeoutError()

    with patch.object(rh, "redis_client", fake):
        result = rh.task_pop()

        assert result is None


# -----------------------------
# enqueue_result
# -----------------------------
def test_enqueue_result():
    fake = FakeRedis()

    with patch.object(rh, "redis_client", fake):

        rh.enqueue_result("123", {"score": 0.95})

        assert len(fake.queues["results"]) == 1

        payload = json.loads(fake.queues["results"][0])

        assert payload["task_id"] == "123"
        assert payload["results"] == {"score": 0.95}


# -----------------------------
# enqueue_result call validation
# -----------------------------
def test_enqueue_result_raw_mock():
    fake = MagicMock()

    with patch.object(rh, "redis_client", fake):

        rh.enqueue_result("abc", {"a": 1})

        fake.rpush.assert_called_once()

        args = fake.rpush.call_args[0]

        assert args[0] == "results"

        payload = json.loads(args[1])

        assert payload == {"task_id": "abc", "results": {"a": 1}}
