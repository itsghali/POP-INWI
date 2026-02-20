"""
Anomaly Analysis Module with Root Cause Detection
Configurable thresholds and time ranges for temperature anomaly analysis
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from scipy import stats

from ..config.settings import FORWARD_FILL_LIMIT


@dataclass
class Anomaly:
    """Represents a detected anomaly"""
    timestamp: pd.Timestamp
    value: float
    anomaly_type: str  # 'high', 'low', 'spike', 'drop'
    severity: float  # 0-1 based on how far from threshold
    duration_minutes: int
    
@dataclass
class RootCause:
    """Represents a potential root cause"""
    cause_type: str
    description: str
    confidence: float  # 0-100%
    evidence: List[str]
    temporal_correlation: float  # How closely the cause aligns with the anomaly
    impact_score: float  # Estimated impact on the anomaly


class AnomalyAnalyzer:
    """
    Analyzes temperature anomalies and identifies root causes with confidence scores
    """
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize the analyzer with data
        
        Args:
            data: DataFrame with time series data including temperature, power, CLIM status, etc.
        """
        self.data = data.copy()
        self.data = self.data.sort_index()
        
    def detect_anomalies(self, 
                        start_date: pd.Timestamp,
                        end_date: pd.Timestamp,
                        min_threshold: float,
                        max_threshold: float,
                        metric: str = 'T°C AMBIANTE') -> List[Anomaly]:
        """
        Detect anomalies in the specified time range and thresholds
        
        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            min_threshold: Minimum normal temperature
            max_threshold: Maximum normal temperature
            metric: Metric to analyze (default: ambient temperature)
            
        Returns:
            List of detected anomalies
        """
        # Filter data to selected range
        mask = (self.data.index >= start_date) & (self.data.index <= end_date)
        period_data = self.data[mask].copy()
        
        if period_data.empty or metric not in period_data.columns:
            return []
        
        anomalies = []
        
        # Detect threshold violations
        high_temp_mask = period_data[metric] > max_threshold
        low_temp_mask = period_data[metric] < min_threshold
        
        # Group consecutive anomalies
        for mask, anomaly_type in [(high_temp_mask, 'high'), (low_temp_mask, 'low')]:
            if mask.any():
                # Find consecutive groups
                groups = mask.ne(mask.shift()).cumsum()
                
                for group_id in groups[mask].unique():
                    group_data = period_data[mask & (groups == group_id)]
                    
                    if len(group_data) > 0:
                        # Calculate severity based on distance from threshold
                        if anomaly_type == 'high':
                            severity = (group_data[metric].max() - max_threshold) / max_threshold
                        else:
                            severity = (min_threshold - group_data[metric].min()) / min_threshold
                        
                        anomalies.append(Anomaly(
                            timestamp=group_data.index[0],
                            value=group_data[metric].max() if anomaly_type == 'high' else group_data[metric].min(),
                            anomaly_type=anomaly_type,
                            severity=min(severity, 1.0),
                            duration_minutes=len(group_data) * 15  # 15-min intervals
                        ))
        
        # Detect sudden spikes/drops
        if len(period_data) > 1:
            # Calculate rate of change
            temp_diff = period_data[metric].diff()
            temp_pct_change = period_data[metric].pct_change()
            
            # Define spike/drop thresholds (2°C change or 10% change)
            spike_mask = (temp_diff > 2.0) | (temp_pct_change > 0.1)
            drop_mask = (temp_diff < -2.0) | (temp_pct_change < -0.1)
            
            for idx in period_data[spike_mask].index:
                anomalies.append(Anomaly(
                    timestamp=idx,
                    value=period_data.loc[idx, metric],
                    anomaly_type='spike',
                    severity=abs(temp_pct_change.loc[idx]),
                    duration_minutes=15
                ))
            
            for idx in period_data[drop_mask].index:
                anomalies.append(Anomaly(
                    timestamp=idx,
                    value=period_data.loc[idx, metric],
                    anomaly_type='drop',
                    severity=abs(temp_pct_change.loc[idx]),
                    duration_minutes=15
                ))
        
        # Sort by timestamp
        anomalies.sort(key=lambda x: x.timestamp)
        
        return anomalies
    
    def analyze_root_causes(self, 
                          anomaly: Anomaly,
                          lookback_minutes: int = 60) -> List[RootCause]:
        """
        Analyze potential root causes for a given anomaly
        
        Args:
            anomaly: The anomaly to analyze
            lookback_minutes: How far back to look for causes
            
        Returns:
            List of root causes ranked by confidence
        """
        root_causes = []
        
        # Get data before and during the anomaly
        anomaly_start = anomaly.timestamp
        lookback_start = anomaly_start - timedelta(minutes=lookback_minutes)
        anomaly_end = anomaly_start + timedelta(minutes=anomaly.duration_minutes)
        
        before_data = self.data[(self.data.index >= lookback_start) & (self.data.index < anomaly_start)]
        during_data = self.data[(self.data.index >= anomaly_start) & (self.data.index <= anomaly_end)]
        
        if before_data.empty or during_data.empty:
            return root_causes
        
        # Analyze different potential causes
        
        # 1. CLIM System Analysis
        clim_causes = self._analyze_clim_causes(before_data, during_data, anomaly)
        root_causes.extend(clim_causes)
        
        # 2. Door State Analysis
        door_causes = self._analyze_door_causes(before_data, during_data, anomaly)
        root_causes.extend(door_causes)
        
        # 3. External Temperature Analysis
        external_causes = self._analyze_external_temp_causes(before_data, during_data, anomaly)
        root_causes.extend(external_causes)
        
        # 4. Power/IT Load Analysis
        power_causes = self._analyze_power_causes(before_data, during_data, anomaly)
        root_causes.extend(power_causes)
        
        # 5. Combined Factors Analysis
        combined_causes = self._analyze_combined_causes(before_data, during_data, anomaly)
        root_causes.extend(combined_causes)
        
        # Sort by confidence
        root_causes.sort(key=lambda x: x.confidence, reverse=True)
        
        return root_causes
    
    def _analyze_clim_causes(self, before_data: pd.DataFrame, 
                           during_data: pd.DataFrame, 
                           anomaly: Anomaly) -> List[RootCause]:
        """Analyze CLIM-related causes"""
        causes = []
        clim_columns = ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status', 'CLIM_E_Status', 'CLIM_F_Status']
        available_clims = [col for col in clim_columns if col in self.data.columns]
        if not available_clims:
            return causes
        for clim_col in available_clims:
            if clim_col in before_data.columns and clim_col in during_data.columns:
                # Check if CLIM turned off
                before_status = before_data[clim_col].iloc[-4:].mean() if len(before_data) >= 4 else before_data[clim_col].mean()
                during_status = during_data[clim_col].mean()
                if before_status > 0.5 and during_status < 0.5:  # Was on, now off
                    # Calculate temporal correlation
                    shutdown_time = before_data[before_data[clim_col] == 0].index[0] if any(before_data[clim_col] == 0) else anomaly.timestamp
                    time_diff = (anomaly.timestamp - shutdown_time).total_seconds() / 60
                    temporal_correlation = max(0, 1 - time_diff / 60)  # Decreases with time
                    # Calculate confidence based on multiple factors
                    confidence = self._calculate_clim_confidence(
                        temporal_correlation,
                        anomaly.severity,
                        anomaly.anomaly_type == 'high'
                    )
                    clim_name = clim_col.replace('_Status', '')
                    causes.append(RootCause(
                        cause_type='CLIM_FAILURE',
                        description=f"{clim_name} s'est arrêté",
                        confidence=confidence,
                        evidence=[
                            f"{clim_name} était actif puis s'est arrêté",
                            f"Arrêt détecté {time_diff:.0f} minutes avant l'anomalie",
                            f"Température a augmenté de {anomaly.value - before_data['T°C AMBIANTE'].mean():.1f}°C"
                        ],
                        temporal_correlation=temporal_correlation,
                        impact_score=0.9 if anomaly.anomaly_type == 'high' else 0.1
                    ))
        # Check overall CLIM capacity
        if available_clims and 'P_Active CLIM' in during_data.columns:
            active_clims = sum(during_data[col].mean() > 0.5 for col in available_clims if col in during_data.columns)
            total_clims = len(available_clims)
            if active_clims < total_clims * 0.5:  # Less than 50% CLIMs active
                confidence = 70 + (1 - active_clims/total_clims) * 20  # 70-90%
                causes.append(RootCause(
                    cause_type='CLIM_CAPACITY_REDUCED',
                    description=f"Capacité CLIM réduite ({active_clims}/{total_clims} actifs)",
                    confidence=confidence,
                    evidence=[
                        f"Seulement {active_clims} CLIM sur {total_clims} sont actifs",
                        f"Puissance CLIM: {during_data['P_Active CLIM'].mean():.1f}kW"
                    ],
                    temporal_correlation=1.0,
                    impact_score=0.8
                ))
        return causes
        return causes
    
    def _analyze_door_causes(self, before_data: pd.DataFrame, 
                           during_data: pd.DataFrame, 
                           anomaly: Anomaly) -> List[RootCause]:
        """Analyze door-related causes"""
        causes = []
        
        if 'Etat de porte' not in self.data.columns:
            return causes
        
        # Check door open events
        door_open_before = (before_data['Etat de porte'] == 1).sum() if 'Etat de porte' in before_data.columns else 0
        door_open_during = (during_data['Etat de porte'] == 1).sum() if 'Etat de porte' in during_data.columns else 0
        
        if door_open_before > 0 or door_open_during > 0:
            # Calculate door open duration
            total_door_open = (door_open_before + door_open_during) * 15  # minutes
            
            # Find when door was opened
            all_data = pd.concat([before_data, during_data])
            door_events = all_data[all_data['Etat de porte'] == 1]
            
            if not door_events.empty:
                first_open = door_events.index[0]
                time_before_anomaly = (anomaly.timestamp - first_open).total_seconds() / 60
                
                # Calculate confidence based on duration and timing
                base_confidence = min(60 + total_door_open / 5, 85)  # Max 85% for door alone
                
                # Adjust for external temperature if available
                if 'T°C EXTERIEURE' in all_data.columns:
                    ext_temp = all_data['T°C EXTERIEURE'].mean()
                    if ext_temp > 30:  # High external temp increases impact
                        base_confidence = min(base_confidence + 10, 90)
                
                causes.append(RootCause(
                    cause_type='DOOR_OPEN',
                    description=f"Porte ouverte pendant {total_door_open} minutes",
                    confidence=base_confidence,
                    evidence=[
                        f"Porte ouverte {time_before_anomaly:.0f} min avant l'anomalie",
                        f"Durée totale d'ouverture: {total_door_open} minutes",
                        f"Température extérieure: {ext_temp:.1f}°C" if 'T°C EXTERIEURE' in all_data.columns else "Température extérieure non disponible"
                    ],
                    temporal_correlation=max(0, 1 - time_before_anomaly / 30),
                    impact_score=0.6 if anomaly.anomaly_type == 'high' else 0.2
                ))
        
        return causes
    
    def _analyze_external_temp_causes(self, before_data: pd.DataFrame, 
                                    during_data: pd.DataFrame, 
                                    anomaly: Anomaly) -> List[RootCause]:
        """Analyze external temperature influence"""
        causes = []
        
        if 'T°C EXTERIEURE' not in self.data.columns:
            return causes
        
        # Calculate external temperature change
        if 'T°C EXTERIEURE' in before_data.columns and 'T°C EXTERIEURE' in during_data.columns:
            ext_temp_before = before_data['T°C EXTERIEURE'].mean()
            ext_temp_during = during_data['T°C EXTERIEURE'].mean()
            ext_temp_change = ext_temp_during - ext_temp_before
            
            # Check if external temp is high or increased significantly
            if ext_temp_during > 35 or ext_temp_change > 3:
                # Calculate correlation between external and internal temp
                if 'T°C AMBIANTE' in during_data.columns:
                    correlation = during_data[['T°C EXTERIEURE', 'T°C AMBIANTE']].corr().iloc[0, 1]
                else:
                    correlation = 0.5  # Default assumption
                
                confidence = 40 + abs(correlation) * 30  # 40-70% base confidence
                
                if ext_temp_during > 40:  # Extreme heat
                    confidence = min(confidence + 20, 85)
                
                causes.append(RootCause(
                    cause_type='EXTERNAL_TEMPERATURE',
                    description=f"Température extérieure élevée ({ext_temp_during:.1f}°C)",
                    confidence=confidence,
                    evidence=[
                        f"Température extérieure: {ext_temp_during:.1f}°C",
                        f"Augmentation de {ext_temp_change:.1f}°C",
                        f"Corrélation avec température ambiante: {correlation:.2f}"
                    ],
                    temporal_correlation=abs(correlation),
                    impact_score=0.5
                ))
        
        return causes
    
    def _analyze_power_causes(self, before_data: pd.DataFrame, 
                            during_data: pd.DataFrame, 
                            anomaly: Anomaly) -> List[RootCause]:
        """Analyze power/IT load related causes"""
        causes = []
        
        if 'Puissance_IT' in before_data.columns and 'Puissance_IT' in during_data.columns:
            it_power_before = before_data['Puissance_IT'].mean()
            it_power_during = during_data['Puissance_IT'].mean()
            it_power_change = it_power_during - it_power_before
            
            # Significant IT load increase (>2kW or >20%)
            if it_power_change > 2 or (it_power_before > 0 and it_power_change / it_power_before > 0.2):
                # Heat generation estimate: ~3.5 BTU per watt
                heat_increase_estimate = it_power_change * 3.5
                
                confidence = 50 + min(it_power_change * 5, 30)  # 50-80% confidence
                
                causes.append(RootCause(
                    cause_type='IT_LOAD_INCREASE',
                    description=f"Augmentation de charge IT de {it_power_change:.1f}kW",
                    confidence=confidence,
                    evidence=[
                        f"Puissance IT: {it_power_before:.1f}kW → {it_power_during:.1f}kW",
                        f"Augmentation de {it_power_change/it_power_before*100:.0f}%" if it_power_before > 0 else f"Augmentation de {it_power_change:.1f}kW",
                        f"Génération de chaleur supplémentaire estimée"
                    ],
                    temporal_correlation=0.7,
                    impact_score=0.6 if anomaly.anomaly_type == 'high' else 0.1
                ))
        
        # Check PUE degradation
        if 'PUE' in during_data.columns:
            pue_during = during_data['PUE'].mean()
            if pue_during > 2.0:
                confidence = 40 + (pue_during - 2.0) * 20  # Higher PUE = higher confidence
                
                causes.append(RootCause(
                    cause_type='COOLING_INEFFICIENCY',
                    description=f"Efficacité de refroidissement dégradée (PUE: {pue_during:.2f})",
                    confidence=min(confidence, 70),
                    evidence=[
                        f"PUE actuel: {pue_during:.2f} (optimal: <1.5)",
                        f"Surconsommation énergétique détectée"
                    ],
                    temporal_correlation=0.6,
                    impact_score=0.5
                ))
        
        return causes
    
    def _analyze_combined_causes(self, before_data: pd.DataFrame, 
                               during_data: pd.DataFrame, 
                               anomaly: Anomaly) -> List[RootCause]:
        """Analyze combinations of factors"""
        causes = []
        
        # Collect all detected issues
        issues = []
        
        # Check CLIM status
        clim_columns = ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status']
        failed_clims = []
        for col in clim_columns:
            if col in during_data.columns and during_data[col].mean() < 0.5:
                failed_clims.append(col.replace('_Status', ''))
        
        if failed_clims:
            issues.append(('clim_failure', len(failed_clims)))
        
        # Check door
        if 'Etat de porte' in during_data.columns and during_data['Etat de porte'].sum() > 0:
            issues.append(('door_open', during_data['Etat de porte'].sum()))
        
        # Check external temp
        if 'T°C EXTERIEURE' in during_data.columns and during_data['T°C EXTERIEURE'].mean() > 35:
            issues.append(('high_external_temp', during_data['T°C EXTERIEURE'].mean()))
        
        # Check IT load
        if 'Puissance_IT' in during_data.columns and 'Puissance_IT' in before_data.columns:
            load_increase = during_data['Puissance_IT'].mean() - before_data['Puissance_IT'].mean()
            if load_increase > 2:
                issues.append(('it_load_increase', load_increase))
        
        # If multiple issues detected, create combined cause
        if len(issues) >= 2:
            confidence = min(70 + len(issues) * 10, 95)  # More issues = higher confidence
            
            description_parts = []
            evidence_parts = []
            
            for issue_type, value in issues:
                if issue_type == 'clim_failure':
                    description_parts.append(f"{value} CLIM en panne")
                    evidence_parts.append(f"{value} unités CLIM non fonctionnelles")
                elif issue_type == 'door_open':
                    description_parts.append("porte ouverte")
                    evidence_parts.append(f"Porte ouverte {value*15} minutes")
                elif issue_type == 'high_external_temp':
                    description_parts.append(f"chaleur extérieure ({value:.1f}°C)")
                    evidence_parts.append(f"Température extérieure: {value:.1f}°C")
                elif issue_type == 'it_load_increase':
                    description_parts.append(f"charge IT +{value:.1f}kW")
                    evidence_parts.append(f"Augmentation charge IT: {value:.1f}kW")
            
            causes.append(RootCause(
                cause_type='MULTIPLE_FACTORS',
                description=f"Facteurs multiples: {', '.join(description_parts)}",
                confidence=confidence,
                evidence=evidence_parts + [f"{len(issues)} problèmes simultanés détectés"],
                temporal_correlation=0.9,
                impact_score=0.95
            ))
        
        return causes
    
    def _calculate_clim_confidence(self, temporal_correlation: float, 
                                 severity: float, 
                                 is_high_temp: bool) -> float:
        """Calculate confidence score for CLIM-related causes"""
        base_confidence = 70 if is_high_temp else 40
        
        # Adjust based on temporal correlation (how close in time)
        time_factor = temporal_correlation * 20
        
        # Adjust based on severity
        severity_factor = severity * 10
        
        return min(base_confidence + time_factor + severity_factor, 95)
    
    def generate_analysis_report(self,
                               start_date: pd.Timestamp,
                               end_date: pd.Timestamp,
                               min_threshold: float,
                               max_threshold: float) -> Dict[str, Any]:
        """
        Generate a complete analysis report for the specified period and thresholds
        
        Returns:
            Dictionary containing anomalies, root causes, and statistics
        """
        # Detect anomalies
        anomalies = self.detect_anomalies(start_date, end_date, min_threshold, max_threshold)
        
        # Analyze each anomaly
        analysis_results = []
        
        for anomaly in anomalies:
            root_causes = self.analyze_root_causes(anomaly)
            
            analysis_results.append({
                'anomaly': anomaly,
                'root_causes': root_causes[:5],  # Top 5 causes
                'primary_cause': root_causes[0] if root_causes else None
            })
        
        # Calculate statistics
        total_duration = sum(a.duration_minutes for a in anomalies)
        severity_avg = np.mean([a.severity for a in anomalies]) if anomalies else 0
        
        # Find most common causes
        all_causes = []
        for result in analysis_results:
            if result['primary_cause']:
                all_causes.append(result['primary_cause'].cause_type)
        
        cause_frequency = pd.Series(all_causes).value_counts().to_dict() if all_causes else {}
        
        return {
            'period': {
                'start': start_date,
                'end': end_date,
                'duration_hours': (end_date - start_date).total_seconds() / 3600
            },
            'thresholds': {
                'min': min_threshold,
                'max': max_threshold
            },
            'summary': {
                'total_anomalies': len(anomalies),
                'total_anomaly_duration_minutes': total_duration,
                'average_severity': severity_avg,
                'anomaly_rate': len(anomalies) / ((end_date - start_date).days + 1) if (end_date - start_date).days > 0 else 0
            },
            'anomaly_types': {
                'high': sum(1 for a in anomalies if a.anomaly_type == 'high'),
                'low': sum(1 for a in anomalies if a.anomaly_type == 'low'),
                'spike': sum(1 for a in anomalies if a.anomaly_type == 'spike'),
                'drop': sum(1 for a in anomalies if a.anomaly_type == 'drop')
            },
            'cause_frequency': cause_frequency,
            'detailed_results': analysis_results
        }