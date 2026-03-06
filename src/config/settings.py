"""
Configuration settings for incident detection and analysis
"""

# Door event thresholds
DOOR_CYCLE_MIN_DURATION = 300  # seconds (5 minutes)
DOOR_EXTENDED_OPEN_WARNING = 300  # 5 minutes
DOOR_EXTENDED_OPEN_CRITICAL = 600  # 10 minutes

# Correlation thresholds
CORRELATION_THRESHOLD_WEAK = 0.3
CORRELATION_THRESHOLD_MODERATE = 0.5
CORRELATION_THRESHOLD_STRONG = 0.7

# Temperature thresholds (from inwi manual)
TEMP_CRITICAL_HIGH = 29.0  # °C
TEMP_WARNING_HIGH = 26.0   # °C
TEMP_OPTIMAL_RANGE = (20.0, 23.0)  # °C
TEMP_WARNING_LOW = 18.0    # °C
TEMP_CRITICAL_LOW = 16.0   # °C

# External temperature thresholds
EXTERNAL_TEMP_EXTREME_HIGH = 40.0  # °C
EXTERNAL_TEMP_HIGH = 35.0          # °C
EXTERNAL_TEMP_EXTREME_LOW = -5.0   # °C

# PUE thresholds
PUE_CRITICAL_HIGH = 2.2
PUE_WARNING_HIGH = 1.8
PUE_OPTIMAL_MAX = 1.5
PUE_THEORETICAL_MIN = 1.0

# Power thresholds
POWER_IT_CRITICAL_HIGH = 14.0  # kW
POWER_IT_WARNING_HIGH = 12.0   # kW
POWER_IT_WARNING_LOW = 8.0     # kW
POWER_IT_CRITICAL_LOW = 6.0    # kW
POWER_CHANGE_THRESHOLD = 3.0   # kW sudden change

# CLIM thresholds
CLIM_EFFICIENCY_POOR = 0.5     # 50% of total power
CLIM_EFFICIENCY_WARNING = 0.4  # 40% of total power
CLIM_EFFICIENCY_GOOD = 0.3     # 30% of total power

# Data quality thresholds
DATA_COMPLETENESS_GOOD = 0.9   # 90% data available
DATA_COMPLETENESS_ACCEPTABLE = 0.7  # 70% data available
DATA_GAP_THRESHOLD_MINUTES = 30     # Gap > 30 minutes is significant