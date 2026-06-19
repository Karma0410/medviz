# NeuroVolumetry: Analyse Volumétrique de l'Hippocame

NeuroVolumetry est une application médicale Web end-to-end d'aide au diagnostic de la maladie d'Alzheimer. Elle permet d'importer une IRM cérébrale structurelle pondérée en T1 au format NIfTI, de visualiser le cerveau en 3D/multiplanaire via la bibliothèque NiiVue, et d'exécuter un pipeline de traitement d'images pour mesurer et comparer le volume des hippocampes gauche et droit par rapport à des courbes de référence normalisées par âge.

---

## Architecture Logicielle Simplifiée

Pour faciliter le déploiement et la maintenance du prototype, l'architecture a été simplifiée par rapport au plan initial :
* **Frontend :** Single-Page Application (SPA) bâtie en **React**, **Vite** et **TailwindCSS**, utilisant **NiiVue** pour le rendu 3D.
* **Backend :** API REST légère développée avec **FastAPI (Python)**.
* **Stockage de fichiers :** Stockage classique sur **disque dur local** (`Backend/data/uploads/` et `Backend/data/masks/`), éliminant la nécessité d'un serveur d'objets MinIO.
* **Base de données :** Base relationnelle légère **SQLite** intégrée sous forme de fichier (`Backend/data/database.db`), éliminant le besoin de configurer PostgreSQL.
* **Tâches en arrière-plan :** Utilisation des **`BackgroundTasks` asynchrones de FastAPI** exécutées dans des threads internes, remplaçant la file d'attente Redis + Celery.

```
                  ┌───────────────────────────────┐
                  │       Navigateur Client       │
                  │  (React UI + NiiVue Renderer) │
                  └──────────────┬────────────────┘
                                 │
                 Upload IRM /    │    Lecture IRM +
                 Infos Patient   │    Masque de Segment
                                 ▼
                  ┌───────────────────────────────┐
                  │        FastAPI Backend        │
                  │     (Port 8000 / Python)      │
                  └──────┬──────────────┬─────────┘
                         │              │
        Lecture / Écriture              │  Enregistrement Résultats
        Fichiers sur Disque             │  & Suivi des Tâches
                         ▼              ▼
                  ┌────────────┐  ┌────────────┐
                  │ Stockage   │  │   SQLite   │
                  │ sur Disque │  │  Database  │
                  └────────────┘  └────────────┘
```

---

## Structure du Projet

L'application est séparée en deux dossiers autonomes :

```
medviz/
├── .github/
│   └── workflows/
│       └── ci-cd.yml        # Pipeline CI/CD GitHub Actions
│
├── Backend/                 # Code source du backend Python FastAPI
│   ├── data/                # Dossier généré contenant la BD SQLite et les fichiers
│   ├── Dockerfile           # Script d'empaquetage Docker pour le backend
│   ├── main.py              # Points d'accès de l'API (upload, status, downloads)
│   ├── db.py                # Gestionnaire de base de données SQLite
│   ├── pipeline.py          # Squelette/Mock du traitement scientifique
│   └── README.md            # Documentation technique du backend
│
├── Frontend/                # Code source du frontend React
│   ├── src/                 # Code source TypeScript / React
│   │   ├── app/
│   │   │   ├── App.tsx      # Composant principal (UI, historique, formulaires)
│   │   │   └── NiivueViewer.tsx # Visualiseur NiiVue avec superposition de masque
│   │   └── ...
│   ├── Dockerfile           # Script d'empaquetage Docker pour le frontend
│   ├── nginx.conf           # Configuration du serveur web Nginx de production
│   └── README.md            # Documentation de l'interface utilisateur
│
├── docs/                    # Documents et guides réglementaires
│   └── IFU.md               # Manuel utilisateur / Instructions for Use (IFU)
│
├── docker-compose.yml       # Orchestrateur de production multi-conteneurs
├── deploy.sh                # Script de déploiement automatique en un clic
└── README.md                # Ce fichier
```

---

## Démarrage et Déploiement

### Déploiement Automatisé de Production
Le projet intègre un script de déploiement en un clic.
1. Assurez-vous que Docker et Docker Compose sont installés sur votre machine.
2. À la racine du projet, lancez :
   ```bash
   ./deploy.sh
   ```
   *Ce script va automatiquement pull les dernières modifications Git, éteindre les anciens conteneurs, recompiler les images Docker du frontend et du backend, et démarrer la stack en tâche de fond (daemon mode).*

3. L'application est accessible aux adresses suivantes :
   * **Interface Web (Frontend) :** `http://localhost:8080`
   * **Documentation Interactive API (Swagger) :** `http://localhost:8000/docs`
