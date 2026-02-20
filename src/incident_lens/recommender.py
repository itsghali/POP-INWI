"""
Recommendation Engine for Incident Lens
Generates actionable recommendations based on root cause analysis
"""
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

try:
    from .analyzer import RootCause, RootCauseType
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from incident_lens.analyzer import RootCause, RootCauseType


class RecommendationPriority(Enum):
    """Priority levels for recommendations"""
    IMMEDIATE = "immediate"      # < 1 hour
    URGENT = "urgent"           # < 4 hours  
    HIGH = "high"               # < 24 hours
    MEDIUM = "medium"           # < 1 week
    LOW = "low"                 # Routine maintenance


class RecommendationType(Enum):
    """Types of recommendations"""
    EMERGENCY_ACTION = "emergency_action"
    PREVENTIVE_MAINTENANCE = "preventive_maintenance"
    CONFIGURATION_CHANGE = "configuration_change"
    MONITORING_ENHANCEMENT = "monitoring_enhancement"
    TRAINING_REQUIRED = "training_required"
    INFRASTRUCTURE_UPGRADE = "infrastructure_upgrade"


@dataclass
class Recommendation:
    """Single actionable recommendation"""
    title: str
    description: str
    priority: RecommendationPriority
    type: RecommendationType
    estimated_time: str  # e.g., "30 minutes", "2 hours"
    responsible_team: str
    steps: List[str] = field(default_factory=list)
    resources_needed: List[str] = field(default_factory=list)
    expected_outcome: str = ""
    related_causes: List[str] = field(default_factory=list)
    cost_estimate: Optional[str] = None
    
    
@dataclass
class MaintenanceSchedule:
    """Schedule for preventive maintenance"""
    task: str
    frequency: str  # e.g., "weekly", "monthly", "quarterly"
    next_due: datetime
    estimated_duration: str
    responsible_team: str
    

