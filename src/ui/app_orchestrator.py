"""
Application Orchestrator Module
Manages lazy tab navigation and rendering for the dashboard.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.services.preload_service import PreloadedStore, PreloadSnapshot


TAB_LABELS = [
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
    "🔄 Comparaison entre POPs",
]


def create_navigation() -> str:
    """Render top navigation and return the active tab label."""
    st.markdown("## 🎯 Navigation")

    if hasattr(st, "segmented_control"):
        try:
            selected = st.segmented_control(
                "Choisissez un onglet",
                options=TAB_LABELS,
                key="active_tab_ui",
                default=TAB_LABELS[0],
            )
        except TypeError:
            selected = st.segmented_control(
                "Choisissez un onglet",
                options=TAB_LABELS,
                key="active_tab_ui",
            )
    else:
        selected = st.radio(
            "Choisissez un onglet",
            options=TAB_LABELS,
            key="active_tab_ui",
            index=0,
            horizontal=True,
        )

    return selected or TAB_LABELS[0]


def show_no_data_message(
    active_tab: str,
    selected_pop: str,
    selected_region: str,
    *,
    selected_pop_loading: bool = False,
    preload_snapshot: PreloadSnapshot | None = None,
) -> None:
    """Show no-data message for the current active tab."""
    if selected_pop_loading:
        # Keep main panel clean while loading; progress is shown in sidebar.
        return

    if active_tab == TAB_LABELS[0]:
        st.error(
            f"❌ **Aucune donnée disponible pour {selected_pop} "
            f"dans la région {selected_region}**"
        )
        st.markdown("### 💡 **Essayez d'autres PoPs avec données complètes:**")
        st.markdown("---")
        with st.expander("🔍 **Détails techniques - Fichiers requis**"):
            st.code(
                """
Température Ambiante.csv
Température Extérieure.csv
P.Active CLIM.csv
P.Active Générale.csv
Etat des CLIMs
Etat de Porte
                """
            )
        st.info(
            "👈 **Changez de région/POP dans la barre latérale pour accéder aux données**"
        )
        return

    st.warning(
        "⚠️ Aucune donnée disponible. Veuillez sélectionner un autre POP avec des données."
    )
    st.info("👈 Changez de région/POP dans la barre latérale")


def render_active_tab(
    active_tab: str,
    filtered_data: pd.DataFrame,
    unfiltered_data: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
    selected_region: str,
    selected_pop: str,
    store: PreloadedStore | None = None,
) -> None:
    """Render only the active tab."""
    if active_tab == TAB_LABELS[0]:
        from .tabs.tab01_vue_ensemble import render_tab as render_vue_ensemble

        render_vue_ensemble(filtered_data, start_date, end_date)
        return

    if active_tab == TAB_LABELS[1]:
        from .tabs.tab02_analyse_temporelle import (
            render_tab as render_analyse_temporelle,
        )

        render_analyse_temporelle(filtered_data, start_date, end_date)
        return

    if active_tab == TAB_LABELS[2]:
        from .tabs.tab03_analyses_eda import render_tab as render_analyses_eda

        render_analyses_eda(filtered_data, start_date, end_date)
        return

    if active_tab == TAB_LABELS[3]:
        from .tabs.tab04_analyse_clim import render_tab as render_analyse_clim

        render_analyse_clim(filtered_data, start_date, end_date)
        return

    if active_tab == TAB_LABELS[4]:
        from .tabs.tab05_analyse_porte import render_tab as render_analyse_porte

        render_analyse_porte(filtered_data, start_date, end_date)
        return

    if active_tab == TAB_LABELS[5]:
        from .tabs.tab07_correlations import render_tab as render_correlations

        render_correlations(
            filtered_data, start_date, end_date, merged_data=unfiltered_data
        )
        return

    if active_tab == TAB_LABELS[6]:
        from .tabs.tab08_changement_temp import (
            render_tab as render_changement_temp,
        )

        render_changement_temp(filtered_data, start_date, end_date)
        return

    if active_tab == TAB_LABELS[7]:
        from .tabs.tab09_simulation_couts import (
            render_tab as render_simulation_couts,
        )

        render_simulation_couts(filtered_data, start_date, end_date)
        return

    if active_tab == TAB_LABELS[8]:
        from .tabs.tab10_rapport_pop import render_tab as render_rapport_pop

        render_rapport_pop(
            filtered_data, start_date, end_date, merged_data=unfiltered_data
        )
        return

    if active_tab == TAB_LABELS[9]:
        from .tabs.tab11_rapport_region import render_tab as render_rapport_region

        render_rapport_region(
            filtered_data,
            start_date,
            end_date,
            selected_region,
            selected_pop,
            store=store,
        )
        return

    if active_tab == TAB_LABELS[10]:
        from .tabs.tab12_rapport_national import (
            render_tab as render_rapport_national,
        )

        render_rapport_national(
            filtered_data,
            start_date,
            end_date,
            selected_region,
            selected_pop,
            store=store,
        )
        return

    if active_tab == TAB_LABELS[11]:
        from .tabs.tab13_comparaison_pops import (
            render_tab as render_comparaison_pops,
        )

        render_comparaison_pops(
            filtered_data,
            start_date,
            end_date,
            selected_region,
            selected_pop,
            store=store,
        )


def orchestrate_dashboard(
    filtered_data: pd.DataFrame,
    unfiltered_data: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
    selected_region: str,
    selected_pop: str,
    store: PreloadedStore | None = None,
    selected_pop_loading: bool = False,
    preload_snapshot: PreloadSnapshot | None = None,
) -> None:
    """Main orchestration function for the dashboard."""
    active_tab = create_navigation()

    if unfiltered_data.empty:
        show_no_data_message(
            active_tab,
            selected_pop,
            selected_region,
            selected_pop_loading=selected_pop_loading,
            preload_snapshot=preload_snapshot,
        )
        return

    render_active_tab(
        active_tab=active_tab,
        filtered_data=filtered_data,
        unfiltered_data=unfiltered_data,
        start_date=start_date,
        end_date=end_date,
        selected_region=selected_region,
        selected_pop=selected_pop,
        store=store,
    )
