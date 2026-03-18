"""
Incident Lens Service — Business logic extracted from incident_lens_ui.py.

Contains:
- Daily incident grouping/clustering
- Severity ranking
- Time window utilities
- Analysis orchestration

All functions are pure (no Streamlit dependencies), making them testable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from src.incident_lens.detector import Incident, IncidentSeverity, IncidentType

logger = logging.getLogger(__name__)


# ---------- Severity helpers ----------

_SEVERITY_RANK = {
    IncidentSeverity.INFO: 1,
    IncidentSeverity.WARNING: 2,
    IncidentSeverity.CRITICAL: 3,
    IncidentSeverity.EMERGENCY: 4,
}


def severity_rank(severity: IncidentSeverity) -> int:
    """Return sortable rank for severity."""
    return _SEVERITY_RANK.get(severity, 0)


# ---------- Daily grouping ----------

def group_incidents_by_day(incidents: list[Incident]) -> list[Incident]:
    """Group ALL incidents into ONE unified incident per calendar day.

    This replaces the 1365-line function from incident_lens_ui.py.
    Logic:
    - Group by calendar day
    - Identify primary ROOT CAUSE (not temperature symptom)
    - Merge durations and metrics
    - Preserve temperature as symptom info
    """
    if not incidents:
        return []

    sorted_incidents = sorted(incidents, key=lambda x: x.timestamp)

    daily_groups: dict = {}
    for inc in sorted_incidents:
        day = inc.timestamp.date()
        daily_groups.setdefault(day, []).append(inc)

    grouped = []
    for day in sorted(daily_groups.keys()):
        merged = _create_daily_incident(daily_groups[day])
        if merged:
            grouped.append(merged)
    return grouped


def _create_daily_incident(group: list[Incident]) -> Incident | None:
    """Create a single unified incident for all incidents of one day."""
    if not group:
        return None

    temp_high = [i for i in group if i.type == IncidentType.TEMPERATURE_HIGH]
    temp_low = [i for i in group if i.type == IncidentType.TEMPERATURE_LOW]
    other = [
        i for i in group
        if i.type not in (IncidentType.TEMPERATURE_HIGH, IncidentType.TEMPERATURE_LOW)
    ]

    # Determine primary type: prefer root cause over temperature symptom
    primary_incident, primary_type, primary_metric, threshold = _pick_primary(
        group, temp_high, temp_low, other
    )

    # Temperature symptom info
    temp_symptom = None
    if temp_high:
        temps = [i.metric_value for i in temp_high]
        temp_symptom = {"type": "high", "max": max(temps), "count": len(temp_high)}
    elif temp_low:
        temps = [i.metric_value for i in temp_low]
        temp_symptom = {"type": "low", "min": min(temps), "count": len(temp_low)}

    # Severity: highest in group
    max_severity = max(group, key=lambda i: severity_rank(i.severity)).severity

    # Duration
    num_points = len(group)
    duration_seconds = num_points * 900  # 15 min per point

    # Cause breakdown
    causes_dict: dict[str, int] = {}
    for inc in group:
        label = inc.type.value.replace("_", " ").title()
        causes_dict[label] = causes_dict.get(label, 0) + 1

    # Failed CLIMs
    failed_clims = _extract_failed_clims(group)

    causes_str = ", ".join(f"{t} ({c})" for t, c in causes_dict.items())
    day_str = group[0].timestamp.strftime("%Y-%m-%d")
    desc = f"Jour {day_str}: {causes_str} ({num_points} points)"

    # Resolve enum type
    try:
        incident_type_enum = IncidentType[primary_type.upper()]
    except (KeyError, AttributeError):
        incident_type_enum = primary_incident.type

    context = {
        "daily_incident": True,
        "causes": causes_dict,
        "num_alerts": len(group),
        "primary_type": primary_type,
        "temp_symptom": temp_symptom,
        "all_incidents": group,
    }
    if failed_clims:
        context["failed_units"] = sorted(failed_clims)

    return Incident(
        id=f"DAILY_UNIFIED_{day_str.replace('-', '')}",
        timestamp=group[0].timestamp,
        type=incident_type_enum,
        severity=max_severity,
        metric_name=primary_incident.metric_name,
        metric_value=primary_metric,
        threshold_violated=threshold,
        duration_seconds=duration_seconds,
        affected_systems=["COOLING"],
        description=desc,
        context=context,
    )


def _pick_primary(group, temp_high, temp_low, other):
    """Determine primary incident type and values."""
    if other:
        cause_counts: dict[str, list] = {}
        for inc in other:
            cause_counts.setdefault(inc.type.value, []).append(inc)
        most_frequent = max(cause_counts.items(), key=lambda x: len(x[1]))
        primary = most_frequent[1][0]
        return primary, primary.type.value, primary.metric_value, primary.threshold_violated

    if temp_high:
        temps = [i.metric_value for i in temp_high]
        return temp_high[0], "temperature_high", max(temps), temp_high[0].threshold_violated

    if temp_low:
        temps = [i.metric_value for i in temp_low]
        return temp_low[0], "temperature_low", min(temps), temp_low[0].threshold_violated

    first = group[0]
    return first, first.type.value, first.metric_value, first.threshold_violated


def _extract_failed_clims(group: list[Incident]) -> set[str]:
    """Extract unique failed CLIM unit names from a group of incidents."""
    failed: set[str] = set()
    clim_types = {"clim_failure", "clim_degraded"}
    for inc in group:
        if inc.type.value in clim_types:
            ctx = inc.context if isinstance(inc.context, dict) else {}
            for unit in ctx.get("failed_units", []):
                failed.add(unit.replace("_Status", "").replace("CLIM_", ""))
            if inc.affected_systems:
                for sys_name in inc.affected_systems:
                    if sys_name not in ("COOLING", "ALL_CLIM_UNITS") and "CLIM" in sys_name:
                        failed.add(sys_name.replace("CLIM_", ""))
    return failed


# ---------- Time-based clustering ----------

def cluster_incidents_by_time(
    incidents: list[dict[str, Any]],
    time_gap_minutes: int = 30,
    temp_min: float = 20.0,
    temp_max: float = 26.0,
) -> list[dict[str, Any]]:
    """Cluster incidents by temporal proximity and temperature anomaly state."""
    if not incidents:
        return []

    sorted_incs = sorted(
        incidents,
        key=lambda x: x["incident"].timestamp if x.get("incident") else datetime.min,
    )

    clusters: list[dict] = []
    current: dict | None = None
    gap = timedelta(minutes=time_gap_minutes)

    for result in sorted_incs:
        inc = result.get("incident")
        if not inc:
            continue
        is_anomaly = inc.metric_value < temp_min or inc.metric_value > temp_max

        if current is None:
            if is_anomaly:
                current = _new_cluster(result, inc)
        else:
            time_since = inc.timestamp - current["end_time"]
            if time_since <= gap and is_anomaly:
                _extend_cluster(current, result, inc)
            else:
                clusters.append(_finalize_cluster(current, len(clusters) + 1))
                current = _new_cluster(result, inc) if is_anomaly else None

    if current:
        clusters.append(_finalize_cluster(current, len(clusters) + 1))
    return clusters


def _new_cluster(result: dict, inc: Incident) -> dict:
    return {
        "start_time": inc.timestamp,
        "end_time": inc.timestamp,
        "incident_results": [result],
        "temperatures": [inc.metric_value],
        "types": [inc.type.value],
        "severities": [inc.severity.value],
    }


def _extend_cluster(cluster: dict, result: dict, inc: Incident) -> None:
    cluster["end_time"] = inc.timestamp
    cluster["incident_results"].append(result)
    cluster["temperatures"].append(inc.metric_value)
    cluster["types"].append(inc.type.value)
    cluster["severities"].append(inc.severity.value)


def _finalize_cluster(cluster: dict, cluster_id: int) -> dict:
    type_counts: dict[str, int] = {}
    for t in cluster["types"]:
        type_counts[t] = type_counts.get(t, 0) + 1
    dominant = max(type_counts, key=type_counts.get) if type_counts else "unknown"

    sev_order = {"critical": 3, "warning": 2, "info": 1}
    max_sev = max(cluster["severities"], key=lambda s: sev_order.get(s, 0))

    duration = cluster["end_time"] - cluster["start_time"]
    duration_min = max(1, int(duration.total_seconds() / 60)) if len(cluster["incident_results"]) > 1 else 0

    return {
        "cluster_id": cluster_id,
        "start_time": cluster["start_time"],
        "end_time": cluster["end_time"],
        "incident_results": cluster["incident_results"],
        "occurrence_count": len(cluster["incident_results"]),
        "temp_min": min(cluster["temperatures"]),
        "temp_max": max(cluster["temperatures"]),
        "dominant_type": dominant,
        "severity": max_sev,
        "duration_minutes": duration_min,
    }
