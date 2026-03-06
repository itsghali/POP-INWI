"""
Incident Lens UI Components for Streamlit
User interface for temperature anomaly root cause analysis
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

try:
    from ..incident_lens.preprocessor import DataPreprocessor
    from ..incident_lens.analyzer import RootCauseAnalyzer
    from ..incident_lens.recommender import RecommendationEngine
    from ..incident_lens.detector import IncidentDetector, Incident, IncidentType, IncidentSeverity
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.incident_lens.preprocessor import DataPreprocessor
    from src.incident_lens.analyzer import RootCauseAnalyzer
    from src.incident_lens.recommender import RecommendationEngine
    from src.incident_lens.detector import IncidentDetector, Incident, IncidentType, IncidentSeverity


# ============= CLUSTERING FUNCTIONS =============

def group_all_incidents_by_day(incidents: List) -> List:
    """
    Group ALL incidents (temperature + others) into ONE incident per day.
    
    Logic:
    - Group by calendar day
    - ALL incidents of same day → 1 daily incident
    - Extract primary anomaly type + list all causes
    - Merge durations and metrics correctly
    """
    if not incidents:
        return []
    
    from datetime import date
    
    # Sort by timestamp
    sorted_incidents = sorted(incidents, key=lambda x: x.timestamp)
    
    # Group by date - all incidents of same day together
    daily_groups = {}
    for incident in sorted_incidents:
        day = incident.timestamp.date()
        if day not in daily_groups:
            daily_groups[day] = []
        daily_groups[day].append(incident)
    
    # Create ONE merged incident per day
    grouped = []
    for day in sorted(daily_groups.keys()):
        day_incidents = daily_groups[day]
        
        if day_incidents:
            merged = create_daily_unified_incident(day_incidents)
            if merged:
                grouped.append(merged)
    
    return grouped


def create_daily_unified_incident(group: List):
    """Create a SINGLE unified incident for all incidents of one day"""
    if not group:
        return None
    
    start_incident = group[0]
    end_incident = group[-1]
    
    # Separate incidents by type for analysis
    temp_high = [inc for inc in group if inc.type.value == 'temperature_high']
    temp_low = [inc for inc in group if inc.type.value == 'temperature_low']
    other_incidents = [inc for inc in group if inc.type.value not in ['temperature_high', 'temperature_low']]
    
    # Determine PRIMARY ROOT CAUSE (not temperature symptom)
    # Temperature is the EFFECT, we want to show the CAUSE as primary
    if other_incidents:
        # Find the most frequent ROOT CAUSE incident (CLIM, door, power, etc.)
        cause_counts = {}
        for inc in other_incidents:
            cause_type = inc.type.value
            if cause_type not in cause_counts:
                cause_counts[cause_type] = []
            cause_counts[cause_type].append(inc)
        
        # Get the most frequent cause as primary
        most_frequent_cause = max(cause_counts.items(), key=lambda x: len(x[1]))
        primary_cause_incidents = most_frequent_cause[1]
        primary_incident = primary_cause_incidents[0]
        
        primary_type = primary_incident.type.value
        primary_metric = primary_incident.metric_value
        threshold = primary_incident.threshold_violated
        
        # Store temperature info as secondary/symptom
        temp_symptom = None
        if temp_high:
            temps = [inc.metric_value for inc in temp_high]
            temp_symptom = {'type': 'high', 'max': max(temps), 'count': len(temp_high)}
        elif temp_low:
            temps = [inc.metric_value for inc in temp_low]
            temp_symptom = {'type': 'low', 'min': min(temps), 'count': len(temp_low)}
    elif temp_high:
        # No causal incidents detected, fallback to temperature
        primary_type = 'temperature_high'
        temps = [inc.metric_value for inc in temp_high]
        primary_metric = max(temps) if temps else 0
        threshold = temp_high[0].threshold_violated if temp_high else 0
        temp_symptom = None
        primary_incident = temp_high[0]
    elif temp_low:
        # No causal incidents detected, fallback to temperature
        primary_type = 'temperature_low'
        temps = [inc.metric_value for inc in temp_low]
        primary_metric = min(temps) if temps else 0
        threshold = temp_low[0].threshold_violated if temp_low else 0
        temp_symptom = None
        primary_incident = temp_low[0]
    else:
        # No incidents at all (shouldn't happen)
        primary_type = group[0].type.value
        primary_metric = group[0].metric_value
        threshold = group[0].threshold_violated
        temp_symptom = None
        primary_incident = group[0]
    
    # Get highest severity from all incidents
    severity_base = max(group, key=lambda inc: severity_rank(inc.severity)).severity
    
    # Calculate total duration
    num_points = len(group)
    duration_seconds = num_points * 900  # 900 sec = 15 min per point
    duration_hours = duration_seconds / 3600
    
    # Build cause list from all incident types
    causes_dict = {}
    for inc in group:
        inc_type = inc.type.value.replace('_', ' ').title()
        if inc_type not in causes_dict:
            causes_dict[inc_type] = 0
        causes_dict[inc_type] += 1
    
    # Extract failed CLIM units from all CLIM incidents in the group
    all_failed_clims = set()
    clim_incident_types = ['clim_failure', 'clim_degraded']
    for inc in group:
        if inc.type.value in clim_incident_types:
            # Extract from context
            if isinstance(inc.context, dict) and 'failed_units' in inc.context:
                for unit in inc.context['failed_units']:
                    # Extract CLIM name (e.g., 'CLIM_A_Status' -> 'A')
                    clim_name = unit.replace('_Status', '').replace('CLIM_', '')
                    all_failed_clims.add(clim_name)
            # Also check affected_systems
            if inc.affected_systems:
                for sys in inc.affected_systems:
                    if sys not in ['COOLING', 'ALL_CLIM_UNITS'] and 'CLIM' in sys:
                        clim_name = sys.replace('CLIM_', '')
                        all_failed_clims.add(clim_name)
    
    causes_str = ", ".join([f"{t} ({c})" for t, c in causes_dict.items()])
    day_str = start_incident.timestamp.strftime('%Y-%m-%d')
    
    # Build description without temperature symptom (symptom will be displayed separately)
    desc = f"Jour {day_str}: {causes_str} ({num_points} points)"
    
    # Determine the IncidentType enum value
    try:
        incident_type_enum = IncidentType[primary_type.upper()]
    except (KeyError, AttributeError):
        # Fallback if primary_type doesn't match enum
        if primary_type == 'temperature_high':
            incident_type_enum = IncidentType.TEMPERATURE_HIGH
        elif primary_type == 'temperature_low':
            incident_type_enum = IncidentType.TEMPERATURE_LOW
        else:
            incident_type_enum = primary_incident.type
    
    # Build unified context with CLIM failure information
    unified_context = {
        'daily_incident': True,
        'causes': causes_dict,
        'num_alerts': len(group),
        'primary_type': primary_type,
        'temp_symptom': temp_symptom,
        'all_incidents': group  # Store for details expansion
    }
    
    # Add failed CLIMs if any were detected
    if all_failed_clims:
        unified_context['failed_units'] = sorted(list(all_failed_clims))
    
    return Incident(
        id=f"DAILY_UNIFIED_{start_incident.timestamp.strftime('%Y%m%d')}",
        timestamp=start_incident.timestamp,
        type=incident_type_enum,
        severity=severity_base,
        metric_name=primary_incident.metric_name,
        metric_value=primary_metric,
        threshold_violated=threshold,
        duration_seconds=duration_seconds,
        affected_systems=['COOLING'],
        description=desc,
        context=unified_context
    )


def severity_rank(severity: IncidentSeverity) -> int:
    """Return sortable rank for severity."""
    order = {
        IncidentSeverity.INFO: 1,
        IncidentSeverity.WARNING: 2,
        IncidentSeverity.CRITICAL: 3,
        IncidentSeverity.EMERGENCY: 4
    }
    return order.get(severity, 0)


def _incident_time_window(incident: Incident) -> tuple:
    """Return (start, end) window for an incident."""
    start = incident.timestamp
    if incident.duration_seconds and incident.duration_seconds > 0:
        end = start + timedelta(seconds=incident.duration_seconds)
    else:
        end = start
    return start, end


def _windows_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    """Check overlap between two inclusive time windows, handling point-temporal cases."""
    # If either window is point-temporal (start==end), use <= instead of <
    # to catch exact timestamp matches
    if start_a == end_a or start_b == end_b:
        return not (end_a < start_b or end_b < start_a)
    return not (end_a < start_b or end_b < start_a)




def cluster_incidents_by_time(incidents: List[Dict[str, Any]], time_gap_minutes: int = 30, temp_min: float = 20.0, temp_max: float = 26.0) -> List[Dict[str, Any]]:
    """Cluster incidents by temporal proximity AND temperature anomaly state.
    
    Groups incidents that:
    1. Occur within time_gap_minutes of each other AND
    2. Both represent anomalies (BOTH outside acceptable temperature range [temp_min, temp_max])
    """
    if not incidents:
        return []
    
    sorted_incidents = sorted(
        incidents,
        key=lambda x: x['incident'].timestamp if x.get('incident') else datetime.min
    )
    
    clusters = []
    current_cluster = None
    time_gap = timedelta(minutes=time_gap_minutes)
    
    for incident_result in sorted_incidents:
        incident = incident_result.get('incident')
        if not incident:
            continue
        
        # Check if current incident is in anomaly state (outside acceptable range)
        is_anomaly = incident.metric_value < temp_min or incident.metric_value > temp_max
        
        if current_cluster is None:
            if is_anomaly:
                current_cluster = {
                    'start_time': incident.timestamp,
                    'end_time': incident.timestamp,
                    'incident_results': [incident_result],
                    'temperatures': [incident.metric_value],
                    'types': [incident.type.value],
                    'severities': [incident.severity.value],
                }
        else:
            time_since_last = incident.timestamp - current_cluster['end_time']
            
            if time_since_last <= time_gap and is_anomaly:
                current_cluster['end_time'] = incident.timestamp
                current_cluster['incident_results'].append(incident_result)
                current_cluster['temperatures'].append(incident.metric_value)
                current_cluster['types'].append(incident.type.value)
                current_cluster['severities'].append(incident.severity.value)
            else:
                if current_cluster:
                    clusters.append(_finalize_cluster(current_cluster, len(clusters) + 1))
                
                if is_anomaly:
                    current_cluster = {
                        'start_time': incident.timestamp,
                        'end_time': incident.timestamp,
                        'incident_results': [incident_result],
                        'temperatures': [incident.metric_value],
                        'types': [incident.type.value],
                        'severities': [incident.severity.value],
                    }
                else:
                    current_cluster = None
    
    if current_cluster:
        clusters.append(_finalize_cluster(current_cluster, len(clusters) + 1))
    
    return clusters


def _finalize_cluster(cluster_data: Dict, cluster_id: int) -> Dict[str, Any]:
    """Finalize cluster with computed statistics."""
    type_counts = {}
    for t in cluster_data['types']:
        type_counts[t] = type_counts.get(t, 0) + 1
    dominant_type = max(type_counts, key=type_counts.get) if type_counts else 'unknown'
    
    severity_order = {'critical': 3, 'warning': 2, 'info': 1}
    max_severity = max(
        cluster_data['severities'],
        key=lambda s: severity_order.get(s, 0)
    ) if cluster_data['severities'] else 'info'
    
    duration = cluster_data['end_time'] - cluster_data['start_time']
    duration_minutes = max(1, int(duration.total_seconds() / 60)) if len(cluster_data['incident_results']) > 1 else 0
    
    return {
        'cluster_id': cluster_id,
        'start_time': cluster_data['start_time'],
        'end_time': cluster_data['end_time'],
        'incident_results': cluster_data['incident_results'],
        'occurrence_count': len(cluster_data['incident_results']),
        'temp_min': min(cluster_data['temperatures']),
        'temp_max': max(cluster_data['temperatures']),
        'dominant_type': dominant_type,
        'severity': max_severity,
        'duration_minutes': duration_minutes
    }


# ============= END CLUSTERING FUNCTIONS =============


def render_incident_lens_interface(data=None, start_date=None, end_date=None, region=None, site=None):
    """Main interface for Incident Lens root cause analysis
    
    Args:
        data: Pre-filtered DataFrame (optional)
        start_date: Start date from unified selector (optional)
        end_date: End date from unified selector (optional)
        region: Selected region (optional)
        site: Selected site/POP (optional)
    """
    st.header("🔍 Incident Lens - Analyse des Causes Racines")
    st.markdown("""
    **Objectif**: Identifier automatiquement les causes des anomalies de température avec des scores de confiance.
    """)
    
    # Display current site information
    if region and site:
        st.info(f"🎯 **Site analysé**: {site} (Région: {region})")
    
    # Use passed region and site, or fallback to defaults
    current_region = region if region else 'Marrakech'
    current_site = site if site else 'BGU-ONE'
    
    # Store the passed data in session state for use in analysis
    if data is not None and not data.empty:
        st.session_state.has_external_data = True
        # Keep only required columns to reduce memory and rerun cost
        required_cols = [
            'Timestamp',
            'Temp_Ambiante',
            'Temp_Exterieure',
            'Puissance_CLIM',
            'Puissance_Generale',
            'Puissance_IT',
            'Porte_Status'
        ]
        clim_cols = [col for col in data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
        available_cols = [col for col in required_cols if col in data.columns] + clim_cols
        data_view = data[available_cols]

        data_signature = (
            region or "",
            site or "",
            start_date,
            end_date,
            len(data_view),
            tuple(available_cols)
        )
        if st.session_state.get('passed_data_signature') != data_signature:
            st.session_state.passed_data = data_view
            st.session_state.passed_data_signature = data_signature
    else:
        st.session_state.has_external_data = False
        st.warning("⚠️ Aucune donnée passée - basculement vers le chargement de fichiers")
    
    # Initialize session state with current site configuration
    if ('current_site' not in st.session_state or 
        st.session_state.get('current_site') != current_site or
        'preprocessor' not in st.session_state):
        
        # Only create preprocessor if we don't have external data
        if not st.session_state.get('has_external_data', False):
            st.session_state.preprocessor = DataPreprocessor('data', region=current_region, site=current_site)
        
        st.session_state.current_site = current_site
        st.session_state.current_region = current_region
        # Clear previous analysis results when site changes
        st.session_state.analysis_results = None
        
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    
    # Create input form
    with st.expander("⚙️ Configuration de l'analyse", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("📅 Période d'analyse")
            
            # Quick time range buttons
            quick_ranges = {
                "Dernière heure": timedelta(hours=1),
                "Dernières 4 heures": timedelta(hours=4),
                "Dernières 24 heures": timedelta(days=1),
                "Derniers 3 jours": timedelta(days=3),
                "Dernière semaine": timedelta(weeks=1),
                "Dernier mois": timedelta(days=30)
            }
            
            selected_range = st.selectbox(
                "Sélection rapide",
                list(quick_ranges.keys()),
                index=2  # Default to 24 hours
            )
            
            # Use passed dates if available, otherwise calculate defaults
            if start_date and end_date:
                # Use the dates passed from the main app's period selector
                default_start_time = start_date
                default_end_time = end_date
            else:
                # Calculate dates from quick range
                default_end_time = datetime.now()
                default_start_time = default_end_time - quick_ranges[selected_range]
            
            # Allow manual override
            use_custom = st.checkbox("Définir une période personnalisée")
            if use_custom:
                input_start_date = st.date_input("Date de début", value=default_start_time.date())
                input_start_time = st.time_input("Heure de début", value=default_start_time.time())
                input_end_date = st.date_input("Date de fin", value=default_end_time.date())
                input_end_time = st.time_input("Heure de fin", value=default_end_time.time())
                
                start_time = datetime.combine(input_start_date, input_start_time)
                end_time = datetime.combine(input_end_date, input_end_time)
            else:
                # Use the default times (either from main app or calculated)
                start_time = default_start_time
                end_time = default_end_time
            
            # Show the selected period
            st.info(f"📅 Période: {start_time.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%Y-%m-%d %H:%M')}")
            
        with col2:
            st.subheader("🌡️ Seuils de température")
            
            temp_min = st.number_input(
                "Température minimale acceptable (°C)",
                min_value=-20.0,
                max_value=50.0,
                value=20.0,
                step=0.1,
                key="temp_min_input",
                help="Températures en dessous de cette valeur seront considérées comme anomalies"
            )
            
            # Allow flexible ranges by region/site, only enforce max > min
            temp_max = st.number_input(
                "Température maximale acceptable (°C)",
                min_value=temp_min + 0.1,
                max_value=60.0,
                value=max(26.0, temp_min + 0.5),
                step=0.1,
                key="temp_max_input",
                help="Températures au dessus de cette valeur seront considérées comme anomalies"
            )
            
            if temp_min >= temp_max:
                st.error("❌ La température minimale doit être inférieure à la maximale")
                return
            
            st.success(f"✅ Plage acceptable: {temp_min}°C - {temp_max}°C")
                
        with col3:
            st.subheader("🎯 Options d'analyse")
            
            show_recommendations = st.checkbox(
                "Générer des recommandations",
                value=True,
                help="Créer des actions correctives spécifiques"
            )
    
    # Analysis button
    analyze_button = st.button(
        "🔍 Lancer l'analyse",
        type="primary",
        help="Analyser les anomalies de température dans la période sélectionnée"
    )
    
    if analyze_button:
        run_incident_analysis(
            start_time, end_time, temp_min, temp_max, show_recommendations
        )
    
    # Display results if available
    if st.session_state.analysis_results:
        display_analysis_results(
            st.session_state.analysis_results,
            show_recommendations
        )


def run_incident_analysis(start_time: datetime, end_time: datetime, 
                         temp_min: float, temp_max: float, show_recommendations: bool):
    """Execute the incident analysis with AUTOMATIC incident regrouping"""
    
    with st.spinner("🔄 Chargement et analyse des données..."):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Get data (use passed data if available, otherwise load from files)
            status_text.text("📂 Préparation des données...")
            progress_bar.progress(20)
            
            if st.session_state.get('has_external_data', False) and 'passed_data' in st.session_state:
                # Use the already-loaded data from main app
                data = st.session_state.passed_data.copy()
                
                # Map column names from main app format to incident lens expected format
                column_mapping = {
                    'Temp_Ambiante': 'T°C AMBIANTE',
                    'Temp_Exterieure': 'T°C EXTERIEURE',
                    'Puissance_CLIM': 'Puissance_CLIM',
                    'Puissance_Generale': 'Puissance_Generale',
                    'Puissance_IT': 'Puissance_IT',
                    'CLIM_A_Status': 'CLIM_A_Status',
                    'CLIM_B_Status': 'CLIM_B_Status',
                    'CLIM_C_Status': 'CLIM_C_Status',
                    'CLIM_D_Status': 'CLIM_D_Status',
                    'Porte_Status': 'Porte_Status'
                }
                
                # Rename columns to match incident lens expectations
                data = data.rename(columns=column_mapping)
                
                # Filter by time range if needed
                if 'Timestamp' in data.columns:
                    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
                    data = data.set_index('Timestamp') if 'Timestamp' in data.columns else data
                    
                    # Filter by time range
                    mask = (data.index >= start_time) & (data.index <= end_time)
                    data = data[mask]
                
            else:
                # Fallback: Load all data from all folders
                status_text.text("📂 Chargement de TOUS les dossiers...")
                import os
                import glob
                
                all_data = []
                data_dirs = 'data'
                
                # Recursively find all CSV files in data directory
                csv_files = glob.glob(os.path.join(data_dirs, '**', '*.csv'), recursive=True)
                st.info(f"ℹ️ {len(csv_files)} fichiers CSV trouvés")
                
                for csv_file in csv_files[:100]:  # Limit to avoid memory issues
                    try:
                        df = pd.read_csv(csv_file)
                        if 'Timestamp' in df.columns and 'T°C AMBIANTE' in df.columns:
                            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                            all_data.append(df)
                    except Exception as e:
                        pass  # Skip files that can't be read
                
                if not all_data:
                    st.error("❌ Aucune donnée trouvée dans les fichiers")
                    progress_bar.empty()
                    status_text.empty()
                    return
                    
                data = pd.concat(all_data, ignore_index=True)
                data['Timestamp'] = pd.to_datetime(data['Timestamp'])
                data = data.set_index('Timestamp')
                
            if data.empty:
                st.error(f"❌ Aucune donnée trouvée pour la période {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}")
                
                # Try to provide guidance
                if st.session_state.get('has_external_data', False):
                    if 'passed_data' in st.session_state and not st.session_state.passed_data.empty:
                        passed_data = st.session_state.passed_data
                        if 'Timestamp' in passed_data.columns:
                            passed_data['Timestamp'] = pd.to_datetime(passed_data['Timestamp'])
                            data_start = passed_data['Timestamp'].min()
                            data_end = passed_data['Timestamp'].max()
                            st.info(f"💡 Données disponibles de {data_start.strftime('%Y-%m-%d %H:%M')} à {data_end.strftime('%Y-%m-%d %H:%M')}")
                            st.info("Veuillez ajuster la période d'analyse.")
                else:
                    # Original file-based error handling
                    try:
                        if 'preprocessor' in st.session_state:
                            preprocessor = st.session_state.preprocessor
                            all_data = preprocessor.load_data()
                            if not all_data.empty:
                                data_start = all_data.index.min()
                                data_end = all_data.index.max()
                                st.info(f"💡 Données disponibles de {data_start.strftime('%Y-%m-%d %H:%M')} à {data_end.strftime('%Y-%m-%d %H:%M')}")
                                st.info("Veuillez ajuster la période d'analyse ou utiliser la sélection rapide.")
                            else:
                                st.warning("⚠️ Aucune donnée disponible dans les fichiers. Vérifiez les fichiers de données dans le dossier 'data'.")
                    except Exception as e:
                        st.warning(f"⚠️ Problème de chargement des données: {str(e)}")
                    
                progress_bar.empty()
                status_text.empty()
                return
            
            # Step 2: Data validation
            status_text.text("✅ Validation des données...")
            progress_bar.progress(40)
            
            # Validate data (use preprocessor if available, otherwise basic validation)
            if st.session_state.get('has_external_data', False):
                # Basic validation for external data (check for mapped column names)
                validation = {
                    'is_valid': True,
                    'errors': [],
                    'warnings': []
                }
                
                # Check for required columns (after mapping)
                required_columns = ['T°C AMBIANTE', 'T°C EXTERIEURE']
                missing_columns = [col for col in required_columns if col not in data.columns]
                if missing_columns:
                    validation['is_valid'] = False
                    validation['errors'].append(f"Colonnes manquantes: {', '.join(missing_columns)}")
                
                # Check data completeness
                if len(data) < 10:
                    validation['warnings'].append(f"Peu de données disponibles ({len(data)} lignes)")
                    
            else:
                # Use preprocessor validation
                if 'preprocessor' in st.session_state:
                    validation = st.session_state.preprocessor.validate_data_for_analysis(data)
                else:
                    validation = {'is_valid': False, 'errors': ['Pas de preprocessor disponible'], 'warnings': []}
            
            if not validation['is_valid']:
                st.error("❌ Données insuffisantes pour une analyse fiable")
                for error in validation['errors']:
                    st.error(f"• {error}")
                progress_bar.empty()
                status_text.empty()
                return
            
            if validation['warnings']:
                for warning in validation['warnings']:
                    st.warning(f"⚠️ {warning}")
            
            # Step 3: Run analysis
            status_text.text("🔍 Analyse des incidents...")
            progress_bar.progress(60)
            
            # Show threshold being used CLEARLY
            st.markdown("---")
            col_thresh1, col_thresh2 = st.columns(2)
            with col_thresh1:
                st.metric("🔻 Seuil Minimum", f"{temp_min}°C", help="Anomalie si temp < ce seuil")
            with col_thresh2:
                st.metric("🔺 Seuil Maximum", f"{temp_max}°C", help="Anomalie si temp > ce seuil")
            st.markdown("---")
            
            # ✅ SIMPLE & CLEAN: Use IncidentDetector with configured thresholds
            detector = IncidentDetector(data, temp_min=temp_min, temp_max=temp_max)
            all_incidents = detector.detect_incidents(real_time=False)
            daily_grouped_incidents = group_all_incidents_by_day(all_incidents)
            
            # Also run temperature-specific grouping for context
            analyzer = RootCauseAnalyzer(data)
            analysis_results = analyzer.analyze_time_range(
                start_time, end_time, temp_min, temp_max
            )

            # Step 4: Generate recommendations for each daily incident
            status_text.text("💡 Génération des recommandations...")
            progress_bar.progress(70)
            
            recommender = RecommendationEngine()
            
            # Use daily grouped incidents and analyze each for recommendations
            combined_incidents = []
            for incident in daily_grouped_incidents:
                # Analyze root causes for this incident
                try:
                    root_causes = analyzer.analyze_incident(
                        incident,
                        time_window_before=60,
                        time_window_after=30
                    )
                    
                    # Analyze context
                    incident_context = analyzer._analyze_incident_context(
                        incident, 
                        data,
                        temp_min,
                        temp_max
                    )
                    
                    # Generate recommendations if requested
                    recommendations = []
                    if show_recommendations:
                        if root_causes:
                            # Generate recommendations based on root causes
                            recommendations = recommender.generate_recommendations(
                                root_causes,
                                incident_severity=incident.severity.value
                            )
                        else:
                            # Generate fallback recommendations based on incident type
                            recommendations = recommender.generate_recommendations_for_incident(
                                incident
                            )
                    
                    combined_incidents.append({
                        'incident': incident,
                        'context': incident_context,
                        'root_causes': root_causes,
                        'recommendations': recommendations
                    })
                except Exception as e:
                    # If analysis fails, still add incident without recommendations
                    combined_incidents.append({
                        'incident': incident,
                        'context': None,
                        'root_causes': [],
                        'recommendations': []
                    })

            combined_incidents.sort(key=lambda x: x['incident'].timestamp)
            
            # Update analysis results to use DAILY GROUPED incidents
            analysis_results['incidents'] = combined_incidents
            
            # Step 5: Store results
            progress_bar.progress(100)
            
            # Add metadata
            analysis_results['metadata'] = {
                'analysis_time': datetime.now(),
                'time_range': f"{start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}",
                'temperature_thresholds': f"{temp_min}°C - {temp_max}°C",
                'data_points': len(data),
                'data_quality': validation['data_quality_score'] if 'data_quality_score' in validation else 0.8,
                'anomaly_count': len(data[((data.get('T°C AMBIANTE', pd.Series()) < temp_min) | (data.get('T°C AMBIANTE', pd.Series()) > temp_max))]) if 'T°C AMBIANTE' in data.columns else 0
            }
            
            st.session_state.analysis_results = analysis_results
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
                
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Erreur lors de l'analyse: {str(e)}")
            st.exception(e)


def display_analysis_results(results: Dict[str, Any], show_recommendations: bool):
    """Display the analysis results"""
    
    if not results or not results.get('incidents'):
        st.info("ℹ️ Aucun incident détecté - système fonctionnel")
        return
    
    # Summary section
    st.subheader("📊 Résumé de l'analyse")
    
    metadata = results.get('metadata', {})
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Incidents détectés",
            len(results['incidents']),
            help="Nombre total d'anomalies de température"
        )
    
    with col2:
        data_quality = metadata.get('data_quality', 0) * 100
        st.metric(
            "Qualité des données",
            f"{data_quality:.0f}%",
            help="Pourcentage de données valides utilisées"
        )
    
    with col3:
        pass
    
    with col4:
        critical_count = sum(1 for inc in results['incidents'] 
                           if inc['incident'].severity.value == 'critical')
        st.metric(
            "Incidents critiques",
            critical_count,
            delta=f"{critical_count}/{len(results['incidents'])}",
            help="Incidents nécessitant une action immédiate"
        )
    
    # Timeline visualization
    st.subheader("📈 Chronologie des incidents")
    timeline_incidents = results['incidents'][:500]
    if len(results['incidents']) > 500:
        st.caption(f"📉 Timeline limitée aux 500 premiers incidents (sur {len(results['incidents'])}) pour la performance.")
    display_incident_timeline(timeline_incidents)
    
    # Display incidents NATURALLY grouped by temperature state continuity
    st.subheader("🔬 Analyse des anomalies")
    
    # Summary info
    with st.expander("ℹ️ À propos du groupement", expanded=False):
        st.markdown("""
        **Groupement automatique par jour calendaire**:
        - **Un incident affiché** = TOUS les incidents d'une même journée fusionnés
        - Tous les types d'incidents du même jour sont combinés en un seul incident journalier
        - La **température** est l'EFFET/SYMPTÔME visible (pas la cause racine)
        - Les **vraies causes** (CLIM, porte, puissance, etc.) sont identifiées et comptées
        
        **Logique cause → effet:**
        - 🔧 **Causes racines**: CLIM en panne, porte ouverte, puissance élevée, etc.
        - ➡️ **Conséquence**: Anomalie de température (trop chaud ou trop froid)
        - 📊 Tous les incidents du jour sont regroupés pour voir cause + effet ensemble
        
        **Informations préservées:**
        - 🌡️ **Symptôme**: L'anomalie de température observée (chaud/froid)
        - 🔍 **Causes identifiées**: Tous les incidents causaux du jour (avec comptage)
        - ⏱️ **Durée totale**: Somme des durées de tous les incidents
        - 🔴 **Sévérité**: La sévérité la plus élevée parmi tous les incidents
        
        **Avantages:**
        - Vue consolidée cause → effet par jour
        - Identification claire des vraies causes derrière les anomalies thermiques
        - Simplification sans perte d'information
        
        **Exemple:**
        - **2024-01-15**: 1 CLIM arrêté + 2 portes ouvertes → 50 points température haute
          → **1 incident journalier** montrant les causes ET leur effet thermique
        """)
    
    # Display incidents organized by day - DÉJÀ REGROUPÉS
    if results['incidents']:

        # Les incidents sont DÉJÀ regroupés par jour dans run_incident_analysis
        incidents_to_display_raw = results['incidents']
        
        max_display_incidents = 300
        incidents_to_display = incidents_to_display_raw[:max_display_incidents]
        if len(incidents_to_display_raw) > max_display_incidents:
            st.warning(
                f"⚠️ Affichage limité aux {max_display_incidents} premiers incidents (sur {len(incidents_to_display_raw)}) pour éviter la surcharge navigateur."
            )
        
        # Show total count with visual stats
        incident_count = len(results['incidents'])
        
        # Calculate stats
        temp_incidents_result = [inc for inc in results['incidents'] if 'temperature' in inc['incident'].type.value]
        other_incidents_result = [inc for inc in results['incidents'] if 'temperature' not in inc['incident'].type.value]
        
        st.divider()
        
        # Display as enhanced cards
        for idx, inc_result in enumerate(incidents_to_display, 1):
            incident = inc_result['incident']
            sev = incident.severity.value
            inc_type = incident.type.value
            display_type = inc_type
            display_label = inc_type.replace('_', ' ').title()
            has_temperature_symptom = inc_type in ['temperature_high', 'temperature_low']

            if isinstance(incident.context, dict):
                causes = incident.context.get('causes', {}) or {}
                if isinstance(causes, dict) and causes:
                    non_temp_causes = {
                        cause_name: count
                        for cause_name, count in causes.items()
                        if str(cause_name).lower() not in ['temperature high', 'temperature low']
                    }

                    if non_temp_causes:
                        dominant_cause = max(non_temp_causes.items(), key=lambda x: x[1])[0]
                        display_label = str(dominant_cause)
                        display_type = display_label.lower().replace(' ', '_')
                    else:
                        dominant_cause = max(causes.items(), key=lambda x: x[1])[0]
                        display_label = str(dominant_cause)
                        display_type = display_label.lower().replace(' ', '_')

                    has_temperature_symptom = any(
                        str(cause_name).lower() in ['temperature high', 'temperature low']
                        for cause_name in causes.keys()
                    )
            
            # Choose icons
            type_icons = {
                'temperature_high': '🔥',
                'temperature_low': '❄️',
                'clim_failure': '❌',
                'clim_degraded': '⚠️',
                'cooling_inefficiency': '🌬️',
                'door_extended_open': '🚪',
                'door_anomaly': '🚪',
                'it_power_high': '⚡',
                'it_power_low': '📉',
                'power_anomaly': '⚡',
                'pue_high': '📊',
                'pue_critical': '📊',
            }
            type_icon = type_icons.get(display_type, '🌡️')
            sev_icon = "🔴" if sev == "critical" else "🟡" if sev == "warning" else "🟠" if sev == "emergency" else "🔵"
            
            # Format metric value - special handling for CLIM incidents
            if display_type in ['clim_failure', 'clim_degraded']:
                # Extract failed CLIM units from context or affected_systems
                failed_clims = []
                if isinstance(incident.context, dict) and 'failed_units' in incident.context:
                    # Extract CLIM names from full column names like 'CLIM_A_Status'
                    failed_clims = [unit.replace('_Status', '').replace('CLIM_', '') 
                                   for unit in incident.context['failed_units']]
                elif incident.affected_systems:
                    # Extract from affected_systems, excluding 'COOLING' and 'ALL_CLIM_UNITS'
                    failed_clims = [sys.replace('CLIM_', '') 
                                   for sys in incident.affected_systems 
                                   if sys not in ['COOLING', 'ALL_CLIM_UNITS'] and 'CLIM' in sys]
                
                if failed_clims:
                    metric_display = ', '.join(failed_clims)
                else:
                    # Fallback if no specific units identified
                    metric_display = f"{incident.metric_value:.0f} unités" if isinstance(incident.metric_value, (int, float)) else str(incident.metric_value)
            else:
                metric_display = f"{incident.metric_value:.1f}" if isinstance(incident.metric_value, (int, float)) else str(incident.metric_value)
            
            timestamp_str = incident.timestamp.strftime('%Y-%m-%d %H:%M')
            
            # Calculate duration display
            duration_display = "N/A"
            duration_color = "normal"
            if incident.duration_seconds:
                duration_hours = incident.duration_seconds / 3600
                if duration_hours >= 24:
                    duration_display = f"{duration_hours/24:.1f} jours"
                    duration_color = "inverse"
                elif duration_hours >= 1:
                    duration_display = f"{duration_hours:.1f}h"
                    duration_color = "normal"
                else:
                    duration_display = f"{incident.duration_seconds/60:.0f}min"
                    duration_color = "off"
            
            # Create enhanced card
            with st.container():
                # Header row with key info
                col1, col2, col3, col4 = st.columns([0.5, 1.5, 2, 2])
                
                with col1:
                    st.markdown(f"### #{idx}")
                
                with col2:
                    st.markdown(f"**{sev_icon} {sev.upper()}**")
                
                with col3:
                    st.markdown(f"**{type_icon} {display_label}**")
                    # Display failed CLIM names directly under the label for CLIM incidents
                    if display_type in ['clim_failure', 'clim_degraded'] and isinstance(metric_display, str) and any(c.isalpha() for c in metric_display):
                        st.caption(f"🔴 {metric_display}")
                
                with col4:
                    st.markdown(f"**⏰ {timestamp_str}**")
                
                # Metrics row - single column for points grouped
                if isinstance(incident.context, dict):
                    # Extract point count from context
                    num_alerts = incident.context.get('num_alerts', 0)
                    if num_alerts > 0:
                        st.metric("📊 Points groupés", num_alerts)
                elif incident.description:
                    # Extract point count from description if available
                    import re
                    match = re.search(r'\((\d+) points\)', incident.description)
                    if match:
                        st.metric("📊 Points groupés", match.group(1))
                
                # ⚠️ DATA QUALITY FLAG: Show if episode has NO returns to normal range
                if incident.duration_seconds and has_temperature_symptom:
                    episode_hours = incident.duration_seconds / 3600
                    if episode_hours > 48:  # More than 2 days
                        st.warning(
                            f"⚠️ **ALERTE**: Épisode thermique anormalement LONG ({episode_hours/24:.1f} jours) "
                            f"sans retour à plage acceptable. Vérifier capteur/données!"
                        )
                
                # Details in expandable section
                with st.expander(f"📖 Détails complets"):
                    display_incident_details(
                        incident, 
                        inc_result.get('context'), 
                        show_recommendations, 
                        inc_result.get('recommendations', []),
                        inc_result.get('root_causes', [])
                    )
                
                st.divider()


def display_incident_timeline(incidents: List[Dict[str, Any]]):
    """Create timeline visualization of incidents"""
    
    if not incidents:
        return
    
    # Prepare data for timeline
    timeline_data = []
    for i, inc_result in enumerate(incidents):
        incident = inc_result['incident']
        # Get context summary for timeline
        context = inc_result.get('context')
        context_summary = "Contexte indisponible"
        if context:
            # Create a brief summary from context
            door = context.door_status.get('severity', 'unknown')
            temp_ext = context.external_temp.get('severity', 'unknown')
            power = context.it_power.get('severity', 'unknown')
            clim = context.clim_status.get('severity', 'unknown')
            
            # Count critical factors
            critical_count = sum(1 for s in [door, temp_ext, power, clim] if s == 'critical')
            if critical_count > 0:
                context_summary = f"{critical_count} facteur(s) critique(s)"
            elif any(s == 'warning' for s in [door, temp_ext, power, clim]):
                context_summary = "Facteurs d'attention"
            else:
                context_summary = "Contexte normal"
        
        timeline_data.append({
            'timestamp': incident.timestamp,
            'temperature': incident.metric_value,
            'severity': incident.severity.value,
            'duration': incident.duration_seconds / 60 if incident.duration_seconds else 0,
            'context_summary': context_summary,
            'incident_id': f"Incident #{i+1}"
        })
    
    df = pd.DataFrame(timeline_data)
    
    # Create timeline plot
    fig = go.Figure()
    
    # Color mapping for severity
    color_map = {
        'critical': 'red',
        'warning': 'orange',
        'info': 'blue'
    }
    
    for severity in df['severity'].unique():
        severity_data = df[df['severity'] == severity]
        
        fig.add_trace(go.Scatter(
            x=severity_data['timestamp'],
            y=severity_data['temperature'],
            mode='markers+lines',
            name=f'Incidents {severity}',
            marker=dict(
                color=color_map.get(severity, 'gray'),
                size=severity_data['duration'].clip(5, 20),  # Size based on duration
                opacity=0.8,
                line=dict(width=1, color='white')
            ),
            text=severity_data['incident_id'],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Température: %{y:.1f}°C<br>"
                "Heure: %{x}<br>"
                "Contexte: %{customdata[1]}"
                "<extra></extra>"
            ),
            customdata=severity_data[['duration', 'context_summary']].values
        ))
    
    fig.update_layout(
        title="Chronologie des incidents de température",
        xaxis_title="Temps",
        yaxis_title="Température (°C)",
        height=400,
        hovermode='closest',
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)


def display_incident_details(incident, context, show_recommendations: bool, recommendations: List, root_causes: List = None):
    """Display detailed information about a specific incident"""
    
    # Incident basic info
    col1, col2 = st.columns(2)
    
    with col1:
        # Format metric value - special handling for CLIM incidents
        incident_type = incident.type.value if hasattr(incident.type, 'value') else str(incident.type)
        if incident_type in ['clim_failure', 'clim_degraded']:
            # Extract failed CLIM units from context or affected_systems
            failed_clims = []
            if isinstance(incident.context, dict) and 'failed_units' in incident.context:
                # Extract CLIM names from full column names like 'CLIM_A_Status'
                failed_clims = [unit.replace('_Status', '').replace('CLIM_', '') 
                               for unit in incident.context['failed_units']]
            elif incident.affected_systems:
                # Extract from affected_systems, excluding 'COOLING' and 'ALL_CLIM_UNITS'
                failed_clims = [sys.replace('CLIM_', '') 
                               for sys in incident.affected_systems 
                               if sys not in ['COOLING', 'ALL_CLIM_UNITS'] and 'CLIM' in sys]
            
            if failed_clims:
                metric_display = f"**CLIMs en panne**: {', '.join(failed_clims)}"
            else:
                metric_display = f"{incident.metric_value:.0f} unités" if isinstance(incident.metric_value, (int, float)) else str(incident.metric_value)
                metric_display = f"**Valeur**: {metric_display} {incident.metric_name}"
        else:
            metric_display = f"{incident.metric_value:.1f}" if isinstance(incident.metric_value, (int, float)) else str(incident.metric_value)
            metric_display = f"**Valeur**: {metric_display} {incident.metric_name}"
        
        st.markdown(metric_display)
    
    with col2:
        st.markdown(f"**Heure**: {incident.timestamp.strftime('%d/%m/%Y %H:%M')}")
    
    # Description
    st.markdown(f"**Description**: {incident.description}")
    
    # Temperature symptom if available (displayed separately)
    if isinstance(incident.context, dict) and incident.context.get('temp_symptom'):
        temp_symptom = incident.context['temp_symptom']
        st.markdown(f"**Symptôme**: Temp {temp_symptom['type']} ({temp_symptom['count']} points)")
    
    # Duration if available
    if incident.duration_seconds:
        duration_min = incident.duration_seconds / 60
        st.markdown(f"**Durée**: {duration_min:.1f} minutes")
    
    # Affected systems if available
    if incident.affected_systems:
        st.markdown(f"**Systèmes affectés**: {', '.join(incident.affected_systems)}")

    # Linked causes for merged temperature episodes
    if isinstance(incident.context, dict) and incident.context.get('linked_causes'):
        linked_causes = incident.context.get('linked_causes', [])
        total_cause_duration = int(incident.context.get('linked_causes_total_duration_seconds', 0) or 0)

        st.markdown("### 🧩 Causes pendant cet épisode thermique")
        st.markdown(f"**Nombre total de causes liées**: {len(linked_causes)}")
        st.markdown(f"**Durée cumulée des causes liées**: {total_cause_duration/3600:.1f}h")

        cause_type_counts = {}
        for cause in linked_causes:
            cause_type = str(cause.get('type', 'unknown')).replace('_', ' ').title()
            cause_type_counts[cause_type] = cause_type_counts.get(cause_type, 0) + 1

        if cause_type_counts:
            st.markdown("**Répartition des causes**:")
            for cause_label, count in sorted(cause_type_counts.items(), key=lambda x: x[0]):
                st.markdown(f"• {cause_label}: {count}")

        with st.expander("Voir le détail des causes liées", expanded=False):
            for idx, cause in enumerate(linked_causes, 1):
                cause_ts = cause.get('timestamp')
                cause_ts_str = cause_ts.strftime('%Y-%m-%d %H:%M') if hasattr(cause_ts, 'strftime') else str(cause_ts)
                cause_duration = int(cause.get('duration_seconds', 0) or 0)
                cause_duration_str = f"{cause_duration/60:.0f} min" if cause_duration > 0 else "N/A"
                st.markdown(
                    f"{idx}. **{str(cause.get('type', 'unknown')).replace('_', ' ').title()}** "
                    f"({str(cause.get('severity', 'info')).upper()}) — {cause_ts_str} — durée: {cause_duration_str}"
                )
                if cause.get('description'):
                    st.caption(str(cause.get('description')))
    
    # Context Analysis (if available)
    if context:
        st.markdown("### 📊 Contexte pendant l'incident")
        
        # Helper function for severity colors
        def get_severity_color(severity):
            if severity == "good":
                return "🟢"
            elif severity == "warning":
                return "🟡"
            elif severity == "critical":
                return "🔴"
            else:
                return "⚪"
        
        try:
            # Display context as a simple table-like structure
            context_data = [
                ("🚪 Porte", context.door_status["status"], get_severity_color(context.door_status["severity"])),
                ("🌡️ Temp. ext", context.external_temp["status"], get_severity_color(context.external_temp["severity"])),
                ("⚡ Puissance IT", context.it_power["status"], get_severity_color(context.it_power["severity"])),
                ("❄️ CLIMs", context.clim_status["status"], get_severity_color(context.clim_status["severity"])),
                ("📈 Tendance", context.temp_trend["status"], get_severity_color(context.temp_trend["severity"]))
            ]
            
            # Create a clean display
            for icon_label, status, color in context_data:
                st.markdown(f"{icon_label}: {status} {color}")
        except (AttributeError, KeyError, TypeError):
            st.info("ℹ️ Contexte détaillé non disponible pour ce type d'incident")
    
    # Root Causes Analysis (if available)
    if root_causes and len(root_causes) > 0:
        st.markdown("### 🔍 Analyse des Causes Racines")
        st.markdown(f"**{len(root_causes)} cause(s) identifiée(s)** avec scores de confiance")
        
        # Sort by confidence (highest first)
        sorted_causes = sorted(root_causes, key=lambda c: c.confidence, reverse=True)
        
        for idx, cause in enumerate(sorted_causes, 1):
            # Get confidence stars
            if cause.confidence >= 90:
                stars = "⭐⭐⭐⭐⭐"
                conf_color = "🟢"
            elif cause.confidence >= 75:
                stars = "⭐⭐⭐⭐"
                conf_color = "🟢"
            elif cause.confidence >= 60:
                stars = "⭐⭐⭐"
                conf_color = "🟡"
            elif cause.confidence >= 40:
                stars = "⭐⭐"
                conf_color = "🟠"
            else:
                stars = "⭐"
                conf_color = "🔴"
            
            # Cause type label
            cause_label = cause.cause_type.value.replace('_', ' ').title()
            
            st.markdown(f"**{idx}. {cause_label}** {conf_color} ({cause.confidence:.0f}% confiance) {stars}")
            st.markdown(f"   📝 {cause.description}")
            
            # Show evidence if available
            if cause.evidence and len(cause.evidence) > 0:
                with st.expander(f"🔬 Voir les preuves ({len(cause.evidence)} éléments)", expanded=False):
                    for ev in cause.evidence:
                        st.markdown(f"• **{ev.type}**: {ev.description}")
                        if ev.value is not None:
                            st.caption(f"  Valeur: {ev.value}")
            
            st.markdown("")  # Spacing
    
    # Recommendations
    if show_recommendations and recommendations:
        st.markdown("### 💡 Recommandations")
        
        # Group by priority
        priority_order = ['immediate', 'urgent', 'high', 'medium', 'low']
        priority_labels = {
            'immediate': '🚨 IMMÉDIAT',
            'urgent': '⚡ URGENT',
            'high': '🔴 HAUTE PRIORITÉ',
            'medium': '🟡 PRIORITÉ MOYENNE',
            'low': '🟢 PRÉVENTIF'
        }
        
        recommendations_by_priority = {}
        for rec in recommendations:
            priority = rec.priority.value
            if priority not in recommendations_by_priority:
                recommendations_by_priority[priority] = []
            recommendations_by_priority[priority].append(rec)
        
        for priority in priority_order:
            if priority in recommendations_by_priority:
                st.markdown(f"#### {priority_labels[priority]}")
                
                for rec in recommendations_by_priority[priority]:
                    st.markdown(f"**{rec.title}** - {rec.estimated_time}")
                    st.markdown(f"**Description**: {rec.description}")
                    st.markdown(f"**Équipe responsable**: {rec.responsible_team}")
                    
                    if rec.steps:
                        st.markdown("**Étapes**:")
                        for step in rec.steps:
                            st.markdown(f"• {step}")
                    
                    if rec.resources_needed:
                        st.markdown(f"**Ressources nécessaires**: {', '.join(rec.resources_needed)}")
                    
                    if rec.expected_outcome:
                        st.markdown(f"**Résultat attendu**: {rec.expected_outcome}")
                    
                    st.markdown("---")  # Separator between recommendations


def render_incident_lens_summary():
    """Render summary view for main dashboard"""
    st.subheader("🔍 Incident Lens - Aperçu")
    
    if 'analysis_results' in st.session_state and st.session_state.analysis_results:
        results = st.session_state.analysis_results
        incidents = results.get('incidents', [])
        
        if incidents:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Incidents récents", len(incidents))
            
            with col2:
                critical_count = sum(1 for inc in incidents 
                                   if inc['incident'].severity.value == 'critical')
                st.metric("Critiques", critical_count)
            
            with col3:
                if incidents:
                    last_incident = max(incidents, key=lambda x: x['incident'].timestamp)
                    time_since = datetime.now() - last_incident['incident'].timestamp
                    st.metric("Dernier incident", f"Il y a {time_since.seconds // 3600}h")
            
            # Quick actions
            if st.button("🔍 Analyser maintenant", key="quick_analysis"):
                st.switch_page("Incident Lens")
        
        else:
            st.success("✅ Aucun incident récent détecté")
    
    else:
        st.info("ℹ️ Aucune analyse récente. Cliquez ci-dessous pour commencer.")
        if st.button("🚀 Lancer première analyse", key="first_analysis"):
            st.switch_page("Incident Lens")