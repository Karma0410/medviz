import pytest
from unittest.mock import MagicMock, patch

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from src.db import TaskRepository, Task, TaskUpdate
from src.enums import TaskStatus


class FakeResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value

    def all(self):
        return self._value


class FakeSession:
    def __init__(self):
        self.storage = {}

    def add(self, obj):
        self.storage[obj.task_id] = obj

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def delete(self, obj):
        self.storage.pop(obj.task_id, None)

    def exec(self, statement):
        # on ignore SQL, on simule via storage
        if statement.whereclause is not None:
            task_id = getattr(statement.whereclause.right, "value", None)

            # fallback simple
            for t in self.storage.values():
                if t.task_id == task_id:
                    return FakeResult(t)

        return FakeResult(list(self.storage.values()))


@pytest.fixture
def repo():
    return TaskRepository()


# Save Task
def test_save_task(repo):
    fake_session = FakeSession()

    fake_cm = MagicMock()
    fake_cm.__enter__.return_value = fake_session
    fake_cm.__exit__.return_value = None

    with patch("src.db.Session", return_value=fake_cm):
        with patch("src.db.engine", new=object()):

            task = repo.save_task("123", "file.nii", 70)

            assert task.task_id == "123"
            assert task.filename == "file.nii"
            assert task.age == 70


# Update Task
def test_update_task(repo):
    fake_session = FakeSession()

    fake_cm = MagicMock()
    fake_cm.__enter__.return_value = fake_session
    fake_cm.__exit__.return_value = None

    # preload task
    t = Task(task_id="123", filename="a", age=50)
    fake_session.add(t)

    with patch("src.db.Session", return_value=fake_cm):
        with patch("src.db.engine", new=object()):

            update = TaskUpdate(left_volume=10.0, status=TaskStatus.STARTED)

            result = repo.update_task("123", update)

            assert result.left_volume == 10.0
            assert result.status == TaskStatus.STARTED


# Delete Task
def test_delete_task(repo):
    fake_session = FakeSession()

    fake_cm = MagicMock()
    fake_cm.__enter__.return_value = fake_session
    fake_cm.__exit__.return_value = None

    t = Task(task_id="123", filename="a", age=50)
    fake_session.add(t)

    with patch("src.db.Session", return_value=fake_cm):
        with patch("src.db.engine", new=object()):

            assert repo.delete_task("123") is True
            assert "123" not in fake_session.storage


# Select Task
def test_select_task(repo):
    fake_session = FakeSession()

    fake_cm = MagicMock()
    fake_cm.__enter__.return_value = fake_session
    fake_cm.__exit__.return_value = None

    t = Task(task_id="123", filename="a", age=50)
    fake_session.add(t)

    with patch("src.db.Session", return_value=fake_cm):
        with patch("src.db.engine", new=object()):

            result = repo.select_task("123")

            assert result.task_id == "123"


# Select all
def test_select_all(repo):
    fake_session = FakeSession()

    fake_cm = MagicMock()
    fake_cm.__enter__.return_value = fake_session
    fake_cm.__exit__.return_value = None

    fake_session.add(Task(task_id="1", filename="a", age=1))
    fake_session.add(Task(task_id="2", filename="b", age=2))

    with patch("src.db.Session", return_value=fake_cm):
        with patch("src.db.engine", new=object()):

            result = repo.select_all()

            assert len(result) == 2
