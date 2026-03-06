"""
Ultimate Root Cause Analysis Engine - Final Reliable Implementation
Combines best practices from multiple approaches for maximum reliability
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
    PUE_DEGRADATION = "pue_degradation"
    COMPOUND_CAUSE = "compound_cause"
    UNKNOWN = "unknown"


@dataclass
class Evidence:
    """Evidence supporting a root cause with reliability scoring"""
    type: str                           # "primary", "supporting", "temporal", "correlation"
    description: str                    # Human-readable explanation
    value: Any                         # Measurement or metric
    confidence_contribution: float     # Raw confidence points (0-50)
    reliability_factor: float = 1.0    # Quality multiplier (0.3-1.0)
    
    @property
    def weighted_contribution(self) -> float:
        """Calculate quality-weighted confidence contribution"""
        return self.confidence_contribution * self.reliability_factor


@dataclass
class RootCause:
    """Identified root cause with evidence-based confidence calculation"""
    cause_type: RootCauseType
    description: str
    evidence: List[Evidence] = field(default_factory=list)
    affected_metrics: List[str] = field(default_factory=list)
    time_detected: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    severity: str = "medium"
    recommendations: List[str] = field(default_factory=list)
    
    def add_evidence(self, evidence_type: str, description: str, value: Any, 
                    confidence_points: float, reliability: float = 1.0):
        """Add evidence with reliability-adjusted confidence"""
        self.evidence.append(Evidence(
            type=evidence_type,
            description=description,
            value=value,
            confidence_contribution=confidence_points,
            reliability_factor=max(0.3, min(1.0, reliability))  # Clamp reliability
        ))
    
    @property
    def calculated_confidence(self) -> float:
        """Calculate total confidence from weighted evidence"""
        if not self.evidence:
            return 0.0
            
        # Sum weighted contributions with diminishing returns
        total_contribution = sum(e.weighted_contribution for e in self.evidence)
        
        # Apply diminishing returns curve: confidence = 80 * (1 - e^(-total/25))
        # This prevents overconfidence even with many evidence pieces
        raw_confidence = 80.0 * (1 - np.exp(-total_contribution / 25.0))
        
        # Conservative capping: max 80% confidence, min 15%
        return max(15.0, min(80.0, raw_confidence))
    
    @property 
    def confidence(self) -> float:
        """Alias for calculated_confidence for compatibility"""
        return self.calculated_confidence


@dataclass
class DataQualityReport:
    """Comprehensive data quality assessment"""
    completeness: float                 # 0-1 percentage of expected data points
    reliability: Dict[str, float]       # Per-sensor reliability scores
    time_gaps: List[Tuple[datetime, datetime]] = field(default_factory=list)
    missing_sensors: List[str] = field(default_factory=list)
    quality_score: float = 0.0         # Overall quality metric
    is_analysis_viable: bool = True     # Whether analysis should proceed
    
    def __post_init__(self):
        """Calculate overall quality and viability"""
        if self.reliability:
            avg_reliability = np.mean(list(self.reliability.values()))
            self.quality_score = (self.completeness + avg_reliability) / 2
        else:
            self.quality_score = self.completeness
            
        # Analysis is viable if we have reasonable data quality
        self.is_analysis_viable = (
            self.completeness > 0.4 and  # At least 40% data completeness
            self.quality_score > 0.3     # At least 30% overall quality
        )


class UltimateRootCauseAnalyzer:
    """
    Ultimate root cause analyzer combining reliability with simplicity
    Evidence-based confidence with robust validation
    """
    
    def __init__(self, data: pd.DataFrame):
        """Initialize analyzer with comprehensive data preparation"""
        self.data = data.copy().sort_index()
        self._prepare_derived_metrics()
        self._init_detectors()
        
    def _prepare_derived_metrics(self):
        """Precompute derived metrics for efficient analysis"""
        # CLIM metrics
        clim_cols = ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status']
        available_clim = [col for col in clim_cols if col in self.data.columns]
        if available_clim:
            self.data['clim_active_count'] = self.data[available_clim].sum(axis=1)
            self.data['clim_availability_pct'] = (self.data['clim_active_count'] / len(available_clim)) * 100
        
        # Temperature differentials
        if all(col in self.data.columns for col in ['T°C AMBIANTE', 'T°C EXTERIEURE']):
            self.data['temp_differential'] = self.data['T°C AMBIANTE'] - self.data['T°C EXTERIEURE']
            
        # Power change rates
        if 'Puissance_IT' in self.data.columns:
            self.data['power_change_rate'] = self.data['Puissance_IT'].diff()
            self.data['power_rolling_avg'] = self.data['Puissance_IT'].rolling(window=4).mean()
        
        # Door activity patterns
        if 'Etat de porte' in self.data.columns:
            self.data['door_open_duration'] = self.data['Etat de porte'].rolling(window=8).sum() * 15  # Minutes
            
    def _init_detectors(self):
        """Initialize specialized cause detectors"""
        self.detectors = {
            'clim': UltimateCLIMDetector(),
            'environmental': UltimateEnvironmentalDetector(),
            'door': UltimateDoorDetector(),
            'power': UltimatePowerDetector()
        }
    
    def assess_data_quality(self, start_time: datetime, end_time: datetime) -> DataQualityReport:
        """Comprehensive data quality assessment with reliability scoring"""
        # Extract period data
        mask = (self.data.index >= start_time) & (self.data.index <= end_time)
        period_data = self.data[mask]
        
        if period_data.empty:
            return DataQualityReport(completeness=0.0, reliability={}, is_analysis_viable=False)
        
        # Calculate completeness
        duration = end_time - start_time
        expected_points = max(1, int(duration.total_seconds() / 900))  # 15-min intervals
        actual_points = len(period_data)
        completeness = min(1.0, actual_points / expected_points)
        
        # Assess per-sensor reliability
        reliability = {}
        critical_sensors = ['T°C AMBIANTE', 'T°C EXTERIEURE', 'Puissance_IT'] + \
                          [f'CLIM_{l}_Status' for l in 'ABCD']
        
        for sensor in critical_sensors:
            if sensor in period_data.columns:
                sensor_data = period_data[sensor].dropna()
                if len(sensor_data) > 1:
                    # Check for stuck sensors and reasonable variance
                    std_dev = sensor_data.std()
                    if sensor.startswith('CLIM') and sensor.endswith('Status'):
                        # Binary sensors: good if they change
                        reliability[sensor] = 1.0 if std_dev > 0 else 0.4
                    else:
                        # Continuous sensors: need reasonable variance
                        if std_dev > 0.1:
                            reliability[sensor] = 1.0
                        elif std_dev > 0.01:
                            reliability[sensor] = 0.7
                        else:
                            reliability[sensor] = 0.3  # Likely stuck
                else:
                    reliability[sensor] = 0.2  # Insufficient data
        
        # Detect significant time gaps
        time_gaps = []
        if len(period_data) > 1:
            time_diffs = period_data.index.to_series().diff()
            gap_threshold = pd.Timedelta(minutes=45)  # More than 3 intervals
            for i, diff in enumerate(time_diffs[1:], 1):
                if diff > gap_threshold:
                    time_gaps.append((period_data.index[i-1], period_data.index[i]))
        
        # Identify missing critical sensors
        missing_sensors = [s for s in critical_sensors if s not in self.data.columns]
        
        return DataQualityReport(
            completeness=completeness,
            reliability=reliability,
            time_gaps=time_gaps,
            missing_sensors=missing_sensors
        )
    
    def analyze_incident(self, incident: Incident, 
                        time_window_before: int = 60, 
                        time_window_after: int = 30) -> List[RootCause]:
        """Analyze incident with ultimate reliability"""
        # Define analysis window
        start_time = incident.timestamp - timedelta(minutes=time_window_before)
        end_time = incident.timestamp + timedelta(minutes=time_window_after)
        
        # Get window data
        mask = (self.data.index >= start_time) & (self.data.index <= end_time)
        window_data = self.data[mask]
        
        if window_data.empty:
            return [RootCause(
                cause_type=RootCauseType.UNKNOWN,
                description="Données insuffisantes pour l'analyse",
                time_detected=incident.timestamp
            )]
        
        # Assess data quality
        quality = self.assess_data_quality(start_time, end_time)
        
        # Don't proceed if data quality is too poor
        if not quality.is_analysis_viable:
            return [RootCause(
                cause_type=RootCauseType.UNKNOWN,
                description=f"Qualité des données insuffisante ({quality.quality_score*100:.0f}%)",
                time_detected=incident.timestamp
            )]
        
        # Build analysis context
        context = {
            'incident': incident,
            'time_range': end_time - start_time,
            'data_quality': quality,
            'incident_duration': incident.duration_seconds / 60 if incident.duration_seconds else None,
            'window_data': window_data
        }
        
        # Run all detectors
        all_causes = []
        for detector_name, detector in self.detectors.items():
            try:
                causes = detector.detect(window_data, context)
                for cause in causes:
                    cause.time_detected = incident.timestamp
                all_causes.extend(causes)
            except Exception as e:
                logger.error(f"Error in {detector_name} detector: {e}")
        
        # Apply final quality adjustments and ranking
        final_causes = self._apply_quality_adjustments(all_causes, quality)
        
        # Generate recommendations
        for cause in final_causes:
            cause.recommendations = self._generate_recommendations(cause)
        
        return final_causes
    
    def _apply_quality_adjustments(self, causes: List[RootCause], 
                                  quality: DataQualityReport) -> List[RootCause]:
        """Apply final quality adjustments and filtering"""
        if not causes:
            return causes
        
        adjusted_causes = []
        for cause in causes:
            # Apply sensor-specific reliability adjustments
            reliability_penalty = 1.0
            for metric in cause.affected_metrics:
                if metric in quality.reliability:
                    reliability_penalty *= quality.reliability[metric]
            
            # Calculate final adjusted confidence
            base_confidence = cause.calculated_confidence
            adjusted_confidence = base_confidence * max(0.5, reliability_penalty)
            
            # Add quality indicator to description for transparency
            if quality.quality_score < 0.7:
                cause.description += f" (fiabilité: {quality.quality_score*100:.0f}%)"
            
            # Only keep causes with sufficient confidence
            if adjusted_confidence >= 25.0:
                # Create adjusted cause (can't modify confidence directly due to property)
                adjusted_cause = RootCause(
                    cause_type=cause.cause_type,
                    description=cause.description,
                    affected_metrics=cause.affected_metrics,
                    time_detected=cause.time_detected,
                    duration_minutes=cause.duration_minutes,
                    severity=cause.severity
                )
                # Copy evidence with adjusted reliability
                for evidence in cause.evidence:
                    adjusted_cause.add_evidence(
                        evidence.type,
                        evidence.description,
                        evidence.value,
                        evidence.confidence_contribution,
                        evidence.reliability_factor * max(0.5, reliability_penalty)
                    )
                adjusted_causes.append(adjusted_cause)
        
        # Sort by final confidence
        return sorted(adjusted_causes, key=lambda x: x.calculated_confidence, reverse=True)
    
    def _generate_recommendations(self, cause: RootCause) -> List[str]:
        """Generate specific recommendations based on cause type"""
        recommendations = []
        
        if cause.cause_type == RootCauseType.CLIM_TOTAL_FAILURE:
            recommendations.extend([
                "🚨 URGENCE: Intervention immédiate sur système CLIM",
                "📞 Contactez l'équipe technique en priorité absolue",
                "🌡️ Activez le plan de contingence thermique",
                "📊 Surveillez la température toutes les 5 minutes"
            ])
        elif cause.cause_type == RootCauseType.CLIM_PARTIAL_FAILURE:
            recommendations.extend([
                "🔧 Vérifiez les unités CLIM défaillantes identifiées",
                "⚡ Contrôlez l'alimentation électrique des unités",
                "📅 Planifiez une maintenance préventive",
                "📈 Surveillez la performance des unités restantes"
            ])
        elif cause.cause_type == RootCauseType.EXTERNAL_HEAT_WAVE:
            recommendations.extend([
                "❄️ Augmentez la capacité de refroidissement disponible",
                "🌡️ Surveillez les prévisions météorologiques",
                "🔄 Optimisez la circulation d'air interne",
                "⏰ Considérez le refroidissement nocturne"
            ])
        elif cause.cause_type == RootCauseType.DOOR_EXTENDED_OPEN:
            recommendations.extend([
                "🚪 Vérifiez le système de fermeture automatique",
                "👥 Sensibilisez le personnel aux procédures d'accès",
                "📱 Configurez des alertes pour portes ouvertes >3min",
                "🔒 Envisagez un système de contrôle d'accès amélioré"
            ])
        elif cause.cause_type == RootCauseType.IT_POWER_SURGE:
            recommendations.extend([
                "💻 Identifiez les équipements à l'origine du pic",
                "⚖️ Rééquilibrez la distribution de charge",
                "📊 Analysez la planification des tâches intensives",
                "🔌 Vérifiez l'infrastructure électrique"
            ])
        
        return recommendations


class UltimateCLIMDetector:
    """Ultra-reliable CLIM system cause detector"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        """Detect CLIM issues with evidence-based confidence"""
        causes = []
        incident = context['incident']
        quality = context['data_quality']
        
        # Check for required CLIM data
        clim_cols = [col for col in ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status'] 
                    if col in data.columns]
        if not clim_cols:
            return causes
        
        # Extract analysis window
        incident_time = incident.timestamp
        analysis_window = data[
            (data.index >= incident_time - timedelta(minutes=45)) &
            (data.index <= incident_time + timedelta(minutes=15))
        ]
        
        if analysis_window.empty:
            return causes
        
        # Calculate CLIM activity metrics
        clim_data = analysis_window[clim_cols].fillna(0)
        active_counts = clim_data.sum(axis=1)
        total_clims = len(clim_cols)
        
        # Evidence collection for total failure
        zero_activity_ratio = (active_counts == 0).mean()
        if zero_activity_ratio > 0.7:  # More than 70% of time with no CLIM
            cause = RootCause(
                cause_type=RootCauseType.CLIM_TOTAL_FAILURE,
                description=f"Défaillance totale CLIM - {total_clims} unités inactives",
                affected_metrics=clim_cols,
                severity="critical"
            )
            
            # Primary evidence: Activity pattern
            cause.add_evidence(
                "activity_pattern",
                f"Aucune activité CLIM pendant {zero_activity_ratio*100:.0f}% de la période",
                zero_activity_ratio,
                confidence_points=35.0,
                reliability=quality.reliability.get('CLIM_A_Status', 0.8)
            )
            
            # Supporting evidence: Power correlation
            if 'P_Active CLIM' in analysis_window.columns:
                clim_power = analysis_window['P_Active CLIM'].fillna(0)
                power_correlation = abs(active_counts.corr(clim_power))
                if not pd.isna(power_correlation):
                    cause.add_evidence(
                        "power_correlation",
                        f"Corrélation puissance CLIM: {power_correlation:.2f}",
                        power_correlation,
                        confidence_points=25.0 if power_correlation > 0.6 else 10.0,
                        reliability=quality.reliability.get('P_Active CLIM', 0.7)
                    )
            
            # Temperature impact evidence
            if 'T°C AMBIANTE' in analysis_window.columns:
                temp_trend = analysis_window['T°C AMBIANTE'].diff().mean()
                if temp_trend > 0.1:  # Rising temperature
                    cause.add_evidence(
                        "temperature_impact",
                        f"Tendance température: +{temp_trend:.2f}°C/période",
                        temp_trend,
                        confidence_points=20.0,
                        reliability=quality.reliability.get('T°C AMBIANTE', 0.8)
                    )
            
            causes.append(cause)
            
        # Evidence collection for partial failure
        elif (active_counts < total_clims * 0.5).mean() > 0.6:  # Less than 50% capacity
            failed_units = []
            for col in clim_cols:
                if (analysis_window[col] == 0).mean() > 0.7:
                    failed_units.append(col.replace('_Status', ''))
            
            if failed_units:
                cause = RootCause(
                    cause_type=RootCauseType.CLIM_PARTIAL_FAILURE,
                    description=f"Défaillance partielle CLIM - unités affectées: {', '.join(failed_units)}",
                    affected_metrics=[f"{unit}_Status" for unit in failed_units],
                    severity="high"
                )
                
                cause.add_evidence(
                    "unit_failure_pattern",
                    f"Défaillance détectée sur {len(failed_units)} unité(s)",
                    failed_units,
                    confidence_points=30.0,
                    reliability=np.mean([quality.reliability.get(f"{unit}_Status", 0.8) for unit in failed_units])
                )
                
                # Capacity impact
                avg_capacity = active_counts.mean() / total_clims
                cause.add_evidence(
                    "capacity_reduction",
                    f"Capacité réduite à {avg_capacity*100:.0f}%",
                    avg_capacity,
                    confidence_points=20.0,
                    reliability=0.9
                )
                
                causes.append(cause)
        
        return causes


class UltimateEnvironmentalDetector:
    """Ultra-reliable environmental cause detector"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        causes = []
        incident = context['incident']
        quality = context['data_quality']
        
        if 'T°C EXTERIEURE' not in data.columns:
            return causes
        
        # Extended analysis window for environmental factors
        analysis_window = data[
            (data.index >= incident.timestamp - timedelta(hours=3)) &
            (data.index <= incident.timestamp + timedelta(minutes=30))
        ]
        
        if analysis_window.empty:
            return causes
        
        ext_temps = analysis_window['T°C EXTERIEURE'].dropna()
        if len(ext_temps) < 3:
            return causes
        
        max_temp = ext_temps.max()
        avg_temp = ext_temps.mean()
        
        # Heat wave detection with conservative thresholds
        if max_temp > 40:  # Extreme heat
            cause = RootCause(
                cause_type=RootCauseType.EXTERNAL_HEAT_WAVE,
                description=f"Canicule extrême - température max: {max_temp:.1f}°C",
                affected_metrics=['T°C EXTERIEURE', 'T°C AMBIANTE'],
                severity="high"
            )
            
            # Temperature extremity evidence
            cause.add_evidence(
                "temperature_extreme",
                f"Température extérieure extrême: {max_temp:.1f}°C",
                max_temp,
                confidence_points=40.0,
                reliability=quality.reliability.get('T°C EXTERIEURE', 0.8)
            )
            
            # Internal correlation evidence
            if 'T°C AMBIANTE' in analysis_window.columns:
                int_temps = analysis_window['T°C AMBIANTE'].dropna()
                if len(int_temps) > 3:
                    correlation = ext_temps.corr(int_temps)
                    if not pd.isna(correlation) and correlation > 0.4:
                        cause.add_evidence(
                            "internal_correlation",
                            f"Corrélation température interne: {correlation:.2f}",
                            correlation,
                            confidence_points=25.0 if correlation > 0.6 else 15.0,
                            reliability=min(
                                quality.reliability.get('T°C EXTERIEURE', 0.8),
                                quality.reliability.get('T°C AMBIANTE', 0.8)
                            )
                        )
            
            causes.append(cause)
            
        elif max_temp > 35 and avg_temp > 32:  # Moderate heat wave
            cause = RootCause(
                cause_type=RootCauseType.EXTERNAL_TEMP_INFLUENCE,
                description=f"Influence thermique externe - max: {max_temp:.1f}°C, moy: {avg_temp:.1f}°C",
                affected_metrics=['T°C EXTERIEURE', 'T°C AMBIANTE'],
                severity="medium"
            )
            
            cause.add_evidence(
                "elevated_temperature",
                f"Température externe élevée (max: {max_temp:.1f}°C, moy: {avg_temp:.1f}°C)",
                {'max': max_temp, 'avg': avg_temp},
                confidence_points=25.0,
                reliability=quality.reliability.get('T°C EXTERIEURE', 0.8)
            )
            
            causes.append(cause)
        
        return causes


