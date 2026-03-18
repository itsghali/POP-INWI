"""
POP Repository — Single source of truth for POP/region discovery and raw data access.

All data access goes through SQLite (data_raw.db). Filesystem discovery is removed.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

import pandas as pd

from src.domain.data_models import DATA_FILE_KEYS, REQUIRED_FILES
from src.domain.exceptions import DatabaseError, PopNotFoundError

logger = logging.getLogger(__name__)

_DB_FILENAME = "data_raw.db"


class PopRepository:
    """Read-only repository for POP data backed by SQLite."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.cwd() / _DB_FILENAME
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise DatabaseError(f"Database not found: {self.db_path}")
        logger.info("PopRepository initialized with DB: %s", self.db_path)

    # ---- connection helper ----

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    # ---- table introspection ----

    @staticmethod
    def _table_candidates(filename: str) -> list[str]:
        """Generate candidate table names for a given CSV filename."""
        base = os.path.splitext(filename)[0].replace(" ", "_").replace("-", "_")
        candidates = [base]
        try:
            import unicodedata

            ascii_name = (
                unicodedata.normalize("NFKD", base)
                .encode("ascii", "ignore")
                .decode()
            )
            if ascii_name != base:
                candidates.append(ascii_name)
        except Exception:
            pass
        return candidates

    def _tables_with_region_pop(self, conn: sqlite3.Connection) -> list[str]:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        result = []
        for (tname,) in rows:
            cols = conn.execute(f'PRAGMA table_info("{tname}")').fetchall()
            col_names = {str(c[1]).lower() for c in cols}
            if {"region", "pop"}.issubset(col_names):
                result.append(tname)
        return result

    # ---- discovery ----

    def get_regions(self) -> list[str]:
        """Return sorted list of all regions in the database."""
        try:
            conn = self._connect()
            tables = self._tables_with_region_pop(conn)
            if not tables:
                conn.close()
                return []
            regions: set[str] = set()
            for table in tables:
                rows = conn.execute(
                    f'SELECT DISTINCT region FROM "{table}" WHERE region IS NOT NULL'
                ).fetchall()
                regions.update(r[0] for r in rows if r and r[0] is not None)
            conn.close()
            return sorted(regions)
        except Exception as exc:
            logger.error("Failed to get regions: %s", exc)
            return []

    def get_pops(self, region: str) -> list[str]:
        """Return sorted list of POPs for a given region."""
        try:
            conn = self._connect()
            tables = self._tables_with_region_pop(conn)
            if not tables:
                conn.close()
                return []
            pops: set[str] = set()
            for table in tables:
                rows = conn.execute(
                    f'SELECT DISTINCT pop FROM "{table}" WHERE region = ? AND pop IS NOT NULL',
                    (region,),
                ).fetchall()
                pops.update(r[0] for r in rows if r and r[0] is not None)
            conn.close()
            return sorted(pops)
        except Exception as exc:
            logger.error("Failed to get POPs for region %s: %s", region, exc)
            return []

    def has_pop_data(
        self, region: str, pop: str, required_files: list[str] | None = None
    ) -> bool:
        """Check if a POP has the minimum required data tables populated."""
        required_files = required_files or REQUIRED_FILES
        try:
            conn = self._connect()
            for filename in required_files:
                found = False
                for tname in self._table_candidates(filename):
                    if conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (tname,),
                    ).fetchone():
                        count = conn.execute(
                            f'SELECT 1 FROM "{tname}" WHERE region=? AND pop=? LIMIT 1',
                            (region, pop),
                        ).fetchone()
                        if count:
                            found = True
                            break
                if not found:
                    conn.close()
                    return False
            conn.close()
            return True
        except Exception:
            return False

    # ---- raw data loading ----

    def load_raw_tables(self, region: str, pop: str) -> dict[str, pd.DataFrame]:
        """Load raw DataFrames for all known data files for a single POP.

        Returns:
            dict mapping data key (e.g. 'temp_ambiante') to raw DataFrame.
        """
        conn = self._connect()
        raw_data: dict[str, pd.DataFrame] = {}

        for key, filename in DATA_FILE_KEYS.items():
            for tname in self._table_candidates(filename):
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (tname,),
                ).fetchone()
                if exists:
                    try:
                        df = pd.read_sql_query(
                            f'SELECT * FROM "{tname}" WHERE region=? AND pop=?',
                            conn,
                            params=(region, pop),
                        )
                        if not df.empty:
                            raw_data[key] = df
                            logger.debug(
                                "Loaded %s for %s/%s (%d rows)",
                                filename, region, pop, len(df),
                            )
                        break
                    except Exception as exc:
                        logger.warning(
                            "Error reading table %s for %s/%s: %s",
                            tname, region, pop, exc,
                        )
                        continue

        conn.close()
        logger.info(
            "Loaded %d raw tables for %s/%s", len(raw_data), region, pop
        )
        return raw_data
