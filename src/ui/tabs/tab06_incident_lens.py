"""
Tab 6: Incident Lens
Interface pour l'analyse des incidents et anomalies dans les données POP.
"""

import streamlit as st


def render_tab(filtered_merged_data, start_date, end_date, region=None, site=None):
    """
    Affiche l'interface Incident Lens pour l'analyse des incidents.
    
    Args:
        filtered_merged_data: DataFrame avec données filtrées
        start_date: Date de début de la période
        end_date: Date de fin de la période
        region: Région sélectionnée (optionnel)
        site: Site/POP sélectionné (optionnel)
    """
    st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
    
    try:
        # Import the Incident Lens interface
        from src.ui.incident_lens_ui import render_incident_lens_interface
        
        # Pass filtered data to Incident Lens with current region and site
        render_incident_lens_interface(
            data=filtered_merged_data, 
            start_date=start_date, 
            end_date=end_date,
            region=region,
            site=site
        )
    except ImportError as e:
        st.error(f"🚫 Incident Lens non disponible - problème d'import des modules: {e}")
        st.info("📋 Vérifiez que tous les modules sont correctement installés")
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement d'Incident Lens: {e}")
        st.info("💡 Consultez les logs pour plus de détails")
