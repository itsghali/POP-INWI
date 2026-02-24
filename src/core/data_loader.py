"""
Module de chargement des données
"""
import streamlit as st
import pandas as pd
from data_cleaning import DataCleaner


@st.cache_data
def load_data(region, pop):
    """Charge les données avec gestion robuste - VERSION COMPLÈTE"""
    try:
        st.sidebar.write(f"🎯 Début du chargement: {region}/{pop}")
        
        cleaner = DataCleaner(auto_sync=False)  # No auto-sync in cached function
        
        # Vérifier que la région et le POP existent
        regions = cleaner.get_regions()
        pops = cleaner.get_pops(region) if region else []
        
        if region not in regions:
            return {}, pd.DataFrame()
            
        if pop not in pops:
            return {}, pd.DataFrame()
        
        # Chargement avec spinner
        with st.spinner(f"📂 Chargement de {region}/{pop}..."):
            result = cleaner.load_pops_data(region=region, pop=pop)
        
        # Gestion des différents types de retour
        if isinstance(result, tuple) and len(result) == 2:
            cleaned_data, merged_data = result
            
        elif isinstance(result, dict):
            # Si c'est un dict de DataFrames (multiple POPs)
            if result and any(isinstance(v, pd.DataFrame) for v in result.values()):
                first_key = list(result.keys())[0]
                merged_data = result[first_key]
                cleaned_data = {}
            else:
                # Si c'est cleaned_data seul
                cleaned_data = result
                merged_data = cleaner.merge_all_data(cleaned_data)
        else:
            return {}, pd.DataFrame()
            
        return cleaned_data, merged_data
        
    except Exception as e:
        import traceback
        return {}, pd.DataFrame()


def load_multiple_pops_optimized(pops_to_load):
    """
    Charge plusieurs POPs en réutilisant les données déjà mises en cache
    Utilise st.session_state pour éviter le rechargement inutile
    Beaucoup plus rapide que load_multiple_pops() classique
    """
    all_pops_data = {}
    cached_count = 0
    fresh_load_count = 0
    
    # Créer une clé unique pour cette liste de POPs
    pops_key = str(sorted(pops_to_load))
    
    # Vérifier si cette exact combinaison de POPs est déjà en cache
    if pops_key in st.session_state.multi_pop_cache:
        return st.session_state.multi_pop_cache[pops_key], len(pops_to_load), 0
    
    for region, pop in pops_to_load:
        pop_id = f"{region}_{pop}"
        
        try:
            # Vérifier d'abord si ce POP spécifique est déjà en cache session
            if pop_id in st.session_state.multi_pop_cache:
                all_pops_data[(region, pop)] = st.session_state.multi_pop_cache[pop_id]
                cached_count += 1
                continue
            
            # Utiliser la fonction cachée load_data (cache Streamlit)
            cleaned_data, merged_data = load_data(region, pop)
            
            if merged_data is not None and not merged_data.empty:
                # Ajouter les métadonnées du POP
                merged_data = merged_data.copy()
                merged_data['Region'] = region
                merged_data['POP'] = pop
                merged_data['POP_ID'] = pop_id
                
                all_pops_data[(region, pop)] = merged_data
                
                # Stocker dans le cache session pour les futures utilisations
                st.session_state.multi_pop_cache[pop_id] = merged_data
                
                fresh_load_count += 1
                    
            else:
                st.warning(f"⚠️ {region}/{pop}: Aucune donnée disponible")
                
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement de {region}/{pop}: {str(e)}")
            continue
    
    # Stocker cette combinaison complète dans le cache pour les futures utilisations
    if all_pops_data:
        st.session_state.multi_pop_cache[pops_key] = all_pops_data
    
    return all_pops_data, cached_count, fresh_load_count
