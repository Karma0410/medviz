from sqlmodel import SQLModel, Field, Session, select

from src.enums import TaskStatus
from config import engine


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: str  # ID of the associated redis taks
    filename: str
    age: int
    status: TaskStatus = Field(default=TaskStatus.STARTED)
    left_volume: float | None = Field(default=None)
    right_volume: float | None = Field(default=None)
    total_volume: float | None = Field(default=None)
    brain_volume: float | None = Field(default=None)
    hippo_ratio_left: float | None = Field(default=None)
    hippo_ratio_right: float | None = Field(default=None)
    asymmetry_index: float | None = Field(default=None)
    dice_left: float | None = Field(default=None)
    dice_right: float | None = Field(default=None)
    iou_left: float | None = Field(default=None)
    iou_right: float | None = Field(default=None)
    hd95_left: float | None = Field(default=None)
    hd95_right: float | None = Field(default=None)
    status_text: str | None = Field(default=None)


class TaskUpdate(SQLModel):
    status: TaskStatus | None = None
    left_volume: float | None = None
    right_volume: float | None = None
    total_volume: float | None = None
    brain_volume: float | None = None
    hippo_ratio_left: float | None = None
    hippo_ratio_right: float | None = None
    asymmetry_index: float | None = None
    dice_left: float | None = None
    dice_right: float | None = None
    iou_left: float | None = None
    iou_right: float | None = None
    hd95_left: float | None = None
    hd95_right: float | None = None
    status_text: str | None = None


class TaskRepository:
    def __init__(self):
        pass

    def save_task(self, task_id: str, filename: str, age: int):
        new_task = Task(task_id=task_id, filename=filename, age=age)
        with Session(engine) as session:
            session.add(new_task)
            session.commit()
            session.refresh(new_task)
            return new_task

    def update_task(self, task_id: str, update: TaskUpdate):
        with Session(engine) as session:
            statement = select(Task).where(Task.task_id == task_id)
            task = session.exec(statement).first()

            if task is None:
                return None

            update_data = update.model_dump(exclude_unset=True)

            for key, value in update_data.items():
                setattr(task, key, value)

            session.add(task)
            session.commit()
            session.refresh(task)

            return task

    def delete_task(self, task_id: str):
        with Session(engine) as session:
            statement = select(Task).where(Task.task_id == task_id)
            task = session.exec(statement).first()

            if task is None:
                return False

            session.delete(task)
            session.commit()

            return True

    def select_task(self, task_id: str):
        with Session(engine) as session:
            statement = select(Task).where(Task.task_id == task_id)
            task = session.exec(statement).first()
            return task

    def select_all(self, limit: int = 100, offset: int = 0):
        with Session(engine) as session:
            statement = select(Task).offset(offset).limit(limit)
            tasks = session.exec(statement).all()
            return tasks
