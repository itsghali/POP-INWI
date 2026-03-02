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
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
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


# ---------------------------------------------------------------------------
# Clustering / grouping helper functions
# ---------------------------------------------------------------------------

def severity_rank(severity: IncidentSeverity) -> int:
    """Return numeric rank for severity (higher = more severe)."""
    order = {
        IncidentSeverity.INFO: 0,
        IncidentSeverity.WARNING: 1,
        IncidentSeverity.CRITICAL: 2,
        IncidentSeverity.EMERGENCY: 3,
    }
    return order.get(severity, 0)


def _incident_time_window(incident: Incident) -> Tuple[datetime, datetime]:
    """Return (start, end) time window for an incident."""
    start = incident.timestamp
    duration = incident.duration_seconds or 900
    end = start + timedelta(seconds=duration)
    return start, end


def _windows_overlap(start_a, end_a, start_b, end_b) -> bool:
    """Check overlap between two inclusive time windows, handling point-temporal cases."""
    if start_a == end_a or start_b == end_b:
        return not (end_a < start_b or end_b < start_a)
    return not (end_a < start_b or end_b < start_a)


def _max_deviation(value: float, temp_min: float, temp_max: float) -> float:
    """Return the maximum absolute deviation of *value* from either threshold."""
    return max(abs(value - temp_max), abs(value - temp_min))


def cluster_incidents_by_time(
    incidents: List[Incident],
    gap_threshold: timedelta = timedelta(minutes=30)
) -> List[List[Incident]]:
    """Cluster incidents where consecutive incidents are within gap_threshold of each other."""
    if not incidents:
        return []
    sorted_incidents = sorted(incidents, key=lambda inc: inc.timestamp)
    clusters: List[List[Incident]] = []
    current_cluster = [sorted_incidents[0]]
    for inc in sorted_incidents[1:]:
        prev = current_cluster[-1]
        prev_end = _incident_time_window(prev)[1]
        if inc.timestamp - prev_end <= gap_threshold:
            current_cluster.append(inc)
        else:
            clusters.append(current_cluster)
            current_cluster = [inc]
    clusters.append(current_cluster)
    return clusters


def _finalize_cluster(cluster: List[Incident]) -> Incident:
    """Merge a list of incidents into a single representative incident."""
    if len(cluster) == 1:
        return cluster[0]
    start_incident = min(cluster, key=lambda inc: inc.timestamp)
    end_incident = max(cluster, key=lambda inc: inc.timestamp)
    duration_seconds = int((end_incident.timestamp - start_incident.timestamp).total_seconds())
    if duration_seconds == 0:
        duration_seconds = 900
    worst = max(cluster, key=lambda inc: severity_rank(inc.severity))
    return Incident(
        id=start_incident.id,
        timestamp=start_incident.timestamp,
        type=worst.type,
        severity=worst.severity,
        metric_name=worst.metric_name,
        metric_value=worst.metric_value,
        threshold_violated=worst.threshold_violated,
        duration_seconds=duration_seconds,
        affected_systems=list({s for inc in cluster for s in inc.affected_systems}),
        description=worst.description,
        context=worst.context,
    )


def group_temperature_incidents_by_continuity(
    incidents: List[Incident],
    gap_threshold: timedelta = timedelta(hours=2)
) -> List[List[Incident]]:
    """Group temperature incidents into continuous episodes."""
    temp_incidents = [
        inc for inc in incidents
        if inc.type in (IncidentType.TEMPERATURE_HIGH, IncidentType.TEMPERATURE_LOW)
    ]
    return cluster_incidents_by_time(temp_incidents, gap_threshold)


def create_merged_incident_daily(
    group: List[Incident],
    temp_min: float,
    temp_max: float
) -> Incident:
    """Merge a group of temperature incidents into a single daily representative."""
    if not group:
        raise ValueError("Cannot merge empty group")
    start_incident = min(group, key=lambda inc: inc.timestamp)
    end_incident = max(group, key=lambda inc: inc.timestamp)
    # Use actual timestamp span instead of counting points
    duration_seconds = int((end_incident.timestamp - start_incident.timestamp).total_seconds())
    if duration_seconds == 0:
        duration_seconds = 900  # Single point = 15 min default

    high_temps = [inc.metric_value for inc in group if inc.type == IncidentType.TEMPERATURE_HIGH]
    low_temps = [inc.metric_value for inc in group if inc.type == IncidentType.TEMPERATURE_LOW]
    # Pick the most extreme deviation from thresholds
    all_temps = [inc.metric_value for inc in group]
    merged_metric_value = max(all_temps, key=lambda t: _max_deviation(t, temp_min, temp_max))

    if high_temps and (not low_temps or len(high_temps) >= len(low_temps)):
        merged_type = IncidentType.TEMPERATURE_HIGH
        threshold = temp_max
    else:
        merged_type = IncidentType.TEMPERATURE_LOW
        threshold = temp_min

    worst_severity = max(group, key=lambda inc: severity_rank(inc.severity)).severity
    return Incident(
        id=start_incident.id,
        timestamp=start_incident.timestamp,
        type=merged_type,
        severity=worst_severity,
        metric_name='T°C AMBIANTE',
        metric_value=merged_metric_value,
        threshold_violated=threshold,
        duration_seconds=duration_seconds,
        affected_systems=['TEMPERATURE'],
        description=(
            f"Episode: {len(group)} anomalie(s) de "
            f"{start_incident.timestamp.strftime('%H:%M')} à "
            f"{end_incident.timestamp.strftime('%H:%M')}"
        ),
        context={'num_anomalies': len(group), 'high_temps': high_temps, 'low_temps': low_temps},
    )


