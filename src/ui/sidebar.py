"""
Sidebar — Region/POP selection, period selector, and cache controls.

Changes from previous version:
- Uses preloaded in-memory catalog for all region/POP discovery.
- Avoids repeated SQLite queries during navigation.
"""
from __future__ import annotations

import logging

import streamlit as st

from src.services import cache_service
from src.services.preload_service import (
    PreloadedStore,
    get_preload_snapshot,
    is_pop_loaded,
)
from src.ui.period_selector import period_selector

logger = logging.getLogger(__name__)


def _on_user_selection_change() -> None:
    """Mark that the user took manual control of POP/region selection."""
    st.session_state.user_selected_pop_locked = True


def _render_preload_status(store: PreloadedStore) -> None:
    """Render progressive preload status in sidebar."""
    snapshot = get_preload_snapshot(store)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⏳ Préchargement")

    if snapshot.total_pops <= 0:
        st.sidebar.caption("Aucun POP à précharger")
        return

    pct = min(1.0, snapshot.loaded_count / snapshot.total_pops)
    try:
        st.sidebar.progress(
            pct,
            text=f"{snapshot.loaded_count}/{snapshot.total_pops} POPs",
        )
    except TypeError:
        st.sidebar.progress(pct)
        st.sidebar.caption(
            f"{snapshot.loaded_count}/{snapshot.total_pops} POPs"
        )

    if snapshot.is_loading:
        st.sidebar.caption("Préchargement des POPs en cours...")
        if snapshot.loading_pop_id:
            st.sidebar.caption(f"POP en cours: {snapshot.loading_pop_id}")
    elif snapshot.is_complete:
        st.sidebar.caption("Préchargement terminé ✅")
    else:
        st.sidebar.caption("Préchargement en attente...")


def get_region_pop_selection(store: PreloadedStore) -> tuple[str, str]:
    """Render sidebar and return (selected_region, selected_pop).

    Args:
        store: Preloaded in-memory store.

    Returns:
        Tuple of (region, pop) as selected by the user.
    """
    period_selector.ensure_initialized()
    st.sidebar.title("Sélection du Site")

    # Cache controls
    _render_cache_controls()
    _render_preload_status(store)
    st.sidebar.markdown("---")

    # Region selection
    regions = store.all_regions
    if not regions:
        st.error("Aucune région trouvée dans le catalogue préchargé")
        st.stop()

    if (
        "selected_region_ui" not in st.session_state
        or st.session_state.selected_region_ui not in regions
    ):
        st.session_state.selected_region_ui = regions[0]

    selected_region = st.sidebar.selectbox(
        "Sélectionnez une région",
        regions,
        key="selected_region_ui",
        on_change=_on_user_selection_change,
    )

    # POP selection
    pops = store.catalog_by_region.get(selected_region, [])
    if not pops:
        st.error(f"Aucun POP trouvé dans la région {selected_region}")
        st.stop()

    if (
        "selected_pop_ui" not in st.session_state
        or st.session_state.selected_pop_ui not in pops
    ):
        st.session_state.selected_pop_ui = pops[0]

    # Readiness reflects actual in-memory preload state, not catalog metadata.
    readiness: dict[str, bool] = {
        pop: is_pop_loaded(store, selected_region, pop)
        for pop in pops
    }
    if not any(readiness.values()):
        st.sidebar.warning(
            f"Aucun POP de {selected_region} n'est prêt pour le moment."
        )
        st.sidebar.info(
            "Les POPs marqués '(données indisponibles)' ne sont pas encore "
            "préchargés ou n'ont pas de dataset exploitable."
        )

    selected_pop = st.sidebar.selectbox(
        "Sélectionnez un POP",
        pops,
        key="selected_pop_ui",
        format_func=lambda pop: (
            f"{pop} (données disponibles)"
            if readiness.get(pop, False)
            else f"{pop} (données indisponibles)"
        ),
        help="Affiche l'état de disponibilité des données en mémoire par POP",
        on_change=_on_user_selection_change,
    )

    # Period selector
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Sélecteur de Période")
    period_selector.render_selector(key_suffix="main")

    # Cache info
    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"📦 {get_preload_snapshot(store).loaded_count} POP(s) déjà préchargés"
    )

    return selected_region, selected_pop


def _render_cache_controls() -> None:
    """Render cache clear button."""
    if st.sidebar.button(
        "🗑️ Vider le cache",
        help="Efface les données en mémoire pour forcer un rechargement.",
    ):
        cache_service.clear_cache()
        st.session_state.user_selected_pop_locked = False
        st.session_state.auto_first_pop_applied = False
        st.session_state.preload_last_seen_revision = -1
        st.sidebar.success("✅ Cache vidé.")
        st.rerun()
