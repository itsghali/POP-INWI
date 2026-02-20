import streamlit as st
import scipy.stats
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from pathlib import Path
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats
from data_cleaning import DataCleaner
from src.analysis.exterior_cause import power_causes_ambient_spike, exterior_causes_ambient_spike
import warnings
import time
warnings.filterwarnings('ignore')
import scipy.stats

# ===== IMPORTS DES MODULES =====
from src.utils.startup_detection import is_server_startup
from src.core.data_loader import load_data, load_multiple_pops_optimized
from src.core.cache_manager import preload_all_pops
from src.core.data_filter import filter_by_date_range, get_data_summary, validate_data_availability
from src.ui.sidebar import get_region_pop_selection
from src.ui.styles import apply_custom_css, apply_print_styles, render_page_header, render_title_with_logo
from src.ui.app_orchestrator import orchestrate_dashboard

# Initialiser le DataCleaner
data_cleaner = DataCleaner("data")

# Import period selector for date extraction
from src.ui.period_selector import period_selector

# Import Incident Lens UI
try:
    from src.ui.incident_lens_ui import render_incident_lens_interface, render_incident_lens_summary
except ImportError as e:
    st.error(f"Erreur d'import Incident Lens: {e}")
    render_incident_lens_interface = None
    render_incident_lens_summary = None

# Configuration de la page
st.set_page_config(
    page_title="Centre de Données INWI - Tableau de Bord",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Obtenir la région et le POP sélectionnés
selected_region, selected_pop = get_region_pop_selection(data_cleaner)

# Track POP changes for timing purposes - only for initial load
if 'current_pop' not in st.session_state:
    st.session_state.current_pop = None
    st.session_state.load_start_time = None
    st.session_state.first_load_completed = False

# Initialize multi-POP cache in session state
if 'multi_pop_cache' not in st.session_state:
    st.session_state.multi_pop_cache = {}
    
if 'cached_pop_list' not in st.session_state:
    st.session_state.cached_pop_list = []

# Check if POP has changed (only start timing for new POP selection)
pop_changed = st.session_state.current_pop != f"{selected_region}_{selected_pop}"
if pop_changed:
    st.session_state.current_pop = f"{selected_region}_{selected_pop}"
    st.session_state.load_start_time = time.time()
    st.session_state.first_load_completed = False  # Reset for new POP

# Style CSS personnalisé
render_page_header(selected_pop, selected_region)
apply_custom_css()
apply_print_styles()

# ===== LOAD AND PREPARE DATA =====
try:
    # Load data for the selected POP - returns tuple (cleaned_data, merged_data)
    cleaned_data, merged_data = load_data(selected_region, selected_pop)
    
    if merged_data is None or merged_data.empty:
        st.error(f"❌ Aucune donnée disponible pour {selected_pop} ({selected_region})")
        st.stop()
    
    # Ensure Timestamp is datetime
    if 'Timestamp' in merged_data.columns:
        # Convert all timestamp types to datetime
        merged_data['Timestamp'] = pd.to_datetime(merged_data['Timestamp'], errors='coerce', utc=False)
        # Remove rows with NaT timestamps
        merged_data = merged_data.dropna(subset=['Timestamp'])
    
    if merged_data.empty:
        st.error(f"❌ No valid data after timestamp conversion")
        st.stop()
    
    # Get date range from session state or use full range
    if 'start_date' not in st.session_state:
        if 'Timestamp' in merged_data.columns:
            ts_min = merged_data['Timestamp'].min()
            # Convert pandas Timestamp to Python datetime
            if hasattr(ts_min, 'to_pydatetime'):
                st.session_state.start_date = ts_min.to_pydatetime()
            elif isinstance(ts_min, str):
                st.session_state.start_date = pd.to_datetime(ts_min).to_pydatetime()
            else:
                st.session_state.start_date = ts_min if isinstance(ts_min, datetime) else datetime.now()
        else:
            st.session_state.start_date = datetime.now()
    
    if 'end_date' not in st.session_state:
        if 'Timestamp' in merged_data.columns:
            ts_max = merged_data['Timestamp'].max()
            # Convert pandas Timestamp to Python datetime
            if hasattr(ts_max, 'to_pydatetime'):
                st.session_state.end_date = ts_max.to_pydatetime()
            elif isinstance(ts_max, str):
                st.session_state.end_date = pd.to_datetime(ts_max).to_pydatetime()
            else:
                st.session_state.end_date = ts_max if isinstance(ts_max, datetime) else datetime.now()
        else:
            st.session_state.end_date = datetime.now()
    
    # Ensure start_date and end_date are proper Python datetime objects
    start_date = st.session_state.start_date
    end_date = st.session_state.end_date
    
    # Final conversion safety check
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date).to_pydatetime()
    elif isinstance(start_date, pd.Timestamp):
        start_date = start_date.to_pydatetime()
    elif not isinstance(start_date, datetime):
        start_date = datetime.now()
    
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date).to_pydatetime()
    elif isinstance(end_date, pd.Timestamp):
        end_date = end_date.to_pydatetime()
    elif not isinstance(end_date, datetime):
        end_date = datetime.now()
    
    # Store corrected dates back in session state
    st.session_state.start_date = start_date
    st.session_state.end_date = end_date
    
    # Filter data by date range using data_filter utility
    filtered_merged_data = filter_by_date_range(merged_data, start_date, end_date)
    
    # Validate data availability
    required_cols = ['Temp_Ambiante', 'Timestamp']
    is_valid, missing = validate_data_availability(filtered_merged_data, required_cols)
    if not is_valid and len(filtered_merged_data) > 0:
        st.warning(f"⚠️ Colonnes manquantes: {missing}")
    
    # Get selected period from period_selector (rendered in sidebar)
    if hasattr(period_selector, 'start_date') and hasattr(period_selector, 'end_date'):
        sidebar_start_date = period_selector.start_date
        sidebar_end_date = period_selector.end_date
        
        # Use sidebar dates if available, otherwise use defaults
        if sidebar_start_date is not None and sidebar_end_date is not None:
            start_date = sidebar_start_date
            end_date = sidebar_end_date
            # Re-filter data with selected period
            filtered_merged_data = filter_by_date_range(merged_data, start_date, end_date)
    
    # Orchestrate the dashboard with all prepared data
    orchestrate_dashboard(
        filtered_merged_data,
        merged_data,
        start_date,
        end_date,
        selected_region,
        selected_pop
    )
    
except Exception as e:
    st.error(f"❌ Erreur lors du chargement des données: {str(e)}")
    st.stop()

# Footer
st.markdown("---")
st.caption("🏢 Data Center Monitoring Dashboard | © 2025")