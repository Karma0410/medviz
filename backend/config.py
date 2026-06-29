import os
from sqlmodel import SQLModel, create_engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
MASK_DIR = os.path.join(DATA_DIR, "masks")
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)


def init_db():
    SQLModel.metadata.create_all(engine)
