"""
Global preload service for all POP datasets.

This module provides a single warm-up entry point that:
- creates DB indexes (once, idempotent),
- builds an in-memory discovery catalog,
- preloads all POP datasets in background (non-blocking).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import threading
from typing import Iterable

import pandas as pd
import streamlit as st

from src.domain.data_models import PopDataset, make_pop_id
from src.services.pop_loader import load_pop
from src.services.pop_repository import PopRepository

logger = logging.getLogger(__name__)
_DEFAULT_DB_FILENAME = "data_raw.db"


@dataclass
class PreloadedStore:
    """Global in-memory store for preloaded POP data and discovery metadata."""

    datasets_by_pop_id: dict[str, PopDataset]
    catalog_by_region: dict[str, list[str]]
    availability_by_pop_id: dict[str, bool]
    all_regions: list[str]
    db_version: str
    total_pops: int = 0
    loaded_count: int = 0
    loading_pop_id: str | None = None
    is_loading: bool = False
    is_complete: bool = False
    first_loaded_pop_id: str | None = None
    load_revision: int = 0
    _lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False
    )
    _worker_thread: threading.Thread | None = field(default=None, repr=False)
    _stop_event: threading.Event = field(
        default_factory=threading.Event, repr=False
    )


@dataclass(frozen=True)
class PreloadSnapshot:
    """Immutable snapshot for safe UI rendering."""

    total_pops: int
    loaded_count: int
    loading_pop_id: str | None
    is_loading: bool
    is_complete: bool
    first_loaded_pop_id: str | None
    load_revision: int


_REGISTERED_STORES: dict[str, PreloadedStore] = {}


def _compute_db_version(db_path: Path) -> str:
    stat = db_path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _resolve_db_path(db_path: str | Path | None) -> Path:
    if db_path is None:
        return Path.cwd() / _DEFAULT_DB_FILENAME
    return Path(db_path)


def _ensure_runtime_fields(store: PreloadedStore) -> None:
    """Hydrate missing runtime fields for cached/legacy store objects."""
    if not hasattr(store, "_lock") or store._lock is None:
        store._lock = threading.Lock()
    if not hasattr(store, "_stop_event") or store._stop_event is None:
        store._stop_event = threading.Event()
    if not hasattr(store, "_worker_thread"):
        store._worker_thread = None

    catalog = getattr(store, "catalog_by_region", {})
    datasets = getattr(store, "datasets_by_pop_id", {})

    if (
        not hasattr(store, "total_pops")
        or (store.total_pops <= 0 and bool(catalog))
    ):
        store.total_pops = sum(
            len(pops) for pops in catalog.values()
        )
    if not hasattr(store, "loaded_count") or store.loaded_count < len(datasets):
        store.loaded_count = len(datasets)
    if not hasattr(store, "loading_pop_id"):
        store.loading_pop_id = None
    if not hasattr(store, "is_loading"):
        store.is_loading = False
    if not hasattr(store, "is_complete"):
        store.is_complete = (
            store.loaded_count >= store.total_pops if store.total_pops > 0 else True
        )
    if not hasattr(store, "first_loaded_pop_id"):
        store.first_loaded_pop_id = None
    if store.first_loaded_pop_id is None:
        for pop_id, dataset in datasets.items():
            if dataset is not None and not getattr(dataset, "is_empty", True):
                store.first_loaded_pop_id = pop_id
                break
    if not hasattr(store, "load_revision") or store.load_revision < 0:
        store.load_revision = int(store.loaded_count)


def _ordered_pop_pairs(
    catalog_by_region: dict[str, list[str]],
    availability_by_pop_id: dict[str, bool],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for region in sorted(catalog_by_region.keys()):
        for pop in sorted(catalog_by_region.get(region, [])):
            pairs.append((region, pop))

    preferred = [
        pair
        for pair in pairs
        if availability_by_pop_id.get(make_pop_id(pair[0], pair[1]), False)
    ]
    preferred_set = set(preferred)
    others = [pair for pair in pairs if pair not in preferred_set]
    return preferred + others


def _set_loading_state(
    store: PreloadedStore,
    *,
    is_loading: bool,
    is_complete: bool | None = None,
    loading_pop_id: str | None = None,
) -> None:
    with store._lock:
        store.is_loading = is_loading
        store.loading_pop_id = loading_pop_id
        if is_complete is not None:
            store.is_complete = is_complete


def _load_all_pop_datasets(
    store: PreloadedStore,
    db_path: Path,
    ordered_pairs: Iterable[tuple[str, str]],
) -> None:
    """Worker logic for progressive preload."""
    repo = PopRepository(db_path)
    _set_loading_state(store, is_loading=True, is_complete=False, loading_pop_id=None)

    for region, pop in ordered_pairs:
        if store._stop_event.is_set():
            break

        pop_id = make_pop_id(region, pop)
        _set_loading_state(
            store,
            is_loading=True,
            loading_pop_id=pop_id,
        )

        try:
            dataset = load_pop(repo, region, pop)
        except Exception as exc:
            logger.exception("Failed to preload %s/%s: %s", region, pop, exc)
            dataset = PopDataset(
                region=region,
                pop=pop,
                pop_id=pop_id,
                merged=pd.DataFrame(),
            )

        with store._lock:
            store.datasets_by_pop_id[pop_id] = dataset
            store.loaded_count += 1
            if (
                store.first_loaded_pop_id is None
                and not dataset.is_empty
            ):
                store.first_loaded_pop_id = pop_id
            store.load_revision += 1

    with store._lock:
        store.loading_pop_id = None
        store.is_loading = False
        store.is_complete = not store._stop_event.is_set()
        store.load_revision += 1


def _start_preload_worker(
    store: PreloadedStore,
    db_path: Path,
    ordered_pairs: list[tuple[str, str]],
) -> None:
    """Start worker thread once."""
    with store._lock:
        running = (
            store._worker_thread is not None
            and store._worker_thread.is_alive()
        )
        if running or store.is_complete:
            return

        store._stop_event.clear()
        worker = threading.Thread(
            target=_load_all_pop_datasets,
            args=(store, db_path, ordered_pairs),
            name="pop-preload-worker",
            daemon=True,
        )
        store._worker_thread = worker
        worker.start()


def _ensure_worker_running(store: PreloadedStore, db_path: Path) -> None:
    _ensure_runtime_fields(store)
    ordered_pairs = _ordered_pop_pairs(
        store.catalog_by_region,
        store.availability_by_pop_id,
    )
    with store._lock:
        if store.is_complete:
            return
    _start_preload_worker(store, db_path, ordered_pairs)


def _build_preloaded_store_impl(repo: PopRepository) -> PreloadedStore:
    """Build store without Streamlit cache wrapper (test-friendly)."""
    repo.ensure_indexes()

    catalog_by_region, availability_by_pop_id, all_regions = repo.build_catalog()

    ordered_pairs = _ordered_pop_pairs(
        catalog_by_region,
        availability_by_pop_id,
    )
    store = PreloadedStore(
        datasets_by_pop_id={},
        catalog_by_region=catalog_by_region,
        availability_by_pop_id=availability_by_pop_id,
        all_regions=all_regions,
        db_version=_compute_db_version(repo.db_path),
        total_pops=len(ordered_pairs),
    )
    _REGISTERED_STORES[store.db_version] = store
    _start_preload_worker(store, repo.db_path, ordered_pairs)

    logger.info(
        "Preloaded store initialized: %d regions, %d POPs queued",
        len(store.all_regions),
        store.total_pops,
    )
    return store


@st.cache_resource(show_spinner=False)
def build_preloaded_store(db_path: str | Path | None = None) -> PreloadedStore:
    """Build and cache the global preloaded store."""
    repo = PopRepository(db_path)
    return _build_preloaded_store_impl(repo)


def get_preloaded_store(db_path: str | Path | None = None) -> PreloadedStore:
    """Get the preloaded store and ensure it is registered for cache lookups."""
    store = build_preloaded_store(db_path)
    _ensure_runtime_fields(store)
    _ensure_worker_running(store, _resolve_db_path(db_path))
    _REGISTERED_STORES[store.db_version] = store
    return store


def get_registered_store(db_version: str) -> PreloadedStore | None:
    """Retrieve a store from in-process registry by db version."""
    return _REGISTERED_STORES.get(db_version)


def get_preload_snapshot(store: PreloadedStore) -> PreloadSnapshot:
    """Return a thread-safe immutable snapshot."""
    _ensure_runtime_fields(store)
    with store._lock:
        return PreloadSnapshot(
            total_pops=store.total_pops,
            loaded_count=store.loaded_count,
            loading_pop_id=store.loading_pop_id,
            is_loading=store.is_loading,
            is_complete=store.is_complete,
            first_loaded_pop_id=store.first_loaded_pop_id,
            load_revision=store.load_revision,
        )


def is_pop_loaded(store: PreloadedStore, region: str, pop: str) -> bool:
    """Return True when a POP dataset is ready for use in UI."""
    _ensure_runtime_fields(store)
    pop_id = make_pop_id(region, pop)
    with store._lock:
        dataset = store.datasets_by_pop_id.get(pop_id)
    return dataset is not None and not dataset.is_empty


def get_first_loaded_pop(
    store: PreloadedStore,
) -> tuple[str, str] | None:
    """Return (region, pop) for first successfully loaded POP."""
    snapshot = get_preload_snapshot(store)
    target = snapshot.first_loaded_pop_id
    if not target:
        return None
    for region in store.all_regions:
        for pop in store.catalog_by_region.get(region, []):
            if make_pop_id(region, pop) == target:
                return region, pop
    return None


def get_load_revision(store: PreloadedStore) -> int:
    """Return current incremental load revision."""
    return get_preload_snapshot(store).load_revision


def get_dataset(store: PreloadedStore, region: str, pop: str) -> PopDataset | None:
    """Get a preloaded dataset from memory, without DB access."""
    _ensure_runtime_fields(store)
    pop_id = make_pop_id(region, pop)
    with store._lock:
        return store.datasets_by_pop_id.get(pop_id)


def clear_registered_stores() -> None:
    """Clear in-process store registry."""
    for store in _REGISTERED_STORES.values():
        store._stop_event.set()
    _REGISTERED_STORES.clear()
