import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from src.task_service import TaskService
from src.enums import TaskStatus


class FakeRepo:
    def __init__(self):
        self.storage = {}

    def save_task(self, task_id, filepath, age):
        obj = MagicMock()
        obj.task_id = task_id
        obj.filename = filepath
        obj.age = age
        self.storage[task_id] = obj
        return obj

    def update_task(self, task_id, update):
        obj = self.storage.get(task_id, MagicMock())
        for k, v in update.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        self.storage[task_id] = obj
        return obj

    def select_task(self, task_id):
        return self.storage.get(task_id)

    def select_all(self, limit=100, offset=0):
        return list(self.storage.values())


@pytest.fixture
def service():
    svc = TaskService()
    svc.task_repository = FakeRepo()
    return svc


# Save file
@pytest.mark.asyncio
async def test_save_file(service):
    fake_file = AsyncMock()
    fake_file.filename = "image.nii.gz"
    fake_file.read = AsyncMock(return_value=b"data")

    with patch("builtins.open", mock_open()) as mocked_file:
        with patch("os.path.join", return_value="/fake/path/file.nii.gz"):

            path = await service.save_file(fake_file, "123")

            assert path == "/fake/path/file.nii.gz"
            mocked_file().write.assert_called_once_with(b"data")


# Create task
def test_create_task(service):
    task = service.create_task("123", "file.nii", 70)

    assert task.task_id == "123"
    assert task.filename == "file.nii"


# Send task
@pytest.mark.asyncio
async def test_send_task(service):
    service.task_repository.save_task("123", "file.nii", 70)

    with patch("src.task_service.enqueue_task", new=AsyncMock()) as mock_enqueue:
        task = await service.send_task("123")

        mock_enqueue.assert_called_once_with("123", "file.nii")
        assert task.status == TaskStatus.PENDING


# Get task by id
def test_get_task(service):
    service.task_repository.save_task("123", "file.nii", 70)

    task = service.get_task_by_task_id("123")

    assert task.task_id == "123"


# Get tasks
def test_get_tasks(service):
    service.task_repository.save_task("1", "a", 1)
    service.task_repository.save_task("2", "b", 2)

    tasks = service.get_tasks()

    assert len(tasks) == 2


# Get MRI path
def test_get_mri_path(service):
    with patch("os.listdir", return_value=["123.nii.gz"]):
        with patch("os.path.join", return_value="/fake/123.nii.gz"):

            path = service.get_mri_path("123")

            assert path == "/fake/123.nii.gz"


# Get mask path success
def test_get_mask_path_done(service):
    with patch("os.listdir", return_value=["123_mask.nii.gz"]):
        with patch("os.path.join", return_value="/fake/mask.nii.gz"):

            path = service.get_mask_path("123", TaskStatus.DONE)

            assert path == "/fake/mask.nii.gz"


# Get mask path not done
def test_get_mask_path_not_done(service):
    path = service.get_mask_path("123", TaskStatus.PENDING)

    assert path == -2


# Get result
@pytest.mark.asyncio
async def test_get_result(service):
    fake_payload = json.dumps({"a": 1})

    with patch(
        "src.task_service.result_pop", new=AsyncMock(return_value=("id", fake_payload))
    ):

        result = await service.get_result()

        assert result == {"a": 1}


# Update task done
def test_update(service):
    service.task_repository.save_task("123", "file.nii", 70)

    results = {"left_volume": 1.0, "right_volume": 2.0}

    task = service.update("123", results)

    assert task.status == TaskStatus.DONE
    assert task.left_volume == 1.0
