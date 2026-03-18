"""
POP-INWI Dashboard — Main application entry point.

This is a thin orchestrator that:
1. Configures the page
2. Initializes services
3. Renders sidebar for user selection
4. Loads data on demand (via cache_service)
5. Delegates rendering to the dashboard orchestrator

All business logic lives in src/services/ and src/domain/.
All rendering logic lives in src/ui/.
"""
from __future__ import annotations

import logging
import warnings
from datetime import datetime

import pandas as pd
import streamlit as st

from src.domain.data_models import TIMESTAMP_COL
from src.services import cache_service
from src.services.pop_repository import PopRepository
from src.services.session_service import coerce_datetime, init_session_state
from src.ui.app_orchestrator import orchestrate_dashboard
from src.ui.sidebar import get_region_pop_selection
from src.ui.styles import apply_custom_css, apply_print_styles, render_page_header

warnings.filterwarnings("ignore")

from src.config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


# ---- Page config (must be first Streamlit call) ----

st.set_page_config(
    page_title="Centre de Données INWI - Tableau de Bord",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Initialize ----

init_session_state()
repo = PopRepository()

# ---- Sidebar: user selects region + POP ----

selected_region, selected_pop = get_region_pop_selection(repo)

# ---- Header + styles ----

render_page_header(selected_pop, selected_region)
apply_custom_css()
apply_print_styles()

# ---- Load data ----

try:
    dataset = cache_service.get_or_load(repo, selected_region, selected_pop)

    if dataset.is_empty:
        now = datetime.now()
        orchestrate_dashboard(
            pd.DataFrame(),
            pd.DataFrame(),
            now,
            now,
            selected_region,
            selected_pop,
        )
    else:
        merged_data = dataset.inject_metadata()

        # Prepare timestamps
        if TIMESTAMP_COL in merged_data.columns:
            merged_data[TIMESTAMP_COL] = pd.to_datetime(
                merged_data[TIMESTAMP_COL], errors="coerce", utc=False
            )
            merged_data = merged_data.dropna(subset=[TIMESTAMP_COL])

        if merged_data.empty:
            st.error("❌ Aucune donnée valide après préparation.")
            st.stop()

        # Determine date range
        now = datetime.now()
        ts_min = merged_data[TIMESTAMP_COL].min()
        ts_max = merged_data[TIMESTAMP_COL].max()
        default_start = coerce_datetime(ts_min, now)
        default_end = coerce_datetime(ts_max, now)

        # Use period selector dates if available
        start_date = default_start
        end_date = default_end
        if "unified_period" in st.session_state:
            period = st.session_state.unified_period
            sidebar_start = period.get("start_date")
            sidebar_end = period.get("end_date")
            if sidebar_start is not None and sidebar_end is not None:
                start_date = coerce_datetime(sidebar_start, start_date)
                end_date = coerce_datetime(sidebar_end, end_date)

        # Filter
        filtered_data = merged_data[
            (merged_data[TIMESTAMP_COL] >= start_date)
            & (merged_data[TIMESTAMP_COL] <= end_date)
        ]

        orchestrate_dashboard(
            filtered_data,
            merged_data,
            start_date,
            end_date,
            selected_region,
            selected_pop,
        )

except Exception as exc:
    logger.exception("Error loading dashboard data")
    st.error(f"❌ Erreur lors du chargement des données: {exc}")
    st.stop()

st.markdown("---")
st.caption("🏢 Data Center Monitoring Dashboard | © 2025")
