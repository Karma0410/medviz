# NeuroVolumetry: Serveur d'Analyse (Backend)

Ce répertoire contient la base de l'application backend de **NeuroVolumetry**. Ce serveur léger est écrit en Python en utilisant le framework **FastAPI** et s'exécute de façon autonome.

---

## Choix de Conception de la Base (Squelette Simplifié)

Afin d'obtenir un prototype simple, fiable et portable, nous avons mis en œuvre les simplifications suivantes :
1. **Remplacement de MinIO (Stockage Disque Classique) :** Plus besoin d'un conteneur d'object storage ou d'appels S3 complexes. Les fichiers originaux et les masques générés sont écrits sous forme de fichiers classiques sur le disque dur du serveur dans les dossiers `data/uploads/` et `data/masks/`.
<!-- 2. **Remplacement de Celery/Redis (Threads de fond FastAPI) :** Le démarrage de la tâche scientifique s'effectue de manière asynchrone via les `BackgroundTasks` natives de FastAPI, sans nécessiter de file d'attente Redis externe. -->

---

## Structure du Répertoire

```
Backend/
├── modules/            # Modules additionnels
├── data/               # Généré au démarrage
│   ├── uploads/        # Dossier de stockage disque des IRM d'origine (.nii, .nii.gz)
│   └── masks/          # Dossier de stockage disque des masques calculés (.nii, .nii.gz)
├── main.py             # Points d'entrée de l'API (FastAPI REST endpoints)
├── pyproject.toml      # Dépendances Python (fastapi, uvicorn, nibabel, numpy...)
└── Dockerfile          # Configuration d'empaquetage Docker
```

---

## Schéma de la Base de Données

La table `analyses` est créée automatiquement avec la structure suivante :

| Colonne | Type | Description |
| :--- | :--- | :--- |
| `task_id` | `TEXT` (PK) | UUID unique généré lors de l'upload. |
| `filename` | `TEXT` | Nom d'origine du fichier MRI téléversé. |
| `age` | `INTEGER` | Âge du patient (nécessaire pour la normalisation). |
| `status` | `TEXT` | État de la tâche (`pending`, `processing`, `completed`, `failed`). |
| `created_at` | `TEXT` | Horodatage de création au format ISO (UTC). |
| `left_volume` | `REAL` | Volume de l'hippocampe gauche calculé en mm³ (optionnel). |
| `right_volume` | `REAL` | Volume de l'hippocampe droit calculé en mm³ (optionnel). |
| `total_volume` | `REAL` | Volume hippocampique combiné en mm³ (optionnel). |
| `status_text` | `TEXT` | Rapport textuel d'analyse clinique et d'atrophie (optionnel). |

---

## API REST

### 1. Démarrer l'analyse
* **POST `/api/analyze`**
* Reçoit le fichier et l'âge dans un formulaire multi-parties. Crée une tâche, enregistre le fichier d'origine dans le dossier `data/uploads/`, puis délègue le traitement à un thread asynchrone avant de renvoyer l'ID de la tâche au format JSON.

<!-- TODO: changer en websocket -->
### 2. Suivre le traitement
* **GET `/api/tasks/{task_id}`**
* Renvoie les métadonnées et résultats de la tâche (y compris les volumes calculés si le statut est `completed`). 

### 3. Télécharger les fichiers
* **GET `/api/tasks/{task_id}/mri`** : Renvoie le fichier d'origine.
* **GET `/api/tasks/{task_id}/mask`** : Renvoie le masque calculé enregistré sur le disque dur dans `data/masks/`.

---

## Démarrage et Validation

### Installer les dépendances :
```bash
uv sync
```

<!-- TODO: mettre une testsuite des endpoints en place
### Valider le pipeline de test :
Une suite de tests unitaires est disponible pour valider la BD SQLite et le pipeline scientifique de simulation. Lancez :
```bash
python3 test_pipeline.py
``` -->

### Démarrer le serveur de développement :
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
*Le port 8000 doit être libre. L'interface Swagger interactive est disponible sur `http://localhost:8000/docs`.*
