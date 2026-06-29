import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import main

client = TestClient(main.app)


# =========================================================
# FIXTURES MOCK TASK SERVICE
# =========================================================


@pytest.fixture
def mock_service():
    task = MagicMock()
    task.task_id = "123"
    task.filename = "file.nii"
    task.status = "DONE"
    task.model_dump.return_value = {
        "task_id": "123",
        "filename": "file.nii",
        "status": "DONE",
    }

    service = MagicMock()

    service.save_file = AsyncMock(return_value="/tests/fake/path/file.nii")
    service.create_task.return_value = MagicMock(
        id=1,
        model_dump=lambda mode=None: {
            "id": 1,
            "task_id": "123",
            "filename": "file.nii",
            "status": "STARTED",
        },
    )

    service.send_task = AsyncMock(return_value=service.create_task.return_value)
    service.get_task_by_task_id.return_value = task

    service.get_mri_path.return_value = "./tests/fake/file.nii"
    service.get_mask_path.return_value = "./tests/fake/mask.nii"

    service.get_tasks.return_value = [task]

    service.get_result = AsyncMock(
        side_effect=[None, {"task_id": "123", "results": {"left_volume": 10}}]
    )

    service.update.return_value = task

    return service


# =========================================================
# PATCH SERVICE INTO APP
# =========================================================


@pytest.fixture(autouse=True)
def patch_service(mock_service):
    with patch.object(main, "task_service", mock_service):
        yield


# =========================================================
# /analyze
# =========================================================


def test_analyze_mri():
    response = client.post(
        "/analyze", files={"file": ("test.nii", b"fakecontent")}, data={"age": 70}
    )

    assert response.status_code == 200
    assert "task_id" in response.json()


# =========================================================
# GET TASK
# =========================================================


def test_get_task():
    response = client.get("/tasks/123")

    assert response.status_code == 200
    assert response.json()["task_id"] == "123"


def test_get_task_not_found(mock_service):
    mock_service.get_task_by_task_id.return_value = None

    response = client.get("/tasks/404")

    assert response.status_code == 404


# =========================================================
# MRI FILE
# =========================================================


def test_get_mri():
    response = client.get("/tasks/123/mri")

    assert response.status_code == 200


def test_get_mri_not_found(mock_service):
    mock_service.get_mri_path.return_value = -1

    response = client.get("/tasks/123/mri")

    assert response.status_code == 404


# =========================================================
# MASK FILE
# =========================================================


def test_get_mask():
    response = client.get("/tasks/123/mask")

    assert response.status_code == 200


def test_get_mask_not_found(mock_service):
    mock_service.get_mask_path.return_value = -1

    response = client.get("/tasks/123/mask")

    assert response.status_code == 404


def test_get_mask_processing(mock_service):
    mock_service.get_mask_path.return_value = -2

    response = client.get("/tasks/123/mask")

    assert response.status_code == 400


# =========================================================
# LIST TASKS
# =========================================================


def test_get_tasks():
    response = client.get("/tasks")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =========================================================
# WEBSOCKET
# =========================================================


def test_websocket():
    with client.websocket_connect("/ws") as ws:

        data = ws.receive_json()

        assert "task_id" in data
