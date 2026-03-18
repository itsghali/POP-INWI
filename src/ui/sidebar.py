"""
Sidebar — Region/POP selection, period selector, and cache controls.

Changes from previous version:
- Removed auto-switch to first preloaded POP (confusing UX)
- Removed preload status/progress display (no more background preload)
- Uses PopRepository for discovery (single source of truth)
- Uses cache_service for simple cache management
- User selection is always stable and respected
"""
from __future__ import annotations

import logging

import streamlit as st

from src.services import cache_service
from src.services.pop_repository import PopRepository
from src.ui.period_selector import period_selector

logger = logging.getLogger(__name__)


def get_region_pop_selection(repo: PopRepository) -> tuple[str, str]:
    """Render sidebar and return (selected_region, selected_pop).

    Args:
        repo: PopRepository for region/POP discovery and availability checks.

    Returns:
        Tuple of (region, pop) as selected by the user.
    """
    period_selector.ensure_initialized()
    st.sidebar.title("Sélection du Site")

    # Cache controls
    _render_cache_controls()
    st.sidebar.markdown("---")

    # Region selection
    regions = repo.get_regions()
    if not regions:
        st.error("Aucune région trouvée dans la base de données")
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
    )

    # POP selection
    pops = repo.get_pops(selected_region)
    if not pops:
        st.error(f"Aucun POP trouvé dans la région {selected_region}")
        st.stop()

    if (
        "selected_pop_ui" not in st.session_state
        or st.session_state.selected_pop_ui not in pops
    ):
        st.session_state.selected_pop_ui = pops[0]

    # Check data availability for each POP
    availability: dict[str, bool] = {}
    for pop in pops:
        try:
            availability[pop] = repo.has_pop_data(selected_region, pop)
        except Exception:
            availability[pop] = False

    if not any(availability.values()):
        st.sidebar.warning(
            f"Aucun POP dans {selected_region} n'a de données complètes"
        )
        st.sidebar.info("Essayez une autre région")

    selected_pop = st.sidebar.selectbox(
        "Sélectionnez un POP",
        pops,
        key="selected_pop_ui",
        format_func=lambda pop: (
            f"✅ {pop} (données disponibles)"
            if availability.get(pop, False)
            else f"❌ {pop} (données manquantes)"
        ),
        help="✅ = Données disponibles, ❌ = Données manquantes",
    )

    # Period selector
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Sélecteur de Période")
    period_selector.render_selector(key_suffix="main")

    # Cache info
    st.sidebar.markdown("---")
    n_cached = cache_service.cache_size()
    if n_cached > 0:
        st.sidebar.caption(f"📦 {n_cached} POP(s) en cache")

    return selected_region, selected_pop


def _render_cache_controls() -> None:
    """Render cache clear button."""
    if st.sidebar.button(
        "🗑️ Vider le cache",
        help="Efface les données en mémoire pour forcer un rechargement.",
    ):
        cache_service.clear_cache()
        st.sidebar.success("✅ Cache vidé.")
        st.rerun()
