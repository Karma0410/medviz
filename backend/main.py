import os
import uuid
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlmodel import Session, select, create_engine
from src.redis_helpers import *
from src.db import TaskUpdate, init_db, save_task, update_task, delete_task, select_task
from src.enums import TaskStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("     main")

app = FastAPI(title="NeuroVolumetry API - Squelette Base", version="0.1.0")

# CORS (for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
MASK_DIR = os.path.join(DATA_DIR, "masks")

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

@app.on_event("startup")
def startup_event():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(MASK_DIR, exist_ok=True)
    logger.info("Dossiers de stockage sur disque initialisés.")
    
    init_db(engine)
    logger.info("Base de donnée PostgreSQL initialisée.")

@app.post("/analyze")
async def analyze_mri(
    file: UploadFile = File(...),
    age: int = Form(...)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    
    task_id = str(uuid.uuid4())
    logger.info(f"Nouvelle requête d'analyse reçue: file={file.filename}, age={age}, task_id={task_id}")

    # file extension handling
    file_ext = os.path.splitext(file.filename)[1]
    if file.filename.endswith(".nii.gz"):
        file_ext = ".nii.gz"
        
    saved_filename = f"{task_id}{file_ext}"
    saved_file_path = os.path.join(UPLOAD_DIR, saved_filename)
    mask_filename = f"{task_id}_mask{file_ext}"
    saved_mask_path = os.path.join(MASK_DIR, mask_filename)

    # file saved on drive
    try:
        with open(saved_file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        logger.error(f"Échec de la sauvegarde du fichier : {e}")
        raise HTTPException(status_code=500, detail=f"Impossible de sauvegarder le fichier sur le disque : {e}")

    saved_task = save_task(engine, task_id, saved_file_path, age)
    logger.info(f"Tâche sauvegardée en DB: {saved_task["id"]}")

    # Frontend needs that
    update = TaskUpdate(status=TaskStatus.PENDING)
    update_task(engine, task_id, update)

    enqueue_task(task_id, saved_file_path)

    return {
        "task_id": task_id,
        "filename": saved_file_path,
        "age": age,
        "status": TaskStatus.PENDING
    }

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = select_task(engine, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    return task

@app.get("/tasks/{task_id}/mri")
async def get_task_mri(task_id: str):
    task = select_task(engine, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    
    files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(task_id)]
    if not files:
         raise HTTPException(status_code=404, detail="Fichier IRM introuvable sur le serveur")
    
    file_path = os.path.join(UPLOAD_DIR, files[0])
    return FileResponse(file_path, media_type="application/octet-stream", filename=task.filename)

@app.get("/tasks/{task_id}/mask")
async def get_task_mask(task_id: str):
    task = select_task(engine, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Masque non généré ou analyse en cours")
    
    files = [f for f in os.listdir(MASK_DIR) if f.startswith(task_id)]
    if not files:
         raise HTTPException(status_code=404, detail="Fichier Masque introuvable sur le disque")
    
    file_path = os.path.join(MASK_DIR, files[0])
    return FileResponse(file_path, media_type="application/octet-stream", filename=f"mask_{task.filename}")

@app.get("/tasks")
async def get_tasks():
    return list_tasks()
