"""Tests for src.services.pop_repository."""
from __future__ import annotations

import sqlite3

from src.domain.data_models import make_pop_id
from src.services.pop_repository import PopRepository


def _build_test_db(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute('CREATE TABLE "A" (region TEXT, pop TEXT, value REAL)')
        conn.execute('CREATE TABLE "B" (region TEXT, pop TEXT, value REAL)')
        conn.execute('CREATE TABLE "C" (region TEXT, pop TEXT, value REAL)')

        conn.executemany(
            'INSERT INTO "A"(region, pop, value) VALUES (?, ?, ?)',
            [("R1", "P1", 1.0), ("R1", "P2", 2.0), ("R2", "P3", 3.0)],
        )
        conn.executemany(
            'INSERT INTO "B"(region, pop, value) VALUES (?, ?, ?)',
            [("R1", "P1", 10.0), ("R2", "P3", 20.0)],
        )
        conn.executemany(
            'INSERT INTO "C"(region, pop, value) VALUES (?, ?, ?)',
            [("R1", "P1", 100.0), ("R1", "P2", 200.0)],
        )
        conn.commit()
    finally:
        conn.close()


def test_ensure_indexes_creates_region_pop_index(tmp_path):
    db_path = tmp_path / "test.db"
    _build_test_db(db_path)

    repo = PopRepository(db_path)
    repo.ensure_indexes()

    conn = sqlite3.connect(str(db_path))
    try:
        indexes = conn.execute('PRAGMA index_list("A")').fetchall()
    finally:
        conn.close()

    index_names = [row[1] for row in indexes]
    assert any("region_pop" in name for name in index_names)


def test_build_catalog_returns_expected_availability(tmp_path):
    db_path = tmp_path / "test.db"
    _build_test_db(db_path)

    repo = PopRepository(db_path)
    catalog_by_region, availability_by_pop_id, all_regions = repo.build_catalog(
        required_files=["A.csv", "B.csv"]
    )

    assert all_regions == ["R1", "R2"]
    assert catalog_by_region["R1"] == ["P1", "P2"]
    assert catalog_by_region["R2"] == ["P3"]

    assert availability_by_pop_id[make_pop_id("R1", "P1")] is True
    assert availability_by_pop_id[make_pop_id("R2", "P3")] is True
    assert availability_by_pop_id[make_pop_id("R1", "P2")] is False


def test_build_catalog_includes_filesystem_only_pops_as_unavailable(tmp_path):
    db_path = tmp_path / "test.db"
    _build_test_db(db_path)

    (tmp_path / "data" / "R1" / "P4").mkdir(parents=True)
    (tmp_path / "data" / "R3" / "P5").mkdir(parents=True)

    repo = PopRepository(db_path)
    catalog_by_region, availability_by_pop_id, all_regions = repo.build_catalog(
        required_files=["A.csv", "B.csv"]
    )

    assert all_regions == ["R1", "R2", "R3"]
    assert catalog_by_region["R1"] == ["P1", "P2", "P4"]
    assert catalog_by_region["R2"] == ["P3"]
    assert catalog_by_region["R3"] == ["P5"]

    assert availability_by_pop_id[make_pop_id("R1", "P4")] is False
    assert availability_by_pop_id[make_pop_id("R3", "P5")] is False
