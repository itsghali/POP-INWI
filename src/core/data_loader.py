"""
Data loader — backward-compatible wrapper around the new service layer.

Tabs and other modules that import `load_data` from here will continue to work.
New code should use src.services.pop_loader.load_pop() or cache_service.get_or_load().
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from src.services.pop_loader import load_pop
from src.services.pop_repository import PopRepository

logger = logging.getLogger(__name__)


@st.cache_data
def load_data(region: str, pop: str, silent: bool = False):
    """Load data for a region/POP pair.

    Returns:
        Tuple of ({}, merged_dataframe) for backward compatibility.
    """
    try:
        repo = PopRepository()
        dataset = load_pop(repo, region, pop)
        if dataset.is_empty:
            return {}, pd.DataFrame()
        return {}, dataset.merged
    except Exception as exc:
        if not silent:
            logger.error("Error loading %s/%s: %s", region, pop, exc)
        return {}, pd.DataFrame()


def load_multiple_pops_optimized(pops_to_load):
    """Load multiple POPs, using session cache where possible."""
    from src.services import cache_service

    all_pops_data = {}
    cached_count = 0
    fresh_count = 0

    repo = PopRepository()
    for region, pop in pops_to_load:
        dataset = cache_service.get_or_load(repo, region, pop)
        if not dataset.is_empty:
            all_pops_data[(region, pop)] = dataset.inject_metadata()
            cached_count += 1
        else:
            fresh_count += 1

    return all_pops_data, cached_count, fresh_count
