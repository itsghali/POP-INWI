# 📊 POP-INWI — Tableau de Bord de Surveillance des Centres de Données

Un **tableau de bord de surveillance basé sur Streamlit** pour les centres de données INWI (PDI — Points de Présence) au Maroc. Il fournit une surveillance environnementale en temps réel, une détection des incidents, une analyse de corrélation et des rapports automatisés dans plusieurs régions et sites.

---

## 🚀 Fonctionnalités

- **Support multi-régions** — Agadir, Casablanca, Laâyoune, Marrakech, Meknès, Oujda, Rabat, Tanger
- **13 onglets interactifs** comprenant :
  - 🌡️ Aperçu et surveillance de la température ambiante
  - 📈 Analyse temporelle et tendances
  - 🔍 Analyse Exploratoire des Données (EDA)
  - ❄️ Analyse de climatisation
  - 🚪 Analyse des ouvertures de porte
  - 🔎 Incident Lens — détection automatique des incidents
  - 🔗 Analyse de corrélation
  - 🌡️ Détection des changements de température
  - 💰 Simulation des coûts
  - 📋 Rapports au niveau PDI, régional et national
  - 📊 Comparaison multi-PDI
- **Détection automatique des incidents** utilisant des algorithmes de détection d'anomalies
- **Analyse des causes externes** — distingue les défaillances internes des pics de température externes
- **Chargement de données optimisé** avec mise en cache pour plusieurs PDI
- **Rapports adaptés à l'impression** avec styles CSS pour l'impression
- **Base de données SQLite** — migration depuis les fichiers CSV vers une base de données centralisée pour améliorer les performances et la scalabilité
- **Architecture modulaire** — application `app.py` refactorisée en modules distincts pour une meilleure maintenabilité et extensibilité

---

## 🗂️ Structure du Projet

```
POP-INWI/
│
├── app.py                          # Point d'entrée principal de l'application Streamlit
├── data_cleaning.py                # Nettoyage et prétraitement des données
├── requirements.txt                # Dépendances Python
│
├── data/                           # Fichiers de données CSV organisés par région/PDI (source originale)
│   ├── Agadir/
│   ├── Casablanca/
│   ├── Laâyoune/
│   ├── Marrakech/
│   ├── Meknès/
│   ├── Oujda/
│   ├── Rabat/
│   └── Tanger/
│
├── src/
│   ├── core/                       # Gestion des données de base
│   │   ├── data_loader.py          # Chargement des données et optimisation multi-PDI
│   │   ├── cache_manager.py        # Gestion du cache et préchargement
│   │   ├── database.py             # Connexion et requêtes de base de données SQLite
│   │   └── data_filter.py          # Filtrage par plage de dates et validation
│   │
│   ├── ui/                         # Composants de l'interface utilisateur
│   │   ├── sidebar.py              # Barre latérale de sélection région/PDI
│   │   ├── period_selector.py      # Sélecteur de période de dates
│   │   ├── incident_lens_ui.py     # Interface Incident Lens
│   │   ├── styles.py               # Thèmes CSS et styles d'impression
│   │   ├── app_orchestrator.py     # Orchestration des onglets
│   │   └── tabs/                   # 13 composants d'onglets modulaires
│   │       ├── tab01_vue_ensemble.py
│   │       ├── tab02_analyse_temporelle.py
│   │       ├── tab03_analyses_eda.py
│   │       ├── tab04_analyse_clim.py
│   │       ├── tab05_analyse_porte.py
│   │       ├── tab06_incident_lens.py
│   │       ├── tab07_correlations.py
│   │       ├── tab08_changement_temp.py
│   │       ├── tab09_simulation_couts.py
│   │       ├── tab10_rapport_pop.py
│   │       ├── tab11_rapport_region.py
│   │       ├── tab12_rapport_national.py
│   │       └── tab13_comparaison_pops.py
│   │
│   ├── analysis/
│   │   ├── anomaly_analyzer.py     # Logique de détection d'anomalies
│   │   └── exterior_cause.py       # Analyse des causes externes
│   │
│   ├── incident_lens/
│   │   ├── detector.py             # Moteur de détection d'incidents
│   │   └── analyzer-improved.py   # Analyseur d'incidents amélioré
│   │
│   ├── config/
│   │   └── settings.py             # Configuration de l'application
│   │
│   └── utils/
│       └── startup_detection.py    # Détection du démarrage du serveur
│
├── scripts/                        # Scripts utilitaires
│   ├── csv_to_sqlite.py            # Conversion des données CSV en SQLite
│   └── sync_missing_pops_to_db.py  # Synchronisation des PDI manquants dans la base de données
│
└── reports/                        # Rapports générés et exports
    ├── csv_columns_report.csv
    └── csv_columns_report.json
```