def group_non_temperature_incidents_by_continuity(
    incidents: List[Incident],
    gap_threshold: timedelta = timedelta(hours=1)
) -> List[List[Incident]]:
    """Group non-temperature incidents into continuous episodes."""
    non_temp = [
        inc for inc in incidents
        if inc.type not in (IncidentType.TEMPERATURE_HIGH, IncidentType.TEMPERATURE_LOW)
    ]
    return cluster_incidents_by_time(non_temp, gap_threshold)


def create_merged_non_temp_incident(group: List[Incident]) -> Incident:
    """Merge a group of non-temperature incidents into a single representative."""
    if not group:
        raise ValueError("Cannot merge empty group")
    start_incident = min(group, key=lambda inc: inc.timestamp)
    end_incident = max(group, key=lambda inc: inc.timestamp)
    duration_seconds = int((end_incident.timestamp - start_incident.timestamp).total_seconds())
    if duration_seconds == 0:
        duration_seconds = 900
    worst = max(group, key=lambda inc: severity_rank(inc.severity))
    return Incident(
        id=start_incident.id,
        timestamp=start_incident.timestamp,
        type=worst.type,
        severity=worst.severity,
        metric_name=worst.metric_name,
        metric_value=worst.metric_value,
        threshold_violated=worst.threshold_violated,
        duration_seconds=duration_seconds,
        affected_systems=list({s for inc in group for s in inc.affected_systems}),
        description=(
            f"Episode: {len(group)} événement(s) de "
            f"{start_incident.timestamp.strftime('%H:%M')} à "
            f"{end_incident.timestamp.strftime('%H:%M')}"
        ),
        context=worst.context,
    )


def group_all_incidents_by_day(
    incidents: List[Incident]
) -> Dict[date, List[Incident]]:
    """Group all incidents by calendar day."""
    day_map: Dict[date, List[Incident]] = {}
    for inc in incidents:
        day = inc.timestamp.date()
        day_map.setdefault(day, []).append(inc)
    return day_map


def create_daily_unified_incident(
    day_incidents: List[Incident],
    temp_min: float,
    temp_max: float
) -> Incident:
    """Create a single representative incident for a given day."""
    if not day_incidents:
        raise ValueError("Cannot create daily incident from empty list")
    start_incident = min(day_incidents, key=lambda inc: inc.timestamp)
    end_incident = max(day_incidents, key=lambda inc: inc.timestamp)
    # Use actual timestamp span
    duration_seconds = int((end_incident.timestamp - start_incident.timestamp).total_seconds())
    if duration_seconds == 0:
        duration_seconds = 900

    temp_incidents = [
        inc for inc in day_incidents
        if inc.type in (IncidentType.TEMPERATURE_HIGH, IncidentType.TEMPERATURE_LOW)
    ]
    if temp_incidents:
        all_temps = [inc.metric_value for inc in temp_incidents]
        metric_value = max(all_temps, key=lambda t: _max_deviation(t, temp_min, temp_max))
        worst_type = max(temp_incidents, key=lambda inc: severity_rank(inc.severity)).type
        threshold = temp_max if worst_type == IncidentType.TEMPERATURE_HIGH else temp_min
    else:
        worst = max(day_incidents, key=lambda inc: severity_rank(inc.severity))
        metric_value = worst.metric_value
        worst_type = worst.type
        threshold = worst.threshold_violated

    worst_severity = max(day_incidents, key=lambda inc: severity_rank(inc.severity)).severity
    return Incident(
        id=start_incident.id,
        timestamp=start_incident.timestamp,
        type=worst_type,
        severity=worst_severity,
        metric_name='T°C AMBIANTE' if temp_incidents else day_incidents[0].metric_name,
        metric_value=metric_value,
        threshold_violated=threshold,
        duration_seconds=duration_seconds,
        affected_systems=list({s for inc in day_incidents for s in inc.affected_systems}),
        description=(
            f"Journée: {len(day_incidents)} incident(s) entre "
            f"{start_incident.timestamp.strftime('%H:%M')} et "
            f"{end_incident.timestamp.strftime('%H:%M')}"
        ),
        context={'total_incidents': len(day_incidents), 'temp_incidents': len(temp_incidents)},
    )


