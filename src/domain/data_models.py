"""
Domain data models for the POP monitoring application.

These provide typed contracts for data flowing through the system,
replacing raw loosely-structured DataFrames passed without context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


# ---------- Column name constants ----------

TIMESTAMP_COL = "Timestamp"
TEMP_AMBIANTE = "Temp_Ambiante"
TEMP_EXTERIEURE = "Temp_Exterieure"
PUISSANCE_GENERALE = "Puissance_Generale"
PUISSANCE_CLIM = "Puissance_CLIM"
PUISSANCE_IT = "Puissance_IT"
PORTE_STATUS = "Porte_Status"

CORE_METRICS = {
    TEMP_AMBIANTE,
    TEMP_EXTERIEURE,
    PUISSANCE_GENERALE,
    PUISSANCE_CLIM,
    PUISSANCE_IT,
    PORTE_STATUS,
}

# Display-name mapping for UI
METRIC_DISPLAY_NAMES: dict[str, str] = {
    TEMP_AMBIANTE: "Température Ambiante",
    TEMP_EXTERIEURE: "Température Extérieure",
    PUISSANCE_IT: "Puissance IT",
    PUISSANCE_GENERALE: "Puissance Générale",
    PUISSANCE_CLIM: "Puissance CLIM",
    PORTE_STATUS: "État Porte",
}

# Keys used to identify raw data files / DB tables
DATA_FILE_KEYS: dict[str, str] = {
    "temp_ambiante": "Température Ambiante.csv",
    "temp_exterieure": "Température Extérieure.csv",
    "puissance_clim": "P.Active CLIM.csv",
    "puissance_generale": "P.Active Générale.csv",
    "clim_a": "Etat CLIM A.csv",
    "clim_b": "Etat CLIM B.csv",
    "clim_c": "Etat CLIM C.csv",
    "clim_d": "Etat CLIM D.csv",
    "clim_e": "Etat CLIM E.csv",
    "clim_f": "Etat CLIM F.csv",
    "clim_g": "Etat CLIM G.csv",
    "clim_h": "Etat CLIM H.csv",
    "porte": "Etat Porte.csv",
}

REQUIRED_FILES = [
    "Température Ambiante.csv",
    "Température Extérieure.csv",
    "P.Active CLIM.csv",
    "P.Active Générale.csv",
]


# ---------- Data containers ----------

@dataclass
class PopDataset:
    """Typed container for a loaded, merged POP dataset."""

    region: str
    pop: str
    pop_id: str
    merged: pd.DataFrame
    available_metrics: set[str] = field(default_factory=set)
    time_min: datetime | None = None
    time_max: datetime | None = None

    def __post_init__(self):
        if self.merged is not None and not self.merged.empty:
            self.available_metrics = {
                col for col in self.merged.columns if col in CORE_METRICS
            }
            # Also include CLIM status columns
            self.available_metrics.update(
                col
                for col in self.merged.columns
                if col.startswith("CLIM_") and col.endswith("_Status")
            )
            if TIMESTAMP_COL in self.merged.columns:
                ts = self.merged[TIMESTAMP_COL]
                self.time_min = ts.min()
                self.time_max = ts.max()

    @property
    def is_empty(self) -> bool:
        return self.merged is None or self.merged.empty

    def inject_metadata(self) -> pd.DataFrame:
        """Return a copy of merged with Region/POP/POP_ID columns set."""
        df = self.merged.copy()
        df["Region"] = self.region
        df["POP"] = self.pop
        df["POP_ID"] = self.pop_id
        return df


def make_pop_id(region: str, pop: str) -> str:
    return f"{region}_{pop}"


def validate_required_columns(
    df: pd.DataFrame, required: list[str] | None = None
) -> tuple[bool, list[str]]:
    """Check that required columns exist in a DataFrame."""
    if df.empty:
        return False, list(required or [])
    required = required or [TIMESTAMP_COL, TEMP_AMBIANTE]
    missing = [col for col in required if col not in df.columns]
    return len(missing) == 0, missing
