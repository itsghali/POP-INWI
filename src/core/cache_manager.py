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
    # Check if preloading is already completed
    if st.session_state.get('preload_completed', False):
        return
    
    # Initialize preloading state if not exists
    if 'preload_started' not in st.session_state:
        st.session_state.preload_started = False
        st.session_state.preload_completed = False
        st.session_state.preload_progress = 0
        st.session_state.total_pops_to_load = 0
        st.session_state.loaded_pops_count = 0
    
    # If preloading was already started but not completed, skip (don't restart mid-process)
    if st.session_state.get('preload_started', False):
        return
    
    # Get all available POPs from all regions (logic only, no UI)
    try:
        if 'multi_pop_cache' not in st.session_state:
            st.session_state.multi_pop_cache = {}

        regions = data_cleaner.get_regions()
        all_pops_list = []
        for region in regions:
            pops = data_cleaner.get_pops(region)
            for pop in pops:
                all_pops_list.append((region, pop))
        st.session_state.total_pops_to_load = len(all_pops_list)

        if not st.session_state.preload_started:
            st.session_state.preload_started = True

        # Load each POP (no UI)
        successful_loads = 0
        failed_loads = 0
        for idx, (region, pop) in enumerate(all_pops_list):
            try:
                cleaned_data, merged_data = load_data_func(region, pop, silent=True)
                if merged_data is not None and not merged_data.empty:
                    pop_id = f"{region}_{pop}"
                    merged_data_copy = merged_data.copy()
                    merged_data_copy['Region'] = region
                    merged_data_copy['POP'] = pop
                    merged_data_copy['POP_ID'] = pop_id
                    st.session_state.multi_pop_cache[pop_id] = merged_data_copy
                    successful_loads += 1
                    st.session_state.loaded_pops_count = successful_loads
                else:
                    failed_loads += 1
            except Exception:
                failed_loads += 1
                continue
        st.session_state.preload_completed = True
    except Exception:
        st.session_state.preload_started = False
        st.session_state.preload_completed = False
