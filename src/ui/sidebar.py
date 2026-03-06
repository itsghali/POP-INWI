"""
Module de gestion de la barre latérale (sidebar)
"""
import streamlit as st
import time
from src.utils.startup_detection import is_server_startup
from src.ui.period_selector import period_selector


def get_region_pop_selection(data_cleaner):
    """
    Gère la sélection de la région et du POP dans la barre latérale 
    avec indicateurs de disponibilité des données
    
    Args:
        data_cleaner: Instance de DataCleaner
        
    Returns:
        tuple: (selected_region, selected_pop)
    """
    period_selector.ensure_initialized()
    st.sidebar.title("Sélection du Site")
    
    # Performance options section (restored to original position)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Cache & Performance")
    
    # Initialize preloading preference - ALWAYS enabled automatically
    if 'preload_enabled' not in st.session_state:
        st.session_state.preload_enabled = True  # ✅ Automatique par défaut
        # Initialize all preloading state variables
        st.session_state.preload_started = False
        st.session_state.preload_completed = False
        st.session_state.preload_progress = 0
        st.session_state.loaded_pops_count = 0
        st.session_state.preload_session_attempted = False
    
    # Show preloading status (informational only - no user control)
    if st.session_state.get('preload_completed', False):
        total_pops = st.session_state.get('loaded_pops_count', 0)
        st.sidebar.success(f"✅ {total_pops} POPs préchargés")
    elif st.session_state.get('preload_started', False):
        progress = st.session_state.get('preload_progress', 0)
        st.sidebar.info(f"🔄 Chargement en cours... {int(progress*100)}%")
    
    # Clear cache button
    if st.sidebar.button("🗑️ Vider le cache", help="Efface le cache - Utile après actualisation du navigateur"):
        # Clear all cached data
        st.session_state.multi_pop_cache = {}
        st.session_state.preload_completed = False
        st.session_state.preload_started = False
        st.session_state.loaded_pops_count = 0
        st.session_state.total_pops_to_load = 0
        st.session_state.preload_progress = 0
        st.session_state.preload_session_attempted = False  # Allow new preload attempt
        st.session_state.refresh_message_shown = False  # Reset message flag
        # Reset startup detection cache
        if 'startup_detection_cached' in st.session_state:
            del st.session_state.startup_detection_cached
            del st.session_state.startup_detection_result
        # Clear Streamlit's @st.cache_data
        st.cache_data.clear()
        st.sidebar.success("✅ Cache vidé! Actualisez de nouveau si nécessaire.")
    
    # Show preloading status in sidebar
    if st.session_state.preload_enabled:
        if 'preload_completed' in st.session_state:
            if st.session_state.get('preload_completed', False):
                st.sidebar.success("🚀 Navigation rapide activée!")
                if 'loaded_pops_count' in st.session_state and st.session_state.loaded_pops_count > 0:
                    st.sidebar.info(f"💾 {st.session_state.loaded_pops_count} POPs en cache")
            elif st.session_state.get('preload_started', False):
                # Check if preloading might be stuck (no progress for too long)
                current_time = time.time()
                
                if 'preload_last_update' not in st.session_state:
                    st.session_state.preload_last_update = current_time
                
                # If no progress for more than 60 seconds, consider it stuck
                time_since_update = current_time - st.session_state.preload_last_update
                
                progress = st.session_state.get('loaded_pops_count', 0) / max(1, st.session_state.get('total_pops_to_load', 1))
                st.sidebar.progress(progress)
                st.sidebar.info(f"⏳ Préchargement... {st.session_state.get('loaded_pops_count', 0)}/{st.session_state.get('total_pops_to_load', 0)}")
                
                # Add force restart button when preloading is in progress
                if st.sidebar.button("🔄 Forcer le redémarrage", help="Force le redémarrage du préchargement s'il est bloqué"):
                    # Complete reset of all preloading states
                    st.session_state.preload_started = False
                    st.session_state.preload_completed = False
                    st.session_state.loaded_pops_count = 0
                    st.session_state.total_pops_to_load = 0
                    st.session_state.preload_progress = 0
                    st.session_state.preload_session_attempted = False  # Allow new preload attempt
                    st.session_state.preload_last_update = current_time  # Reset timer
                    # Also clear any cached data to force fresh start
                    st.session_state.multi_pop_cache = {}
                    st.cache_data.clear()
                    st.sidebar.success("🔄 Redémarrage forcé - états réinitialisés!")
                    st.sidebar.info("↻ La page va se recharger automatiquement...")
                    st.rerun()  # Force reload to restart fresh
    
    st.sidebar.markdown("---")
    
    # Sélection de la région
    regions = data_cleaner.get_regions()
    if not regions:
        st.error("Aucune région trouvée dans la base SQLite")
        st.stop()
        
    selected_region = st.sidebar.selectbox(
        "Sélectionnez une région",
        regions
    )
    
    # Sélection du POP
    pops = data_cleaner.get_pops(selected_region)
    if not pops:
        st.error(f"Aucun POP trouvé dans la région {selected_region}")
        st.stop()
    
    # Vérifier la disponibilité des données pour chaque POP
    def check_pop_data_availability(region, pop):
        """Vérifie si un POP a les données requises dans la DB"""
        try:
            return data_cleaner.has_pop_data(region, pop)
        except Exception:
            return False
    
    # Créer une liste des POPs avec indicateurs de disponibilité
    pop_options = []
    for pop in pops:
        has_data = check_pop_data_availability(selected_region, pop)
        if has_data:
            pop_options.append(f"✅ {pop} (données disponibles)")
        else:
            pop_options.append(f"❌ {pop} (données manquantes)")
    
    # Si aucun POP n'a de données, afficher une alerte
    available_pops = [pop for pop in pops if check_pop_data_availability(selected_region, pop)]
    if not available_pops:
        st.sidebar.warning(f"⚠️ Aucun POP dans {selected_region} n'a de données complètes")
        st.sidebar.info("💡 Essayez d'autre Région")
    
    selected_pop_display = st.sidebar.selectbox(
        "Sélectionnez un POP",
        pop_options,
        help="✅ = Données disponibles, ❌ = Données manquantes"
    )
    
    # Extraire le nom réel du POP (sans l'indicateur)
    selected_pop = selected_pop_display.split(' ', 1)[1].split(' (')[0]
    
    # Display loading message BEFORE period selector
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### 🎯 Début du chargement: {selected_region}/{selected_pop}")
    
    # Render period selector AFTER loading message
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Sélecteur de Période")
    period_selector.render_selector(key_suffix="main")
    
    return selected_region, selected_pop
