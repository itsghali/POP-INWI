"""
Module de gestion du cache et préchargement
"""
import streamlit as st
import time
from data_cleaning import DataCleaner


def preload_all_pops(data_cleaner, load_data_func):
    """
    Preload all POPs from all regions at startup
    This makes POP switching instantaneous after initial load
    
    Args:
        data_cleaner: Instance de DataCleaner
        load_data_func: Fonction de chargement de données (load_data)
    """
    # Check if preloading is already done
    if 'preload_completed' in st.session_state and st.session_state.preload_completed:
        return
    
    # Initialize preloading state
    if 'preload_started' not in st.session_state:
        st.session_state.preload_started = False
        st.session_state.preload_completed = False
        st.session_state.preload_progress = 0
        st.session_state.total_pops_to_load = 0
        st.session_state.loaded_pops_count = 0
    
    # If preloading was already started but not completed, don't restart it
    if st.session_state.get('preload_started', False) and not st.session_state.get('preload_completed', False):
        return
    
    # Get all available POPs from all regions
    try:
        regions = data_cleaner.get_regions()
        all_pops_list = []
        
        for region in regions:
            pops = data_cleaner.get_pops(region)
            for pop in pops:
                all_pops_list.append((region, pop))
        
        st.session_state.total_pops_to_load = len(all_pops_list)
        
        if not st.session_state.preload_started:
            st.session_state.preload_started = True
        
        # Create preloading UI
        preload_container = st.container()
        with preload_container:
            st.markdown("### 🚀 Initialisation du système")
            st.info(f"🔄 Chargement de {len(all_pops_list)} POPs pour une navigation rapide...")
            
            # Progress bars
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Load each POP
            start_time = time.time()
            successful_loads = 0
            failed_loads = 0
            
            for idx, (region, pop) in enumerate(all_pops_list):
                progress = (idx) / len(all_pops_list)
                progress_bar.progress(progress)
                status_text.text(f"Chargement {region}/{pop} ({idx+1}/{len(all_pops_list)})...")
                
                try:
                    # Load data for this POP
                    cleaned_data, merged_data = load_data_func(region, pop)
                    
                    if merged_data is not None and not merged_data.empty:
                        # Cache the data
                        pop_id = f"{region}_{pop}"
                        merged_data_copy = merged_data.copy()
                        merged_data_copy['Region'] = region
                        merged_data_copy['POP'] = pop
                        merged_data_copy['POP_ID'] = pop_id
                        st.session_state.multi_pop_cache[pop_id] = merged_data_copy
                        successful_loads += 1
                    else:
                        failed_loads += 1
                        
                except Exception as e:
                    failed_loads += 1
                    continue
                
                st.session_state.loaded_pops_count = idx + 1
            
            # Final progress update
            progress_bar.progress(1.0)
            
            total_time = time.time() - start_time
            
            # Mark as completed
            st.session_state.preload_completed = True
            
            # Show final success message (single, consolidated message)
            status_text.markdown(f"""
            ✅ **Préchargement terminé!**
            - ✅ {successful_loads} POPs chargés avec succès
            - ❌ {failed_loads} POPs échoués  
            - ⏱️ Temps total: {total_time:.1f} secondes
            - 🚀 **Navigation instantanée activée!**
            
            👆 Rechargez la page ou changez de POP dans la barre latérale!
            """)
            
            # Show a button to continue
            if st.button("✅ Continuer vers l'application", type="primary"):
                st.rerun()
                
    except Exception as e:
        st.error(f"❌ Erreur pendant le préchargement: {str(e)}")
        st.session_state.preload_started = False
        st.session_state.preload_completed = False
