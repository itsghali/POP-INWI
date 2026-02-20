# 📊 POP-INWI — Data Center Monitoring Dashboard

A **Streamlit-based monitoring dashboard** for INWI data centers (POPs — Points of Presence) across Morocco. It provides real-time environmental monitoring, incident detection, correlation analysis, and automated reporting across multiple regions and sites.

---

## 🚀 Features

- **Multi-region support** — Agadir, Casablanca, Laayoune, Marrakech, Meknès, Oujda, Rabat, Tanger
- **13 interactive tabs** covering:
  - 🌡️ Overview & ambient temperature monitoring
  - 📈 Temporal analysis & trends
  - 🔍 Exploratory Data Analysis (EDA)
  - ❄️ Climatisation analysis
  - 🚪 Door opening analysis
  - 🔎 Incident Lens — automated incident detection
  - 🔗 Correlation analysis
  - 🌡️ Temperature change detection
  - 💰 Cost simulation
  - 📋 POP-level, region-level, and national reports
  - 📊 Multi-POP comparison
- **Automated incident detection** using anomaly detection algorithms
- **Exterior cause analysis** — distinguishes internal failures from external temperature spikes
- **Optimised data loading** with caching for multiple POPs
- **Print-friendly reports** with CSS print styles

---

## 🗂️ Project Structure

```
POP-INWI/
│
├── app.py                          # Main Streamlit application entry point
├── data_cleaning.py                # Data cleaning and preprocessing
├── requirements.txt                # Python dependencies
│
├── data/                           # CSV data files organised by region/POP
│   ├── Agadir/
│   ├── Casablanca/
│   ├── Laayoune/
│   ├── Marrakech/
│   ├── Meknès/
│   ├── Oujda/
│   ├── Rabat/
│   └── Tanger/
│
├── src/
│   ├── core/                       # Core data handling
│   │   ├── data_loader.py          # Data loading & multi-POP optimised loading
│   │   ├── cache_manager.py        # Cache & preloading management
│   │   └── data_filter.py          # Date range filtering & validation
│   │
│   ├── ui/                         # User interface components
│   │   ├── sidebar.py              # Region/POP selection sidebar
│   │   ├── period_selector.py      # Date period selector
│   │   ├── incident_lens_ui.py     # Incident Lens interface
│   │   ├── styles.py               # CSS themes & print styles
│   │   ├── app_orchestrator.py     # Tab orchestration
│   │   └── tabs/                   # 13 modular tab components
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
│   │   ├── anomaly_analyzer.py     # Anomaly detection logic
│   │   └── exterior_cause.py       # Exterior cause analysis
│   │
│   ├── incident_lens/
│   │   ├── detector.py             # Incident detection engine
│   │   └── analyzer-improved.py   # Improved incident analyzer
│   │
│   ├── config/
│   │   └── settings.py             # Application configuration
│   │
│   └── utils/
│       └── startup_detection.py    # Server startup detection
│
├── scripts/                        # Utility scripts
│   ├── csv_to_sqlite.py            # Convert CSV data to SQLite
│   └── sync_missing_pops_to_db.py  # Sync missing POPs to database
│
└── reports/                        # Generated reports & exports
    ├── csv_columns_report.csv
    └── csv_columns_report.json
```

---

## ⚙️ Prerequisites

- Python 3.9 or higher
- pip

---

## 🛠️ Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/itsghali/POP-INWI.git
   cd POP-INWI
   ```

2. **Create and activate a virtual environment** (recommended)

   ```bash
   python -m venv venv
   source venv/bin/activate       # Linux/macOS
   venv\Scripts\activate          # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Add your data files**

   Place your CSV data files in the appropriate `data/<Region>/<POP>/` directories.

---

## ▶️ Running the Application

```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501` by default.

---

## 📦 Dependencies

| Package | Version |
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

---

## 🏗️ Architecture

The application follows a **modular architecture** with clear separation of concerns:

- **`app.py`** — Entry point; loads data, manages session state, orchestrates the UI
- **`src/core/`** — Data loading, caching, and filtering logic
- **`src/ui/`** — All UI components, including 13 independent tab modules
- **`src/analysis/`** — Anomaly detection and exterior cause analysis
- **`src/incident_lens/`** — Automated incident detection and analysis engine
- **`src/config/`** — Centralised application settings

---

*Data Center Monitoring Dashboard | © 2025 INWI*
