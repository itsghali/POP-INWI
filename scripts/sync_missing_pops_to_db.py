"""
Sync missing POPs from data folder into data_raw.db.

- Detect POPs present in data/ but missing in DB.
- Import only those POPs and skip rows already in the DB.
"""

import os
import sqlite3
import warnings
from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")
DB_PATH = Path("data_raw.db")

STANDARD_COLUMNS = ["Timestamp", "Trend Flags", "Status", "Value"]


def find_table_with_columns(conn, required_cols):
    required = {c.lower() for c in required_cols}
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for (tname,) in tables:
        cols = conn.execute(f"PRAGMA table_info(\"{tname}\")").fetchall()
        col_names = {str(c[1]).lower() for c in cols}
        if required.issubset(col_names):
            return tname
    return None


def get_tables_with_region_pop(conn):
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    result = []
    for (tname,) in tables:
        cols = conn.execute(f"PRAGMA table_info(\"{tname}\")").fetchall()
        col_names = {str(c[1]).lower() for c in cols}
        if {'region', 'pop'}.issubset(col_names):
            result.append(tname)
    return result


def list_folder_pops():
    pops = set()
    if not DATA_DIR.exists():
        return pops
    for region_dir in DATA_DIR.iterdir():
        if region_dir.is_dir():
            for pop_dir in region_dir.iterdir():
                if pop_dir.is_dir():
                    pops.add((region_dir.name, pop_dir.name))
    return pops


def list_db_pops(conn):
    tables = get_tables_with_region_pop(conn)
    if not tables:
        return set()
    pops = set()
    for table in tables:
        rows = conn.execute(
            f"SELECT DISTINCT region, pop FROM \"{table}\" WHERE region IS NOT NULL AND pop IS NOT NULL"
        ).fetchall()
        pops.update((r, p) for r, p in rows if r and p)
    return pops


def normalize_columns(df):
    df.columns = [c.strip() for c in df.columns]
    df.columns = [c.replace("Value (°C)", "Value").replace("Value(°C)", "Value") for c in df.columns]
    return df


def build_column_map(df):
    col_map = {}
    for c in df.columns:
        lc = c.lower()
        if lc.startswith("timestamp"):
            col_map["Timestamp"] = c
        elif "trend" in lc and "flag" in lc:
            col_map["Trend Flags"] = c
        elif lc.startswith("status"):
            col_map["Status"] = c
        elif "value" in lc:
            col_map["Value"] = c
    return col_map


def parse_timestamp(series):
    ts = series.astype(str).str.replace(r"\s+\w+$", "", regex=True).str.strip()
    parsed = pd.to_datetime(ts, format="%d-%b-%y %I:%M:%S %p", errors="coerce")
    mask_na = parsed.isna()
    if mask_na.any():
        parsed.loc[mask_na] = pd.to_datetime(ts[mask_na], format="%d-%b-%y %H:%M:%S", errors="coerce")
    mask_na = parsed.isna()
    if mask_na.any():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed.loc[mask_na] = pd.to_datetime(ts[mask_na], errors="coerce")
    return parsed


def table_has_pop(conn, table_name, region, pop):
    row = conn.execute(
        f"SELECT 1 FROM \"{table_name}\" WHERE region=? AND pop=? LIMIT 1",
        (region, pop),
    ).fetchone()
    return row is not None


def import_csv_to_table(conn, file_path, table_name, region, pop):
    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()
    header_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("Timestamp"))
    df = pd.read_csv(file_path, skiprows=header_idx)

    df = normalize_columns(df)
    col_map = build_column_map(df)

    for std in STANDARD_COLUMNS:
        if std not in col_map:
            df[std] = pd.NA

    try:
        df_sel = df[
            [
                col_map.get("Timestamp", "Timestamp"),
                col_map.get("Trend Flags", "Trend Flags"),
                col_map.get("Status", "Status"),
                col_map.get("Value", "Value"),
            ]
        ]
    except Exception:
        df_sel = df.iloc[:, :4]
        df_sel.columns = STANDARD_COLUMNS[: len(df_sel.columns)]
        for std in STANDARD_COLUMNS:
            if std not in df_sel.columns:
                df_sel[std] = pd.NA

    df_sel.columns = STANDARD_COLUMNS
    df_sel["region"] = region
    df_sel["pop"] = pop
    df_sel["Timestamp"] = parse_timestamp(df_sel["Timestamp"])

    out_cols = STANDARD_COLUMNS + ["region", "pop"]
    for col in out_cols:
        if col not in df_sel.columns:
            df_sel[col] = pd.NA

    df_out = df_sel[out_cols].copy()
    df_out = df_out.replace(r"^\s*$", pd.NA, regex=True)
    df_out = df_out.replace(["nan", "NaN", "None", "NONE", "NULL", "null"], pd.NA)

    df_out.to_sql(table_name, conn, if_exists="append", index=False)


def main():
    if not DB_PATH.exists():
        raise SystemExit("data_raw.db introuvable")

    folder_pops = list_folder_pops()
    if not folder_pops:
        raise SystemExit("Aucun POP trouve dans data/")

    conn = sqlite3.connect(str(DB_PATH))
    db_pops = list_db_pops(conn)
    missing_pops = sorted(folder_pops - db_pops)

    print(f"POPs dossier: {len(folder_pops)}")
    print(f"POPs DB: {len(db_pops)}")
    print(f"POPs manquants: {len(missing_pops)}")

    if not missing_pops:
        conn.close()
        return

    imported_tables = 0
    imported_files = 0

    for region, pop in missing_pops:
        pop_dir = DATA_DIR / region / pop
        if not pop_dir.exists():
            continue

        for file in pop_dir.iterdir():
            if not file.is_file() or file.suffix.lower() != ".csv":
                continue

            table_name = file.stem.replace(" ", "_").replace("-", "_")

            # Skip if the table already has rows for this pop
            if table_has_pop(conn, table_name, region, pop):
                continue

            try:
                import_csv_to_table(conn, file, table_name, region, pop)
                imported_files += 1
            except Exception as exc:
                print(f"Erreur import {file}: {exc}")
                continue

        imported_tables += 1
        print(f"OK: {region}/{pop}")

    conn.close()
    print(f"Imports termines. Fichiers importes: {imported_files}")


if __name__ == "__main__":
    main()
