import os
import json
import logging
from pathlib import Path

from .pipeline import run_segmentation_pipeline
from .redis_helpers import *

# Doit correspondre à DATA_DIR/MASK_DIR de backend/main.py — partagé via le
# volume "shared_data" monté sur /app/data dans les deux conteneurs.
MASK_DIR = "/app/data/masks"


def _mask_output_path(task_id: str, mri_path: str) -> str:
    name = Path(mri_path).name
    ext = ".nii.gz" if name.endswith(".nii.gz") else Path(mri_path).suffix
    os.makedirs(MASK_DIR, exist_ok=True)
    return os.path.join(MASK_DIR, f"{task_id}_mask{ext}")


def main():
    logger = logging.getLogger("worker")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("Worker démarré, en attente de tâches…")
    while True:
        try:
            result = task_pop()
            if result is None:
                continue
            _, raw = result
            task = json.loads(raw)
            task_id = task["task_id"]
            mri_path = task["mri_path"]
            already_preprocessed = task.get("already_preprocessed")
            mask_output_path = _mask_output_path(task_id, mri_path)
            logger.info(f"Traitement de la tâche : {mri_path}")
            results = run_segmentation_pipeline(mri_path, already_preprocessed, mask_output_path)
            logger.info(f"Résultats : {results}")
            enqueue_result(task_id, results)
        except Exception as e:
            logger.error(f"Erreur : {e}")


if __name__ == "__main__":
    main()
