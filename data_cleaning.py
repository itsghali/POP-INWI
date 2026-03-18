"""
DataCleaner — Backward-compatible facade.

The actual implementation has been split into:
- src.services.pop_repository (DB access, discovery)
- src.services.data_cleaner (cleaning/normalization)
- src.services.data_merger (merge logic)
- src.services.analytics_service (correlations)

This file exists so that modules importing `from data_cleaning import DataCleaner`
continue to work. New code should import from src.services directly.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.services.pop_repository import PopRepository
from src.services.data_cleaner import clean_all
from src.services.data_merger import merge_cleaned_data
from src.services.analytics_service import calculate_pop_correlations

logger = logging.getLogger(__name__)


class DataCleaner:
    """Backward-compatible wrapper delegating to new service layer."""

    def __init__(self, data_dir="data"):
        db_path = Path.cwd() / "data_raw.db"
        try:
            self._repo = PopRepository(db_path)
        except Exception:
            self._repo = None
            logger.warning("PopRepository unavailable (DB not found)")

    def get_regions(self) -> list[str]:
        if self._repo is None:
            return []
        return self._repo.get_regions()

    def get_pops(self, region: str) -> list[str]:
        if self._repo is None:
            return []
        return self._repo.get_pops(region)

    def has_pop_data(self, region: str, pop: str) -> bool:
        if self._repo is None:
            return False
        return self._repo.has_pop_data(region, pop)

    def load_pops_data(self, pop_list=None, regions=None, region=None, pop=None):
        """Load data for one or more POPs."""
        if self._repo is None:
            return {}, pd.DataFrame()

        # Single POP
        if region and pop and not pop_list and not regions:
            raw = self._repo.load_raw_tables(region, pop)
            cleaned = clean_all(raw)
            if cleaned:
                merged = merge_cleaned_data(cleaned)
                if not merged.empty:
                    merged["Region"] = region
                    merged["POP"] = pop
                    merged["POP_ID"] = f"{region}_{pop}"
                    return cleaned, merged
            return {}, pd.DataFrame()

        # Multiple POPs
        if not pop_list:
            pop_list = []
            target_regions = regions if regions else self.get_regions()
            for reg in target_regions:
                for p in self.get_pops(reg):
                    pop_list.append((reg, p))

        all_data = {}
        for reg, p in pop_list:
            try:
                raw = self._repo.load_raw_tables(reg, p)
                cleaned = clean_all(raw)
                if cleaned:
                    merged = merge_cleaned_data(cleaned)
                    if not merged.empty:
                        merged["Region"] = reg
                        merged["POP"] = p
                        merged["POP_ID"] = f"{reg}_{p}"
                        all_data[(reg, p)] = merged
            except Exception as exc:
                logger.error("Error loading %s/%s: %s", reg, p, exc)
        return all_data

    def merge_all_data(self, cleaned_data):
        """Merge cleaned data dictionaries."""
        if isinstance(cleaned_data, pd.DataFrame):
            return cleaned_data
        return merge_cleaned_data(cleaned_data)

    def calculate_pop_correlations(self, all_pops_data, metric="Temp_Ambiante", period=None):
        return calculate_pop_correlations(all_pops_data, metric, period)

    @staticmethod
    def make_streamlit_safe(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize DataFrame for safe Streamlit rendering."""
        if df.empty:
            return df.copy()
        df = df.copy()
        df = df.replace([np.inf, -np.inf], np.nan)
        return df
