"""
Incident Lens - Root Cause Analysis Module
Automated incident detection and root cause exploration for data center operations
"""
''
from .detector import IncidentDetector
try:
    from .analyzer import RootCauseAnalyzer
except ImportError:
    pass
try:
    from .recommender import RecommendationEngine
except ImportError:
    pass

__version__ = "1.0.0"
__all__ = ['IncidentDetector', 'RootCauseAnalyzer', 'RecommendationEngine']