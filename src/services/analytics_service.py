"""
Analytics Service — Correlation calculations and statistical analysis.

Extracted from data_cleaning.py's calculate_pop_correlations and related helpers.
Pure functions, no DB access, no UI.
"""
from __future__ import annotations

import logging

import pandas as pd

from src.domain.data_models import PopDataset

logger = logging.getLogger(__name__)


# ---------- Status helpers ----------

_DOOR_NUMERIC_MAP = {
    "Open": 1, "Ouvert": 1, "open": 1, "1": 1, 1: 1,
    "Close": 0, "Fermé": 0, "closed": 0, "0": 0, 0: 0,
    "Closed": 0, "OPEN": 1, "CLOSE": 0, "CLOSED": 0,
}

_CLIM_NUMERIC_MAP = {
    "ON": 1, "on": 1, "On": 1, "1": 1, 1: 1,
    "OFF": 0, "off": 0, "Off": 0, "0": 0, 0: 0,
}


def _check_constant_status(series: pd.Series, metric_name: str) -> str | None:
    """Return a label if the series has a single unique non-null value."""
    unique = series.dropna().unique()
    if len(unique) != 1:
        return None
    val = unique[0]
    if "CLIM" in metric_name:
        return "Toujours ON" if val == 1 else "Toujours OFF"
    if "Porte" in metric_name:
        return "Toujours Ouverte" if val == 1 else "Toujours Fermée"
    return None


def _convert_status_to_numeric(series: pd.Series, metric_name: str) -> pd.Series:
    """Convert categorical status values to numeric."""
    if series.dtype == "object":
        if "Porte" in metric_name:
            return series.map(_DOOR_NUMERIC_MAP)
        if "CLIM" in metric_name:
            return series.map(_CLIM_NUMERIC_MAP)
    return series


# ---------- Correlation calculation ----------

def calculate_pop_correlations(
    all_pops_data: dict[tuple[str, str], pd.DataFrame],
    metric: str = "Temp_Ambiante",
    period: tuple | None = None,
) -> pd.DataFrame:
    """Calculate correlations between a primary metric and all others across POPs.

    Args:
        all_pops_data: Dict mapping (region, pop) → merged DataFrame.
        metric: Primary metric column name.
        period: Optional (start_date, end_date) to filter.

    Returns:
        DataFrame with correlation results per POP.
    """
    results: list[dict] = []

    # Detect all available CLIM columns across all POPs
    all_clim_units: set[str] = set()
    for data in all_pops_data.values():
        all_clim_units.update(
            col for col in data.columns
            if col.startswith("CLIM_") and col.endswith("_Status")
        )

    base_metrics = ["Temp_Exterieure", "Puissance_IT", "Puissance_CLIM", "Porte_Status"]
    correlation_metrics = base_metrics + sorted(all_clim_units)

    for (region, pop), data in all_pops_data.items():
        original_data = data.copy()

        # Apply period filter
        if period and "Timestamp" in data.columns:
            start_date, end_date = period
            mask = (data["Timestamp"] >= start_date) & (data["Timestamp"] <= end_date)
            data = data[mask]

        pop_corr: dict = {
            "Region": region,
            "POP": pop,
            "POP_ID": f"{region}_{pop}",
            "Data_Points": len(data),
            "Period_Start": data["Timestamp"].min() if "Timestamp" in data.columns and len(data) > 0 else None,
            "Period_End": data["Timestamp"].max() if "Timestamp" in data.columns and len(data) > 0 else None,
        }

        if len(data) < 10 or metric not in data.columns:
            # Insufficient data
            for corr_metric in correlation_metrics:
                pop_corr[f"{corr_metric}_Pearson"] = None
                pop_corr[f"{corr_metric}_Spearman"] = None
                pop_corr[f"{corr_metric}_Count"] = 0
            results.append(pop_corr)
            continue

        for corr_metric in correlation_metrics:
            if corr_metric not in data.columns:
                pop_corr[f"{corr_metric}_Pearson"] = None
                pop_corr[f"{corr_metric}_Spearman"] = None
                pop_corr[f"{corr_metric}_Count"] = 0
                continue

            corr_data = data[[metric, corr_metric]].dropna()
            if len(corr_data) < 10:
                pop_corr[f"{corr_metric}_Pearson"] = None
                pop_corr[f"{corr_metric}_Spearman"] = None
                pop_corr[f"{corr_metric}_Count"] = 0
                continue

            corr_series = _convert_status_to_numeric(corr_data[corr_metric], corr_metric)
            constant = _check_constant_status(corr_series, corr_metric)
            if constant:
                pop_corr[f"{corr_metric}_Pearson"] = constant
                pop_corr[f"{corr_metric}_Spearman"] = constant
                pop_corr[f"{corr_metric}_Count"] = len(corr_data)
            else:
                corr_data = corr_data.copy()
                corr_data[corr_metric] = corr_series
                try:
                    pop_corr[f"{corr_metric}_Pearson"] = corr_data[metric].corr(
                        corr_data[corr_metric], method="pearson"
                    )
                    pop_corr[f"{corr_metric}_Spearman"] = corr_data[metric].corr(
                        corr_data[corr_metric], method="spearman"
                    )
                    pop_corr[f"{corr_metric}_Count"] = len(corr_data)
                except Exception:
                    pop_corr[f"{corr_metric}_Pearson"] = None
                    pop_corr[f"{corr_metric}_Spearman"] = None
                    pop_corr[f"{corr_metric}_Count"] = 0

        # Basic stats for primary metric
        pop_corr[f"{metric}_Mean"] = data[metric].mean()
        pop_corr[f"{metric}_Std"] = data[metric].std()
        pop_corr[f"{metric}_Min"] = data[metric].min()
        pop_corr[f"{metric}_Max"] = data[metric].max()

        results.append(pop_corr)

    return pd.DataFrame(results) if results else pd.DataFrame()
