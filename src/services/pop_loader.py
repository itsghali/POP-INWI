"""
POP Loader — High-level service that orchestrates load → clean → merge for a POP.

This replaces the scattered loading logic that was in data_cleaning.py, data_loader.py,
cache_manager.py, and app.py. Single entry point for getting a PopDataset.
"""
from __future__ import annotations

import logging

import pandas as pd

from src.domain.data_models import PopDataset, make_pop_id
from src.services.data_cleaner import clean_all
from src.services.data_merger import merge_cleaned_data
from src.services.pop_repository import PopRepository

logger = logging.getLogger(__name__)


def load_pop(
    repo: PopRepository, region: str, pop: str
) -> PopDataset:
    """Load, clean, merge data for a single POP.

    Args:
        repo: PopRepository instance.
        region: Region name.
        pop: POP name.

    Returns:
        PopDataset (may have empty merged if data is unavailable).
    """
    pop_id = make_pop_id(region, pop)
    logger.info("Loading POP %s/%s", region, pop)

    raw_tables = repo.load_raw_tables(region, pop)
    if not raw_tables:
        logger.warning("No raw data found for %s/%s", region, pop)
        return PopDataset(
            region=region, pop=pop, pop_id=pop_id, merged=pd.DataFrame()
        )

    cleaned = clean_all(raw_tables)
    if not cleaned:
        logger.warning("All data empty after cleaning for %s/%s", region, pop)
        return PopDataset(
            region=region, pop=pop, pop_id=pop_id, merged=pd.DataFrame()
        )

    merged = merge_cleaned_data(cleaned)

    # Ensure Timestamp is proper datetime
    if "Timestamp" in merged.columns:
        merged["Timestamp"] = pd.to_datetime(
            merged["Timestamp"], errors="coerce", utc=False
        )
        merged = merged.dropna(subset=["Timestamp"])

    dataset = PopDataset(
        region=region, pop=pop, pop_id=pop_id, merged=merged
    )
    logger.info(
        "POP %s loaded: %d rows, metrics: %s",
        pop_id,
        len(merged),
        sorted(dataset.available_metrics),
    )
    return dataset
