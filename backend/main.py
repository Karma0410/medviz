import os
import uuid
import logging
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline import run_segmentation_pipeline

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="NeuroVolumetry API - Squelette Base", version="0.1.0")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define file storage directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
MASK_DIR = os.path.join(DATA_DIR, "masks")

# =====================================================================
# TABLEAU DES TÂCHES EN MÉMOIRE
# TODO : Remplacer ce dictionnaire temporaire en mémoire par une vraie base de données.
# SQLite peut faire l'affaire pour un prototype local.
# =====================================================================
tasks = {}

@app.on_event("startup")
def startup_event():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(MASK_DIR, exist_ok=True)
    logger.info("Dossiers de stockage sur disque initialisés.")

def process_mri_task(task_id: str, file_path: str, mask_path: str, age: int):
    """Tâche de fond exécutant le pipeline scientifique."""
    try:
        tasks[task_id]["status"] = "processing"
        
        # Exécute le pipeline scientifique (squelette dans pipeline.py)
        results = run_segmentation_pipeline(file_path, mask_path, age)
        
        # TODO : Enregistrer ces résultats en base de données persistante
        tasks[task_id].update({
            "status": "completed",
            "left_volume": results["left_volume"],
            "right_volume": results["right_volume"],
            "total_volume": results["total_volume"],
            "status_text": results["status_text"]
        })
        logger.info(f"Tâche {task_id} terminée avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de la tâche {task_id} : {e}")
        tasks[task_id]["status"] = "failed"

@app.post("/api/analyze")
async def analyze_mri(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    age: int = Form(...)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")
    
    task_id = str(uuid.uuid4())
    logger.info(f"Nouvelle requête d'analyse reçue: file={file.filename}, age={age}, task_id={task_id}")

    # Gestion de l'extension de fichier
    file_ext = os.path.splitext(file.filename)[1]
    if file.filename.endswith(".nii.gz"):
        file_ext = ".nii.gz"
        
    saved_filename = f"{task_id}{file_ext}"
    saved_file_path = os.path.join(UPLOAD_DIR, saved_filename)
    mask_filename = f"{task_id}_mask{file_ext}"
    saved_mask_path = os.path.join(MASK_DIR, mask_filename)

    # Sauvegarde du fichier sur le disque
    try:
        with open(saved_file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        logger.error(f"Échec de la sauvegarde du fichier : {e}")
        raise HTTPException(status_code=500, detail=f"Impossible de sauvegarder le fichier sur le disque : {e}")

    # Enregistrement initial dans le dictionnaire temporaire
    # TODO : Remplacer l'insertion suivante par une requête SQL (INSERT INTO...)
    tasks[task_id] = {
        "task_id": task_id,
        "filename": file.filename,
        "age": age,
        "status": "pending",
        "left_volume": None,
        "right_volume": None,
        "total_volume": None,
        "status_text": None
    }

    # Lancement de la tâche de fond
    background_tasks.add_task(
        process_mri_task, 
        task_id=task_id, 
        file_path=saved_file_path, 
        mask_path=saved_mask_path, 
        age=age
    )

    return {
        "task_id": task_id,
        "filename": file.filename,
        "age": age,
        "status": "pending"
    }

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    # TODO Remplacer par une requête SELECT sur la base de données
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    return task

@app.get("/api/tasks/{task_id}/mri")
async def get_task_mri(task_id: str):
    # TODO : Récupérer le nom de fichier associé en interrogeant la BD
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    
    # Recherche du fichier sur le disque
    files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(task_id)]
    if not files:
         raise HTTPException(status_code=404, detail="Fichier IRM introuvable sur le serveur")
    
    file_path = os.path.join(UPLOAD_DIR, files[0])
    return FileResponse(file_path, media_type="application/octet-stream", filename=task["filename"])

@app.get("/api/tasks/{task_id}/mask")
async def get_task_mask(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Masque non généré ou analyse en cours")
    
    # Recherche du masque sur le disque
    files = [f for f in os.listdir(MASK_DIR) if f.startswith(task_id)]
    if not files:
         raise HTTPException(status_code=404, detail="Fichier Masque introuvable sur le disque")
    
    file_path = os.path.join(MASK_DIR, files[0])
    return FileResponse(file_path, media_type="application/octet-stream", filename=f"mask_{task['filename']}")

@app.get("/api/tasks")
async def list_tasks():
    # TODO : Remplacer par un SELECT * FROM analyses ORDER BY ...
    # Renvoie la liste en mémoire pour l'historique frontend
    return list(tasks.values())