---

## 🛠️ Installation

1. **Cloner le référentiel**

   ```bash
   git clone https://github.com/itsghali/POP-INWI.git
   cd POP-INWI
   ```

2. **Créer et activer un environnement virtuel** (recommandé)

   ```bash
   python -m venv venv
   source venv/bin/activate       # Linux/macOS
   venv\Scripts\activate          # Windows
   ```

3. **Installer les dépendances**

   ```bash
   pip install -r requirements.txt
   ```

4. **Ajouter vos fichiers de données**

   Placez vos fichiers de données CSV dans les répertoires appropriés `data/<Région>/<PDI>/`.

5. **Initialiser la base de données** (optionnel si utilisation d'une base de données existante)

   ```bash
   python scripts/csv_to_sqlite.py
   ```

   Cela convertira les fichiers CSV en base de données SQLite pour améliorer les performances.

---

## ▶️ Lancer l'Application

```bash
streamlit run app.py
```

Le tableau de bord sera disponible à `http://localhost:8501` par défaut.

---

## 📦 Dépendances

| Paquet | Version |
|---|---|
| streamlit | 1.29.0 |
| pandas | 2.1.4 |
| numpy | 1.26.2 |
| plotly | 5.18.0 |
| seaborn | 0.13.0 |
| matplotlib | 3.8.2 |
| scipy | 1.11.4 |
| scikit-learn | ≥ 1.3.0 |
| networkx | ≥ 3.0 |
| openpyxl | 3.1.2 |
| kaleido | 0.2.1 |
| sqlite3 | Intégré |

---

## 🏗️ Architecture

L'application suit une **architecture modulaire** avec une séparation claire des préoccupations :

### 🔧 Changements Majeurs

#### 1. **Migration vers la Base de Données SQLite**
L'application a été migrée des fichiers CSV vers une **base de données SQLite centralisée**, offrant :
- **Performances améliorées** — Requêtes plus rapides et indexation de base de données
- **Scalabilité** — Gestion efficace de grandes quantités de données
- **Intégrité des données** — Contraintes et transactions ACID
- **Accès concurrent** — Meilleure gestion des accès utilisateur simultanés

Les scripts `csv_to_sqlite.py` et `sync_missing_pops_to_db.py` facilitent la conversion et la synchronisation des données.

#### 2. **Architecture Modularisée de l'Application**
Le fichier `app.py` a été refactorisé en modules distincts pour une meilleure maintenabilité :
- **`src/core/`** — Logique de chargement des données, mise en cache et filtrage
- **`src/ui/`** — Tous les composants d'interface utilisateur, y compris 13 modules d'onglets indépendants
- **`src/analysis/`** — Détection d'anomalies et analyse des causes externes
- **`src/incident_lens/`** — Moteur de détection et d'analyse des incidents automatisés
- **`src/config/`** — Paramètres d'application centralisés
- **`src/utils/`** — Fonctions utilitaires et outils

### Composants Clés

- **`app.py`** — Point d'entrée ; orchestre la charge des données du module `core` et l'interface utilisateur via `app_orchestrator`
- **`src/core/database.py`** — Interface de la base de données SQLite pour toutes les opérations de données
- **`src/ui/app_orchestrator.py`** — Orchestre les 13 onglets indépendants
- **`src/ui/sidebar.py`** — Sélection dynamique des régions et PDI
- **`src/ui/tabs/`** — 13 modules d'onglets indépendants et réutilisables
- **`scripts/csv_to_sqlite.py`** — Utilitaire de migration des données CSV vers SQLite

---

*Tableau de Bord de Surveillance des Centres de Données | © 2025 INWI*
