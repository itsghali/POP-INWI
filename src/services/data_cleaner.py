"""
Data Cleaner — Normalizes raw DataFrames from the DB into clean, typed columns.

Responsible for:
- Column name normalization
- Timestamp parsing
- Value type conversion (ON/OFF → 1/0, numeric cleaning)
- Outlier clamping
- Deduplication

NOT responsible for: DB access, merging, or business logic.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Value mappings
_ON_VALUES = {"ON", "MARCHE", "1", "TRUE", "VRAI"}
_OFF_VALUES = {"OFF", "ARRET", "ARRÊT", "0", "FALSE", "FAUX"}
_CLIM_MAP = {v: 1 for v in _ON_VALUES} | {v: 0 for v in _OFF_VALUES}

_DOOR_MAP = {
    "OUVERTE": 1, "OUVERT": 1, "OPEN": 1,
    "FERMÉ": 0, "FERMÉE": 0, "FERME": 0, "FERMEE": 0,
    "CLOSED": 0, "CLOSE": 0,
    "1": 1, "0": 0, "TRUE": 1, "FALSE": 0,
}

_TIMESTAMP_FORMATS = [
    "%d-%b-%y %I:%M:%S %p",
    "%d-%b-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]


def clean_raw_dataframe(df: pd.DataFrame, data_key: str) -> pd.DataFrame:
    """Clean a single raw DataFrame from the database.

    Args:
        df: Raw DataFrame loaded from SQLite.
        data_key: Logical key like 'temp_ambiante', 'clim_a', 'porte', etc.

    Returns:
        Cleaned DataFrame with normalized Timestamp and Value columns.
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Drop importer metadata columns
    for meta in ("region", "pop"):
        if meta in df.columns:
            df.drop(columns=[meta], inplace=True)

    # Normalize column names
    df.columns = [
        str(c).strip().replace("\ufeff", "").replace("ï»¿", "") for c in df.columns
    ]

    # Find and normalize Timestamp column
    df = _normalize_timestamp(df)
    if "Timestamp" not in df.columns or df.empty:
        return pd.DataFrame()

    # Find and normalize Value column
    df = _normalize_value(df, data_key)

    # Drop fully-empty columns
    df = df.dropna(axis=1, how="all")

    # Deduplicate on Timestamp
    if "Timestamp" in df.columns:
        df = df.sort_values("Timestamp").drop_duplicates(subset=["Timestamp"], keep="last")

    # Ensure Timestamp is first
    cols = df.columns.tolist()
    if "Timestamp" in cols:
        cols = ["Timestamp"] + [c for c in cols if c != "Timestamp"]
        df = df[cols]

    return df


def _normalize_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    """Find the timestamp column, parse it, and drop invalid rows."""
    ts_col = None
    for c in df.columns:
        if "timestamp" in str(c).lower():
            ts_col = c
            break
    if ts_col is None and len(df.columns) > 0:
        ts_col = df.columns[0]
    if ts_col and ts_col != "Timestamp":
        df.rename(columns={ts_col: "Timestamp"}, inplace=True)

    if "Timestamp" not in df.columns:
        return df

    # Strip timezone suffixes
    df["Timestamp"] = (
        df["Timestamp"]
        .astype(str)
        .str.replace(r"\s+(WEST|WET|GMT|UTC|CET|CEST)$", "", regex=True)
        .str.strip()
    )

    # Try specific formats first, then fall back to general parsing
    for fmt in _TIMESTAMP_FORMATS:
        try:
            parsed = pd.to_datetime(df["Timestamp"], format=fmt, errors="coerce")
            if parsed.notna().sum() > 0:
                df["Timestamp"] = parsed
                break
        except Exception:
            continue
    else:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    df = df.dropna(subset=["Timestamp"])
    return df


def _normalize_value(df: pd.DataFrame, data_key: str) -> pd.DataFrame:
    """Find the value column and apply type-specific cleaning."""
    value_col = None
    for c in df.columns:
        if any(x in str(c).lower() for x in ["value", "valeur"]):
            value_col = c
            break

    if value_col is None:
        return df

    if value_col != "Value":
        df.rename(columns={value_col: "Value"}, inplace=True)

    df["Value"] = df["Value"].astype(str).str.strip()
    key_lower = data_key.lower()

    if key_lower.startswith("clim_"):
        # CLIM status: ON/OFF → 1/0
        df["Value"] = df["Value"].str.upper().map(_CLIM_MAP)
    elif key_lower == "porte":
        # Door status
        df["Value"] = df["Value"].str.upper().map(_DOOR_MAP)
    else:
        # Numeric value
        df["Value"] = (
            df["Value"]
            .str.replace(",", ".", regex=False)
            .str.replace(r"[^0-9eE+\-\.]+", "", regex=True)
        )
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

        # Clamp outliers
        if "temp" in key_lower or "température" in key_lower:
            df.loc[df["Value"] > 60, "Value"] = np.nan
            df.loc[df["Value"] < -10, "Value"] = np.nan
        elif "puissance" in key_lower or "p.active" in key_lower:
            df.loc[df["Value"] < 0, "Value"] = 0

    return df


def clean_all(raw_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Clean all raw tables for a POP.

    Args:
        raw_tables: dict mapping data key → raw DataFrame.

    Returns:
        dict mapping data key → cleaned DataFrame (empty ones excluded).
    """
    cleaned: dict[str, pd.DataFrame] = {}
    for key, raw_df in raw_tables.items():
        result = clean_raw_dataframe(raw_df, key)
        if not result.empty:
            cleaned[key] = result
            logger.debug("Cleaned %s: %d rows", key, len(result))
        else:
            logger.debug("Cleaned %s: empty after cleaning", key)
    return cleaned