def merge_incidents_into_temperature_episodes(
    incidents: List[Incident],
    temp_min: float,
    temp_max: float,
    gap_threshold: timedelta = timedelta(hours=2)
) -> List[Incident]:
    """Merge consecutive temperature incidents into episodes using window overlap."""
    temp_incidents = [
        inc for inc in incidents
        if inc.type in (IncidentType.TEMPERATURE_HIGH, IncidentType.TEMPERATURE_LOW)
    ]
    if not temp_incidents:
        return []
    sorted_incidents = sorted(temp_incidents, key=lambda inc: inc.timestamp)
    episodes: List[List[Incident]] = []
    current_episode = [sorted_incidents[0]]
    for inc in sorted_incidents[1:]:
        prev = current_episode[-1]
        prev_start, prev_end = _incident_time_window(prev)
        cur_start, cur_end = _incident_time_window(inc)
        # Use gap-extended end for overlap check
        extended_prev_end = prev_end + gap_threshold
        if _windows_overlap(prev_start, extended_prev_end, cur_start, cur_end):
            current_episode.append(inc)
        else:
            episodes.append(current_episode)
            current_episode = [inc]
    episodes.append(current_episode)
    return [create_merged_incident_daily(ep, temp_min, temp_max) for ep in episodes]


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
    # Only update if the data object has actually changed to avoid unnecessary reruns
    if data is not None and not data.empty:
        if 'passed_data' not in st.session_state or id(st.session_state.passed_data) != id(data):
            st.session_state.passed_data = data
        st.session_state.has_external_data = True
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
                min_value=15.0,
                max_value=25.0,
                value=20.0,
                step=0.5,
                help="Températures en dessous de cette valeur seront considérées comme anomalies"
            )
            
            temp_max = st.number_input(
                "Température maximale acceptable (°C)",
                min_value=22.0,
                max_value=35.0,
                value=26.0,
                step=0.5,
                help="Températures au dessus de cette valeur seront considérées comme anomalies"
            )
            
            if temp_min >= temp_max:
                st.error("❌ La température minimale doit être inférieure à la maximale")
                return
                
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
    """Execute the incident analysis"""
    
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
                # Fallback to file loading
                if 'preprocessor' not in st.session_state:
                    st.error("❌ Pas de données disponibles et pas de preprocessor configuré")
                    progress_bar.empty()
                    status_text.empty()
                    return
                    
                preprocessor = st.session_state.preprocessor
                data = preprocessor.load_data(start_time, end_time, force_reload=True)
                
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

            # Add debugging information for temperature analysis
            if 'T°C AMBIANTE' in data.columns:
                st.info(f"🎯 **Seuils configurés**: Min: {temp_min}°C, Max: {temp_max}°C")

            # Detect all incidents using IncidentDetector
            detector = IncidentDetector(data)
            raw_incidents = detector.detect_incidents()

            # Merge temperature incidents into continuous episodes
            temp_episodes = merge_incidents_into_temperature_episodes(
                raw_incidents, temp_min, temp_max
            )

            # Cluster non-temperature incidents
            non_temp_groups = group_non_temperature_incidents_by_continuity(raw_incidents)
            non_temp_episodes = [create_merged_non_temp_incident(g) for g in non_temp_groups if g]

            # Combine all episodes and sort by timestamp
            all_episodes: List[Incident] = sorted(
                temp_episodes + non_temp_episodes, key=lambda inc: inc.timestamp
            )

            # Step 4: Generate recommendations if requested
            if show_recommendations and all_episodes:
                status_text.text("💡 Génération des recommandations...")
                progress_bar.progress(80)

            # Step 5: Store results and show final message
            progress_bar.progress(100)
            incident_count = len(all_episodes)
            st.success(f"✅ **Analyse terminée: {incident_count} incident(s) détecté(s)**")

            # Fix: compute anomaly_count using direct column access (not data.get)
            anomaly_count = (
                len(data[(data['T°C AMBIANTE'] < temp_min) | (data['T°C AMBIANTE'] > temp_max)])
                if 'T°C AMBIANTE' in data.columns else 0
            )

            # Add metadata
            analysis_results = {
                'incidents': all_episodes,
                'metadata': {
                    'analysis_time': datetime.now(),
                    'time_range': f"{start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}",
                    'temperature_thresholds': f"{temp_min}°C - {temp_max}°C",
                    'data_points': len(data),
                    'anomaly_count': anomaly_count,
                    'data_quality': validation['data_quality_score'] if 'data_quality_score' in validation else 0.8
                }
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

    incidents: List[Incident] = results['incidents']

    # Summary section
    st.subheader("📊 Résumé de l'analyse")

    metadata = results.get('metadata', {})
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Incidents détectés",
            len(incidents),
            help="Nombre total d'épisodes d'incidents"
        )

    with col2:
        data_quality = metadata.get('data_quality', 0) * 100
        st.metric(
            "Qualité des données",
            f"{data_quality:.0f}%",
            help="Pourcentage de données valides utilisées"
        )

    with col3:
        anomaly_count = metadata.get('anomaly_count', 0)
        st.metric(
            "Points d'anomalie",
            anomaly_count,
            help="Nombre de points de mesure hors seuils"
        )

    with col4:
        critical_count = sum(
            1 for inc in incidents
            if inc.severity in (IncidentSeverity.CRITICAL, IncidentSeverity.EMERGENCY)
        )
        st.metric(
            "Incidents critiques",
            critical_count,
            delta=f"{critical_count}/{len(incidents)}",
            help="Incidents nécessitant une action immédiate"
        )

    # Timeline visualization
    st.subheader("📈 Chronologie des incidents")
    display_incident_timeline(incidents)

    # Card-based detailed incident display
    st.subheader("🔬 Analyse détaillée des incidents")

    severity_icons = {
        IncidentSeverity.EMERGENCY: "🚨",
        IncidentSeverity.CRITICAL: "🔴",
        IncidentSeverity.WARNING: "🟡",
        IncidentSeverity.INFO: "🔵",
    }

    for i, incident in enumerate(incidents, 1):
        icon = severity_icons.get(incident.severity, "⚪")
        is_temp = incident.type in (IncidentType.TEMPERATURE_HIGH, IncidentType.TEMPERATURE_LOW)
        value_str = f"{incident.metric_value:.1f}°C" if is_temp else f"{incident.metric_value:.2f}"
        label = (
            f"{icon} Incident #{i}: {incident.metric_name} = {value_str} "
            f"— {incident.timestamp.strftime('%d/%m %H:%M')} "
            f"({incident.severity.value})"
        )
        with st.expander(label, expanded=i <= 3):
            c1, c2, c3 = st.columns(3)
            with c1:
                unit = "°C" if is_temp else ""
                st.markdown(f"**{incident.metric_name}**: {incident.metric_value:.2f}{unit}")
                st.markdown(f"**Seuil dépassé**: {incident.threshold_violated:.2f}{unit}")
            with c2:
                duration_min = (incident.duration_seconds or 0) // 60
                st.markdown(f"**Durée**: {duration_min} min")
                st.markdown(f"**Type**: {incident.type.value}")
            with c3:
                st.markdown(f"**Heure**: {incident.timestamp.strftime('%d/%m/%Y %H:%M')}")
                st.markdown(f"**Description**: {incident.description}")
            if incident.context:
                st.markdown("**Contexte**:")
                for k, v in incident.context.items():
                    st.markdown(f"- {k}: {v}")


