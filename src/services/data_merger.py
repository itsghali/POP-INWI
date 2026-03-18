"""
Data Merger — Combines cleaned single-metric DataFrames into one merged dataset.

Responsible for:
- Renaming Value columns to metric-specific names
- Timestamp-aligned merge (outer join)
- Derived metric calculation (Puissance_IT = Generale - CLIM)
- Forward-fill for continuous metrics (with limit)

NOT responsible for: DB access, cleaning, or UI logic.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.domain.data_models import (
    PUISSANCE_CLIM,
    PUISSANCE_GENERALE,
    PUISSANCE_IT,
    TEMP_AMBIANTE,
    TEMP_EXTERIEURE,
    TIMESTAMP_COL,
)

logger = logging.getLogger(__name__)

# Forward-fill limit: max consecutive NaN values to fill
_FFILL_LIMIT = 30

# Columns eligible for forward-fill (continuous metrics only)
_CONTINUOUS_COLS = [
    TEMP_AMBIANTE,
    TEMP_EXTERIEURE,
    PUISSANCE_CLIM,
    PUISSANCE_GENERALE,
    PUISSANCE_IT,
]

# Mapping from cleaned-data key to target column name
_KEY_TO_COLUMN = {
    "temp_ambiante": TEMP_AMBIANTE,
    "temp_exterieure": TEMP_EXTERIEURE,
    "porte": "Porte_Status",
}


def _find_value_column(df: pd.DataFrame) -> str | None:
    """Find the value column in a cleaned DataFrame."""
    # Prefer columns with unit indicators
    for col in df.columns:
        lower = col.lower()
        if any(x in lower for x in ["value", "valeur"]) and any(
            x in col for x in ["°C", "kW", "Â°C"]
        ):
            return col
    # Fallback: any column with 'Value' in name
    for col in df.columns:
        if "Value" in col:
            return col
    return None


def _extract_metric(
    cleaned_data: dict[str, pd.DataFrame], key: str, target_col: str
) -> pd.DataFrame | None:
    """Extract a single metric as a Timestamp + target_col DataFrame."""
    if key not in cleaned_data:
        return None
    df = cleaned_data[key].copy()
    value_col = _find_value_column(df)
    if value_col is None or TIMESTAMP_COL not in df.columns:
        return None
    df = df[[TIMESTAMP_COL, value_col]]
    df.rename(columns={value_col: target_col}, inplace=True)
    return df


def merge_cleaned_data(cleaned_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge all cleaned DataFrames into a single time-aligned dataset.

    Args:
        cleaned_data: dict mapping data key → cleaned DataFrame.

    Returns:
        Merged DataFrame sorted by Timestamp.
    """
    if not cleaned_data:
        return pd.DataFrame()

    dfs: list[pd.DataFrame] = []

    # Simple metrics: temp_ambiante, temp_exterieure, porte
    for key, target_col in _KEY_TO_COLUMN.items():
        extracted = _extract_metric(cleaned_data, key, target_col)
        if extracted is not None:
            dfs.append(extracted)

    # Power metrics: merge generale + clim, derive IT power
    power_df = _build_power_dataframe(cleaned_data)
    if power_df is not None:
        dfs.append(power_df)

    # CLIM status columns (A-H)
    for letter in "abcdefgh":
        key = f"clim_{letter}"
        target_col = f"CLIM_{letter.upper()}_Status"
        extracted = _extract_metric(cleaned_data, key, target_col)
        if extracted is not None:
            dfs.append(extracted)

    if not dfs:
        return pd.DataFrame()

    # Progressive merge on Timestamp
    merged = dfs[0]
    for df in dfs[1:]:
        merged = pd.merge(merged, df, on=TIMESTAMP_COL, how="outer")

    merged = merged.sort_values(TIMESTAMP_COL).reset_index(drop=True)

    # Forward-fill continuous metrics (limited)
    for col in _CONTINUOUS_COLS:
        if col in merged.columns:
            merged[col] = merged[col].ffill(limit=_FFILL_LIMIT)

    logger.info(
        "Merged dataset: %d rows, %d columns, period %s to %s",
        len(merged),
        len(merged.columns),
        merged[TIMESTAMP_COL].min() if TIMESTAMP_COL in merged.columns else "?",
        merged[TIMESTAMP_COL].max() if TIMESTAMP_COL in merged.columns else "?",
    )
    return merged


def _build_power_dataframe(
    cleaned_data: dict[str, pd.DataFrame],
) -> pd.DataFrame | None:
    """Build combined power DataFrame with derived IT power."""
    has_gen = "puissance_generale" in cleaned_data
    has_clim = "puissance_clim" in cleaned_data

    if not has_gen and not has_clim:
        return None

    parts: list[pd.DataFrame] = []

    if has_gen:
        df_gen = _extract_metric(cleaned_data, "puissance_generale", PUISSANCE_GENERALE)
        if df_gen is not None:
            df_gen[PUISSANCE_GENERALE] = pd.to_numeric(
                df_gen[PUISSANCE_GENERALE], errors="coerce"
            )
            parts.append(df_gen)

    if has_clim:
        df_clim = _extract_metric(cleaned_data, "puissance_clim", PUISSANCE_CLIM)
        if df_clim is not None:
            df_clim[PUISSANCE_CLIM] = pd.to_numeric(
                df_clim[PUISSANCE_CLIM], errors="coerce"
            )
            parts.append(df_clim)

    if not parts:
        return None

    if len(parts) == 1:
        return parts[0]

    # Merge generale + clim
    power_df = pd.merge(parts[0], parts[1], on=TIMESTAMP_COL, how="outer")

    # Derive IT power
    if PUISSANCE_GENERALE in power_df.columns and PUISSANCE_CLIM in power_df.columns:
        power_df[PUISSANCE_IT] = (
            power_df[PUISSANCE_GENERALE] - power_df[PUISSANCE_CLIM]
        )
        power_df.loc[power_df[PUISSANCE_IT] < 0, PUISSANCE_IT] = 0

    return power_df