class UltimateDoorDetector:
    """Ultra-reliable door activity detector"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        causes = []
        incident = context['incident']
        quality = context['data_quality']
        
        if 'Etat de porte' not in data.columns:
            return causes
        
        # Door analysis window
        analysis_window = data[
            (data.index >= incident.timestamp - timedelta(minutes=90)) &
            (data.index <= incident.timestamp + timedelta(minutes=15))
        ]
        
        if analysis_window.empty:
            return causes
        
        door_states = analysis_window['Etat de porte'].fillna(0)
        
        # Calculate maximum consecutive open duration
        max_consecutive_open = 0
        current_open = 0
        
        for state in door_states:
            if state == 1:
                current_open += 1
                max_consecutive_open = max(max_consecutive_open, current_open)
            else:
                current_open = 0
        
        # Convert to minutes (assuming 15-min intervals)
        max_open_minutes = max_consecutive_open * 15
        
        if max_open_minutes > 60:  # More than 1 hour
            cause = RootCause(
                cause_type=RootCauseType.DOOR_EXTENDED_OPEN,
                description=f"Porte ouverte de façon prolongée - durée max: {max_open_minutes:.0f} minutes",
                affected_metrics=['Etat de porte', 'T°C AMBIANTE'],
                severity="high",
                duration_minutes=int(max_open_minutes)
            )
            
            # Duration evidence
            cause.add_evidence(
                "open_duration",
                f"Porte ouverte pendant {max_open_minutes:.0f} minutes consécutives",
                max_open_minutes,
                confidence_points=35.0,
                reliability=quality.reliability.get('Etat de porte', 0.8)
            )
            
            # Temperature impact evidence
            if 'T°C AMBIANTE' in analysis_window.columns:
                temp_data = analysis_window['T°C AMBIANTE']
                temp_change = temp_data.max() - temp_data.min()
                if temp_change > 1.0:  # Significant temperature change
                    cause.add_evidence(
                        "temperature_impact",
                        f"Impact thermique: variation de {temp_change:.1f}°C",
                        temp_change,
                        confidence_points=20.0,
                        reliability=quality.reliability.get('T°C AMBIANTE', 0.8)
                    )
            
            causes.append(cause)
        
        return causes


class UltimatePowerDetector:
    """Ultra-reliable power system detector"""
    
    def detect(self, data: pd.DataFrame, context: Dict[str, Any]) -> List[RootCause]:
        causes = []
        incident = context['incident']
        quality = context['data_quality']
        
        if 'Puissance_IT' not in data.columns:
            return causes
        
        # Power analysis window
        analysis_window = data[
            (data.index >= incident.timestamp - timedelta(hours=2)) &
            (data.index <= incident.timestamp + timedelta(minutes=30))
        ]
        
        if analysis_window.empty or len(analysis_window) < 3:
            return causes
        
        power_data = analysis_window['Puissance_IT'].dropna()
        if len(power_data) < 3:
            return causes
        
        # Calculate power statistics
        power_changes = power_data.diff().abs()
        max_change = power_changes.max()
        
        # Power surge detection
        if max_change > 5:  # Conservative threshold for power surge
            surge_time = power_changes.idxmax()
            time_before_incident = (incident.timestamp - surge_time).total_seconds() / 60
            
            cause = RootCause(
                cause_type=RootCauseType.IT_POWER_SURGE,
                description=f"Pic de consommation IT - variation: {max_change:.1f}kW",
                affected_metrics=['Puissance_IT', 'T°C AMBIANTE'],
                severity="medium"
            )
            
            # Power spike evidence
            cause.add_evidence(
                "power_spike",
                f"Variation brutale de puissance: {max_change:.1f}kW",
                max_change,
                confidence_points=30.0,
                reliability=quality.reliability.get('Puissance_IT', 0.8)
            )
            
            # Temporal correlation
            if 0 <= time_before_incident <= 60:  # Within 1 hour of incident
                cause.add_evidence(
                    "temporal_correlation",
                    f"Pic survenu {time_before_incident:.0f} minutes avant l'incident",
                    time_before_incident,
                    confidence_points=20.0,
                    reliability=0.9
                )
            
            # Temperature correlation
            if 'T°C AMBIANTE' in analysis_window.columns:
                temp_corr = power_data.corr(analysis_window['T°C AMBIANTE'])
                if not pd.isna(temp_corr) and temp_corr > 0.4:
                    cause.add_evidence(
                        "temperature_correlation",
                        f"Corrélation avec température: {temp_corr:.2f}",
                        temp_corr,
                        confidence_points=15.0,
                        reliability=quality.reliability.get('T°C AMBIANTE', 0.8)
                    )
            
            causes.append(cause)
        
        return causes