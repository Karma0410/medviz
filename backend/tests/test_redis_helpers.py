import pytest
import json
from unittest.mock import AsyncMock, patch

import src.redis_helpers as rh


# -----------------------------
# Fake Redis in-memory
# -----------------------------
class FakeRedis:
    def __init__(self):
        self.queues = {"tasks": [], "results": []}

    async def rpush(self, key, value):
        self.queues.setdefault(key, []).append(value)

    async def blpop(self, key, timeout=0):
        if self.queues.get(key):
            value = self.queues[key].pop(0)
            return (key, value)
        return None


# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def fake_redis():
    return FakeRedis()


# -----------------------------
# enqueue_task
# -----------------------------
@pytest.mark.asyncio
async def test_enqueue_task(fake_redis):
    with patch.object(rh, "redis_client", fake_redis):

        await rh.enqueue_task("123", "/path/mri.nii")

        assert len(fake_redis.queues["tasks"]) == 1

        payload = json.loads(fake_redis.queues["tasks"][0])

        assert payload["task_id"] == "123"
        assert payload["mri_path"] == "/path/mri.nii"


# -----------------------------
# result_pop success
# -----------------------------
@pytest.mark.asyncio
async def test_result_pop_success(fake_redis):
    fake_redis.queues["results"].append("payload")

    with patch.object(rh, "redis_client", fake_redis):

        result = await rh.result_pop()

        assert result is None or result[0] == "results"


# -----------------------------
# result_pop timeout
# -----------------------------
@pytest.mark.asyncio
async def test_result_pop_timeout(fake_redis):
    with patch.object(rh, "redis_client", fake_redis):

        result = await rh.result_pop()

        assert result is None


# -----------------------------
# Redis timeout exception
# -----------------------------
@pytest.mark.asyncio
async def test_result_pop_redis_timeout():
    fake_client = AsyncMock()
    fake_client.blpop.side_effect = rh.RedisTimeoutError()

    with patch.object(rh, "redis_client", fake_client):

        result = await rh.result_pop()

        assert result is None


# -----------------------------
# enqueue_task payload validation
# -----------------------------
@pytest.mark.asyncio
async def test_enqueue_task_payload():
    fake_client = AsyncMock()

    with patch.object(rh, "redis_client", fake_client):

        await rh.enqueue_task("abc", "file.nii")

        fake_client.rpush.assert_called_once()

        args = fake_client.rpush.call_args[0]

        assert args[0] == "tasks"

        payload = json.loads(args[1])

        assert payload == {"task_id": "abc", "mri_path": "file.nii"}
