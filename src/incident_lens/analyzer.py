"""
Root Cause Analysis Engine for Incident Lens
Analyzes temperature anomalies and identifies likely causes with confidence scores
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

try:
    from .detector import Incident, IncidentType, IncidentSeverity
except ImportError:
    # For standalone testing
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from incident_lens.detector import Incident, IncidentType, IncidentSeverity


logger = logging.getLogger(__name__)


class RootCauseType(Enum):
    """Types of root causes that can be identified"""
    CLIM_TOTAL_FAILURE = "clim_total_failure"
    CLIM_PARTIAL_FAILURE = "clim_partial_failure"
    CLIM_INEFFICIENCY = "clim_inefficiency"
    DOOR_EXTENDED_OPEN = "door_extended_open"
    DOOR_FREQUENT_CYCLES = "door_frequent_cycles"
    EXTERNAL_HEAT_WAVE = "external_heat_wave"
    EXTERNAL_TEMP_INFLUENCE = "external_temp_influence"
    IT_POWER_SURGE = "it_power_surge"
    IT_POWER_HIGH_SUSTAINED = "it_power_high_sustained"
    COOLING_POWER_LOSS = "cooling_power_loss"
    PUE_DEGRADATION = "pue_degradation"
    COMPOUND_CAUSE = "compound_cause"
    UNKNOWN = "unknown"


@dataclass
class Evidence:
    """Evidence supporting a root cause"""
    type: str
    description: str
    value: Any
    confidence_contribution: float = 0.0
    

@dataclass
class RootCause:
    """Identified root cause with evidence and confidence"""
    cause_type: RootCauseType
    confidence: float
    description: str
    evidence: List[Evidence] = field(default_factory=list)
    affected_metrics: List[str] = field(default_factory=list)


@dataclass
class IncidentContext:
    """Simple context analysis for an incident"""
    door_status: Dict[str, Any]
    external_temp: Dict[str, Any] 
    it_power: Dict[str, Any]
    clim_status: Dict[str, Any]
    temp_trend: Dict[str, Any]
        

@dataclass 
class DataQualityReport:
    """Report on data quality for the analysis period"""
    completeness: float  # 0-1 percentage of expected data points
    reliability: float   # 0-1 based on sensor consistency
    time_gaps: List[Tuple[datetime, datetime]] = field(default_factory=list)
    missing_sensors: List[str] = field(default_factory=list)
    quality_score: float = 0.0  # Overall quality 0-1
    
    def __post_init__(self):
        # Calculate overall quality score
        self.quality_score = (self.completeness + self.reliability) / 2


class RootCauseAnalyzer:
    """
    Analyzes incidents to identify root causes with evidence-based confidence scoring
    Adapts analysis strategy based on time range and data quality
    """
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize analyzer with data
        
        Args:
            data: Time-series DataFrame with all sensor readings
        """
        self.data = data.copy()
        self.data = self.data.sort_index()
        
        # Initialize column mappings for robust data access
        self._init_column_mappings()
        
        # Precompute derived metrics for faster analysis
        self._prepare_data()
        
        # Initialize cause detectors
        self._init_detectors()
        
    def _init_column_mappings(self):
        """Initialize column name mappings to handle variations"""
        # Define standard column names and their possible variations
        self.column_mappings = {
            'door_state': ['Etat de porte', 'Status_porte', 'Door_Status', 'Porte', 'Door'],
            'external_temp': ['T°C EXTERIEURE', 'T°C_EXT', 'External_Temp', 'Temp_Ext', 'Temperature_External'],
            'ambient_temp': ['T°C AMBIANTE', 'T°C_AMB', 'Ambient_Temp', 'Temp_Amb', 'Temperature_Ambient'],
            'it_power': ['Puissance_IT', 'IT_Power', 'Power_IT', 'Puissance IT', 'puissance_it', 'PUISSANCE_IT'],
            'clim_pattern': ['CLIM.*Status', 'CLIM.*_Status', 'clim.*status']  # Regex pattern for CLIM status columns
        }
        
        # Create mapping from actual columns to standard names
        self.actual_columns = {}
        for standard_name, variations in self.column_mappings.items():
            if standard_name == 'clim_pattern':
                # Handle CLIM columns specially
                import re
                pattern = variations[0]
                self.actual_columns['clim_cols'] = [
                    col for col in self.data.columns 
                    if re.search(pattern, col)
                ]
            else:
                # Find first matching column
                for variation in variations:
                    if variation in self.data.columns:
                        self.actual_columns[standard_name] = variation
                        break
                        
    def _get_column_name(self, standard_name: str) -> Optional[str]:
        """Get actual column name for a standard name"""
        return self.actual_columns.get(standard_name)
        
    def _prepare_data(self):
        """Precompute derived metrics for efficient analysis"""
        # CLIM active count using mapped columns
        clim_cols = self.actual_columns.get('clim_cols', [])
        available_clim = [col for col in clim_cols if col in self.data.columns]
        if available_clim:
            self.data['clim_active_count'] = self.data[available_clim].sum(axis=1)
            self.data['clim_availability_pct'] = self.data['clim_active_count'] / len(available_clim) * 100
        
        # Temperature differentials using mapped columns
        ambient_col = self._get_column_name('ambient_temp')
        external_col = self._get_column_name('external_temp')
        if ambient_col and external_col and ambient_col in self.data.columns and external_col in self.data.columns:
            self.data['temp_differential'] = self.data[ambient_col] - self.data[external_col]
            
        # Power metrics using calculated IT power column
        if 'Puissance_IT' in self.data.columns:
            self.data['power_change_rate'] = self.data['Puissance_IT'].diff()
            
        # Door open duration using mapped columns
        door_col = self._get_column_name('door_state')
        if door_col and door_col in self.data.columns:
            # Count consecutive open states
            self.data['door_open_rolling'] = self.data[door_col].rolling(window=4, min_periods=1).sum()
            
    def _init_detectors(self):
        """Initialize cause-specific detectors"""
        self.detectors = {
            'clim': CLIMCauseDetector(),
            'environmental': EnvironmentalCauseDetector(),
            'door': DoorCauseDetector(),
            'power': PowerCauseDetector()
        }
        
    def assess_data_quality(self, start_time: datetime, end_time: datetime) -> DataQualityReport:
        """
        Assess quality of data in the specified time range
        
        Args:
            start_time: Start of analysis period
            end_time: End of analysis period
            
        Returns:
            DataQualityReport with quality metrics
        """
        # Filter data to time range
        mask = (self.data.index >= start_time) & (self.data.index <= end_time)
        period_data = self.data[mask]
        
        if period_data.empty:
            return DataQualityReport(completeness=0.0, reliability=0.0)
            
        # Calculate expected data points (assuming 15-min intervals)
        duration = end_time - start_time
        expected_points = int(duration.total_seconds() / 900)  # 900 seconds = 15 minutes
        actual_points = len(period_data)
        
        completeness = min(1.0, actual_points / expected_points) if expected_points > 0 else 0.0
        
        # Check for time gaps
        time_gaps = []
        if len(period_data) > 1:
            time_diffs = period_data.index.to_series().diff()
            gap_threshold = pd.Timedelta(minutes=30)  # Gap if > 30 minutes
            
            for i, diff in enumerate(time_diffs[1:], 1):
                if diff > gap_threshold:
                    gap_start = period_data.index[i-1]
                    gap_end = period_data.index[i]
                    time_gaps.append((gap_start, gap_end))
                    
        # Check sensor reliability (look for stuck values)
        reliability_scores = []
        for col in ['T°C AMBIANTE', 'T°C EXTERIEURE']:
            if col in period_data.columns:
                # Check if sensor is stuck (no variation)
                col_std = period_data[col].std()
                col_mean = period_data[col].mean()
                # Sensor is reliable if it shows variation or is legitimately constant
                is_reliable = col_std > 0.1 or (col_std == 0 and not pd.isna(col_mean))
                reliability_scores.append(1.0 if is_reliable else 0.5)
        
        # Check IT power column reliability
        if 'Puissance_IT' in period_data.columns:
            # Check if sensor is stuck (no variation)
            power_std = period_data['Puissance_IT'].std()
            power_mean = period_data['Puissance_IT'].mean()
            # Sensor is reliable if it shows variation or is legitimately constant
            is_reliable = power_std > 0.1 or (power_std == 0 and not pd.isna(power_mean))
            reliability_scores.append(1.0 if is_reliable else 0.5)
                
        reliability = np.mean(reliability_scores) if reliability_scores else 0.5
        
        # Check for missing sensors
        expected_sensors = ['T°C AMBIANTE', 'T°C EXTERIEURE', 'Etat de porte', 
                           'CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status']
        missing_sensors = [s for s in expected_sensors if s not in self.data.columns]
        
        return DataQualityReport(
            completeness=completeness,
            reliability=reliability,
            time_gaps=time_gaps,
            missing_sensors=missing_sensors
        )
        
    def analyze_incident(self, 
                        incident: Incident,
                        time_window_before: int = 60,
                        time_window_after: int = 30) -> List[RootCause]:
        """
        Analyze a specific incident to identify root causes
        
        Args:
            incident: Temperature incident to analyze
            time_window_before: Minutes to analyze before incident
            time_window_after: Minutes to analyze after incident
            
        Returns:
            List of root causes ranked by confidence
        """
        # Define analysis window
        start_time = incident.timestamp - timedelta(minutes=time_window_before)
        end_time = incident.timestamp + timedelta(minutes=time_window_after)
        
        # Get data for analysis window
        mask = (self.data.index >= start_time) & (self.data.index <= end_time)
        window_data = self.data[mask]
        
        if window_data.empty:
            logger.warning(f"No data available for incident at {incident.timestamp}")
            return [RootCause(
                cause_type=RootCauseType.UNKNOWN,
                confidence=0.0,
                description="Données insuffisantes pour l'analyse"
            )]
            
        # Assess data quality
        quality = self.assess_data_quality(start_time, end_time)
        
        # Get context for adaptive analysis
        context = {
            'incident': incident,
            'time_range': end_time - start_time,
            'data_quality': quality,
            'incident_duration': incident.duration_seconds / 60 if incident.duration_seconds else None
        }
        
        # Run all detectors
        all_causes = []
        for detector_name, detector in self.detectors.items():
            try:
                causes = detector.detect(window_data, context)
                all_causes.extend(causes)
            except Exception as e:
                logger.error(f"Error in {detector_name} detector: {e}")
                
        # Combine and rank causes
        ranked_causes = self._rank_causes(all_causes, quality)
        
        # Add recommendations
        for cause in ranked_causes:
            cause.recommendations = self._generate_recommendations(cause)
            
        return ranked_causes
        
    def analyze_time_range(self,
                          start_time: datetime,
                          end_time: datetime,
                          temp_min: float,
                          temp_max: float) -> Dict[str, Any]:
        """
        Analyze all incidents in a time range
        
        Args:
            start_time: Start of analysis period
            end_time: End of analysis period  
            temp_min: Minimum acceptable temperature
            temp_max: Maximum acceptable temperature
            
        Returns:
            Analysis results with incidents and root causes
        """
        # Filter data to time range
        mask = (self.data.index >= start_time) & (self.data.index <= end_time)
        period_data = self.data[mask]
        
        if period_data.empty:
            return {
                'analysis_period': {
                    'start': start_time,
                    'end': end_time,
                    'data_available': False
                },
                'incidents': [],
                'summary': {'error': 'No data available for selected period'}
            }
            
        # Assess overall data quality
        quality = self.assess_data_quality(start_time, end_time)
        
        # Find temperature anomalies
        anomalies = self._find_temperature_anomalies(period_data, temp_min, temp_max)
        
        # Group anomalies into incidents
        incidents = self._group_anomalies_to_incidents(anomalies, temp_min, temp_max)
        
        # Analyze each incident with context
        results = []
        for incident in incidents:
            context = self._analyze_incident_context(incident, period_data, temp_min, temp_max)
            results.append({
                'incident': incident,
                'context': context
            })
            
        # Generate summary statistics
        summary = self._generate_summary(results, quality)
        
        return {
            'analysis_period': {
                'start': start_time,
                'end': end_time,
                'duration_hours': (end_time - start_time).total_seconds() / 3600,
                'data_completeness': quality.completeness,
                'data_quality_score': quality.quality_score
            },
            'incidents': results,
            'summary': summary
        }
        
    def _find_temperature_anomalies(self, data: pd.DataFrame, temp_min: float, temp_max: float) -> pd.DataFrame:
        """Find all temperature readings outside acceptable range"""
        if 'T°C AMBIANTE' not in data.columns:
            return pd.DataFrame()
            
        mask = (data['T°C AMBIANTE'] < temp_min) | (data['T°C AMBIANTE'] > temp_max)
        anomalies = data[mask].copy()
        
        # Add severity classification
        anomalies['deviation'] = anomalies['T°C AMBIANTE'].apply(
            lambda x: max(x - temp_max, temp_min - x, 0)
        )
        
        return anomalies
    
    def _analyze_incident_context(self, incident: Incident, data: pd.DataFrame, temp_min: float, temp_max: float) -> IncidentContext:
        """Analyze incident context with 5 key metrics"""
        incident_time = incident.timestamp
        window_start = incident_time - timedelta(minutes=15)
        window_end = incident_time + timedelta(minutes=15)
        
        # Get data window (±15 minutes)
        window_data = data[(data.index >= window_start) & (data.index <= window_end)]
        
        # 1. Door Status Analysis
        door_status = self._analyze_door_context(window_data, incident_time)
        
        # 2. External Temperature Analysis  
        external_temp = self._analyze_external_temp_context(window_data, incident_time)
        
        # 3. IT Power Analysis
        it_power = self._analyze_power_context(window_data, incident_time)
        
        # 4. CLIM Status Analysis
        clim_status = self._analyze_clim_context(window_data, incident_time)
        
        # 5. Temperature Trend Analysis
        temp_trend = self._analyze_temp_trend_context(window_data, incident)
        
        return IncidentContext(
            door_status=door_status,
            external_temp=external_temp,
            it_power=it_power,
            clim_status=clim_status,  
            temp_trend=temp_trend
        )
    
    def _analyze_door_context(self, window_data: pd.DataFrame, incident_time: datetime) -> Dict[str, Any]:
        """Analyze door status during 15min window"""
        try:
            door_col = self._get_column_name('door_state')
            if not door_col or door_col not in window_data.columns:
                return {"status": "Données manquantes", "severity": "unknown", "description": "Capteur porte indisponible"}
            
            # Calculate how long door was open during the last 15 minutes
            door_data = window_data[door_col]
            if len(door_data) == 0:
                return {"status": "Données manquantes", "severity": "unknown", "description": "Aucune donnée"}
            
            # Count how many data points show door as open (1=open, 0=closed)
            # Assume each data point represents ~1 minute interval
            open_count = 0
            for val in door_data:
                if pd.notna(val) and (val == 1 or val == '1' or val == 'OPEN' or val == 'Ouvert' or val > 0):
                    open_count += 1
            
            total_minutes = len(door_data)
            open_minutes = open_count
            
            # Determine severity and create description
            if open_minutes == 0:
                severity = "good"
                description = "Fermée durant les dernières 15min"
            elif open_minutes <= 2:
                severity = "good" 
                description = f"Ouverte {open_minutes}min durant les dernières 15min"
            elif open_minutes <= 5:
                severity = "warning"
                description = f"Ouverte {open_minutes}min durant les dernières 15min"
            else:
                severity = "critical"
                description = f"Ouverte {open_minutes}min durant les dernières 15min"
            
            return {
                "status": description,
                "severity": severity,
                "open_minutes": open_minutes,
                "total_minutes": total_minutes
            }
        except Exception as e:
            return {"status": "Erreur analyse", "severity": "unknown", "description": f"Erreur: {str(e)}"}
    
    def _analyze_external_temp_context(self, window_data: pd.DataFrame, incident_time: datetime) -> Dict[str, Any]:
        """Analyze external temperature and trend"""
        try:
            ext_temp_col = self._get_column_name('external_temp')
            if not ext_temp_col or ext_temp_col not in window_data.columns:
                return {"status": "Données manquantes", "severity": "unknown", "description": "Capteur externe indisponible"}
            
            current_temp = window_data[ext_temp_col].iloc[-1] if len(window_data) > 0 else None
            if current_temp is None or pd.isna(current_temp):
                return {"status": "Données manquantes", "severity": "unknown", "description": "Pas de données récentes"}
            
            # Calculate trend (compare first half vs second half of window)
            mid_point = len(window_data) // 2
            if mid_point > 0:
                first_half_avg = window_data[ext_temp_col].iloc[:mid_point].mean()
                second_half_avg = window_data[ext_temp_col].iloc[mid_point:].mean()
                temp_change = second_half_avg - first_half_avg
            else:
                temp_change = 0
            
            # Determine trend
            if temp_change > 1:
                trend = "↗️"
                trend_desc = f"+{temp_change:.1f}°C"
            elif temp_change < -1:
                trend = "↘️"
                trend_desc = f"{temp_change:.1f}°C"
            else:
                trend = "➡️"
                trend_desc = "stable"
            
            # Determine severity based on temperature
            if current_temp > 30:
                severity = "critical"
            elif current_temp > 25:
                severity = "warning"
            else:
                severity = "good"
            
            description = f"{current_temp:.1f}°C ({trend} {trend_desc})"
            
            return {
                "status": description,
                "severity": severity,
                "current_temp": current_temp,
                "trend": trend,
                "change": temp_change
            }
        except Exception as e:
            return {"status": "Erreur analyse", "severity": "unknown", "description": f"Erreur: {str(e)}"}
    
    def _analyze_power_context(self, window_data: pd.DataFrame, incident_time: datetime) -> Dict[str, Any]:
        """Analyze IT power consumption 24h before, during, and after incident"""
        try:
            # Try multiple column names for IT power data (prioritize calculated IT power)
            power_col = None
            power_variations = ['Puissance_IT', 'puissance_it', 'IT_Power', 'Power_IT', 'PUISSANCE_IT']
            
            for col_name in power_variations:
                if col_name in self.data.columns:
                    power_col = col_name
                    break
            
            if not power_col:
                # No fallback to total power - IT power should be properly calculated
                return {"status": "Puissance IT non disponible", "severity": "unknown", "description": "Colonne Puissance_IT manquante - vérifier le préprocesseur"}
            
            # Get IT power data for different time periods
            power_24h_before = self._get_power_stats(incident_time - timedelta(hours=24), incident_time - timedelta(hours=23), power_col)
            power_during = self._get_power_stats(incident_time - timedelta(minutes=30), incident_time + timedelta(minutes=30), power_col)
            power_after = self._get_power_stats(incident_time + timedelta(minutes=30), incident_time + timedelta(hours=1, minutes=30), power_col)
            
            # Format the description with real values
            description_parts = []
            
            # 24h before
            if power_24h_before['mean'] is not None:
                description_parts.append(f"24h avant: {power_24h_before['mean']:.1f}kW")
            else:
                description_parts.append("24h avant: N/A")
            
            # During incident
            if power_during['mean'] is not None:
                description_parts.append(f"Pendant: {power_during['mean']:.1f}kW")
            else:
                description_parts.append("Pendant: N/A")
            
            # After incident
            if power_after['mean'] is not None:
                description_parts.append(f"Après: {power_after['mean']:.1f}kW")
            else:
                description_parts.append("Après: N/A")
            
            # Determine severity based on power changes
            severity = "good"
            anomaly_detected = False
            
            if power_24h_before['mean'] is not None and power_during['mean'] is not None:
                # Check if power during incident is significantly higher than 24h before
                power_increase = power_during['mean'] - power_24h_before['mean']
                if power_increase > 5:  # More than 5kW increase
                    severity = "critical"
                    anomaly_detected = True
                    description_parts.append(f"⚠️ Hausse: +{power_increase:.1f}kW")
                elif power_increase > 2:
                    severity = "warning"
                    anomaly_detected = True
                    description_parts.append(f"↗️ Hausse: +{power_increase:.1f}kW")
            
            # Check if anomaly persists after incident
            if anomaly_detected and power_after['mean'] is not None and power_24h_before['mean'] is not None:
                if power_after['mean'] > power_24h_before['mean'] + 2:
                    description_parts.append("⚠️ Anomalie persistante")
                else:
                    description_parts.append("✓ Retour normal")
            
            description = " | ".join(description_parts)
            
            return {
                "status": description,
                "severity": severity,
                "power_24h_before": power_24h_before,
                "power_during": power_during,
                "power_after": power_after,
                "anomaly_detected": anomaly_detected
            }
        except Exception as e:
            return {"status": "Erreur analyse", "severity": "unknown", "description": f"Erreur: {str(e)}"}
    
    def _get_power_stats(self, start_time: datetime, end_time: datetime, power_col: str) -> Dict[str, float]:
        """Get power statistics for a specific time period"""
        try:
            # Filter data for the time period
            mask = (self.data.index >= start_time) & (self.data.index <= end_time)
            period_data = self.data[mask]
            
            if period_data.empty or power_col not in period_data.columns:
                return {'mean': None, 'min': None, 'max': None, 'std': None}
            
            power_data = period_data[power_col].dropna()
            
            if power_data.empty:
                return {'mean': None, 'min': None, 'max': None, 'std': None}
            
            return {
                'mean': power_data.mean(),
                'min': power_data.min(),
                'max': power_data.max(),
                'std': power_data.std()
            }
        except Exception:
            return {'mean': None, 'min': None, 'max': None, 'std': None}
    
    def _analyze_clim_context(self, window_data: pd.DataFrame, incident_time: datetime) -> Dict[str, Any]:
        """Analyze CLIM status"""
        try:
            # Get CLIM columns from mapping
            clim_cols = self.actual_columns.get('clim_cols', [])
            # Filter to only columns present in current window_data
            clim_cols = [col for col in clim_cols if col in window_data.columns]
            
            if not clim_cols:
                return {"status": "Données manquantes", "severity": "unknown", "description": "Capteurs CLIM indisponibles"}
            
            # Get latest status
            latest_data = window_data.iloc[-1] if len(window_data) > 0 else None
            if latest_data is None:
                return {"status": "Données manquantes", "severity": "unknown", "description": "Pas de données récentes"}
            
            total_clims = len(clim_cols)
            # Debug: check what values we're getting
            clim_values = {col: latest_data[col] for col in clim_cols}
            
            # More flexible active CLIM detection - handle different value formats
            active_clims = 0
            for col in clim_cols:
                val = latest_data[col]
                # Handle different representations of "active"
                if pd.notna(val):
                    # Convert to string and check for ON/OFF status
                    val_str = str(val).upper().strip()
                    # Also handle numeric values
                    try:
                        val_num = float(val)
                        if val_num > 0:
                            active_clims += 1
                            continue
                    except (ValueError, TypeError):
                        pass
                    
                    # Check string representations
                    if val_str in ['ON', '1', 'ACTIVE', 'TRUE']:
                        active_clims += 1
            
            # Determine severity
            if total_clims == 0:
                severity = "unknown"
                description = "Aucun capteur CLIM détecté"
            elif active_clims == total_clims:
                severity = "good"
                description = f"Toutes actives ({active_clims}/{total_clims})"
            elif active_clims >= total_clims * 0.75:
                severity = "good"
                description = f"{active_clims}/{total_clims} actives"
            elif active_clims >= total_clims * 0.5:
                severity = "warning"
                description = f"{active_clims}/{total_clims} actives"
            else:
                severity = "critical"
                description = f"{active_clims}/{total_clims} actives"
                
            # Add debug info for troubleshooting
            if active_clims == 0 and total_clims > 0:
                sample_values = {col: latest_data[col] for col in clim_cols[:2]}  # Show first 2 values
                description += f" (valeurs: {sample_values})"
            
            return {
                "status": description,
                "severity": severity,
                "active_clims": active_clims,
                "total_clims": total_clims
            }
        except Exception as e:
            return {"status": "Erreur analyse", "severity": "unknown", "description": f"Erreur: {str(e)}"}
    
    def _analyze_temp_trend_context(self, window_data: pd.DataFrame, incident: Incident) -> Dict[str, Any]:
        """Analyze temperature trend during incident"""
        try:
            ambient_temp_col = self._get_column_name('ambient_temp')
            if not ambient_temp_col or ambient_temp_col not in window_data.columns:
                return {"status": "Données manquantes", "severity": "unknown", "description": "Capteur température indisponible"}
            
            temp_data = window_data[ambient_temp_col]
            if len(temp_data) < 2:
                return {"status": "Données insuffisantes", "severity": "unknown", "description": "Pas assez de données"}
            
            # Calculate trend over the window
            start_temp = temp_data.iloc[0]
            end_temp = temp_data.iloc[-1]
            temp_change = end_temp - start_temp
            
            # Determine trend type
            if temp_change > 2:
                severity = "critical"
                trend_desc = "Hausse rapide"
            elif temp_change > 0.5:
                severity = "warning"
                trend_desc = "En hausse"
            elif temp_change < -0.5:
                severity = "good"  
                trend_desc = "En baisse"
            else:
                severity = "good"
                trend_desc = "Stable"
            
            return {
                "status": trend_desc,
                "severity": severity,
                "trend": trend_desc,
                "change": temp_change
            }
        except Exception as e:
            return {"status": "Erreur analyse", "severity": "unknown", "description": f"Erreur: {str(e)}"}
        
    def _group_anomalies_to_incidents(self, anomalies: pd.DataFrame, temp_min: float, temp_max: float) -> List[Incident]:
        """
        Group anomalies based on TEMPERATURE STATE CONTINUITY
        One incident = continuous period where temperature stays outside acceptable range
        Incident ends only when temperature returns to acceptable range
        """
        if anomalies.empty:
            return []
        
        incidents = []
        current_group = []
        
        # Sort anomalies by timestamp
        anomalies_sorted = anomalies.sort_index()
        
        for idx, row in anomalies_sorted.iterrows():
            temp = row['T°C AMBIANTE']
            
            # Check if this reading violates the thresholds
            is_outside_range = temp < temp_min or temp > temp_max
            
            if is_outside_range:
                # Temperature is still outside acceptable range - add to current group
                current_group.append((idx, row))
            else:
                # Temperature came back to acceptable range
                if current_group:
                    # Close the current incident cluster
                    incident = self._create_incident_from_group(current_group, temp_min, temp_max)
                    incidents.append(incident)
                    current_group = []
                # Skip this point (it's not an anomaly anymore)
        
        # Don't forget the last group if analysis ends during an anomaly
        if current_group:
            incident = self._create_incident_from_group(current_group, temp_min, temp_max)
            incidents.append(incident)
        
        return incidents
        
    def _create_incident_from_group(self, group: List[Tuple[datetime, pd.Series]], temp_min: float, temp_max: float) -> Incident:
        """Create an Incident object from a group of anomalies"""
        start_time = group[0][0]
        end_time = group[-1][0]
        max_temp = max(row['T°C AMBIANTE'] for _, row in group)
        
        # Determine which threshold was violated
        if max_temp > temp_max:
            threshold_violated = temp_max
            incident_type = IncidentType.TEMPERATURE_HIGH
        else:
            threshold_violated = temp_min
            incident_type = IncidentType.TEMPERATURE_LOW
        
        # Determine severity based on how far from threshold
        temp_deviation = abs(max_temp - threshold_violated)
        if temp_deviation > 3:
            severity = IncidentSeverity.CRITICAL
        elif temp_deviation > 1:
            severity = IncidentSeverity.WARNING
        else:
            severity = IncidentSeverity.INFO
            
        return Incident(
            id=f"INC_{start_time.strftime('%Y%m%d_%H%M')}",
            timestamp=start_time,
            type=incident_type,
            severity=severity,
            metric_name='T°C AMBIANTE',
            metric_value=max_temp,
            threshold_violated=threshold_violated,
            duration_seconds=int((end_time - start_time).total_seconds()),
            description=f"Anomalie température: {max_temp:.1f}°C"
        )
        
    def _rank_causes(self, causes: List[RootCause], quality: DataQualityReport) -> List[RootCause]:
        """Rank causes by confidence with improved data quality adjustments"""
        if not causes:
            return causes
            
        quality_factor = max(0.3, quality.quality_score)  # Minimum 30% factor
        
        for cause in causes:
            # Base data quality adjustment (less aggressive)
            cause.confidence *= (0.7 + 0.3 * quality_factor)  # Range: 70-100% of original
            
            # Penalty for missing sensors (more nuanced)
            if cause.affected_metrics:
                missing_count = sum(1 for m in cause.affected_metrics if m in quality.missing_sensors)
                if missing_count > 0:
                    missing_ratio = missing_count / len(cause.affected_metrics)
                    cause.confidence *= (1 - 0.15 * missing_ratio)  # Up to 15% reduction
                    
            # Add uncertainty indicator for low data quality
            if quality.quality_score < 0.6:
                cause.description += f" (confiance réduite - qualité données: {quality.quality_score*100:.0f}%)"
                
            # Ensure minimum threshold - no cause should be above 90% confidence
            cause.confidence = min(90.0, max(10.0, cause.confidence))
                    
        # Sort by adjusted confidence
        ranked = sorted(causes, key=lambda x: x.confidence, reverse=True)
        
        # Filter out very low confidence causes (< 25%)
        return [c for c in ranked if c.confidence >= 25.0]
        
    def _generate_recommendations(self, cause: RootCause) -> List[str]:
        """Generate actionable recommendations based on root cause"""
        recommendations = []
        
        if cause.cause_type == RootCauseType.CLIM_TOTAL_FAILURE:
            recommendations.append("🔧 Intervention urgente requise sur le système CLIM")
            recommendations.append("📞 Contacter l'équipe de maintenance immédiatement")
            recommendations.append("🌡️ Activer le plan de contingence thermique")
            
        elif cause.cause_type == RootCauseType.CLIM_PARTIAL_FAILURE:
            recommendations.append("🔍 Vérifier les unités CLIM défaillantes")
            recommendations.append("⚡ Contrôler l'alimentation électrique des unités")
            recommendations.append("📅 Planifier une maintenance préventive")
            
        elif cause.cause_type == RootCauseType.DOOR_EXTENDED_OPEN:
            recommendations.append("🚪 Vérifier le système de fermeture automatique")
            recommendations.append("👤 Sensibiliser le personnel aux procédures")
            recommendations.append("📱 Configurer des alertes pour portes ouvertes >5min")
            
        elif cause.cause_type == RootCauseType.EXTERNAL_HEAT_WAVE:
            recommendations.append("❄️ Augmenter la capacité de refroidissement")
            recommendations.append("🌡️ Surveiller les prévisions météo")
            recommendations.append("🔄 Optimiser la circulation d'air")
            
        elif cause.cause_type == RootCauseType.IT_POWER_SURGE:
            recommendations.append("💻 Identifier les équipements à forte charge")
            recommendations.append("⚖️ Équilibrer la distribution de charge")
            recommendations.append("📊 Revoir la planification des tâches intensives")
            
        return recommendations
        
    def _generate_summary(self, results: List[Dict], quality: DataQualityReport) -> Dict[str, Any]:
        """Generate summary statistics for the analysis"""
        if not results:
            return {'total_incidents': 0, 'message': 'Aucune anomalie détectée'}
            
        # Count context severity patterns
        context_patterns = {
            'door_issues': 0,
            'external_heat': 0, 
            'power_issues': 0,
            'clim_issues': 0,
            'multiple_factors': 0
        }
        
        for result in results:
            if result.get('context'):
                context = result['context']
                critical_factors = []
                
                # Check each factor for critical severity
                if context.door_status.get('severity') == 'critical':
                    critical_factors.append('door')
                    context_patterns['door_issues'] += 1
                    
                if context.external_temp.get('severity') == 'critical':
                    critical_factors.append('external_temp')
                    context_patterns['external_heat'] += 1
                    
                if context.it_power.get('severity') in ['critical', 'warning']:
                    critical_factors.append('power')
                    context_patterns['power_issues'] += 1
                    
                if context.clim_status.get('severity') == 'critical':
                    critical_factors.append('clim')
                    context_patterns['clim_issues'] += 1
                
                # Count incidents with multiple critical factors
                if len(critical_factors) > 1:
                    context_patterns['multiple_factors'] += 1
                
        # Calculate statistics
        total_duration = sum(
            inc['incident'].duration_seconds / 60 
            for inc in results 
            if inc['incident'].duration_seconds
        )
        
        # Find most common pattern
        most_common_pattern = max(context_patterns, key=context_patterns.get) if any(context_patterns.values()) else None
        
        return {
            'total_incidents': len(results),
            'total_anomaly_duration_minutes': total_duration,
            'context_patterns': context_patterns,
            'data_quality_score': quality.quality_score,
            'most_common_pattern': most_common_pattern,
            'recommendation': self._generate_context_recommendation(context_patterns)
        }
    
    def _generate_context_recommendation(self, context_patterns: Dict[str, int]) -> str:
        """Generate overall recommendation based on context patterns"""
        if not any(context_patterns.values()):
            return "✅ Surveillance continue recommandée"
        
        # Find the most common issue
        max_count = max(context_patterns.values())
        most_common = [k for k, v in context_patterns.items() if v == max_count][0]
        
        recommendations = {
            'door_issues': "🚪 Vérifier les procédures d'accès et la formation du personnel",
            'external_heat': "🌡️ Surveiller les conditions météo et prévoir des mesures de refroidissement",
            'power_issues': "⚡ Analyser la consommation électrique et équilibrer les charges",
            'clim_issues': "❄️ Maintenance prioritaire du système de climatisation",
            'multiple_factors': "🔧 Analyse approfondie recommandée - facteurs multiples détectés"
        }
        
        return recommendations.get(most_common, "📊 Surveillance et analyse continue recommandée")
        
    def _generate_global_recommendation(self, cause_distribution: Dict[str, int]) -> str:
        """Generate overall recommendation based on cause distribution"""
        if not cause_distribution:
            return "Continuer la surveillance normale"
            
        most_common = max(cause_distribution, key=cause_distribution.get)
        
        if 'clim' in most_common:
            return "🔧 Programme de maintenance CLIM recommandé - défaillances récurrentes détectées"
        elif 'door' in most_common:
            return "🚪 Formation du personnel nécessaire - incidents portes fréquents"
        elif 'external' in most_common:
            return "🌡️ Amélioration de l'isolation thermique recommandée"
        elif 'power' in most_common:
            return "⚡ Audit énergétique recommandé - pics de consommation fréquents"
        else:
            return "📊 Analyse approfondie recommandée - causes multiples"


