"""
Session Service — Manages Streamlit session state initialization and access.

Centralizes all session state defaults and provides typed access helpers.
Replaces scattered session state bootstrapping across app.py and sidebar.py.
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.services.preload_service import get_first_loaded_pop, is_pop_loaded


def init_session_state() -> None:
    """Initialize all session state defaults. Safe to call multiple times."""
    defaults = {
        # POP cache (managed by cache_service)
        "pop_cache": {},
        # Current selection
        "selected_region_ui": None,
        "selected_pop_ui": None,
        # Progressive preload UX flags
        "user_selected_pop_locked": False,
        "auto_first_pop_applied": False,
        "preload_last_seen_revision": -1,
        # Period selection
        "start_date": None,
        "end_date": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def maybe_auto_select_first_ready_pop(store) -> bool:
    """Select the first ready POP unless the user already chose manually.

    Returns:
        True when the selection was updated in session state, else False.
    """
    if st.session_state.get("user_selected_pop_locked", False):
        return False

    first_ready = get_first_loaded_pop(store)
    if first_ready is None:
        return False

    first_region, first_pop = first_ready
    current_region = st.session_state.get("selected_region_ui")
    current_pop = st.session_state.get("selected_pop_ui")
    current_ready = (
        current_region is not None
        and current_pop is not None
        and is_pop_loaded(store, current_region, current_pop)
    )

    if st.session_state.get("auto_first_pop_applied", False) and current_ready:
        return False

    st.session_state.selected_region_ui = first_region
    st.session_state.selected_pop_ui = first_pop
    st.session_state.auto_first_pop_applied = True
    return True


def coerce_datetime(value, fallback: datetime) -> datetime:
    """Safely coerce a value to a Python datetime."""
    import pandas as pd

    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, str):
        try:
            return pd.to_datetime(value).to_pydatetime()
        except Exception:
            return fallback
    return fallback
