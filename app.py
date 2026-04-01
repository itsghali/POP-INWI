"""
POP-INWI Dashboard — Main application entry point.

This is a thin orchestrator that:
1. Configures the page
2. Initializes services
3. Renders sidebar for user selection
4. Uses globally preloaded in-memory datasets
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
from src.services.preload_service import (
    get_dataset,
    get_preload_snapshot,
    get_preloaded_store,
    get_load_revision,
    is_pop_loaded,
)
from src.services.session_service import (
    coerce_datetime,
    init_session_state,
    maybe_auto_select_first_ready_pop,
)
from src.ui.app_orchestrator import orchestrate_dashboard
from src.ui.sidebar import get_region_pop_selection
from src.ui.styles import apply_custom_css, apply_print_styles, render_page_header

warnings.filterwarnings("ignore")

from src.config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def _start_preload_refresh_fragment(store) -> None:
    """Trigger lightweight reruns when preload progress changes."""
    if not hasattr(st, "fragment"):
        return

    @st.fragment(run_every="2s")
    def _preload_refresh_tick():
        snapshot = get_preload_snapshot(store)
        last_seen = st.session_state.get("preload_last_seen_revision", -1)
        if snapshot.load_revision != last_seen:
            st.session_state.preload_last_seen_revision = snapshot.load_revision
            st.rerun()

    _preload_refresh_tick()


# ---- Page config (must be first Streamlit call) ----

st.set_page_config(
    page_title="Centre de Données INWI - Tableau de Bord",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Initialize ----

init_session_state()
store = get_preloaded_store()
_start_preload_refresh_fragment(store)

# ---- Auto-select first ready POP (before any user selection) ----

maybe_auto_select_first_ready_pop(store)

# ---- Sidebar: user selects region + POP ----

selected_region, selected_pop = get_region_pop_selection(store)

# ---- Header + styles ----

render_page_header(selected_pop, selected_region)
apply_custom_css()
apply_print_styles()

# ---- Load data ----

try:
    preload_snapshot = get_preload_snapshot(store)
    selected_pop_ready = is_pop_loaded(store, selected_region, selected_pop)
    dataset = get_dataset(store, selected_region, selected_pop)

    if dataset is None:
        now = datetime.now()
        orchestrate_dashboard(
            pd.DataFrame(),
            pd.DataFrame(),
            now,
            now,
            selected_region,
            selected_pop,
            store=store,
            selected_pop_loading=not preload_snapshot.is_complete,
            preload_snapshot=preload_snapshot,
        )
    elif dataset.is_empty:
        now = datetime.now()
        orchestrate_dashboard(
            pd.DataFrame(),
            pd.DataFrame(),
            now,
            now,
            selected_region,
            selected_pop,
            store=store,
            selected_pop_loading=False,
            preload_snapshot=preload_snapshot,
        )
    else:
        merged_data = dataset.inject_metadata()

        # Prepare timestamps
        if TIMESTAMP_COL in merged_data.columns:
            if not pd.api.types.is_datetime64_any_dtype(
                merged_data[TIMESTAMP_COL]
            ):
                merged_data[TIMESTAMP_COL] = pd.to_datetime(
                    merged_data[TIMESTAMP_COL], errors="coerce", utc=False
                )
            merged_data = merged_data.loc[
                merged_data[TIMESTAMP_COL].notna()
            ].copy()

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

        # Filter from preloaded in-memory store (cached by period + db version)
        filtered_data = cache_service.get_filtered_period_data(
            pop_id=dataset.pop_id,
            start_date=start_date,
            end_date=end_date,
            db_version=store.db_version,
            load_revision=get_load_revision(store),
        )
        if not filtered_data.empty:
            filtered_data = filtered_data.copy()
            filtered_data["Region"] = dataset.region
            filtered_data["POP"] = dataset.pop
            filtered_data["POP_ID"] = dataset.pop_id

        orchestrate_dashboard(
            filtered_data,
            merged_data,
            start_date,
            end_date,
            selected_region,
            selected_pop,
            store=store,
            selected_pop_loading=not selected_pop_ready,
            preload_snapshot=preload_snapshot,
        )

except Exception as exc:
    logger.exception("Error loading dashboard data")
    st.error(f"❌ Erreur lors du chargement des données: {exc}")
    st.stop()

st.markdown("---")
st.caption("🏢 Data Center Monitoring Dashboard | © 2025")
