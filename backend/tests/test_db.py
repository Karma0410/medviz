# test_db.py

import uuid
from sqlmodel import create_engine, SQLModel
from src.db import init_db, save_task, select_task, update_task, delete_task, TaskUpdate
from src.enums import TaskStatus

DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/medviz"
engine = create_engine(DATABASE_URL)

init_db(engine)

def test_save_and_select_task():
    task_id = str(uuid.uuid4())
    filename = "scan.nii.gz"
    age = 42

    save_task(engine, task_id, filename, age)
    task = select_task(engine, task_id)

    assert task is not None
    assert task.task_id == task_id
    assert task.filename == filename
    assert task.age == age


def test_default_values():
    task_id = str(uuid.uuid4())

    save_task(engine, task_id, "image.nii.gz", 25)
    task = select_task(engine, task_id)

    assert task.status == TaskStatus.STARTED
    assert task.left_volume == None
    assert task.right_volume == None
    assert task.total_volume == None
    assert task.hippo_ratio_left == None
    assert task.hippo_ratio_right == None
    assert task.asymmetry_index == None
    assert task.dice_left == None
    assert task.dice_right == None
    assert task.iou_left == None
    assert task.iou_right == None
    assert task.hd95_left == None
    assert task.hd95_right == None
    assert task.status_text == None


def test_unknown_task_returns_none():
    task = select_task(engine, "does-not-exist")
    assert task is None


# =========================================================
# 🆕 UPDATE TEST
# =========================================================

def test_update_task():
    task_id = str(uuid.uuid4())

    save_task(engine, task_id, "image.nii.gz", 30)

    update = TaskUpdate(
        status=TaskStatus.DONE,
        left_volume=12.5,
        right_volume=8.2,
        status_text="healthy"
    )

    updated = update_task(engine, task_id, update)

    assert updated is not None
    assert updated.status == TaskStatus.DONE
    assert updated.left_volume == 12.5
    assert updated.right_volume == 8.2
    assert updated.status_text == "healthy"


# =========================================================
# 🆕 DELETE TEST
# =========================================================

def test_delete_task():
    task_id = str(uuid.uuid4())

    save_task(engine, task_id, "image.nii.gz", 22)

    # delete should return True
    result = delete_task(engine, task_id)
    assert result is True

    # task should no longer exist
    task = select_task(engine, task_id)
    assert task is None


def test_delete_unknown_task():
    result = delete_task(engine, "does-not-exist")
    assert result is False