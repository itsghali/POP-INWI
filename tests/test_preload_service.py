"""Tests for src.services.preload_service."""
from pathlib import Path

import pandas as pd

from src.domain.data_models import PopDataset
from src.services import preload_service


class _FakeRepo:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.ensure_indexes_calls = 0

    def ensure_indexes(self) -> None:
        self.ensure_indexes_calls += 1

    def build_catalog(self):
        return (
            {"R1": ["P1", "P2"], "R2": ["P3"]},
            {"R1_P1": True, "R1_P2": False, "R2_P3": True},
            ["R1", "R2"],
        )


def test_build_preloaded_store_impl_builds_catalog_and_datasets(monkeypatch, tmp_path):
    db_path = tmp_path / "data_raw.db"
    db_path.write_text("db", encoding="utf-8")
    repo = _FakeRepo(db_path)

    load_calls: list[tuple[str, str]] = []

    def _fake_load_pop(repo_obj, region: str, pop: str) -> PopDataset:
        load_calls.append((region, pop))
        return PopDataset(
            region=region,
            pop=pop,
            pop_id=f"{region}_{pop}",
            merged=pd.DataFrame(
                {
                    "Timestamp": pd.to_datetime(["2024-01-01 00:00:00"]),
                    "Temp_Ambiante": [22.0],
                }
            ),
        )

    preload_service.clear_registered_stores()
    monkeypatch.setattr(preload_service, "load_pop", _fake_load_pop)

    def _sync_start_worker(store, db_path, ordered_pairs):
        preload_service._load_all_pop_datasets(store, db_path, ordered_pairs)

    monkeypatch.setattr(
        preload_service,
        "_start_preload_worker",
        _sync_start_worker,
    )

    store = preload_service._build_preloaded_store_impl(repo)

    assert repo.ensure_indexes_calls == 1
    assert set(load_calls) == {("R1", "P1"), ("R1", "P2"), ("R2", "P3")}
    assert store.catalog_by_region["R1"] == ["P1", "P2"]
    assert store.availability_by_pop_id["R1_P2"] is False
    assert preload_service.get_registered_store(store.db_version) is store

    dataset = preload_service.get_dataset(store, "R1", "P1")
    assert dataset is not None
    assert dataset.pop_id == "R1_P1"
    assert not dataset.is_empty
    snapshot = preload_service.get_preload_snapshot(store)
    assert snapshot.is_complete is True
    assert snapshot.loaded_count == 3


def test_build_preloaded_store_impl_initializes_progressive_state(monkeypatch, tmp_path):
    db_path = tmp_path / "data_raw.db"
    db_path.write_text("db", encoding="utf-8")
    repo = _FakeRepo(db_path)

    monkeypatch.setattr(
        preload_service,
        "_start_preload_worker",
        lambda *args, **kwargs: None,
    )

    store = preload_service._build_preloaded_store_impl(repo)
    snapshot = preload_service.get_preload_snapshot(store)

    assert snapshot.total_pops == 3
    assert snapshot.loaded_count == 0
    assert snapshot.is_complete is False
    assert store.datasets_by_pop_id == {}
