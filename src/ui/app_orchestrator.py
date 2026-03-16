"""
Application Orchestrator Module
Manages tab creation, rendering, and navigation for the dashboard
"""
import streamlit as st
import pandas as pd
from datetime import datetime

# Import all tab render functions
from .tabs.tab01_vue_ensemble import render_tab as render_vue_ensemble
from .tabs.tab02_analyse_temporelle import render_tab as render_analyse_temporelle
from .tabs.tab03_analyses_eda import render_tab as render_analyses_eda
from .tabs.tab04_analyse_clim import render_tab as render_analyse_clim
from .tabs.tab05_analyse_porte import render_tab as render_analyse_porte
from .tabs.tab07_correlations import render_tab as render_correlations
from .tabs.tab08_changement_temp import render_tab as render_changement_temp
from .tabs.tab09_simulation_couts import render_tab as render_simulation_couts
from .tabs.tab10_rapport_pop import render_tab as render_rapport_pop
from .tabs.tab11_rapport_region import render_tab as render_rapport_region
from .tabs.tab12_rapport_national import render_tab as render_rapport_national
from .tabs.tab13_comparaison_pops import render_tab as render_comparaison_pops


def create_tabs():
    """
    Create and return tab objects for the dashboard navigation
    
    Returns:
        Tuple of tab objects (tab1, tab2, ..., tab13)
    """
    st.markdown("## 🎯 Navigation")
    
    tabs = st.tabs([
        "📊 Vue d'ensemble",
        "📈 Analyse temporelle", 
        "🔬 Analyses EDA",
        "❄️ Analyse CLIM",
        "🚪 Analyse Porte",
        "🔗 Corrélations",
        "Analyse anomalie",
        "💰 Simulation Coûts",
        "📋 Rapport POP",
        "🏢 Rapport Région",
        "🇲🇦 Rapport National",
        "🔄 Comparaison entre POPs"
    ])
    return tabs

def show_no_data_message(tabs, selected_pop: str, selected_region: str):
    """
    Show appropriate messages when no data is available
    
    Args:
        tabs: Tuple of tab objects
        selected_pop: Selected POP name
        selected_region: Selected region name
    """
    tab1 = tabs[0]
    other_tabs = tabs[1:]
    
    with tab1:
        st.error(f"❌ **Aucune donnée disponible pour {selected_pop} dans la région {selected_region}**")
        
        st.markdown("### 💡 **Essayez d'autres PoPs avec données complètes:**")
        
        st.markdown("---")
        with st.expander("🔍 **Détails techniques - Fichiers requis**"):
            st.code("""
        Température Ambiante.csv
        Température Extérieure.csv
        P.Active CLIM.csv
        P.Active Générale.csv
        Etat des CLIMs
        Etat de Porte
            """)
        
        st.info("👈 **Changez de région/POP dans la barre latérale pour accéder aux données**")
    
    # Show message in other tabs
    for tab in other_tabs:
        with tab:
            st.warning("⚠️ Aucune donnée disponible. Veuillez sélectionner un autre POP avec des données.")
            st.info("👈 Changez de région/POP dans la barre latérale")


def show_preloading_message(tabs, selected_pop: str, selected_region: str):
    """
    Keep tabs available during background preloading without showing
    preload banners/messages in the main area.

    Args:
        tabs: Tuple of tab objects
        selected_pop: Selected POP name
        selected_region: Selected region name
    """
    _ = selected_pop
    _ = selected_region

    for tab in tabs:
        with tab:
            st.empty()


def render_all_tabs(tabs, filtered_data: pd.DataFrame, unfiltered_data: pd.DataFrame,
                   start_date: datetime, end_date: datetime, 
                   selected_region: str, selected_pop: str):
    """
    Render all tabs with appropriate data
    
    Args:
        tabs: Tuple of tab objects (tab1, tab2, ..., tab13)
        filtered_data: Filtered DataFrame based on selected period
        unfiltered_data: Complete unfiltered DataFrame
        start_date: Start date for the period
        end_date: End date for the period
        selected_region: Selected region name
        selected_pop: Selected POP name
    """
    tab1, tab2, tab3, tab4, tab5, tab7, tab8, tab9, tab10, tab11, tab12, tab13 = tabs
    
    # 1. VUE D'ENSEMBLE
    with tab1:
        render_vue_ensemble(filtered_data, start_date, end_date)

    # 2. ANALYSE TEMPORELLE INTERACTIVE
    with tab2:
        render_analyse_temporelle(filtered_data, start_date, end_date)

    # 3. ANALYSES EDA
    with tab3:
        render_analyses_eda(filtered_data, start_date, end_date)

    # 4. ANALYSE CLIM
    with tab4:
        render_analyse_clim(filtered_data, start_date, end_date)

    # 5. ANALYSE PORTE
    with tab5:
        render_analyse_porte(filtered_data, start_date, end_date)

    # 7. CORRÉLATIONS
    with tab7:
        render_correlations(filtered_data, start_date, end_date, merged_data=unfiltered_data)

    # 8. ANALYSE CHANGEMENT TEMPÉRATURE
    with tab8:
        render_changement_temp(filtered_data, start_date, end_date)

    # 9. SIMULATION DE COÛTS
    with tab9:
        render_simulation_couts(filtered_data, start_date, end_date)

    # 10. RAPPORT POP
    with tab10:
        render_rapport_pop(filtered_data, start_date, end_date, merged_data=unfiltered_data)

    # 11. RAPPORT RÉGION
    with tab11:
        render_rapport_region(filtered_data, start_date, end_date, selected_region, selected_pop)

    # 12. RAPPORT NATIONAL
    with tab12:
        render_rapport_national(filtered_data, start_date, end_date, selected_region, selected_pop)


    # 13. COMPARAISON ENTRE POPs
    with tab13:
        render_comparaison_pops(filtered_data, start_date, end_date, 
                               selected_region, selected_pop)

    


def orchestrate_dashboard(filtered_data: pd.DataFrame, unfiltered_data: pd.DataFrame,
                         start_date: datetime, end_date: datetime,
                         selected_region: str, selected_pop: str,
                         is_preloading: bool = False):
    """
    Main orchestration function for the dashboard
    Handles tab creation and rendering based on data availability
    
    Args:
        filtered_data: Filtered DataFrame based on selected period
        unfiltered_data: Complete unfiltered DataFrame
        start_date: Start date for the period
        end_date: End date for the period
        selected_region: Selected region name
        selected_pop: Selected POP name
        is_preloading: True when background preload is still running and
            placeholders should be rendered instead of no-data errors
    """
    # Create tabs
    tabs = create_tabs()
    
    # Check data availability and render appropriately
    if is_preloading:
        show_preloading_message(tabs, selected_pop, selected_region)
    elif unfiltered_data.empty:
        show_no_data_message(tabs, selected_pop, selected_region)
    else:
        render_all_tabs(tabs, filtered_data, unfiltered_data, 
                       start_date, end_date, selected_region, selected_pop)