def display_incident_timeline(incidents: List[Incident]):
    """Create timeline visualization of incidents"""

    if not incidents:
        return

    # Prepare data for timeline
    timeline_data = []
    for i, incident in enumerate(incidents):
        timeline_data.append({
            'timestamp': incident.timestamp,
            'temperature': incident.metric_value,
            'severity': incident.severity.value,
            'duration': (incident.duration_seconds or 0) / 60,
            'context_summary': incident.description or "Aucun contexte",
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


def display_incident_details(incident, context, show_recommendations: bool, recommendations: List):
    """Display detailed information about a specific incident"""
    
    # Incident info
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"**Température**: {incident.metric_value:.1f}°C")
    
    with col2:
        st.markdown(f"**Seuil dépassé**: {incident.threshold_violated:.1f}°C")
    
    with col3:
        st.markdown(f"**Heure**: {incident.timestamp.strftime('%d/%m/%Y %H:%M')}")
        st.markdown(f"**Description**: {incident.description}")
    
    # Context Analysis
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
                critical_count = sum(
                    1 for inc in incidents
                    if inc.severity in (IncidentSeverity.CRITICAL, IncidentSeverity.EMERGENCY)
                )
                st.metric("Critiques", critical_count)
            
            with col3:
                if incidents:
                    last_incident = max(incidents, key=lambda x: x.timestamp)
                    time_since = datetime.now() - last_incident.timestamp
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