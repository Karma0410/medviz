# NeuroVolumetry: Interface Utilisateur (Frontend)

Ce répertoire contient le code source de l'interface utilisateur de **NeuroVolumetry**, développée avec React, TypeScript, TailwindCSS et Radix UI primitives. Il intègre le visualiseur d'images médicales WebGL **NiiVue**.

---

## Stack Technique

* **Framework :** React 18 & TypeScript (bâti avec Vite pour des temps de build ultra-rapides)
* **Styling :** TailwindCSS (mise en page moderne et responsive)
* **Composants d'interface :** Radix UI primitives (gestion accessible des onglets, fenêtres modales et curseurs de réglage 3D)
* **Rendu 3D Médical :** `@niivue/niivue` (WebGL-based)
* **Icônes :** Lucide-React

---

## Structure des Fichiers Clés

```
Frontend/
├── src/
│   ├── app/
│   │   ├── App.tsx             # Composant racine orchestrant l'UI et la logique
│   │   ├── NiivueViewer.tsx    # Wrapper React autour de la canvas NiiVue
│   │   └── translations.ts     # Dictionnaire de traduction (FR, EN, ES)
│   ├── styles/
│   │   └── index.css           # Thème CSS de base et styles globaux
│   ├── main.tsx                # Point d'entrée de l'application
│   └── ...
├── Dockerfile                  # Build multi-stage Docker (Node.js -> Nginx)
├── nginx.conf                  # Serveur web Nginx pour la mise en production
├── package.json                # Dépendances Node.js et scripts NPM
└── README.md                   # Ce fichier
```

---

## Intégration NiiVue & Masque de Superposition

Le composant [NiivueViewer.tsx](file:///wsl.localhost/Ubuntu/home/klervichoblet/Ing2/majeure/MedViz/medviz/Frontend/src/app/NiivueViewer.tsx) gère le canvas WebGL de NiiVue. Il a été adapté pour accepter deux sources de données principales :
1. **Un scan IRM T1 original** (sous forme d'objet `File` local ou d'URL `mriUrl` pointant vers le disque dur du backend).
2. **Un masque de segmentation** (fourni via l'URL `maskUrl` depuis le serveur).

Lorsqu'un masque est disponible, le composant charge les deux volumes simultanément :
```typescript
const volumesToLoad = [
  { url: primaryUrl },  // IRM en échelle de gris (fond)
  {
    url: maskUrl,       // Masque de segmentation
    colormap: 'red',    // Couleur de mise en évidence
    opacity: 0.65,      // Transparence semi-visible
    cal_min: 0.5,       // Ignore le fond noir (valeur 0)
    cal_max: 2.5        // Affiche les labels 1 (gauche) et 2 (droit)
  }
];
await nvRef.current.loadVolumes(volumesToLoad);
```

---

## Communication avec l'API Backend

Les appels à l'API sont configurés sur l'adresse du serveur local `http://localhost:8000`. Les flux principaux gérés dans [App.tsx](file:///wsl.localhost/Ubuntu/home/klervichoblet/Ing2/majeure/MedViz/medviz/Frontend/src/app/App.tsx) sont :

1. **Upload & Analyse :** Envoi de l'image NIfTI et de l'âge du patient via un formulaire multipart.
2. **Polling de statut :** Requête répétée toutes les secondes pour suivre l'état de l'analyse (`pending` -> `processing` -> `completed`).
3. **Mise à jour des métriques :** Une fois l'analyse terminée, l'interface télécharge le masque et met à jour les volumes hippocampiques (mm³) et le texte clinique.
4. **Historique :** Récupération de l'historique complet au chargement de l'application. Sélectionner un ancien examen recharge instantanément l'image et ses métriques.

---

## Lancement Local

1. Assurez-vous d'avoir installé **Node.js** (v18 ou supérieur recommandé).
2. Installez les paquets de dépendances :
   ```bash
   npm install
   ```
3. Démarrez le serveur de développement :
   ```bash
   npm run dev
   ```
4. Par défaut, le frontend se lancera sur `http://localhost:5173`.