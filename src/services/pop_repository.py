"""
POP Repository — Single source of truth for POP/region discovery and raw data access.

All data access goes through SQLite (data_raw.db). Filesystem discovery is used
only to complete the POP catalog when folders exist without usable DB rows yet.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import hashlib
from pathlib import Path

import pandas as pd

from src.domain.data_models import DATA_FILE_KEYS, REQUIRED_FILES, make_pop_id
from src.domain.exceptions import DatabaseError, PopNotFoundError

logger = logging.getLogger(__name__)

_DB_FILENAME = "data_raw.db"
_DATA_DIRNAME = "data"


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

    def _filesystem_pairs(self) -> set[tuple[str, str]]:
        """Discover region/POP pairs from the sibling data directory, if present."""
        data_root = self.db_path.parent / _DATA_DIRNAME
        if not data_root.exists() or not data_root.is_dir():
            return set()

        pairs: set[tuple[str, str]] = set()
        for region_dir in data_root.iterdir():
            if not region_dir.is_dir():
                continue
            region = region_dir.name
            for pop_dir in region_dir.iterdir():
                if pop_dir.is_dir():
                    pairs.add((region, pop_dir.name))
        return pairs

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

    @staticmethod
    def _safe_index_name(raw_name: str) -> str:
        """Create a SQLite-safe, deterministic index name."""
        import re
        import unicodedata

        ascii_name = (
            unicodedata.normalize("NFKD", raw_name)
            .encode("ascii", "ignore")
            .decode()
        )
        ascii_name = re.sub(r"[^0-9A-Za-z_]+", "_", ascii_name).strip("_")
        if not ascii_name:
            ascii_name = "idx_region_pop"
        digest = hashlib.md5(raw_name.encode("utf-8")).hexdigest()[:8]
        return f"{ascii_name[:100]}_{digest}"

    @staticmethod
    def _region_pop_columns(
        conn: sqlite3.Connection, table_name: str
    ) -> tuple[str, str] | None:
        """Return actual region/pop column names (preserving case), if present."""
        cols = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        region_col = None
        pop_col = None
        for col in cols:
            col_name = str(col[1])
            lower = col_name.lower()
            if lower == "region":
                region_col = col_name
            elif lower == "pop":
                pop_col = col_name
        if region_col and pop_col:
            return region_col, pop_col
        return None

    # ---- performance helpers ----

    def ensure_indexes(self) -> None:
        """Create `(region, pop)` indexes on all relevant tables."""
        conn = self._connect()
        try:
            tables = self._tables_with_region_pop(conn)
            for table_name in tables:
                cols = self._region_pop_columns(conn, table_name)
                if cols is None:
                    continue
                region_col, pop_col = cols
                index_name = self._safe_index_name(
                    f"idx_{table_name}_region_pop"
                )
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                    f'ON "{table_name}"("{region_col}", "{pop_col}")'
                )
            conn.commit()
            logger.info("SQLite indexes ensured for region/pop columns")
        finally:
            conn.close()

    def build_catalog(
        self, required_files: list[str] | None = None
    ) -> tuple[dict[str, list[str]], dict[str, bool], list[str]]:
        """Build discovery catalog in one pass: region -> pops + availability."""
        required_files = required_files or REQUIRED_FILES
        conn = self._connect()
        try:
            table_rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            existing_tables = {str(row[0]) for row in table_rows}
            candidate_tables = self._tables_with_region_pop(conn)

            all_pairs: set[tuple[str, str]] = set()
            for table_name in candidate_tables:
                cols = self._region_pop_columns(conn, table_name)
                if cols is None:
                    continue
                region_col, pop_col = cols
                rows = conn.execute(
                    f'SELECT DISTINCT "{region_col}", "{pop_col}" '
                    f'FROM "{table_name}" '
                    f'WHERE "{region_col}" IS NOT NULL AND "{pop_col}" IS NOT NULL'
                ).fetchall()
                for region, pop in rows:
                    if region is not None and pop is not None:
                        all_pairs.add((str(region), str(pop)))

            # Include POP folders present on disk even if they are not yet usable
            # from the database, so the UI can expose them as unavailable.
            all_pairs.update(self._filesystem_pairs())

            required_tables: list[str] = []
            for filename in required_files:
                table_name = None
                for candidate in self._table_candidates(filename):
                    if candidate in existing_tables:
                        table_name = candidate
                        break
                if table_name is None:
                    required_tables = []
                    break
                required_tables.append(table_name)

            available_pairs: set[tuple[str, str]] = set()
            if required_tables:
                available_pairs = set(all_pairs)
                for table_name in required_tables:
                    cols = self._region_pop_columns(conn, table_name)
                    if cols is None:
                        available_pairs = set()
                        break
                    region_col, pop_col = cols
                    rows = conn.execute(
                        f'SELECT DISTINCT "{region_col}", "{pop_col}" '
                        f'FROM "{table_name}" '
                        f'WHERE "{region_col}" IS NOT NULL AND "{pop_col}" IS NOT NULL'
                    ).fetchall()
                    table_pairs = {
                        (str(region), str(pop))
                        for region, pop in rows
                        if region is not None and pop is not None
                    }
                    available_pairs &= table_pairs

            catalog_by_region: dict[str, list[str]] = {}
            for region, pop in sorted(all_pairs):
                catalog_by_region.setdefault(region, []).append(pop)
            for region in list(catalog_by_region.keys()):
                catalog_by_region[region] = sorted(set(catalog_by_region[region]))

            availability_by_pop_id: dict[str, bool] = {}
            for region, pop in all_pairs:
                availability_by_pop_id[make_pop_id(region, pop)] = (
                    (region, pop) in available_pairs
                )

            all_regions = sorted(catalog_by_region.keys())
            return catalog_by_region, availability_by_pop_id, all_regions
        finally:
            conn.close()

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
