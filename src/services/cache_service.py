"""
Cache Service — Simple session-state cache for loaded POP datasets.

Replaces the complex preload thread/queue/event system with on-demand loading + caching.
POPs are loaded when selected and cached in session state for instant switching.

Design:
- No background threads, no queues, no events
- Load on demand, cache in st.session_state
- Predictable state transitions on Streamlit reruns
"""
from __future__ import annotations

import logging

import streamlit as st

from src.domain.data_models import PopDataset, make_pop_id
from src.services.pop_loader import load_pop
from src.services.pop_repository import PopRepository

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
    # Also clear Streamlit's built-in cache
    st.cache_data.clear()
    logger.info("POP cache cleared")


def cache_size() -> int:
    """Return number of cached POPs."""
    return len(_ensure_cache())


def cached_pop_ids() -> list[str]:
    """Return list of cached POP IDs."""
    return list(_ensure_cache().keys())
