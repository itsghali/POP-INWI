"""
Session Service — Manages Streamlit session state initialization and access.

Centralizes all session state defaults and provides typed access helpers.
Replaces scattered session state bootstrapping across app.py and sidebar.py.
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st


def init_session_state() -> None:
    """Initialize all session state defaults. Safe to call multiple times."""
    defaults = {
        # POP cache (managed by cache_service)
        "pop_cache": {},
        # Current selection
        "selected_region_ui": None,
        "selected_pop_ui": None,
        # Period selection
        "start_date": None,
        "end_date": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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
