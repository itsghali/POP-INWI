"""
Cache Service — Runtime caching helpers for preloaded POP datasets.

Design:
- Keep compatibility helpers for legacy on-demand access (`get_or_load`)
- Provide period and analytics caches over the global preloaded store
- Centralize cache invalidation for both Streamlit data/resource caches
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from src.domain.data_models import TIMESTAMP_COL
from src.domain.data_models import PopDataset, make_pop_id
from src.services.analytics_service import calculate_pop_correlations
from src.services.pop_loader import load_pop
from src.services.pop_repository import PopRepository
from src.services.preload_service import (
    clear_registered_stores,
    get_dataset,
    get_registered_store,
)

logger = logging.getLogger(__name__)

# Session state keys
_CACHE_KEY = "pop_cache"  # dict[str, PopDataset]


def _ensure_cache() -> dict[str, PopDataset]:
    """Ensure the POP cache exists in session state."""
    if _CACHE_KEY not in st.session_state:
        st.session_state[_CACHE_KEY] = {}
    return st.session_state[_CACHE_KEY]


def get_cached(pop_id: str) -> PopDataset | None:
    """Retrieve a cached PopDataset, or None if not cached."""
    cache = _ensure_cache()
    return cache.get(pop_id)


def get_or_load(
    repo: PopRepository, region: str, pop: str
) -> PopDataset:
    """Get a POP from cache or load it on demand.

    This is the primary entry point for the UI to get data.
    """
    pop_id = make_pop_id(region, pop)
    cache = _ensure_cache()

    cached = cache.get(pop_id)
    if cached is not None:
        logger.debug("Cache hit for %s", pop_id)
        return cached

    logger.info("Cache miss for %s, loading...", pop_id)
    dataset = load_pop(repo, region, pop)
    cache[pop_id] = dataset
    return dataset


def clear_cache() -> None:
    """Clear the entire POP cache."""
    st.session_state[_CACHE_KEY] = {}
    clear_registered_stores()
    # Also clear Streamlit's built-in cache
    st.cache_data.clear()
    st.cache_resource.clear()
    logger.info("POP cache cleared")


def cache_size() -> int:
    """Return number of cached POPs."""
    return len(_ensure_cache())


def cached_pop_ids() -> list[str]:
    """Return list of cached POP IDs."""
    return list(_ensure_cache().keys())


def _to_iso(dt_value) -> str:
    return pd.to_datetime(dt_value).isoformat()


def _normalize_pop_pairs(
    pop_pairs: tuple[tuple[str, str], ...] | list[tuple[str, str]]
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(region), str(pop)) for region, pop in pop_pairs))


def get_filtered_period_data(
    pop_id: str,
    start_date,
    end_date,
    db_version: str,
    load_revision: int = 0,
) -> pd.DataFrame:
    """Return cached period-filtered dataframe for one POP from preloaded store."""
    return _get_filtered_period_data_cached(
        pop_id=pop_id,
        start_iso=_to_iso(start_date),
        end_iso=_to_iso(end_date),
        db_version=db_version,
        load_revision=int(load_revision),
    )


@st.cache_data(show_spinner=False)
def _get_filtered_period_data_cached(
    pop_id: str,
    start_iso: str,
    end_iso: str,
    db_version: str,
    load_revision: int,
) -> pd.DataFrame:
    _ = load_revision  # part of cache key for progressive preload invalidation
    store = get_registered_store(db_version)
    if store is None:
        return pd.DataFrame()

    dataset = store.datasets_by_pop_id.get(pop_id)
    if dataset is None or dataset.is_empty:
        return pd.DataFrame()

    df = dataset.merged
    if TIMESTAMP_COL not in df.columns or df.empty:
        return pd.DataFrame()

    start = pd.to_datetime(start_iso)
    end = pd.to_datetime(end_iso)
    mask = (df[TIMESTAMP_COL] >= start) & (df[TIMESTAMP_COL] <= end)
    return df.loc[mask].copy()


def get_cached_multi_pop_data(
    pop_pairs: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    start_date,
    end_date,
    db_version: str,
    load_revision: int = 0,
) -> dict[tuple[str, str], pd.DataFrame]:
    """Return cached period-filtered data for multiple POPs."""
    normalized = _normalize_pop_pairs(pop_pairs)
    return _get_cached_multi_pop_data_cached(
        pop_pairs=normalized,
        start_iso=_to_iso(start_date),
        end_iso=_to_iso(end_date),
        db_version=db_version,
        load_revision=int(load_revision),
    )


@st.cache_data(show_spinner=False)
def _get_cached_multi_pop_data_cached(
    pop_pairs: tuple[tuple[str, str], ...],
    start_iso: str,
    end_iso: str,
    db_version: str,
    load_revision: int,
) -> dict[tuple[str, str], pd.DataFrame]:
    _ = load_revision  # part of cache key for progressive preload invalidation
    store = get_registered_store(db_version)
    if store is None:
        return {}

    start = pd.to_datetime(start_iso)
    end = pd.to_datetime(end_iso)
    result: dict[tuple[str, str], pd.DataFrame] = {}

    for region, pop in pop_pairs:
        dataset = get_dataset(store, region, pop)
        if dataset is None or dataset.is_empty:
            continue

        df = dataset.merged
        if TIMESTAMP_COL in df.columns and not df.empty:
            mask = (df[TIMESTAMP_COL] >= start) & (df[TIMESTAMP_COL] <= end)
            filtered = df.loc[mask].copy()
        else:
            filtered = df.copy()

        if not filtered.empty:
            result[(region, pop)] = filtered

    return result


def get_cached_pop_correlations(
    pop_pairs: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    metric: str,
    start_date,
    end_date,
    db_version: str,
    load_revision: int = 0,
) -> pd.DataFrame:
    """Return cached correlation dataframe for a multi-POP selection."""
    normalized = _normalize_pop_pairs(pop_pairs)
    return _get_cached_pop_correlations_cached(
        pop_pairs=normalized,
        metric=metric,
        start_iso=_to_iso(start_date),
        end_iso=_to_iso(end_date),
        db_version=db_version,
        load_revision=int(load_revision),
    )


@st.cache_data(show_spinner=False)
def _get_cached_pop_correlations_cached(
    pop_pairs: tuple[tuple[str, str], ...],
    metric: str,
    start_iso: str,
    end_iso: str,
    db_version: str,
    load_revision: int,
) -> pd.DataFrame:
    pop_data = _get_cached_multi_pop_data_cached(
        pop_pairs=pop_pairs,
        start_iso=start_iso,
        end_iso=end_iso,
        db_version=db_version,
        load_revision=load_revision,
    )
    return calculate_pop_correlations(pop_data, metric=metric, period=None)
