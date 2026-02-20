"""
Incident Detection Engine for Incident Lens
Real-time monitoring and incident detection based on configurable thresholds
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import uuid

try:
    from ..config.settings import (
        DOOR_CYCLE_MIN_DURATION,
        CORRELATION_THRESHOLD_STRONG
    )
except ImportError:
    # For standalone testing - use constants directly
    DOOR_CYCLE_MIN_DURATION = 300
    CORRELATION_THRESHOLD_STRONG = 0.7


class IncidentSeverity(Enum):
    """Incident severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class IncidentType(Enum):
    """Types of incidents that can be detected"""
    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    POWER_ANOMALY = "power_anomaly"
    PUE_HIGH = "pue_high"
    PUE_CRITICAL = "pue_critical"
    CLIM_FAILURE = "clim_failure"
    CLIM_DEGRADED = "clim_degraded"
    DOOR_ANOMALY = "door_anomaly"
    DOOR_EXTENDED_OPEN = "door_extended_open"
    IT_POWER_HIGH = "it_power_high"
    IT_POWER_LOW = "it_power_low"
    COOLING_INEFFICIENCY = "cooling_inefficiency"


@dataclass
class Incident:
    """Data model for an incident"""
    id: str
    timestamp: datetime
    type: IncidentType
    severity: IncidentSeverity
    metric_name: str
    metric_value: float
    threshold_violated: float
    duration_seconds: Optional[int] = None
    affected_systems: List[str] = None
    description: str = ""
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.affected_systems is None:
            self.affected_systems = []
        if self.context is None:
            self.context = {}


