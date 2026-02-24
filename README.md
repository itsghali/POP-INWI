# 📊 POP-INWI — Data Center Monitoring Dashboard

A **Streamlit-based monitoring dashboard** for INWI data centers (POPs — Points of Presence) across Morocco. It provides environmental monitoring, incident detection, correlation analysis, and automated reporting across multiple regions and sites.

---

## 🚀 Features

- **Multi-region support** — Agadir, Casablanca, Laayoune, Marrakech, Meknès, Oujda, Rabat, Tanger
- **13 interactive tabs** covering:
  - 🌡️ Overview & ambient temperature monitoring
  - 📈 Temporal analysis & trends
  - 🔍 Exploratory Data Analysis (EDA)
  - ❄️ Climatisation analysis
  - 🚪 Door opening analysis
  - 🔎 Incident Lens — automated incident detection & root-cause exploration
  - 🔗 Correlation analysis
  - 🌡️ Temperature change detection
  - 💰 Cost simulation
  - 📋 POP-level, region-level, and national reports
  - 📊 Multi-POP comparison
- **Automated incident detection** (power/door/CLIM/composite incidents)
- **Exterior cause analysis** — helps distinguish internal failures from external temperature spikes
- **Optimised data loading** with caching / preloading for multiple POPs
- **Print-friendly reports** with custom CSS print styles

---

## 🗂️ Project Structure

```
POP-INWI/
│
├── app.py                          # Main Streamlit application entry point
├── data_cleaning.py                # Data cleaning and preprocessing helpers
├── requirements.txt                # Python dependencies
├── README.md                       # Project documentation (this file)
│
├── data_raw.db                     # SQLite database generated from CSVs (see scripts/)
├── logo_inwi.png                   # UI/branding asset used in the app
├── Rapport d'Avancement.pdf        # Project progress report / documentation
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
│   │   ├── incident_lens_ui.py     # Incident Lens UI (analysis workflow + visuals)
│   │   ├── styles.py               # CSS themes & print styles
│   │   ├── app_orchestrator.py     # Tab orchestration (creates & renders 13 tabs)
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
│   │   └── exterior_cause.py       # Exterior cause analysis (ambient spike causes)
│   │
│   ├── incident_lens/              # Incident detection engine & analysis helpers
│   │   ├── detector.py             # Incident detection engine
│   │   └── analyzer-improved.py    # Improved incident analyzer
│   │
│   ├── config/
│   │   └── settings.py             # Application configuration
│   │
│   └── utils/
│       └── startup_detection.py    # Server startup detection
│
├── scripts/                        # Utility scripts (see scripts/README.md)
│   ├── csv_to_sqlite.py            # Convert CSV data to SQLite
│   └── sync_missing_pops_to_db.py  # Sync missing POPs to database
│
└── reports/                        # Generated reports & exports (see reports/README.md)
    ├── README.md
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

*Data Center Monitoring Dashboard | © 2025 INWI*