class CLIMCauseDetector:
    """Detector for CLIM-related root causes with improved reliability"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        """Detect CLIM-related causes with proper data validation"""
        causes = []
        incident = context['incident']
        data_quality = context.get('data_quality')
        
        # Check if we have CLIM data
        clim_cols = ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status']
        available_clim = [col for col in clim_cols if col in data.columns]
        
        if not available_clim:
            return causes
            
        # Validate CLIM sensor data quality first
        clim_data_quality = self._assess_clim_data_quality(data, available_clim)
        if clim_data_quality['reliability'] < 0.3:  # Very poor data quality
            return causes  # Don't make unreliable conclusions
            
        # Get broader context around incident (not just single point)
        incident_window = self._get_incident_window(data, incident.timestamp, window_minutes=30)
        if incident_window.empty:
            return causes
            
        # Analyze CLIM patterns during incident period
        clim_analysis = self._analyze_clim_behavior(incident_window, available_clim)
        
        # Generate causes based on evidence strength
        if clim_analysis['total_failure_evidence'] > 0.7:
            cause = self._create_total_failure_cause(clim_analysis, available_clim, data_quality)
            if cause:
                causes.append(cause)
                
        elif clim_analysis['partial_failure_evidence'] > 0.6:
            cause = self._create_partial_failure_cause(clim_analysis, available_clim, data_quality)
            if cause:
                causes.append(cause)
                
        # Check for CLIM inefficiency with temperature correlation
        inefficiency_cause = self._analyze_clim_inefficiency(incident_window, incident, available_clim)
        if inefficiency_cause:
            causes.append(inefficiency_cause)
                
        return causes
        
    def _assess_clim_data_quality(self, data: pd.DataFrame, clim_cols: List[str]) -> Dict[str, float]:
        """Assess quality and reliability of CLIM sensor data"""
        total_points = len(data)
        if total_points == 0:
            return {'reliability': 0.0, 'completeness': 0.0}
            
        completeness_scores = []
        reliability_scores = []
        
        for col in clim_cols:
            if col not in data.columns:
                completeness_scores.append(0.0)
                reliability_scores.append(0.0)
                continue
                
            # Check data completeness
            non_null_count = data[col].notna().sum()
            completeness = non_null_count / total_points
            completeness_scores.append(completeness)
            
            # Check for stuck sensors (same value for too long)
            if non_null_count > 4:
                value_changes = data[col].diff().abs().sum()
                # If no changes in the data, likely stuck sensor
                reliability = min(1.0, value_changes / 2)  # At least 2 changes expected
                reliability_scores.append(reliability)
            else:
                reliability_scores.append(0.5)  # Insufficient data
                
        return {
            'reliability': np.mean(reliability_scores) if reliability_scores else 0.0,
            'completeness': np.mean(completeness_scores) if completeness_scores else 0.0
        }
        
    def _get_incident_window(self, data: pd.DataFrame, incident_time: datetime, window_minutes: int = 30) -> pd.DataFrame:
        """Get data window around incident for analysis"""
        start_time = incident_time - timedelta(minutes=window_minutes)
        end_time = incident_time + timedelta(minutes=window_minutes//2)  # Less time after
        
        mask = (data.index >= start_time) & (data.index <= end_time)
        return data[mask]
        
    def _analyze_clim_behavior(self, window_data: pd.DataFrame, clim_cols: List[str]) -> Dict[str, Any]:
        """Analyze CLIM behavior patterns during incident window"""
        total_clims = len(clim_cols)
        
        # Calculate active CLIM count over time
        clim_data = window_data[clim_cols].fillna(0)  # Treat NaN as inactive
        active_counts = clim_data.sum(axis=1)
        
        # Evidence for total failure
        zero_readings = (active_counts == 0).sum()
        total_failure_evidence = zero_readings / len(window_data) if len(window_data) > 0 else 0
        
        # Evidence for partial failure  
        partial_readings = (active_counts < total_clims * 0.5).sum()
        partial_failure_evidence = partial_readings / len(window_data) if len(window_data) > 0 else 0
        
        # Check for correlation with power consumption
        power_correlation = 0.0
        if 'P_Active CLIM' in window_data.columns:
            clim_power = window_data['P_Active CLIM'].fillna(0)
            if active_counts.std() > 0 and clim_power.std() > 0:
                power_correlation = abs(active_counts.corr(clim_power))
                
        # Analyze failed units
        failed_units = []
        for col in clim_cols:
            if col in window_data.columns:
                failure_rate = (window_data[col] == 0).mean()
                if failure_rate > 0.7:  # Failed more than 70% of the time
                    failed_units.append(col.replace('_Status', ''))
                    
        return {
            'total_failure_evidence': total_failure_evidence,
            'partial_failure_evidence': partial_failure_evidence,
            'power_correlation': power_correlation,
            'failed_units': failed_units,
            'avg_active_count': active_counts.mean(),
            'min_active_count': active_counts.min(),
            'total_clims': total_clims
        }
        
    def _create_total_failure_cause(self, analysis: Dict, clim_cols: List[str], data_quality) -> Optional[RootCause]:
        """Create total failure cause with evidence-based confidence"""
        evidence_strength = analysis['total_failure_evidence']
        if evidence_strength < 0.7:
            return None
            
        # Calculate confidence based on evidence quality
        base_confidence = min(85.0, evidence_strength * 100)  # Max 85% instead of 95%
        
        # Adjust for power correlation
        if analysis['power_correlation'] > 0.6:
            base_confidence += 10
        elif analysis['power_correlation'] < 0.3:
            base_confidence -= 15  # Reduce confidence if power doesn't match
            
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(30.0, min(90.0, base_confidence))  # Clamp between 30-90%
        
        cause = RootCause(
            cause_type=RootCauseType.CLIM_TOTAL_FAILURE,
            confidence=base_confidence,
            description=f"Défaillance majeure du système CLIM - {len(analysis['failed_units'])}/{analysis['total_clims']} unités affectées",
            affected_metrics=clim_cols,
            severity="critical" if base_confidence > 70 else "high"
        )
        
        # Add evidence
        cause.add_evidence(
            "pattern_analysis",
            f"Aucune activité CLIM détectée pendant {evidence_strength*100:.0f}% de la période d'incident",
            analysis['total_failure_evidence'],
            30.0
        )
        
        if analysis['power_correlation'] > 0.5:
            cause.add_evidence(
                "power_correlation",
                f"Corrélation avec consommation CLIM: {analysis['power_correlation']:.2f}",
                analysis['power_correlation'],
                20.0
            )
            
        return cause
        
    def _create_partial_failure_cause(self, analysis: Dict, clim_cols: List[str], data_quality) -> Optional[RootCause]:
        """Create partial failure cause with evidence-based confidence"""
        evidence_strength = analysis['partial_failure_evidence']
        if evidence_strength < 0.6 or not analysis['failed_units']:
            return None
            
        # Calculate confidence based on evidence
        base_confidence = min(75.0, evidence_strength * 90)  # More conservative
        
        # Adjust for data quality  
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(25.0, min(80.0, base_confidence))
        
        cause = RootCause(
            cause_type=RootCauseType.CLIM_PARTIAL_FAILURE,
            confidence=base_confidence,
            description=f"Capacité CLIM réduite - {len(analysis['failed_units'])} unité(s) défaillante(s): {', '.join(analysis['failed_units'])}",
            affected_metrics=analysis['failed_units'],
            severity="high" if base_confidence > 60 else "medium"
        )
        
        cause.add_evidence(
            "unit_analysis", 
            f"Unités défaillantes identifiées: {', '.join(analysis['failed_units'])}",
            analysis['failed_units'],
            25.0
        )
        
        return cause
        
    def _analyze_clim_inefficiency(self, window_data: pd.DataFrame, incident, clim_cols: List[str]) -> Optional[RootCause]:
        """Analyze CLIM inefficiency with temperature correlation"""
        if 'T°C AMBIANTE' not in window_data.columns or 'P_Active CLIM' not in window_data.columns:
            return None
            
        # Check if CLIMs are running but temperature still rises
        clim_active = window_data[clim_cols].sum(axis=1) > 0
        clim_power = window_data['P_Active CLIM']
        
        if clim_active.sum() < len(window_data) * 0.5:  # Not enough active time
            return None
            
        # Calculate temperature trend when CLIM is active
        active_periods = window_data[clim_active]
        if len(active_periods) < 3:
            return None
            
        temp_trend = np.polyfit(range(len(active_periods)), active_periods['T°C AMBIANTE'], 1)[0]
        
        # If temperature is rising despite CLIM being active
        if temp_trend > 0.1:  # Temperature rising more than 0.1°C per period
            confidence = min(60.0, abs(temp_trend) * 200)  # Scale with trend strength
            
            cause = RootCause(
                cause_type=RootCauseType.CLIM_INEFFICIENCY,
                confidence=confidence,
                description=f"Système CLIM actif mais inefficace - température continue d'augmenter (+{temp_trend:.2f}°C/période)",
                affected_metrics=['P_Active CLIM', 'T°C AMBIANTE'],
                severity="medium"
            )
            
            cause.add_evidence(
                "temperature_trend",
                f"Tendance température: +{temp_trend:.3f}°C/période malgré CLIM active",
                temp_trend,
                30.0
            )
            
            # Check power consumption efficiency
            if clim_power.mean() > 0:
                power_efficiency = temp_trend / clim_power.mean()  # Temperature rise per kW
                cause.add_evidence(
                    "power_efficiency",
                    f"Efficacité énergétique: {power_efficiency:.3f}°C/kW",
                    power_efficiency,
                    15.0
                )
                
            return cause
            
        return None


class EnvironmentalCauseDetector:
    """Detector for environmental/external causes with improved reliability"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        """Detect environmental causes with proper data validation"""
        causes = []
        incident = context['incident']
        data_quality = context.get('data_quality')
        
        if 'T°C EXTERIEURE' not in data.columns:
            return causes
            
        # Get broader context around incident
        window_data = self._get_environmental_context(data, incident.timestamp)
        if window_data.empty:
            return causes
            
        # Analyze external temperature patterns
        ext_analysis = self._analyze_external_temperature(window_data, incident)
        
        # Check for heat wave with correlation analysis
        if ext_analysis['heat_wave_evidence'] > 0.6:
            cause = self._create_heat_wave_cause(ext_analysis, data_quality)
            if cause:
                causes.append(cause)
                
        # Check for general external influence
        elif ext_analysis['influence_evidence'] > 0.4:
            cause = self._create_influence_cause(ext_analysis, data_quality)
            if cause:
                causes.append(cause)
                
        return causes
        
    def _get_environmental_context(self, data: pd.DataFrame, incident_time: datetime) -> pd.DataFrame:
        """Get environmental data context around incident"""
        start_time = incident_time - timedelta(hours=2)  # Look back 2 hours
        end_time = incident_time + timedelta(minutes=30)
        
        mask = (data.index >= start_time) & (data.index <= end_time)
        return data[mask]
        
    def _analyze_external_temperature(self, window_data: pd.DataFrame, incident) -> Dict[str, Any]:
        """Analyze external temperature patterns and correlations"""
        ext_temps = window_data['T°C EXTERIEURE'].dropna()
        if len(ext_temps) == 0:
            return {'heat_wave_evidence': 0, 'influence_evidence': 0}
            
        # Heat wave analysis
        extreme_threshold = 38  # More conservative threshold
        hot_threshold = 32
        
        max_temp = ext_temps.max()
        avg_temp = ext_temps.mean()
        
        # Heat wave evidence
        heat_wave_evidence = 0
        if max_temp > extreme_threshold:
            heat_wave_evidence = min(0.9, (max_temp - extreme_threshold) / 10)  # Scale with extremity
        elif max_temp > hot_threshold:
            heat_wave_evidence = min(0.6, (max_temp - hot_threshold) / 15)
            
        # Correlation analysis
        correlation = 0
        if 'T°C AMBIANTE' in window_data.columns:
            int_temps = window_data['T°C AMBIANTE'].dropna()
            if len(int_temps) > 3 and len(ext_temps) > 3:
                # Align the data
                common_index = int_temps.index.intersection(ext_temps.index)
                if len(common_index) > 3:
                    correlation = int_temps.loc[common_index].corr(ext_temps.loc[common_index])
                    correlation = 0 if pd.isna(correlation) else abs(correlation)
                    
        # External influence evidence
        influence_evidence = 0
        if avg_temp > hot_threshold:
            temp_factor = min(0.6, (avg_temp - hot_threshold) / 10)
            correlation_factor = max(0.2, correlation) if correlation > 0.3 else 0
            influence_evidence = temp_factor * correlation_factor
            
        return {
            'heat_wave_evidence': heat_wave_evidence,
            'influence_evidence': influence_evidence,
            'max_temp': max_temp,
            'avg_temp': avg_temp,
            'correlation': correlation,
            'extreme_duration': (ext_temps > extreme_threshold).sum()
        }
        
    def _create_heat_wave_cause(self, analysis: Dict, data_quality) -> Optional[RootCause]:
        """Create heat wave cause with evidence-based confidence"""
        evidence_strength = analysis['heat_wave_evidence']
        max_temp = analysis['max_temp']
        correlation = analysis['correlation']
        
        # Base confidence from temperature extremity
        base_confidence = min(75.0, evidence_strength * 80)  # More conservative max
        
        # Boost confidence with correlation
        if correlation > 0.6:
            base_confidence += 15
        elif correlation > 0.4:
            base_confidence += 8
        elif correlation < 0.2:
            base_confidence -= 20  # Penalize weak correlation
            
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(25.0, min(80.0, base_confidence))
        
        if base_confidence < 35:  # Don't create weak causes
            return None
            
        cause = RootCause(
            cause_type=RootCauseType.EXTERNAL_HEAT_WAVE,
            confidence=base_confidence,
            description=f"Conditions météorologiques extrêmes - température max: {max_temp:.1f}°C",
            affected_metrics=['T°C EXTERIEURE', 'T°C AMBIANTE'],
            severity="high" if max_temp > 40 else "medium"
        )
        
        cause.add_evidence(
            "temperature_extreme",
            f"Température extérieure maximale: {max_temp:.1f}°C",
            max_temp,
            25.0
        )
        
        if correlation > 0.4:
            cause.add_evidence(
                "internal_correlation",
                f"Corrélation avec température interne: {correlation:.2f}",
                correlation,
                20.0
            )
            
        return cause
        
    def _create_influence_cause(self, analysis: Dict, data_quality) -> Optional[RootCause]:
        """Create general external influence cause"""
        evidence_strength = analysis['influence_evidence']
        avg_temp = analysis['avg_temp']
        correlation = analysis['correlation']
        
        base_confidence = min(60.0, evidence_strength * 100)
        
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(20.0, min(65.0, base_confidence))
        
        if base_confidence < 30:
            return None
            
        cause = RootCause(
            cause_type=RootCauseType.EXTERNAL_TEMP_INFLUENCE,
            confidence=base_confidence,
            description=f"Influence de la température extérieure - moyenne: {avg_temp:.1f}°C",
            affected_metrics=['T°C EXTERIEURE', 'T°C AMBIANTE'],
            severity="medium"
        )
        
        cause.add_evidence(
            "temperature_influence",
            f"Température extérieure élevée: {avg_temp:.1f}°C (corrélation: {correlation:.2f})",
            {'avg_temp': avg_temp, 'correlation': correlation},
            20.0
        )
        
        return cause


class DoorCauseDetector:
    """Detector for door-related causes with improved analysis"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        """Detect door-related causes with better validation"""
        causes = []
        incident = context['incident']
        data_quality = context.get('data_quality')
        
        if 'Etat de porte' not in data.columns:
            return causes
            
        # Get broader context for door analysis
        door_window = self._get_door_context(data, incident.timestamp)
        if door_window.empty:
            return causes
            
        # Analyze door patterns
        door_analysis = self._analyze_door_patterns(door_window, incident)
        
        # Check for extended opening
        if door_analysis['extended_open_evidence'] > 0.5:
            cause = self._create_extended_open_cause(door_analysis, data_quality)
            if cause:
                causes.append(cause)
                
        # Check for frequent cycles
        if door_analysis['frequent_cycles_evidence'] > 0.4:
            cause = self._create_frequent_cycles_cause(door_analysis, data_quality)
            if cause:
                causes.append(cause)
                
        return causes
        
    def _get_door_context(self, data: pd.DataFrame, incident_time: datetime) -> pd.DataFrame:
        """Get door data context around incident"""
        start_time = incident_time - timedelta(hours=1)  # Look back 1 hour
        end_time = incident_time + timedelta(minutes=15)
        
        mask = (data.index >= start_time) & (data.index <= end_time)
        return data[mask]
        
    def _analyze_door_patterns(self, window_data: pd.DataFrame, incident) -> Dict[str, Any]:
        """Analyze door opening patterns and their impact"""
        door_states = window_data['Etat de porte'].fillna(0)
        
        # Extended opening analysis
        consecutive_open = self._find_consecutive_periods(door_states, 1)
        max_open_duration = max([end - start for start, end in consecutive_open]) if consecutive_open else 0
        total_open_time = sum([end - start for start, end in consecutive_open])
        
        # Convert to minutes (assuming 15-minute intervals)
        max_open_minutes = max_open_duration * 15
        total_open_minutes = total_open_time * 15
        
        # Evidence for extended opening
        extended_open_evidence = 0
        if max_open_minutes > 45:  # More than 45 minutes
            extended_open_evidence = min(0.9, max_open_minutes / 120)  # Scale up to 2 hours
        elif max_open_minutes > 20:
            extended_open_evidence = min(0.6, max_open_minutes / 60)
            
        # Frequent cycles analysis
        door_changes = door_states.diff().abs().sum()
        cycles_count = int(door_changes / 2) if door_changes > 0 else 0
        
        frequent_cycles_evidence = 0
        if cycles_count > 6:  # More than 6 cycles in the window
            frequent_cycles_evidence = min(0.8, cycles_count / 10)
        elif cycles_count > 3:
            frequent_cycles_evidence = min(0.5, cycles_count / 8)
            
        # Temperature impact analysis
        temp_impact = self._calculate_temperature_impact(window_data, consecutive_open)
        
        return {
            'extended_open_evidence': extended_open_evidence,
            'frequent_cycles_evidence': frequent_cycles_evidence,
            'max_open_minutes': max_open_minutes,
            'total_open_minutes': total_open_minutes,
            'cycles_count': cycles_count,
            'temp_impact': temp_impact,
            'open_periods': consecutive_open
        }
        
    def _find_consecutive_periods(self, states: pd.Series, target_state: int) -> List[Tuple[int, int]]:
        """Find consecutive periods of a specific state"""
        periods = []
        start = None
        
        for i, state in enumerate(states):
            if state == target_state and start is None:
                start = i
            elif state != target_state and start is not None:
                periods.append((start, i))
                start = None
                
        # Handle case where period continues to end
        if start is not None:
            periods.append((start, len(states)))
            
        return periods
        
    def _calculate_temperature_impact(self, window_data: pd.DataFrame, open_periods: List[Tuple[int, int]]) -> Dict[str, float]:
        """Calculate temperature impact during door open periods"""
        if 'T°C AMBIANTE' not in window_data.columns or not open_periods:
            return {'impact': 0, 'correlation': 0}
            
        temp_data = window_data['T°C AMBIANTE']
        max_impact = 0
        correlations = []
        
        for start_idx, end_idx in open_periods:
            if end_idx - start_idx < 2:  # Period too short
                continue
                
            # Get temperature before, during, and after
            if start_idx > 0 and end_idx < len(temp_data):
                temp_before = temp_data.iloc[start_idx - 1] if start_idx > 0 else temp_data.iloc[start_idx]
                temp_during = temp_data.iloc[start_idx:end_idx]
                temp_after = temp_data.iloc[end_idx] if end_idx < len(temp_data) else temp_during.iloc[-1]
                
                if len(temp_during) > 0:
                    temp_rise = temp_during.max() - temp_before
                    max_impact = max(max_impact, temp_rise)
                    
                    # Calculate correlation with external temp if available
                    if 'T°C EXTERIEURE' in window_data.columns:
                        ext_temp_during = window_data['T°C EXTERIEURE'].iloc[start_idx:end_idx]
                        if len(ext_temp_during) > 1 and temp_during.std() > 0:
                            corr = temp_during.corr(ext_temp_during)
                            if not pd.isna(corr):
                                correlations.append(abs(corr))
                                
        avg_correlation = np.mean(correlations) if correlations else 0
        
        return {
            'impact': max_impact,
            'correlation': avg_correlation
        }
        
    def _create_extended_open_cause(self, analysis: Dict, data_quality) -> Optional[RootCause]:
        """Create extended door open cause"""
        evidence_strength = analysis['extended_open_evidence']
        duration = analysis['max_open_minutes']
        temp_impact = analysis['temp_impact']['impact']
        
        # Base confidence from duration
        base_confidence = min(70.0, evidence_strength * 75)
        
        # Boost with temperature impact
        if temp_impact > 1.0:
            base_confidence += 15
        elif temp_impact > 0.5:
            base_confidence += 8
            
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(25.0, min(75.0, base_confidence))
        
        if base_confidence < 35:
            return None
            
        cause = RootCause(
            cause_type=RootCauseType.DOOR_EXTENDED_OPEN,
            confidence=base_confidence,
            description=f"Porte ouverte de façon prolongée - durée max: {duration:.0f} minutes",
            affected_metrics=['Etat de porte', 'T°C AMBIANTE'],
            severity="high" if duration > 60 else "medium",
            duration_minutes=int(duration)
        )
        
        cause.add_evidence(
            "duration_analysis",
            f"Ouverture prolongée détectée: {duration:.0f} minutes",
            duration,
            25.0
        )
        
        if temp_impact > 0.3:
            cause.add_evidence(
                "temperature_impact",
                f"Impact thermique mesuré: +{temp_impact:.1f}°C",
                temp_impact,
                20.0
            )
            
        return cause
        
    def _create_frequent_cycles_cause(self, analysis: Dict, data_quality) -> Optional[RootCause]:
        """Create frequent door cycles cause"""
        evidence_strength = analysis['frequent_cycles_evidence']
        cycles = analysis['cycles_count']
        
        base_confidence = min(50.0, evidence_strength * 60)  # More conservative
        
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(20.0, min(55.0, base_confidence))
        
        if base_confidence < 30:
            return None
            
        cause = RootCause(
            cause_type=RootCauseType.DOOR_FREQUENT_CYCLES,
            confidence=base_confidence,
            description=f"Cycles fréquents d'ouverture/fermeture - {cycles} cycles détectés",
            affected_metrics=['Etat de porte'],
            severity="low"
        )
        
        cause.add_evidence(
            "cycle_analysis",
            f"Activité de porte élevée: {cycles} cycles d'ouverture/fermeture",
            cycles,
            20.0
        )
        
        return cause


class PowerCauseDetector:
    """Detector for power-related causes with improved analysis"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        """Detect power-related causes with better validation"""
        causes = []
        incident = context['incident']
        data_quality = context.get('data_quality')
        
        # Get IT power column - should be Puissance_IT after preprocessing
        power_col = None
        for col_name in ['Puissance_IT', 'puissance_it', 'IT_Power', 'Power_IT', 'PUISSANCE_IT']:
            if col_name in data.columns:
                power_col = col_name
                break
        
        if not power_col:
            return causes
            
        # Get power context around incident
        power_window = self._get_power_context(data, incident.timestamp)
        if power_window.empty or len(power_window) < 3:
            return causes
            
        # Analyze power patterns
        power_analysis = self._analyze_power_patterns(power_window, incident)
        
        # Check for power surge
        if power_analysis['surge_evidence'] > 0.5:
            cause = self._create_power_surge_cause(power_analysis, data_quality)
            if cause:
                causes.append(cause)
                
        # Check for sustained high power
        if power_analysis['high_power_evidence'] > 0.4:
            cause = self._create_high_power_cause(power_analysis, data_quality)
            if cause:
                causes.append(cause)
                
        # Check for PUE degradation
        if power_analysis['pue_degradation_evidence'] > 0.4:
            cause = self._create_pue_degradation_cause(power_analysis, data_quality)
            if cause:
                causes.append(cause)
                
        return causes
        
    def _get_power_context(self, data: pd.DataFrame, incident_time: datetime) -> pd.DataFrame:
        """Get power data context around incident"""
        start_time = incident_time - timedelta(hours=2)
        end_time = incident_time + timedelta(minutes=30)
        
        mask = (data.index >= start_time) & (data.index <= end_time)
        return data[mask]
        
    def _analyze_power_patterns(self, window_data: pd.DataFrame, incident) -> Dict[str, Any]:
        """Analyze power consumption patterns"""
        # Get power column using column mapping
        power_col = None
        for col in window_data.columns:
            if any(keyword in col.lower() for keyword in ['puissance', 'p_active']):
                power_col = col
                break
        
        if not power_col:
            return {'surge_evidence': 0, 'high_power_evidence': 0, 'pue_degradation_evidence': 0}
        
        power_data = window_data[power_col].dropna()
        if len(power_data) == 0:
            return {'surge_evidence': 0, 'high_power_evidence': 0, 'pue_degradation_evidence': 0}
            
        # Calculate power statistics
        mean_power = power_data.mean()
        max_power = power_data.max()
        std_power = power_data.std()
        
        # Establish baseline from historical data (if available)
        baseline_power = self._calculate_baseline_power(window_data)
        
        # Power surge analysis
        surge_evidence = 0
        max_change = 0
        if len(power_data) > 1:
            power_changes = power_data.diff().abs()
            max_change = power_changes.max()
            
            # More conservative thresholds
            if max_change > 4:  # 4kW sudden change
                surge_evidence = min(0.8, max_change / 8)  # Scale with change magnitude
            elif max_change > 2:
                surge_evidence = min(0.5, max_change / 6)
                
        # High power evidence
        high_power_evidence = 0
        if baseline_power > 0:
            power_ratio = mean_power / baseline_power
            if power_ratio > 1.3:  # 30% above baseline
                high_power_evidence = min(0.8, (power_ratio - 1.3) / 0.4)
        elif mean_power > 13:  # Fallback absolute threshold
            high_power_evidence = min(0.6, (mean_power - 13) / 5)
            
        # PUE degradation analysis
        pue_evidence = 0
        avg_pue = None
        if 'PUE' in window_data.columns:
            pue_data = window_data['PUE'].dropna()
            if len(pue_data) > 0:
                avg_pue = pue_data.mean()
                if avg_pue > 2.2:  # More conservative threshold
                    pue_evidence = min(0.8, (avg_pue - 2.2) / 0.8)
                elif avg_pue > 1.8:
                    pue_evidence = min(0.5, (avg_pue - 1.8) / 0.6)
                    
        # Temperature correlation analysis
        temp_correlation = self._analyze_power_temperature_correlation(window_data)
        
        return {
            'surge_evidence': surge_evidence,
            'high_power_evidence': high_power_evidence,
            'pue_degradation_evidence': pue_evidence,
            'max_change': max_change,
            'mean_power': mean_power,
            'max_power': max_power,
            'baseline_power': baseline_power,
            'avg_pue': avg_pue,
            'temp_correlation': temp_correlation
        }
        
    def _calculate_baseline_power(self, window_data: pd.DataFrame) -> float:
        """Calculate baseline power consumption"""
        # Use the first quarter of the window as baseline (before incident)
        baseline_length = len(window_data) // 4
        if baseline_length < 2:
            return 0
        
        # Get power column dynamically
        power_col = None
        for col in window_data.columns:
            if any(keyword in col.lower() for keyword in ['puissance', 'p_active']):
                power_col = col
                break
        
        if not power_col:
            return 0
            
        baseline_data = window_data[power_col].head(baseline_length).dropna()
        return baseline_data.mean() if len(baseline_data) > 0 else 0
        
    def _analyze_power_temperature_correlation(self, window_data: pd.DataFrame) -> float:
        """Analyze correlation between power and temperature"""
        if 'T°C AMBIANTE' not in window_data.columns:
            return 0
        
        # Get power column dynamically
        power_col = None
        for col in window_data.columns:
            if any(keyword in col.lower() for keyword in ['puissance', 'p_active']):
                power_col = col
                break
        
        if not power_col:
            return 0
            
        power_data = window_data[power_col].dropna()
        temp_data = window_data['T°C AMBIANTE'].dropna()
        
        if len(power_data) < 3 or len(temp_data) < 3:
            return 0
            
        # Align data on common index
        common_index = power_data.index.intersection(temp_data.index)
        if len(common_index) < 3:
            return 0
            
        aligned_power = power_data.loc[common_index]
        aligned_temp = temp_data.loc[common_index]
        
        correlation = aligned_power.corr(aligned_temp)
        return 0 if pd.isna(correlation) else abs(correlation)
        
    def _create_power_surge_cause(self, analysis: Dict, data_quality) -> Optional[RootCause]:
        """Create power surge cause"""
        evidence_strength = analysis['surge_evidence']
        max_change = analysis['max_change']
        temp_correlation = analysis['temp_correlation']
        
        base_confidence = min(65.0, evidence_strength * 70)  # More conservative
        
        # Boost confidence with temperature correlation
        if temp_correlation > 0.5:
            base_confidence += 10
        elif temp_correlation < 0.2:
            base_confidence -= 15  # Reduce if no temperature impact
            
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(25.0, min(70.0, base_confidence))
        
        if base_confidence < 35:
            return None
            
        cause = RootCause(
            cause_type=RootCauseType.IT_POWER_SURGE,
            confidence=base_confidence,
            description=f"Pic de consommation IT détecté - variation max: {max_change:.1f}kW",
            affected_metrics=['Puissance_IT', 'T°C AMBIANTE'],
            severity="medium"
        )
        
        cause.add_evidence(
            "power_variation",
            f"Variation brutale de puissance: {max_change:.1f}kW",
            max_change,
            25.0
        )
        
        if temp_correlation > 0.3:
            cause.add_evidence(
                "temperature_correlation",
                f"Corrélation avec température: {temp_correlation:.2f}",
                temp_correlation,
                15.0
            )
            
        return cause
        
    def _create_high_power_cause(self, analysis: Dict, data_quality) -> Optional[RootCause]:
        """Create sustained high power cause"""
        evidence_strength = analysis['high_power_evidence']
        mean_power = analysis['mean_power']
        baseline_power = analysis['baseline_power']
        
        base_confidence = min(60.0, evidence_strength * 65)
        
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(20.0, min(65.0, base_confidence))
        
        if base_confidence < 30:
            return None
            
        description = f"Consommation IT élevée soutenue - moyenne: {mean_power:.1f}kW"
        if baseline_power > 0:
            increase_pct = ((mean_power - baseline_power) / baseline_power) * 100
            description += f" (+{increase_pct:.0f}% vs baseline)"
            
        cause = RootCause(
            cause_type=RootCauseType.IT_POWER_HIGH_SUSTAINED,
            confidence=base_confidence,
            description=description,
            affected_metrics=['Puissance_IT', 'PUE'],
            severity="medium"
        )
        
        cause.add_evidence(
            "sustained_consumption",
            f"Puissance IT moyenne élevée: {mean_power:.1f}kW",
            mean_power,
            20.0
        )
        
        return cause
        
    def _create_pue_degradation_cause(self, analysis: Dict, data_quality) -> Optional[RootCause]:
        """Create PUE degradation cause"""
        evidence_strength = analysis['pue_degradation_evidence']
        avg_pue = analysis['avg_pue']
        
        if not avg_pue:
            return None
            
        base_confidence = min(65.0, evidence_strength * 70)
        
        # Adjust for data quality
        if data_quality and data_quality.quality_score < 0.8:
            base_confidence *= data_quality.quality_score
            
        base_confidence = max(25.0, min(70.0, base_confidence))
        
        if base_confidence < 30:
            return None
            
        cause = RootCause(
            cause_type=RootCauseType.PUE_DEGRADATION,
            confidence=base_confidence,
            description=f"Efficacité énergétique dégradée - PUE moyen: {avg_pue:.2f}",
            affected_metrics=['PUE', 'P_Active CLIM', 'Puissance_IT'],
            severity="medium"
        )
        
        cause.add_evidence(
            "pue_analysis",
            f"PUE dégradé: {avg_pue:.2f} (optimal < 1.8)",
            avg_pue,
            25.0
        )
        
        return cause