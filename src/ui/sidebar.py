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

    # --- Affichage de la progression du préchargement en haut de la sidebar ---
    if not st.session_state.get('preload_completed', False):
        st.sidebar.markdown("### 🚀 Initialisation du système")
        if not st.session_state.get('preload_started', False):
            # Lancer le préchargement (en mode non-bloquant pour l'UI)
            st.session_state.preload_started = True
            regions = data_cleaner.get_regions()
            all_pops_list = []
            for region in regions:
                pops = data_cleaner.get_pops(region)
                for pop in pops:
                    all_pops_list.append((region, pop))
            st.session_state.total_pops_to_load = len(all_pops_list)
            st.session_state.loaded_pops_count = 0
            st.session_state._preload_pops_list = all_pops_list
            st.session_state._preload_idx = 0
            st.session_state._preload_success = 0
            st.session_state._preload_fail = 0
        # Afficher la progression
        total = st.session_state.get('total_pops_to_load', 1)
        loaded = st.session_state.get('loaded_pops_count', 0)
        progress = loaded / max(1, total)
        st.sidebar.info(f"🔄 Chargement de {total} POPs pour une navigation rapide...")
        st.sidebar.progress(progress)
        if 'current_preload_status' in st.session_state:
            st.sidebar.text(st.session_state['current_preload_status'])

        # Bouton Terminer préchargement toujours visible pendant le préchargement
        if st.sidebar.button("⏩ Terminer préchargement", help="Force la fin du préchargement et continue à partir du dernier POP chargé."):
            idx = st.session_state.get('_preload_idx', 0)
            if idx < total:
                try:
                    from src.core.data_loader import load_data
                    for i in range(idx, total):
                        region, pop = st.session_state._preload_pops_list[i]
                        cleaned_data, merged_data = load_data(region, pop, silent=True)
                        if merged_data is not None and not merged_data.empty:
                            pop_id = f"{region}_{pop}"
                            merged_data_copy = merged_data.copy()
                            merged_data_copy['Region'] = region
                            merged_data_copy['POP'] = pop
                            merged_data_copy['POP_ID'] = pop_id
                            st.session_state.multi_pop_cache[pop_id] = merged_data_copy
                            st.session_state._preload_success += 1
                        else:
                            st.session_state._preload_fail += 1
                        st.session_state.loaded_pops_count += 1
                        st.session_state._preload_idx += 1
                except Exception:
                    pass
            st.session_state.preload_completed = True
            for k in ['_preload_pops_list', '_preload_idx', '_preload_success', '_preload_fail', 'current_preload_status']:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

        # Effectuer un pas de préchargement à chaque run
        if st.session_state.get('_preload_idx', 0) < st.session_state.get('total_pops_to_load', 0):
            idx = st.session_state._preload_idx
            region, pop = st.session_state._preload_pops_list[idx]
            st.session_state['current_preload_status'] = f"Chargement {region}/{pop} ({idx+1}/{total})...  Running load_data(...)"
            try:
                from src.core.data_loader import load_data
                cleaned_data, merged_data = load_data(region, pop, silent=True)
                if merged_data is not None and not merged_data.empty:
                    pop_id = f"{region}_{pop}"
                    merged_data_copy = merged_data.copy()
                    merged_data_copy['Region'] = region
                    merged_data_copy['POP'] = pop
                    merged_data_copy['POP_ID'] = pop_id
                    st.session_state.multi_pop_cache[pop_id] = merged_data_copy
                    st.session_state._preload_success += 1
                else:
                    st.session_state._preload_fail += 1
            except Exception:
                st.session_state._preload_fail += 1
            st.session_state.loaded_pops_count += 1
            st.session_state._preload_idx += 1
            # Forcer le rerun pour continuer le chargement
            st.rerun()
        else:
            st.session_state.preload_completed = True
            nb_success = st.session_state.get('_preload_success', 0)
            nb_fail = st.session_state.get('_preload_fail', 0)
            st.sidebar.markdown(f"""
            ✅ **Préchargement terminé!**
            - ✅ {nb_success} POPs chargés avec succès
            - ❌ {nb_fail} POPs vides ou échoués
            - 🚀 **Navigation instantanée activée!**
            👆 Vous pouvez maintenant changer de POP rapidement dans la barre latérale!
            """)
            # Nettoyage des variables temporaires
            for k in ['_preload_pops_list', '_preload_idx', '_preload_success', '_preload_fail', 'current_preload_status']:
                if k in st.session_state:
                    del st.session_state[k]
    """
    Gère la sélection de la région et du POP dans la barre latérale 
    avec indicateurs de disponibilité des données
    
    Args:
        data_cleaner: Instance de DataCleaner
        
    Returns:
        tuple: (selected_region, selected_pop)
    """
    period_selector.ensure_initialized()
    
    # Performance options section (restored to original position)
    st.sidebar.markdown("---")
    
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

    # Bouton Terminer préchargement (visible uniquement si préchargement en cours)
    if not st.session_state.get('preload_completed', False) and st.session_state.get('preload_started', False):
        if st.sidebar.button("⏩ Terminer préchargement", help="Force la fin du préchargement et continue à partir du dernier POP chargé."):
            # On saute directement à la fin du préchargement, mais on ne recommence pas depuis zéro
            # On continue à partir de l'index courant
            total = st.session_state.get('total_pops_to_load', 0)
            idx = st.session_state.get('_preload_idx', 0)
            if idx < total:
                # On boucle sur les POPs restants pour finir le préchargement rapidement
                try:
                    from src.core.data_loader import load_data
                    for i in range(idx, total):
                        region, pop = st.session_state._preload_pops_list[i]
                        cleaned_data, merged_data = load_data(region, pop, silent=True)
                        if merged_data is not None and not merged_data.empty:
                            pop_id = f"{region}_{pop}"
                            merged_data_copy = merged_data.copy()
                            merged_data_copy['Region'] = region
                            merged_data_copy['POP'] = pop
                            merged_data_copy['POP_ID'] = pop_id
                            st.session_state.multi_pop_cache[pop_id] = merged_data_copy
                            st.session_state._preload_success += 1
                        else:
                            st.session_state._preload_fail += 1
                        st.session_state.loaded_pops_count += 1
                        st.session_state._preload_idx += 1
                except Exception:
                    pass
            st.session_state.preload_completed = True
            # Nettoyage des variables temporaires
            for k in ['_preload_pops_list', '_preload_idx', '_preload_success', '_preload_fail', 'current_preload_status']:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()
    
    # Show preloading status in sidebar
    if st.session_state.preload_enabled:
        if 'preload_completed' in st.session_state:
            if st.session_state.get('preload_completed', False):
                print("")
                if 'loaded_pops_count' in st.session_state and st.session_state.loaded_pops_count > 0:
                    st.sidebar.info(f"")
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
    
    
    # Render period selector AFTER loading message
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📅 Sélecteur de Période")
    period_selector.render_selector(key_suffix="main")
    
    return selected_region, selected_pop
