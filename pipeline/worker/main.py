import os
import sys
import json
import logging
from urllib.parse import urlparse

import redis

from .pipeline import run_segmentation_pipeline

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_parsed = urlparse(_redis_url)
redisClient = redis.Redis(
    host=_parsed.hostname,
    port=_parsed.port or 6379,
    db=int(_parsed.path.lstrip("/") or 0),
)


def main():
    logger = logging.getLogger("worker")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    print("Worker démarré, en attente de tâches…", flush=True)
    while True:
        try:
            result = redisClient.blpop("tasks", timeout=0)
            if result is None:
                continue
            _, raw = result
            task = json.loads(raw)
            mri_path = task["mri_path"]
            already_preprocessed = task.get("already_preprocessed")
            print(f"Traitement de la tâche : {mri_path}", flush=True)
            results = run_segmentation_pipeline(mri_path, already_preprocessed)
            print(f"Résultats : {results}", flush=True)
        except Exception as e:
            print(f"Erreur : {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
