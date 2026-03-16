"""
Module de gestion de la barre latérale (sidebar)
"""
import streamlit as st
from src.ui.period_selector import period_selector


def _render_preload_status():
    """Render non-blocking preload status information."""
    st.sidebar.markdown("---")
    status_placeholder = st.sidebar.empty()

    @st.fragment(run_every=1)
    def _preload_status_fragment():
        with status_placeholder.container():
            st.markdown("### ⚙️ Cache & Performance")
            st.markdown("### 🚀 Initialisation du système")

            preload_started = st.session_state.get('preload_started', False)
            preload_completed = st.session_state.get('preload_completed', False)
            loaded = st.session_state.get('loaded_pops_count', 0)
            total = st.session_state.get('total_pops_to_load', 0)
            success = st.session_state.get('preload_success_count', 0)
            failed = st.session_state.get('preload_fail_count', 0)
            status = st.session_state.get('current_preload_status', "")
            first_ready_pop = st.session_state.get('first_successful_pop_id')
            last_loaded_pop = st.session_state.get('last_loaded_pop_id')

            if preload_completed:
                st.success(
                    f"✅ Préchargement terminé: {success} POPs chargés, {failed} échecs."
                )
            elif preload_started:
                st.info(f"🔄 Préchargement en cours: {loaded}/{total} POPs")
                if total > 0:
                    st.progress(loaded / max(1, total))
                if status:
                    st.caption(status)
            else:
                st.info("⏳ Préchargement en attente de démarrage...")

            if first_ready_pop:
                st.caption(f"Premier POP prêt: {first_ready_pop}")

    _preload_status_fragment()


def _render_cache_controls():
    """Render cache controls without triggering blocking preload logic."""
    preload_completed = st.session_state.get("preload_completed", False)

    if st.sidebar.button(
        "⏩ Terminer le préchargement",
        help=(
            "Reprend le préchargement à partir du dernier POP traité "
            "sans repartir du début."
        ),
        disabled=preload_completed
    ):
        st.session_state.preload_force_finish_requested = True
        st.session_state.current_preload_status = "Demande de reprise du préchargement..."
        st.rerun()

    if st.sidebar.button(
        "🗑️ Vider le cache",
        help="Efface les données en mémoire et relance un nouveau cycle de préchargement."
    ):
        st.cache_data.clear()

        # App-level runtime reset request handled in app.py on next run
        st.session_state.preload_reset_requested = True

        # Immediate visual reset for sidebar
        st.session_state.multi_pop_cache = {}
        st.session_state.cached_pop_list = []
        st.session_state.preload_started = False
        st.session_state.preload_completed = False
        st.session_state.loaded_pops_count = 0
        st.session_state.total_pops_to_load = 0
        st.session_state.preload_success_count = 0
        st.session_state.preload_fail_count = 0
        st.session_state.current_preload_status = "Réinitialisation demandée..."
        st.session_state.first_successful_pop_id = None
        st.session_state.last_loaded_pop_id = None
        st.session_state.preload_force_finish_requested = False
        st.session_state.auto_sync_first_loaded_pop_done = False

        st.sidebar.success("✅ Cache vidé. Préchargement redémarré.")
        st.rerun()


def get_region_pop_selection(data_cleaner):
    """
    Gère la sélection de la région et du POP dans la barre latérale
    avec indicateurs de disponibilité des données.

    Args:
        data_cleaner: Instance de DataCleaner

    Returns:
        tuple: (selected_region, selected_pop)
    """
    period_selector.ensure_initialized()
    st.sidebar.title("Sélection du Site")

    _render_preload_status()
    _render_cache_controls()
    st.sidebar.markdown("---")

    # Sélection de la région
    regions = data_cleaner.get_regions()
    if not regions:
        st.error("Aucune région trouvée dans la base SQLite")
        st.stop()

    if "selected_region_ui" not in st.session_state or st.session_state.selected_region_ui not in regions:
        st.session_state.selected_region_ui = regions[0]
    if "selected_pop_ui" not in st.session_state:
        st.session_state.selected_pop_ui = None
    if "auto_sync_first_loaded_pop_done" not in st.session_state:
        st.session_state.auto_sync_first_loaded_pop_done = False

    first_loaded_id = st.session_state.get("first_successful_pop_id")
    if first_loaded_id and not st.session_state.auto_sync_first_loaded_pop_done:
        if "_" in first_loaded_id:
            loaded_region, loaded_pop = first_loaded_id.split("_", 1)
            if loaded_region in regions:
                loaded_region_pops = data_cleaner.get_pops(loaded_region)
                if loaded_pop in loaded_region_pops:
                    st.session_state.selected_region_ui = loaded_region
                    st.session_state.selected_pop_ui = loaded_pop
                    st.session_state.auto_sync_first_loaded_pop_done = True

    selected_region = st.sidebar.selectbox(
        "Sélectionnez une région",
        regions,
        key="selected_region_ui"
    )

    # Sélection du POP
    pops = data_cleaner.get_pops(selected_region)
    if not pops:
        st.error(f"Aucun POP trouvé dans la région {selected_region}")
        st.stop()

    if st.session_state.selected_pop_ui not in pops:
        st.session_state.selected_pop_ui = pops[0]

    # Vérifier la disponibilité des données pour chaque POP
    availability = {}
    for pop in pops:
        try:
            availability[pop] = data_cleaner.has_pop_data(selected_region, pop)
        except Exception:
            availability[pop] = False

    if not any(availability.values()):
        st.sidebar.warning(f"⚠️ Aucun POP dans {selected_region} n'a de données complètes")
        st.sidebar.info("💡 Essayez une autre région")

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

    # Render period selector
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Sélecteur de Période")
    period_selector.render_selector(key_suffix="main")

    return selected_region, selected_pop