class IncidentDetector:
    """Real-time incident detection engine"""
    
    def __init__(self, data: pd.DataFrame):
        self.data = data.copy()
        self.data = self.data.sort_index()  # Ensure chronological order
        self.incidents: List[Incident] = []
        self.thresholds = self._initialize_thresholds()
        
    def _initialize_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Initialize detection thresholds with dynamic adjustments"""
        # Base thresholds
        base_thresholds = {
            'T°C AMBIANTE': {
                'critical_high': 26.0,
                'warning_high': 24.0,
                'optimal_range': (20.0, 23.0),
                'warning_low': 18.0,
                'critical_low': 16.0
            },
            'T°C EXTERIEURE': {
                'extreme_high': 40.0,
                'high': 35.0,
                'extreme_low': -5.0
            },
            'PUE': {
                'critical_high': 2.2,
                'warning_high': 1.8,
                'optimal_max': 1.5,
                'theoretical_min': 1.0
            },
            'Puissance_IT': {
                'critical_high': 14.0,
                'warning_high': 12.0,
                'normal_range': (8.0, 12.0),
                'warning_low': 8.0,
                'critical_low': 6.0
            },
            'P_Active CLIM': {
                'critical_high': 10.0,
                'warning_high': 8.0,
                'efficiency_threshold': 0.4  # CLIM/IT ratio
            },
            'door_open_duration': {
                'warning': 300,  # 5 minutes
                'critical': 600,  # 10 minutes
                'emergency': 900  # 15 minutes
            },
            'clim_efficiency': {
                'poor': 0.5,  # CLIM using 50% of total power
                'warning': 0.4,
                'good': 0.3
            }
        }
        
        # Adjust thresholds based on historical data if available
        if len(self.data) > 168:  # At least 1 week of hourly data
            for metric in ['T°C AMBIANTE', 'Puissance_IT', 'PUE']:
                if metric in self.data.columns:
                    # Calculate percentiles for dynamic thresholds
                    p95 = self.data[metric].quantile(0.95)
                    p99 = self.data[metric].quantile(0.99)
                    p5 = self.data[metric].quantile(0.05)
                    p1 = self.data[metric].quantile(0.01)
                    
                    # Update thresholds based on historical patterns
                    if metric in base_thresholds:
                        base_thresholds[metric]['statistical_warning_high'] = p95
                        base_thresholds[metric]['statistical_critical_high'] = p99
                        base_thresholds[metric]['statistical_warning_low'] = p5
                        base_thresholds[metric]['statistical_critical_low'] = p1
        
        return base_thresholds
    
    def detect_incidents(self, 
                        time_window: Optional[pd.Timestamp] = None,
                        real_time: bool = False) -> List[Incident]:
        """
        Detect all incidents in the data or specific time window
        
        Args:
            time_window: Start time for detection (detects from this time to now)
            real_time: If True, only check the latest data point
            
        Returns:
            List of detected incidents
        """
        if real_time:
            # Only check the most recent data point
            data_subset = self.data.tail(1)
        elif time_window:
            data_subset = self.data[self.data.index >= time_window]
        else:
            data_subset = self.data
            
        if data_subset.empty:
            return []
            
        incidents = []
        
        # Temperature incidents
        incidents.extend(self._detect_temperature_incidents(data_subset))
        
        # PUE incidents
        incidents.extend(self._detect_pue_incidents(data_subset))
        
        # Power incidents
        incidents.extend(self._detect_power_incidents(data_subset))
        
        # Door incidents
        incidents.extend(self._detect_door_incidents(data_subset))
        
        # CLIM failures and inefficiencies
        incidents.extend(self._detect_clim_incidents(data_subset))
        
        # Composite incidents (multiple factors)
        incidents.extend(self._detect_composite_incidents(data_subset))
        
        # Sort by timestamp and severity
        incidents.sort(key=lambda x: (x.timestamp, x.severity.value), reverse=True)
        
        # Store incidents
        self.incidents.extend(incidents)
        
        return incidents
    
    def _detect_temperature_incidents(self, data: pd.DataFrame) -> List[Incident]:
        """Detect temperature-related incidents"""
        incidents = []
        
        if 'T°C AMBIANTE' not in data.columns:
            return incidents
            
        thresholds = self.thresholds['T°C AMBIANTE']
        
        for idx, row in data.iterrows():
            temp = row['T°C AMBIANTE']
            
            # Critical high temperature
            if temp >= thresholds['critical_high']:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.TEMPERATURE_HIGH,
                    severity=IncidentSeverity.CRITICAL,
                    metric_name='T°C AMBIANTE',
                    metric_value=temp,
                    threshold_violated=thresholds['critical_high'],
                    affected_systems=['COOLING', 'IT_EQUIPMENT'],
                    description=f"Température ambiante critique: {temp:.1f}°C (seuil: {thresholds['critical_high']}°C)",
                    context={
                        'external_temp': row.get('T°C EXTERIEURE', None),
                        'clim_power': row.get('P_Active CLIM', None),
                        'pue': row.get('PUE', None)
                    }
                ))
            
            # Warning high temperature
            elif temp >= thresholds['warning_high']:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.TEMPERATURE_HIGH,
                    severity=IncidentSeverity.WARNING,
                    metric_name='T°C AMBIANTE',
                    metric_value=temp,
                    threshold_violated=thresholds['warning_high'],
                    affected_systems=['COOLING'],
                    description=f"Température ambiante élevée: {temp:.1f}°C (seuil: {thresholds['warning_high']}°C)"
                ))
            
            # Critical low temperature (less common but possible)
            elif temp <= thresholds['critical_low']:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.TEMPERATURE_LOW,
                    severity=IncidentSeverity.WARNING,
                    metric_name='T°C AMBIANTE',
                    metric_value=temp,
                    threshold_violated=thresholds['critical_low'],
                    affected_systems=['COOLING'],
                    description=f"Température ambiante trop basse: {temp:.1f}°C (seuil: {thresholds['critical_low']}°C)"
                ))
        
        return incidents
    
    def _detect_pue_incidents(self, data: pd.DataFrame) -> List[Incident]:
        """Detect PUE (Power Usage Effectiveness) incidents"""
        incidents = []
        
        if 'PUE' not in data.columns:
            return incidents
            
        thresholds = self.thresholds['PUE']
        
        for idx, row in data.iterrows():
            pue = row['PUE']
            
            if pd.isna(pue) or pue < thresholds['theoretical_min']:
                continue
                
            # Critical PUE
            if pue >= thresholds['critical_high']:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.PUE_CRITICAL,
                    severity=IncidentSeverity.CRITICAL,
                    metric_name='PUE',
                    metric_value=pue,
                    threshold_violated=thresholds['critical_high'],
                    affected_systems=['COOLING', 'POWER_DISTRIBUTION'],
                    description=f"PUE critique: {pue:.2f} (seuil: {thresholds['critical_high']})",
                    context={
                        'it_power': row.get('Puissance_IT', None),
                        'total_power': row.get('P_Active Générale', None),
                        'clim_power': row.get('P_Active CLIM', None),
                        'efficiency_loss': (pue - thresholds['optimal_max']) * row.get('Puissance_IT', 0)
                    }
                ))
            
            # Warning PUE
            elif pue >= thresholds['warning_high']:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.PUE_HIGH,
                    severity=IncidentSeverity.WARNING,
                    metric_name='PUE',
                    metric_value=pue,
                    threshold_violated=thresholds['warning_high'],
                    affected_systems=['COOLING', 'POWER_DISTRIBUTION'],
                    description=f"PUE élevé: {pue:.2f} (seuil: {thresholds['warning_high']})"
                ))
        
        return incidents
    
    def _detect_door_incidents(self, data: pd.DataFrame) -> List[Incident]:
        """Detect door-related incidents"""
        incidents = []
        
        if 'Etat de porte' not in data.columns:
            return incidents
            
        thresholds = self.thresholds['door_open_duration']
        
        # Find continuous door open periods
        door_open = data['Etat de porte'] == 1
        
        # Group consecutive open states
        door_changes = door_open.ne(door_open.shift())
        door_groups = door_changes.cumsum()
        
        # Analyze each group
        for group_id, group_data in data[door_open].groupby(door_groups[door_open]):
            if len(group_data) == 0:
                continue
                
            duration_minutes = len(group_data) * 15  # 15-minute intervals
            start_time = group_data.index[0]
            end_time = group_data.index[-1]
            
            # Determine severity based on duration
            if duration_minutes >= thresholds['emergency']:
                severity = IncidentSeverity.EMERGENCY
                incident_type = IncidentType.DOOR_EXTENDED_OPEN
            elif duration_minutes >= thresholds['critical']:
                severity = IncidentSeverity.CRITICAL
                incident_type = IncidentType.DOOR_EXTENDED_OPEN
            elif duration_minutes >= thresholds['warning']:
                severity = IncidentSeverity.WARNING
                incident_type = IncidentType.DOOR_ANOMALY
            else:
                continue  # Duration too short to be an incident
            
            # Calculate temperature impact during door open period
            temp_impact = None
            if 'T°C AMBIANTE' in data.columns:
                temp_during = data.loc[start_time:end_time, 'T°C AMBIANTE']
                temp_before = data.loc[:start_time, 'T°C AMBIANTE'].tail(4).mean()  # 1 hour before
                if not pd.isna(temp_before) and len(temp_during) > 0:
                    temp_impact = temp_during.max() - temp_before
            
            incidents.append(Incident(
                id=str(uuid.uuid4()),
                timestamp=start_time,
                type=incident_type,
                severity=severity,
                metric_name='Etat de porte',
                metric_value=duration_minutes,
                threshold_violated=thresholds[
                    'emergency' if severity == IncidentSeverity.EMERGENCY 
                    else 'critical' if severity == IncidentSeverity.CRITICAL 
                    else 'warning'
                ],
                duration_seconds=duration_minutes * 60,
                affected_systems=['COOLING', 'SECURITY'],
                description=f"Porte restée ouverte pendant {duration_minutes} minutes",
                context={
                    'start_time': start_time,
                    'end_time': end_time,
                    'temperature_impact': temp_impact,
                    'external_temp_avg': data.loc[start_time:end_time, 'T°C EXTERIEURE'].mean() 
                        if 'T°C EXTERIEURE' in data.columns else None
                }
            ))
        
        return incidents
    
    def _detect_clim_incidents(self, data: pd.DataFrame) -> List[Incident]:
        """Detect CLIM system failures and inefficiencies"""
        incidents = []
        
        clim_columns = ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status']
        available_clim = [col for col in clim_columns if col in data.columns]
        
        if not available_clim:
            return incidents
        
        for idx, row in data.iterrows():
            # Count active CLIM units
            active_clims = sum(row[col] == 1 for col in available_clim if not pd.isna(row[col]))
            total_clims = len(available_clim)
            
            # Check for CLIM failures
            if active_clims == 0:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.CLIM_FAILURE,
                    severity=IncidentSeverity.EMERGENCY,
                    metric_name='CLIM System',
                    metric_value=0,
                    threshold_violated=1,  # At least 1 CLIM should be active
                    affected_systems=['COOLING', 'ALL_CLIM_UNITS'],
                    description="Panne totale du système CLIM - Aucune unité active",
                    context={
                        'failed_units': available_clim,
                        'temperature': row.get('T°C AMBIANTE', None)
                    }
                ))
            
            elif active_clims < total_clims / 2:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.CLIM_DEGRADED,
                    severity=IncidentSeverity.WARNING,
                    metric_name='CLIM System',
                    metric_value=active_clims,
                    threshold_violated=total_clims / 2,
                    affected_systems=['COOLING'] + [col.replace('_Status', '') 
                                                   for col in available_clim 
                                                   if row[col] == 0],
                    description=f"Système CLIM dégradé - Seulement {active_clims}/{total_clims} unités actives"
                ))
            
            # Check CLIM efficiency
            if 'P_Active CLIM' in row and 'P_Active Générale' in row:
                clim_ratio = row['P_Active CLIM'] / row['P_Active Générale'] if row['P_Active Générale'] > 0 else 0
                
                if clim_ratio > self.thresholds['clim_efficiency']['poor']:
                    incidents.append(Incident(
                        id=str(uuid.uuid4()),
                        timestamp=idx,
                        type=IncidentType.COOLING_INEFFICIENCY,
                        severity=IncidentSeverity.WARNING,
                        metric_name='CLIM Efficiency',
                        metric_value=clim_ratio * 100,
                        threshold_violated=self.thresholds['clim_efficiency']['poor'] * 100,
                        affected_systems=['COOLING'],
                        description=f"Efficacité CLIM faible - {clim_ratio*100:.1f}% de la puissance totale",
                        context={
                            'clim_power': row['P_Active CLIM'],
                            'total_power': row['P_Active Générale'],
                            'active_clims': active_clims
                        }
                    ))
        
        return incidents
    
    def _detect_power_incidents(self, data: pd.DataFrame) -> List[Incident]:
        """Detect power-related incidents"""
        incidents = []
        
        if 'Puissance_IT' not in data.columns:
            return incidents
            
        thresholds = self.thresholds['Puissance_IT']
        
        for idx, row in data.iterrows():
            it_power = row['Puissance_IT']
            
            if pd.isna(it_power):
                continue
            
            # IT power too high
            if it_power >= thresholds['critical_high']:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.IT_POWER_HIGH,
                    severity=IncidentSeverity.CRITICAL,
                    metric_name='Puissance_IT',
                    metric_value=it_power,
                    threshold_violated=thresholds['critical_high'],
                    affected_systems=['IT_EQUIPMENT', 'POWER_DISTRIBUTION'],
                    description=f"Puissance IT critique: {it_power:.1f}kW (seuil: {thresholds['critical_high']}kW)",
                    context={
                        'total_power': row.get('P_Active Générale', None),
                        'pue': row.get('PUE', None)
                    }
                ))
            
            # IT power too low (potential equipment failure)
            elif it_power <= thresholds['critical_low']:
                incidents.append(Incident(
                    id=str(uuid.uuid4()),
                    timestamp=idx,
                    type=IncidentType.IT_POWER_LOW,
                    severity=IncidentSeverity.WARNING,
                    metric_name='Puissance_IT',
                    metric_value=it_power,
                    threshold_violated=thresholds['critical_low'],
                    affected_systems=['IT_EQUIPMENT'],
                    description=f"Puissance IT anormalement basse: {it_power:.1f}kW (seuil: {thresholds['critical_low']}kW)"
                ))
            
            # Check for sudden power changes
            if len(data) > 1 and idx != data.index[0]:
                prev_idx = data.index[data.index.get_loc(idx) - 1]
                prev_power = data.loc[prev_idx, 'Puissance_IT']
                
                if not pd.isna(prev_power):
                    power_change = abs(it_power - prev_power)
                    power_change_pct = power_change / prev_power * 100 if prev_power > 0 else 0
                    
                    # Sudden power spike or drop (>20% change)
                    if power_change_pct > 20 and power_change > 2:  # At least 2kW change
                        incidents.append(Incident(
                            id=str(uuid.uuid4()),
                            timestamp=idx,
                            type=IncidentType.POWER_ANOMALY,
                            severity=IncidentSeverity.WARNING,
                            metric_name='Puissance_IT',
                            metric_value=it_power,
                            threshold_violated=prev_power,
                            affected_systems=['IT_EQUIPMENT', 'POWER_DISTRIBUTION'],
                            description=f"Variation brutale de puissance: {power_change:.1f}kW ({power_change_pct:.0f}%)",
                            context={
                                'previous_value': prev_power,
                                'change_amount': power_change,
                                'change_percent': power_change_pct
                            }
                        ))
        
        return incidents
    
    def _detect_composite_incidents(self, data: pd.DataFrame) -> List[Incident]:
        """Detect incidents that involve multiple factors"""
        incidents = []
        
        # Example: High temperature + CLIM failure
        if 'T°C AMBIANTE' in data.columns and any(col in data.columns for col in 
                                                  ['CLIM_A_Status', 'CLIM_B_Status', 
                                                   'CLIM_C_Status', 'CLIM_D_Status']):
            
            for idx, row in data.iterrows():
                temp = row.get('T°C AMBIANTE', 0)
                
                # Count failed CLIMs
                clim_columns = ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status']
                failed_clims = []
                for col in clim_columns:
                    if col in row and row[col] == 0:
                        failed_clims.append(col.replace('_Status', ''))
                
                # High temp + multiple CLIM failures = Emergency
                if temp > self.thresholds['T°C AMBIANTE']['warning_high'] and len(failed_clims) >= 2:
                    incidents.append(Incident(
                        id=str(uuid.uuid4()),
                        timestamp=idx,
                        type=IncidentType.TEMPERATURE_HIGH,
                        severity=IncidentSeverity.EMERGENCY,
                        metric_name='Composite: Temp + CLIM',
                        metric_value=temp,
                        threshold_violated=self.thresholds['T°C AMBIANTE']['warning_high'],
                        affected_systems=['COOLING', 'IT_EQUIPMENT'] + failed_clims,
                        description=f"Urgence: Température élevée ({temp:.1f}°C) avec {len(failed_clims)} CLIMs en panne",
                        context={
                            'temperature': temp,
                            'failed_clim_units': failed_clims,
                            'clim_power': row.get('P_Active CLIM', None),
                            'risk_level': 'EXTREME'
                        }
                    ))
        
        return incidents
    
    def get_incident_summary(self) -> pd.DataFrame:
        """Get a summary of all detected incidents"""
        if not self.incidents:
            return pd.DataFrame()
        
        summary_data = []
        for incident in self.incidents:
            summary_data.append({
                'Timestamp': incident.timestamp,
                'Type': incident.type.value,
                'Severity': incident.severity.value,
                'Metric': incident.metric_name,
                'Value': incident.metric_value,
                'Threshold': incident.threshold_violated,
                'Description': incident.description,
                'Affected Systems': ', '.join(incident.affected_systems)
            })
        
        return pd.DataFrame(summary_data)
    
    def get_incident_statistics(self) -> Dict[str, Any]:
        """Get statistics about detected incidents"""
        if not self.incidents:
            return {
                'total_incidents': 0,
                'by_severity': {},
                'by_type': {},
                'mtbf': None
            }
        
        severity_counts = {}
        type_counts = {}
        
        for incident in self.incidents:
            # Count by severity
            severity = incident.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by type
            inc_type = incident.type.value
            type_counts[inc_type] = type_counts.get(inc_type, 0) + 1
        
        # Calculate mean time between failures (MTBF)
        if len(self.incidents) > 1:
            incident_times = sorted([inc.timestamp for inc in self.incidents])
            time_diffs = [(incident_times[i+1] - incident_times[i]).total_seconds() / 3600 
                         for i in range(len(incident_times)-1)]
            mtbf_hours = np.mean(time_diffs) if time_diffs else None
        else:
            mtbf_hours = None
        
        return {
            'total_incidents': len(self.incidents),
            'by_severity': severity_counts,
            'by_type': type_counts,
            'mtbf_hours': mtbf_hours,
            'most_common_type': max(type_counts, key=type_counts.get) if type_counts else None,
            'critical_incident_rate': severity_counts.get('critical', 0) / len(self.incidents) if self.incidents else 0
        }