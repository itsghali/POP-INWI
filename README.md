# 📊 POP-INWI - Data Center Monitoring & Analytics

Une application d'intelligence opérationnelle développée avec Streamlit pour la surveillance, l'analyse des corrélations et la détection des causes racines des anomalies environnementales dans les Points de Présence (POP) télécoms.

---

## 🎯 Objectif du Projet

**POP-INWI** centralise les données des capteurs (Température, Puissance IT, États des portes, Climatisation) pour fournir des insights actionnables à 3 niveaux : **Local (POP)**, **Régional**, et **National**. 
L'application ne se contente pas d'afficher des graphiques : elle identifie de manière proactive *pourquoi* un POP surchauffe et recommande *comment* y remédier.

---

## ✨ Fonctionnalités Principales

### 🌍 Tableaux de Bord Multi-Niveaux
- **Rapport POP (`tab10`) :** Vue granulaire d'un site. Historique temporel, profils horaires moyens (Température vs Puissance IT), et statistiques détaillées (Min/Max/Moy/Médiane).
- **Rapport Région (`tab11`) :** Benchmarking des POPs d'une même région. Identification des sites critiques et classements de performance thermique.
- **Rapport National (`tab12`) :** Vue macroscopique "Toutes les régions". Couverture globale, moyennes nationales et export de rapports de synthèse de haut niveau.

### 🔗 Analyse des Corrélations (`tab07`)
- Calcul mathématique (Corrélation de Spearman) entre la *Température Ambiante* et ses facteurs d'influence (Porte, Temp. Extérieure, Unités CLIM, Puissance Générale).
- Code couleur automatisé pour la priorisation des actions (🔴 Critique, 🟠 Élevé, 🟡 Modéré).
- Diagnostic d'efficacité des unités de refroidissement (détection des CLIMs qui consomment mais ne refroidissent pas).

### 🔍 Incident Lens (Analyse des Causes Racines)
- Détection algorithmique des épisodes thermiques anormaux.
- Clustering temporel pour lier un symptôme (Ex: Température > 26°C) à sa véritable **cause racine** (Ex: Panne simultanée CLIM A + CLIM B, ou porte restée ouverte 45 minutes).
- Génération d'un plan d'action préventif/correctif avec un taux de confiance (%).

### 🚀 Moteur de Données Haute Performance
- **Architecture Data Models :** Typage fort des données (via `PopDataset`).
- **SQLite Single Source of Truth :** Accès ultra-rapide via `data_raw.db`.
- **Smart Caching :** Intégration de `st.cache_data` et d'une détection de démarrage serveur (`startup_detection.py`) pour éliminer les rechargements de données inutiles.

---

## 🛠️ Stack Technique

- **Interface Utilisateur :** Streamlit
- **Manipulation des Données :** Pandas, Numpy
- **Visualisation :** Plotly (Graphiques interactifs, sous-graphiques, axes secondaires)
- **Base de Données / Stockage :** SQLite3, fichiers CSV (latin-1, utf-8-sig)
- **Langage :** Python 3.9+

---

## 📂 Architecture du Projet

```text
POP-INWI_v3/
├── data/                       # Dossier brut contenant les CSV (Hiérarchie Région/POP)
├── data_raw.db                 # Base SQLite (Single Source of Truth)
├── src/
│   ├── domain/                 # Entités métier
│   │   ├── data_models.py      # Définition de PopDataset et mapping des colonnes
│   │   └── exceptions.py       # Gestion des erreurs custom
│   ├── features/               
│   │   └── incident_lens/      # Logique de regroupement des anomalies
│   ├── incident_lens/          # Moteur d'Analyse des incidents
│   │   ├── analyzer.py         # Identification des causes
│   │   ├── detector.py         # Détection des seuils (temp_min/temp_max)
│   │   ├── preprocessor.py     # Nettoyage robuste et normalisation des CSV
│   │   └── recommender.py      # Moteur de recommandations
│   ├── services/               # Couche d'accès aux données
│   │   ├── analytics_service.py# Moteur de corrélation
│   │   ├── cache_service.py    # Mise en cache en mémoire / session state
│   │   ├── pop_loader.py       # Chargement depuis le repo
│   │   ├── pop_repository.py   # Interactions avec SQLite (Indexation, Requêtes)
│   │   └── preload_service.py  # Préchargement des données en tâche de fond
│   ├── ui/                     # Interface Streamlit
│   │   ├── incident_lens_ui.py # Interface d'investigation
│   │   └── tabs/               # Onglets principaux du Dashboard
│   │       ├── tab07_correlations.py
│   │       ├── tab10_rapport_pop.py
│   │       ├── tab11_rapport_region.py
│   │       └── tab12_rapport_national.py
│   └── utils/                  # Utilitaires
│       └── startup_detection.py# Prévention du rechargement au rafraîchissement
└── requirements.txt            # Dépendances du projet
```

---

## ⚙️ Installation & Lancement

1. **Cloner le dépôt et accéder au dossier :**
   ```bash
   git clone <url-du-repo>
   cd POP-INWI_v3
   ```

2. **Créer et activer un environnement virtuel (Recommandé) :**
   ```bash
   python -m venv venv
   # Sous Windows :
   venv\Scripts\activate
   # Sous macOS/Linux :
   source venv/bin/activate
   ```

3. **Installer les dépendances :**
   ```bash
   pip install -r requirements.txt
   ```

4. **Préparer les données :**
   Vérifiez que la base de données `data_raw.db` ou les répertoires `data/REGION/POP/` contiennent bien vos métriques (Température Ambiante, Température Extérieure, P.Active CLIM, Etat Porte, etc.).

5. **Lancer l'application :**
   ```bash
   streamlit run main.py
   ```

---

## 📖 Format des Données (Standard attendu)

Le `preprocessor.py` et le `pop_repository.py` sont capables de lire de multiples formats (latine-1, UTF-8 avec BOM, séparateurs `,` ou `;`), mais les colonnes normalisées extraites par l'application sont :

- `Timestamp` : Format Date/Heure de l'enregistrement.
- `T°C AMBIANTE` / `Temp_Ambiante` : Température interne du POP.
- `T°C EXTERIEURE` / `Temp_Exterieure` : Température environnementale.
- `P_Active Générale` / `Puissance_Generale` : Puissance électrique totale (kW).
- `P_Active CLIM` / `Puissance_CLIM` : Puissance dédiée au refroidissement.
- `Puissance_IT` : Puissance dédiée aux serveurs/routeurs (Calculée si absente).
- `Etat de porte` / `Porte_Status` : Binaire ou Texte (Ouvert/Fermé).
- `CLIM_[A-H]_Status` : État des unités de climatisation.

---

## 👨‍💻 Maintenabilité et Extension

- Pour ajouter de nouveaux **onglets**, créez un fichier `tabXX_nom.py` dans `src/ui/tabs/` en exposant une fonction `render_tab(...)`.
- Pour modifier la **logique d'alerte** thermique de l'Incident Lens, modifiez les seuils configurables (par défaut : 20.0°C - 26.0°C) accessibles dans l'interface UI de l'outil ou dans `detector.py`.
- Si le schéma de données change, mettez à jour les constantes dans `src/domain/data_models.py` (notamment `DATA_FILE_KEYS` et `CORE_METRICS`).
