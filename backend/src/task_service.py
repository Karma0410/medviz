import os
import json
from fastapi import File

from src.redis_helpers import enqueue_task, result_pop
from src.db import TaskUpdate, TaskRepository
from src.enums import TaskStatus
from config import UPLOAD_DIR, MASK_DIR


class TaskService:
    def __init__(self):
        self.task_repository = TaskRepository()

    async def save_file(self, file: File, task_id: str):
        # file extension handling
        file_ext = os.path.splitext(file.filename)[1]
        if file.filename.endswith(".nii.gz"):
            file_ext = ".nii.gz"

        saved_filename = f"{task_id}{file_ext}"
        saved_file_path = os.path.join(UPLOAD_DIR, saved_filename)

        # file saved on drive
        with open(saved_file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return saved_file_path

    def create_task(self, task_id: str, filepath: str, age: int):
        saved_task = self.task_repository.save_task(task_id, filepath, age)
        return saved_task

    async def send_task(self, task_id: str):
        update = TaskUpdate(status=TaskStatus.PENDING)
        task = self.task_repository.update_task(task_id, update)

        await enqueue_task(task.task_id, task.filename)
        return task

    def get_task_by_task_id(self, task_id: str):
        return self.task_repository.select_task(task_id)

    def get_tasks(self, limit: int = 100, offset: int = 0):
        return self.task_repository.select_all(limit, offset)

    def get_mri_path(self, task_id: str):
        files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(task_id)]
        if not files:
            return -1

        return os.path.join(UPLOAD_DIR, files[0])

    def get_mask_path(self, task_id: str, task_status: TaskStatus):
        if task_status != TaskStatus.DONE:
            return -2

        files = [f for f in os.listdir(MASK_DIR) if f.startswith(task_id)]
        if not files:
            return -1

        return os.path.join(MASK_DIR, files[0])

    async def get_result(self):
        result = await result_pop()
        if result is None:
            return None
        _, raw = result
        results = json.loads(raw)
        return results

    def update(self, task_id: str, results: dict):
        update = TaskUpdate.model_validate(results)
        update.status = TaskStatus.DONE
        task = self.task_repository.update_task(task_id, update)
        return task