class RecommendationEngine:
    """
    Generates actionable recommendations based on root cause analysis results
    Provides immediate actions, preventive measures, and long-term improvements
    """
    
    def __init__(self):
        """Initialize recommendation engine with knowledge base"""
        self.knowledge_base = self._build_knowledge_base()
        self.maintenance_templates = self._build_maintenance_templates()
        
    def _build_knowledge_base(self) -> Dict[str, Dict]:
        """Build knowledge base of cause-to-recommendation mappings"""
        return {
            RootCauseType.CLIM_TOTAL_FAILURE.value: {
                'immediate_actions': [
                    {
                        'title': '🚨 Intervention d\'urgence CLIM',
                        'description': 'Toutes les unités CLIM sont hors service - risque critique pour les équipements',
                        'priority': RecommendationPriority.IMMEDIATE,
                        'type': RecommendationType.EMERGENCY_ACTION,
                        'estimated_time': '30 minutes',
                        'responsible_team': 'Équipe technique sur site',
                        'steps': [
                            'Vérifier l\'alimentation électrique des unités CLIM',
                            'Contrôler les disjoncteurs et fusibles',
                            'Redémarrer les unités si possible',
                            'Activer le plan de contingence thermique',
                            'Contacter le service de maintenance CLIM'
                        ],
                        'resources_needed': ['Multimètre', 'Clés de maintenance', 'Téléphone d\'urgence'],
                        'expected_outcome': 'Restauration partielle ou totale du refroidissement'
                    }
                ],
                'preventive_actions': [
                    {
                        'title': '🔧 Maintenance préventive CLIM renforcée',
                        'description': 'Programme de maintenance intensifié pour éviter les pannes simultanées',
                        'priority': RecommendationPriority.HIGH,
                        'type': RecommendationType.PREVENTIVE_MAINTENANCE,
                        'estimated_time': '4 heures',
                        'responsible_team': 'Service maintenance',
                        'steps': [
                            'Planifier maintenance échelonnée des unités',
                            'Contrôler état des filtres et échangeurs',
                            'Vérifier les capteurs de température',
                            'Tester les systèmes de démarrage automatique'
                        ]
                    }
                ]
            },
            
            RootCauseType.CLIM_PARTIAL_FAILURE.value: {
                'immediate_actions': [
                    {
                        'title': '⚡ Diagnostic unités CLIM défaillantes',
                        'description': 'Identifier et réparer les unités CLIM en panne',
                        'priority': RecommendationPriority.URGENT,
                        'type': RecommendationType.EMERGENCY_ACTION,
                        'estimated_time': '1-2 heures',
                        'responsible_team': 'Technicien CLIM',
                        'steps': [
                            'Identifier les unités spécifiquement en panne',
                            'Vérifier l\'alimentation électrique de chaque unité',
                            'Contrôler les commandes et capteurs',
                            'Effectuer redémarrage si nécessaire',
                            'Documenter les défaillances'
                        ],
                        'resources_needed': ['Outils de diagnostic', 'Pièces de rechange courantes'],
                        'expected_outcome': 'Restauration des unités défaillantes'
                    }
                ]
            },
            
            RootCauseType.DOOR_EXTENDED_OPEN.value: {
                'immediate_actions': [
                    {
                        'title': '🚪 Vérification système de fermeture',
                        'description': 'Contrôler et réparer le système de fermeture automatique des portes',
                        'priority': RecommendationPriority.URGENT,
                        'type': RecommendationType.EMERGENCY_ACTION,
                        'estimated_time': '45 minutes',
                        'responsible_team': 'Équipe sécurité/maintenance',
                        'steps': [
                            'Vérifier le fonctionnement du ferme-porte automatique',
                            'Contrôler les capteurs de porte',
                            'Ajuster la temporisation de fermeture',
                            'Tester les alertes de porte ouverte'
                        ]
                    }
                ],
                'preventive_actions': [
                    {
                        'title': '👥 Formation du personnel',
                        'description': 'Sensibilisation aux procédures d\'accès et impact thermique',
                        'priority': RecommendationPriority.MEDIUM,
                        'type': RecommendationType.TRAINING_REQUIRED,
                        'estimated_time': '2 heures',
                        'responsible_team': 'Responsable sécurité',
                        'steps': [
                            'Organiser session de sensibilisation',
                            'Rappeler les procédures d\'accès',
                            'Expliquer l\'impact thermique des portes ouvertes',
                            'Installer signalisation de rappel'
                        ]
                    }
                ]
            },
            
            RootCauseType.EXTERNAL_HEAT_WAVE.value: {
                'immediate_actions': [
                    {
                        'title': '❄️ Renforcement refroidissement',
                        'description': 'Optimiser la capacité de refroidissement face à la chaleur externe',
                        'priority': RecommendationPriority.HIGH,
                        'type': RecommendationType.CONFIGURATION_CHANGE,
                        'estimated_time': '1 heure',
                        'responsible_team': 'Opérateur technique',
                        'steps': [
                            'Réduire les consignes de température si possible',
                            'Optimiser la circulation d\'air',
                            'Vérifier l\'isolation des entrées d\'air',
                            'Surveiller de près les prévisions météo'
                        ]
                    }
                ],
                'long_term_actions': [
                    {
                        'title': '🏗️ Amélioration isolation thermique',
                        'description': 'Renforcer l\'isolation du bâtiment contre les variations externes',
                        'priority': RecommendationPriority.LOW,
                        'type': RecommendationType.INFRASTRUCTURE_UPGRADE,
                        'estimated_time': '1 semaine',
                        'responsible_team': 'Bureau d\'études',
                        'cost_estimate': '5000-15000 EUR'
                    }
                ]
            },
            
            RootCauseType.IT_POWER_SURGE.value: {
                'immediate_actions': [
                    {
                        'title': '💻 Analyse charge IT',
                        'description': 'Identifier et équilibrer les équipements à forte consommation',
                        'priority': RecommendationPriority.HIGH,
                        'type': RecommendationType.CONFIGURATION_CHANGE,
                        'estimated_time': '2 heures',
                        'responsible_team': 'Administrateur système',
                        'steps': [
                            'Identifier les équipements à forte charge',
                            'Vérifier les tâches de calcul intensives',
                            'Équilibrer la distribution de charge',
                            'Planifier les tâches gourmandes aux heures fraîches'
                        ]
                    }
                ]
            }
        }
        
    def _build_maintenance_templates(self) -> Dict[str, MaintenanceSchedule]:
        """Build templates for recurring maintenance tasks"""
        base_date = datetime.now()
        
        return {
            'clim_filter_check': MaintenanceSchedule(
                task='Contrôle et nettoyage filtres CLIM',
                frequency='monthly',
                next_due=base_date + timedelta(days=30),
                estimated_duration='2 heures',
                responsible_team='Service maintenance'
            ),
            'temperature_sensor_calibration': MaintenanceSchedule(
                task='Étalonnage capteurs de température',
                frequency='quarterly',
                next_due=base_date + timedelta(days=90),
                estimated_duration='4 heures',
                responsible_team='Service métrologie'
            ),
            'door_system_check': MaintenanceSchedule(
                task='Vérification système fermeture portes',
                frequency='monthly',
                next_due=base_date + timedelta(days=30),
                estimated_duration='1 heure',
                responsible_team='Service sécurité'
            ),
            'power_analysis': MaintenanceSchedule(
                task='Analyse consommation énergétique',
                frequency='weekly',
                next_due=base_date + timedelta(days=7),
                estimated_duration='30 minutes',
                responsible_team='Responsable énergie'
            )
        }
    
    def generate_recommendations(self, 
                               root_causes: List[RootCause],
                               incident_severity: str = "medium",
                               historical_data: Optional[pd.DataFrame] = None) -> List[Recommendation]:
        """
        Generate prioritized recommendations based on root causes
        
        Args:
            root_causes: List of identified root causes
            incident_severity: Severity level of the incident
            historical_data: Optional historical data for pattern analysis
            
        Returns:
            List of recommendations sorted by priority
        """
        recommendations = []
        
        # Generate recommendations for each root cause
        for cause in root_causes:
            cause_recommendations = self._get_recommendations_for_cause(cause, incident_severity)
            recommendations.extend(cause_recommendations)
            
        # Add pattern-based recommendations if historical data available
        if historical_data is not None:
            pattern_recommendations = self._analyze_patterns_and_recommend(root_causes, historical_data)
            recommendations.extend(pattern_recommendations)
            
        # Remove duplicates and prioritize
        unique_recommendations = self._deduplicate_recommendations(recommendations)
        prioritized_recommendations = self._prioritize_recommendations(unique_recommendations, incident_severity)
        
        return prioritized_recommendations
        
    def _get_recommendations_for_cause(self, cause: RootCause, severity: str) -> List[Recommendation]:
        """Get recommendations for a specific root cause"""
        recommendations = []
        cause_key = cause.cause_type.value
        
        if cause_key not in self.knowledge_base:
            # Generic recommendation for unknown causes
            return [Recommendation(
                title='🔍 Investigation approfondie requise',
                description=f'Cause non standard détectée: {cause.description}',
                priority=RecommendationPriority.HIGH,
                type=RecommendationType.EMERGENCY_ACTION,
                estimated_time='1 heure',
                responsible_team='Expert technique',
                steps=['Analyser les données en détail', 'Consulter la documentation technique'],
                related_causes=[cause_key]
            )]
            
        cause_kb = self.knowledge_base[cause_key]
        
        # Add immediate actions
        if 'immediate_actions' in cause_kb:
            for action in cause_kb['immediate_actions']:
                rec = self._create_recommendation_from_template(action, cause)
                recommendations.append(rec)
                
        # Add preventive actions if not critical severity
        if severity != "critical" and 'preventive_actions' in cause_kb:
            for action in cause_kb['preventive_actions']:
                rec = self._create_recommendation_from_template(action, cause)
                recommendations.append(rec)
                
        # Add long-term actions for recurring issues
        if cause.confidence > 70 and 'long_term_actions' in cause_kb:
            for action in cause_kb['long_term_actions']:
                rec = self._create_recommendation_from_template(action, cause)
                recommendations.append(rec)
                
        return recommendations
        
    def _create_recommendation_from_template(self, template: Dict, cause: RootCause) -> Recommendation:
        """Create recommendation object from template"""
        return Recommendation(
            title=template['title'],
            description=template['description'],
            priority=template['priority'],
            type=template['type'],
            estimated_time=template['estimated_time'],
            responsible_team=template['responsible_team'],
            steps=template.get('steps', []),
            resources_needed=template.get('resources_needed', []),
            expected_outcome=template.get('expected_outcome', ''),
            related_causes=[cause.cause_type.value],
            cost_estimate=template.get('cost_estimate')
        )
        
    def _analyze_patterns_and_recommend(self, causes: List[RootCause], data: pd.DataFrame) -> List[Recommendation]:
        """Analyze historical patterns and generate additional recommendations"""
        recommendations = []
        
        # Check for recurring cause patterns
        cause_types = [c.cause_type.value for c in causes]
        
        # If CLIM issues are frequent, recommend infrastructure review
        clim_causes = [c for c in cause_types if 'clim' in c]
        if len(clim_causes) > 0:
            recommendations.append(Recommendation(
                title='📊 Audit système CLIM',
                description='Incidents CLIM récurrents détectés - audit complet recommandé',
                priority=RecommendationPriority.MEDIUM,
                type=RecommendationType.PREVENTIVE_MAINTENANCE,
                estimated_time='1 jour',
                responsible_team='Bureau d\'études',
                steps=[
                    'Analyser l\'historique des pannes CLIM',
                    'Évaluer l\'âge et l\'état des équipements',
                    'Calculer le ROI d\'un remplacement',
                    'Proposer un plan de modernisation'
                ],
                related_causes=clim_causes
            ))
            
        # Check for seasonal patterns
        if len(data) > 24*7:  # More than a week of data
            seasonal_rec = self._analyze_seasonal_patterns(data)
            if seasonal_rec:
                recommendations.append(seasonal_rec)
                
        return recommendations
        
    def _analyze_seasonal_patterns(self, data: pd.DataFrame) -> Optional[Recommendation]:
        """Analyze seasonal patterns in the data"""
        if 'T°C EXTERIEURE' not in data.columns:
            return None
            
        # Simple seasonal analysis - could be enhanced
        avg_ext_temp = data['T°C EXTERIEURE'].mean()
        
        if avg_ext_temp > 32:  # Hot period
            return Recommendation(
                title='🌡️ Préparation période chaude',
                description='Températures extérieures élevées détectées - renforcer la préparation',
                priority=RecommendationPriority.MEDIUM,
                type=RecommendationType.PREVENTIVE_MAINTENANCE,
                estimated_time='4 heures',
                responsible_team='Service maintenance',
                steps=[
                    'Vérifier la capacité de refroidissement maximale',
                    'Nettoyer les échangeurs externes',
                    'Contrôler les niveaux de fluide frigorigène',
                    'Prévoir des ventilateurs d\'appoint si nécessaire'
                ]
            )
        return None
        
    def _deduplicate_recommendations(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """Remove duplicate recommendations based on title"""
        seen_titles = set()
        unique_recommendations = []
        
        for rec in recommendations:
            if rec.title not in seen_titles:
                seen_titles.add(rec.title)
                unique_recommendations.append(rec)
            else:
                # Merge related causes for duplicates
                existing = next(r for r in unique_recommendations if r.title == rec.title)
                existing.related_causes.extend(rec.related_causes)
                existing.related_causes = list(set(existing.related_causes))  # Remove duplicates
                
        return unique_recommendations
        
    def _prioritize_recommendations(self, recommendations: List[Recommendation], severity: str) -> List[Recommendation]:
        """Sort recommendations by priority and adjust based on incident severity"""
        
        # Priority order mapping
        priority_order = {
            RecommendationPriority.IMMEDIATE: 1,
            RecommendationPriority.URGENT: 2,
            RecommendationPriority.HIGH: 3,
            RecommendationPriority.MEDIUM: 4,
            RecommendationPriority.LOW: 5
        }
        
        # Adjust priorities based on incident severity
        if severity == "critical":
            for rec in recommendations:
                if rec.priority in [RecommendationPriority.HIGH, RecommendationPriority.URGENT]:
                    rec.priority = RecommendationPriority.IMMEDIATE
                elif rec.priority == RecommendationPriority.MEDIUM:
                    rec.priority = RecommendationPriority.URGENT
                    
        elif severity == "high":
            for rec in recommendations:
                if rec.priority == RecommendationPriority.HIGH:
                    rec.priority = RecommendationPriority.URGENT
                elif rec.priority == RecommendationPriority.MEDIUM:
                    rec.priority = RecommendationPriority.HIGH
                    
        # Sort by priority
        return sorted(recommendations, key=lambda r: priority_order[r.priority])
        
    def generate_maintenance_schedule(self, 
                                    causes: List[RootCause],
                                    horizon_days: int = 90) -> List[MaintenanceSchedule]:
        """
        Generate maintenance schedule based on identified issues
        
        Args:
            causes: Root causes to address
            horizon_days: Planning horizon in days
            
        Returns:
            List of scheduled maintenance tasks
        """
        schedule = []
        base_date = datetime.now()
        end_date = base_date + timedelta(days=horizon_days)
        
        # Add relevant maintenance tasks based on causes
        cause_types = [c.cause_type.value for c in causes]
        
        for cause_type in cause_types:
            if 'clim' in cause_type:
                # Add CLIM-related maintenance
                clim_tasks = ['clim_filter_check', 'temperature_sensor_calibration']
                for task_key in clim_tasks:
                    if task_key in self.maintenance_templates:
                        task = self.maintenance_templates[task_key]
                        if task.next_due <= end_date:
                            schedule.append(task)
                            
            elif 'door' in cause_type:
                # Add door-related maintenance
                if 'door_system_check' in self.maintenance_templates:
                    task = self.maintenance_templates['door_system_check']
                    if task.next_due <= end_date:
                        schedule.append(task)
                        
            elif 'power' in cause_type:
                # Add power analysis
                if 'power_analysis' in self.maintenance_templates:
                    task = self.maintenance_templates['power_analysis']
                    if task.next_due <= end_date:
                        schedule.append(task)
                        
        # Sort by due date
        return sorted(schedule, key=lambda s: s.next_due)
        
    def format_recommendations_for_display(self, recommendations: List[Recommendation]) -> str:
        """Format recommendations for text display"""
        if not recommendations:
            return "Aucune recommandation spécifique - surveillance continue recommandée."
            
        output = []
        
        # Group by priority
        by_priority = {}
        for rec in recommendations:
            priority = rec.priority.value
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append(rec)
            
        # Priority order for display
        priority_order = ['immediate', 'urgent', 'high', 'medium', 'low']
        priority_labels = {
            'immediate': '🚨 ACTIONS IMMÉDIATES',
            'urgent': '⚡ ACTIONS URGENTES', 
            'high': '🔴 HAUTE PRIORITÉ',
            'medium': '🟡 PRIORITÉ MOYENNE',
            'low': '🟢 ACTIONS PRÉVENTIVES'
        }
        
        for priority in priority_order:
            if priority in by_priority:
                output.append(f"\n{priority_labels[priority]}")
                output.append("=" * 50)
                
                for i, rec in enumerate(by_priority[priority], 1):
                    output.append(f"\n{i}. {rec.title}")
                    output.append(f"   Équipe: {rec.responsible_team}")
                    output.append(f"   Durée estimée: {rec.estimated_time}")
                    output.append(f"   Description: {rec.description}")
                    
                    if rec.steps:
                        output.append("   Étapes:")
                        for step in rec.steps:
                            output.append(f"   • {step}")
                            
                    if rec.resources_needed:
                        resources = ", ".join(rec.resources_needed)
                        output.append(f"   Ressources: {resources}")
                        
                    if rec.cost_estimate:
                        output.append(f"   Coût estimé: {rec.cost_estimate}")
                        
        return "\n".join(output)
        
    def export_recommendations_to_json(self, recommendations: List[Recommendation]) -> Dict[str, Any]:
        """Export recommendations to JSON format"""
        return {
            'generated_at': datetime.now().isoformat(),
            'total_recommendations': len(recommendations),
            'recommendations': [
                {
                    'title': rec.title,
                    'description': rec.description,
                    'priority': rec.priority.value,
                    'type': rec.type.value,
                    'estimated_time': rec.estimated_time,
                    'responsible_team': rec.responsible_team,
                    'steps': rec.steps,
                    'resources_needed': rec.resources_needed,
                    'expected_outcome': rec.expected_outcome,
                    'related_causes': rec.related_causes,
                    'cost_estimate': rec.cost_estimate
                }
                for rec in recommendations
            ]
        }