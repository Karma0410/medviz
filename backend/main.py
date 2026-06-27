import os
import uuid
import logging
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import *
from src.task_service import TaskService

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

task_service = TaskService()

@app.on_event("startup")
def startup_event():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(MASK_DIR, exist_ok=True)
    logger.info("Dossiers de stockage sur disque initialisés.")
    
    init_db()
    logger.info("Base de donnée PostgreSQL initialisée.")

@app.post("/analyze")
async def analyze_mri(
    file: UploadFile = File(...),
    age: int = Form(...)
):
    logger.info("Nouvelle requête d'analyse reçue.")
    if not file.filename:
        logger.error("Nom de fichier invalide.")
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    task_id = str(uuid.uuid4())
    logger.info(f"Analyse de : file={file.filename}, age={age}, task_id={task_id}.")

    # Save MRI file
    try:
        saved_file_path = await task_service.save_file(file, task_id)
    except Exception as e:
        logger.error(f"Échec de la sauvegarde du fichier : {e}.")
        raise HTTPException(status_code=500, detail=f"Impossible de sauvegarder le fichier sur le disque : {e}")
    logger.info(f"IRM sauvegardé : {saved_file_path}.")
    
    # Task creation
    task = task_service.create_task(task_id, saved_file_path, age)
    logger.info(f"Tâche sauvegardée en DB: {task.id}.")

    # Task sending (Redis)
    task = await task_service.send_task(task_id)
    logger.info("Tâche envoyée à la pipeline.")
    
    return task.model_dump()

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    logger.info(f"Récupérer la tâche : {task_id}.")
    task = task_service.get_task_by_task_id(task_id)
    if not task:
        logger.error("Tâche non trouvée.")
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    return task.model_dump(mode="json")

@app.get("/tasks/{task_id}/mri")
async def get_task_mri(task_id: str):
    logger.info(f"Récupérer l'IRM de la tâche : {task_id}.")
    task = task_service.get_task_by_task_id(task_id)
    if not task:
        logger.error("Tâche non trouvée.")
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    
    file_path = task_service.get_mri_path(task_id)
    if file_path == -1:
        logger.error("Fichier IRM introuvable sur le serveur.")
        raise HTTPException(status_code=404, detail="Fichier IRM introuvable sur le serveur")

    return FileResponse(file_path, media_type="application/octet-stream", filename=task.filename)

@app.get("/tasks/{task_id}/mask")
async def get_task_mask(task_id: str):
    logger.info(f"Récupérer le masque de la tâche : {task_id}")
    task = task_service.get_task_by_task_id(task_id)
    if not task:
        logger.error("Tâche non trouvée.")
        raise HTTPException(status_code=404, detail="Tâche non trouvée")

    file_path = task_service.get_mask_path(task_id, task.status)
    if file_path == -1:
        logger.error("Fichier de masque non généré ou introuvable sur le serveur.")
        raise HTTPException(status_code=404, detail="Fichier de masque non généré ou introuvable sur le serveur")
    elif file_path == -2:
        logger.error("Analyse en cours.")
        raise HTTPException(status_code=400, detail="Analyse en cours")

    return FileResponse(file_path, media_type="application/octet-stream", filename=f"mask_{task.filename}")

@app.get("/tasks")
async def get_tasks():
    logger.info("Récupérer toutes les tâches.")
    tasks = task_service.get_tasks()
    return [task.model_dump(mode="json") for task in tasks]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            try:
                message = await task_service.get_result()
                if message is None:
                    continue
                task_id = message["task_id"]
                logger.info(f"Résultats de l'analyse pour la tâche {task_id} disponibles.")

                task = task_service.update(task_id, message["results"])
                payload = task.model_dump(mode="json")
                logger.info(f"Update en DB de la tâche {task_id}.")
                await websocket.send_json(payload)
            except asyncio.CancelledError:
                logger.warning("WebSocket annulée")
                break

            except Exception as e:
                logger.error(f"Erreur boucle WS: {repr(e)}")
                break

    except WebSocketDisconnect:
        logger.info("Déconnexion du client.")

    finally:
        logger.info("Cleanup websocket")
