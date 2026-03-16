import queue
import threading
import warnings
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from data_cleaning import DataCleaner
from src.core.data_filter import filter_by_date_range, validate_data_availability
from src.core.data_loader import load_data
from src.ui.app_orchestrator import orchestrate_dashboard
from src.ui.period_selector import period_selector
from src.ui.sidebar import get_region_pop_selection
from src.ui.styles import apply_custom_css, apply_print_styles, render_page_header

warnings.filterwarnings("ignore")


def _init_session_state() -> None:
    defaults = {
        "multi_pop_cache": {},
        "cached_pop_list": [],
        "preload_started": False,
        "preload_completed": False,
        "loaded_pops_count": 0,
        "total_pops_to_load": 0,
        "preload_success_count": 0,
        "preload_fail_count": 0,
        "current_preload_status": "",
        "first_successful_pop_id": None,
        "last_loaded_pop_id": None,
        "preload_force_finish_requested": False,
        "preload_reset_requested": False,
        "_preload_pops_list": [],
        "_preload_event_queue": None,
        "_preload_thread": None,
        "_preload_stop_event": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _coerce_datetime(value, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, str):
        try:
            return pd.to_datetime(value).to_pydatetime()
        except Exception:
            return fallback
    return fallback


def _build_preload_pop_list(cleaner: DataCleaner) -> List[Tuple[str, str]]:
    all_pops = []
    for region in cleaner.get_regions():
        for pop in cleaner.get_pops(region):
            all_pops.append((region, pop))
    return all_pops


def _bg_preload_worker(
    pops_to_load: List[Tuple[str, str]],
    event_queue: "queue.Queue[Dict[str, object]]",
    stop_event: threading.Event,
    start_index: int = 0,
    total_count: int = None,
    initial_success: int = 0,
    initial_failed: int = 0,
) -> None:
    total = total_count if total_count is not None else (start_index + len(pops_to_load))
    success = initial_success
    failed = initial_failed

    for local_idx, (region, pop) in enumerate(pops_to_load, start=1):
        if stop_event.is_set():
            break

        idx = start_index + local_idx
        pop_id = f"{region}_{pop}"
        event_queue.put(
            {
                "type": "current",
                "status": f"En cours: {region}/{pop} ({idx}/{total})",
                "loaded": idx - 1,
                "total": total,
                "success": success,
                "failed": failed,
                "pop_id": pop_id,
            }
        )

        try:
            _, merged_data = load_data(region, pop, silent=True)
            if merged_data is not None and isinstance(merged_data, pd.DataFrame) and not merged_data.empty:
                merged_copy = merged_data.copy()
                merged_copy["Region"] = region
                merged_copy["POP"] = pop
                merged_copy["POP_ID"] = pop_id
                success += 1
                event_queue.put(
                    {
                        "type": "pop_loaded",
                        "pop_id": pop_id,
                        "data": merged_copy,
                        "success": success,
                        "failed": failed,
                        "loaded": idx,
                        "total": total,
                    }
                )
            else:
                failed += 1
        except Exception:
            failed += 1
        finally:
            event_queue.put(
                {
                    "type": "progress",
                    "loaded": idx,
                    "total": total,
                    "success": success,
                    "failed": failed,
                    "status": f"Traité: {region}/{pop} ({idx}/{total})",
                }
            )

    event_queue.put(
        {
            "type": "done",
            "loaded": success + failed,
            "total": total,
            "success": success,
            "failed": failed,
            "stopped": stop_event.is_set(),
        }
    )


def _apply_preload_reset_if_requested() -> None:
    if not st.session_state.get("preload_reset_requested", False):
        return

    stop_event = st.session_state.get("_preload_stop_event")
    if isinstance(stop_event, threading.Event):
        stop_event.set()

    st.session_state["multi_pop_cache"] = {}
    st.session_state["cached_pop_list"] = []
    st.session_state["preload_started"] = False
    st.session_state["preload_completed"] = False
    st.session_state["loaded_pops_count"] = 0
    st.session_state["total_pops_to_load"] = 0
    st.session_state["preload_success_count"] = 0
    st.session_state["preload_fail_count"] = 0
    st.session_state["current_preload_status"] = ""
    st.session_state["first_successful_pop_id"] = None
    st.session_state["last_loaded_pop_id"] = None
    st.session_state["preload_force_finish_requested"] = False
    st.session_state["auto_sync_first_loaded_pop_done"] = False

    st.session_state["_preload_pops_list"] = []
    st.session_state["_preload_event_queue"] = None
    st.session_state["_preload_thread"] = None
    st.session_state["_preload_stop_event"] = None
    st.session_state["preload_reset_requested"] = False


def _handle_force_finish_request(cleaner: DataCleaner) -> None:
    if not st.session_state.get("preload_force_finish_requested", False):
        return

    st.session_state["preload_force_finish_requested"] = False

    all_pops = st.session_state.get("_preload_pops_list", [])
    if not all_pops:
        all_pops = _build_preload_pop_list(cleaner)
        st.session_state["_preload_pops_list"] = all_pops
        st.session_state["total_pops_to_load"] = len(all_pops)

    total = st.session_state.get("total_pops_to_load", len(all_pops))
    loaded = min(st.session_state.get("loaded_pops_count", 0), total)
    success = st.session_state.get("preload_success_count", 0)
    failed = st.session_state.get("preload_fail_count", 0)

    if loaded >= total:
        st.session_state.preload_started = False
        st.session_state.preload_completed = True
        st.session_state.current_preload_status = "Préchargement déjà terminé."
        return

    old_stop_event = st.session_state.get("_preload_stop_event")
    if isinstance(old_stop_event, threading.Event):
        old_stop_event.set()

    old_thread = st.session_state.get("_preload_thread")
    if isinstance(old_thread, threading.Thread) and old_thread.is_alive():
        old_thread.join(timeout=1.0)

    remaining_pops = all_pops[loaded:]
    new_queue: "queue.Queue[Dict[str, object]]" = queue.Queue()
    new_stop_event = threading.Event()

    worker = threading.Thread(
        target=_bg_preload_worker,
        args=(remaining_pops, new_queue, new_stop_event, loaded, total, success, failed),
        daemon=True,
        name="pop-preload-worker-resume",
    )
    worker.start()

    st.session_state["_preload_event_queue"] = new_queue
    st.session_state["_preload_stop_event"] = new_stop_event
    st.session_state["_preload_thread"] = worker
    st.session_state.preload_started = True
    st.session_state.preload_completed = False
    st.session_state.current_preload_status = (
        f"Reprise du préchargement depuis {loaded}/{total}..."
    )


def _start_preload_worker_if_needed(cleaner: DataCleaner) -> None:
    if st.session_state.get("preload_completed", False):
        return

    existing_thread = st.session_state.get("_preload_thread")
    if isinstance(existing_thread, threading.Thread) and existing_thread.is_alive():
        st.session_state.preload_started = True
        return

    # Thread finished but completion event may still be waiting in queue.
    if isinstance(existing_thread, threading.Thread) and not existing_thread.is_alive():
        if st.session_state.get("preload_started", False):
            return

    pops_to_load = _build_preload_pop_list(cleaner)
    event_queue: "queue.Queue[Dict[str, object]]" = queue.Queue()
    stop_event = threading.Event()

    st.session_state["_preload_pops_list"] = pops_to_load
    st.session_state["_preload_event_queue"] = event_queue
    st.session_state["_preload_stop_event"] = stop_event
    st.session_state["total_pops_to_load"] = len(pops_to_load)
    st.session_state["loaded_pops_count"] = 0
    st.session_state["preload_success_count"] = 0
    st.session_state["preload_fail_count"] = 0
    st.session_state["current_preload_status"] = "Préchargement initialisé..."
    st.session_state["preload_started"] = True
    st.session_state["preload_completed"] = False

    worker = threading.Thread(
        target=_bg_preload_worker,
        args=(pops_to_load, event_queue, stop_event),
        daemon=True,
        name="pop-preload-worker",
    )
    worker.start()
    st.session_state["_preload_thread"] = worker


def _drain_preload_events(selected_pop_id: str = "") -> Dict[str, bool]:
    event_queue = st.session_state.get("_preload_event_queue")
    if event_queue is None:
        return {
            "new_data": False,
            "first_success": False,
            "selected_ready": False,
            "completed": False,
            "should_rerun": False,
        }

    new_data = False
    first_success = False
    selected_ready = False
    completed = False

    while True:
        try:
            event = event_queue.get_nowait()
        except queue.Empty:
            break

        event_type = event.get("type")

        if event_type == "pop_loaded":
            pop_id = event.get("pop_id")
            data = event.get("data")
            if pop_id and isinstance(data, pd.DataFrame):
                st.session_state.multi_pop_cache[pop_id] = data
                if pop_id not in st.session_state.cached_pop_list:
                    st.session_state.cached_pop_list.append(pop_id)
                new_data = True
                st.session_state.last_loaded_pop_id = pop_id

                if not st.session_state.get("first_successful_pop_id"):
                    st.session_state.first_successful_pop_id = pop_id
                    first_success = True
                if selected_pop_id and pop_id == selected_pop_id:
                    selected_ready = True

            st.session_state.preload_success_count = event.get(
                "success", st.session_state.preload_success_count
            )
            st.session_state.preload_fail_count = event.get(
                "failed", st.session_state.preload_fail_count
            )
            st.session_state.loaded_pops_count = event.get(
                "loaded", st.session_state.loaded_pops_count
            )
            st.session_state.total_pops_to_load = event.get(
                "total", st.session_state.total_pops_to_load
            )

        elif event_type == "progress":
            st.session_state.loaded_pops_count = event.get(
                "loaded", st.session_state.loaded_pops_count
            )
            st.session_state.total_pops_to_load = event.get(
                "total", st.session_state.total_pops_to_load
            )
            st.session_state.preload_success_count = event.get(
                "success", st.session_state.preload_success_count
            )
            st.session_state.preload_fail_count = event.get(
                "failed", st.session_state.preload_fail_count
            )
            status = event.get("status", "")
            if status:
                st.session_state.current_preload_status = status

        elif event_type == "current":
            st.session_state.loaded_pops_count = event.get(
                "loaded", st.session_state.loaded_pops_count
            )
            st.session_state.total_pops_to_load = event.get(
                "total", st.session_state.total_pops_to_load
            )
            st.session_state.preload_success_count = event.get(
                "success", st.session_state.preload_success_count
            )
            st.session_state.preload_fail_count = event.get(
                "failed", st.session_state.preload_fail_count
            )
            status = event.get("status", "")
            if status:
                st.session_state.current_preload_status = status

        elif event_type == "done":
            st.session_state.preload_started = False
            st.session_state.preload_completed = True
            st.session_state.loaded_pops_count = event.get(
                "loaded", st.session_state.loaded_pops_count
            )
            st.session_state.total_pops_to_load = event.get(
                "total", st.session_state.total_pops_to_load
            )
            st.session_state.preload_success_count = event.get(
                "success", st.session_state.preload_success_count
            )
            st.session_state.preload_fail_count = event.get(
                "failed", st.session_state.preload_fail_count
            )
            stopped = event.get("stopped", False)
            st.session_state.current_preload_status = (
                "Préchargement interrompu." if stopped else "Préchargement terminé."
            )
            completed = True

    worker = st.session_state.get("_preload_thread")
    if (
        isinstance(worker, threading.Thread)
        and not worker.is_alive()
        and st.session_state.get("preload_started", False)
        and event_queue.empty()
    ):
        st.session_state.preload_started = False
        st.session_state.preload_completed = True
        st.session_state.current_preload_status = "Préchargement terminé."
        completed = True

    should_rerun = first_success or selected_ready or completed
    return {
        "new_data": new_data,
        "first_success": first_success,
        "selected_ready": selected_ready,
        "completed": completed,
        "should_rerun": should_rerun,
    }


@st.fragment(run_every=1)
def _preload_poller_fragment(selected_pop_id: str) -> None:
    result = _drain_preload_events(selected_pop_id)
    if result["should_rerun"]:
        st.rerun()


def _resolve_data_for_display(
    selected_region: str, selected_pop: str
) -> Tuple[pd.DataFrame, str, str, str]:
    selected_pop_id = f"{selected_region}_{selected_pop}"
    multi_cache = st.session_state.get("multi_pop_cache", {})

    selected_cached = multi_cache.get(selected_pop_id)
    if isinstance(selected_cached, pd.DataFrame) and not selected_cached.empty:
        return selected_cached, selected_region, selected_pop, selected_pop_id

    if not st.session_state.get("preload_completed", False):
        first_loaded_id = st.session_state.get("first_successful_pop_id")
        if first_loaded_id:
            first_loaded_data = multi_cache.get(first_loaded_id)
            if isinstance(first_loaded_data, pd.DataFrame) and not first_loaded_data.empty:
                if "_" in first_loaded_id:
                    region_display, pop_display = first_loaded_id.split("_", 1)
                else:
                    region_display, pop_display = selected_region, selected_pop
                return first_loaded_data, region_display, pop_display, first_loaded_id
        return None, selected_region, selected_pop, None

    _, merged_data = load_data(selected_region, selected_pop)
    if isinstance(merged_data, pd.DataFrame) and not merged_data.empty:
        merged_copy = merged_data.copy()
        merged_copy["Region"] = selected_region
        merged_copy["POP"] = selected_pop
        merged_copy["POP_ID"] = selected_pop_id
        st.session_state.multi_pop_cache[selected_pop_id] = merged_copy
        if selected_pop_id not in st.session_state.cached_pop_list:
            st.session_state.cached_pop_list.append(selected_pop_id)
        return merged_copy, selected_region, selected_pop, selected_pop_id

    return None, selected_region, selected_pop, None


def _prepare_and_filter_data(
    merged_data: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, datetime, datetime]:
    prepared = merged_data.copy()

    if "Timestamp" in prepared.columns:
        prepared["Timestamp"] = pd.to_datetime(prepared["Timestamp"], errors="coerce", utc=False)
        prepared = prepared.dropna(subset=["Timestamp"])

    if prepared.empty:
        now = datetime.now()
        return prepared, prepared, now, now

    now = datetime.now()
    if "Timestamp" in prepared.columns:
        ts_min = prepared["Timestamp"].min()
        ts_max = prepared["Timestamp"].max()
        default_start = _coerce_datetime(ts_min, now)
        default_end = _coerce_datetime(ts_max, now)
    else:
        default_start = now
        default_end = now

    if "start_date" not in st.session_state:
        st.session_state.start_date = default_start
    if "end_date" not in st.session_state:
        st.session_state.end_date = default_end

    start_date = _coerce_datetime(st.session_state.start_date, default_start)
    end_date = _coerce_datetime(st.session_state.end_date, default_end)

    if "unified_period" in st.session_state:
        sidebar_start = st.session_state.unified_period.get("start_date")
        sidebar_end = st.session_state.unified_period.get("end_date")
        if sidebar_start is not None and sidebar_end is not None:
            start_date = _coerce_datetime(sidebar_start, start_date)
            end_date = _coerce_datetime(sidebar_end, end_date)

    st.session_state.start_date = start_date
    st.session_state.end_date = end_date

    filtered = filter_by_date_range(prepared, start_date, end_date)
    required_cols = ["Temp_Ambiante", "Timestamp"]
    is_valid, missing = validate_data_availability(filtered, required_cols)
    if not is_valid and len(filtered) > 0:
        st.warning(f"⚠️ Colonnes manquantes: {missing}")

    return filtered, prepared, start_date, end_date


st.set_page_config(
    page_title="Centre de Données INWI - Tableau de Bord",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

data_cleaner = DataCleaner("data")
period_selector.ensure_initialized()

_init_session_state()
_apply_preload_reset_if_requested()
_start_preload_worker_if_needed(data_cleaner)
_drain_preload_events("")

selected_region, selected_pop = get_region_pop_selection(data_cleaner)
selected_pop_id = f"{selected_region}_{selected_pop}"

sync_result = _drain_preload_events(selected_pop_id)
if sync_result.get("first_success") and not st.session_state.get(
    "auto_sync_first_loaded_pop_done", False
):
    st.rerun()

_handle_force_finish_request(data_cleaner)
_drain_preload_events(selected_pop_id)

if st.session_state.get("preload_started", False) and not st.session_state.get("preload_completed", False):
    _preload_poller_fragment(selected_pop_id)

render_page_header(selected_pop, selected_region)
apply_custom_css()
apply_print_styles()

try:
    merged_data, region_display, pop_display, displayed_pop_id = _resolve_data_for_display(
        selected_region, selected_pop
    )

    if merged_data is None:
        now = datetime.now()
        orchestrate_dashboard(
            pd.DataFrame(),
            pd.DataFrame(),
            now,
            now,
            selected_region,
            selected_pop,
            is_preloading=not st.session_state.get("preload_completed", False),
        )
    else:
        if not st.session_state.get("preload_completed", False):
            first_pop_id = st.session_state.get("first_successful_pop_id")
            if first_pop_id:
                st.success(f"✅ 1er POP chargé avec succès disponible: {first_pop_id}")

        filtered_data, prepared_data, start_date, end_date = _prepare_and_filter_data(merged_data)
        if prepared_data.empty:
            st.error("❌ Aucune donnée valide après préparation.")
            st.stop()

        orchestrate_dashboard(
            filtered_data,
            prepared_data,
            start_date,
            end_date,
            region_display,
            pop_display,
            is_preloading=False,
        )
except Exception as exc:
    st.error(f"❌ Erreur lors du chargement des données: {str(exc)}")
    import traceback

    st.sidebar.error(traceback.format_exc())
    st.stop()

st.markdown("---")
st.caption("🏢 Data Center Monitoring Dashboard | © 2025")
