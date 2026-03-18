"""Tests for src.features.incident_lens.service."""
from datetime import datetime
import pytest

from src.incident_lens.detector import Incident, IncidentType, IncidentSeverity
from src.features.incident_lens.service import (
    severity_rank,
    group_incidents_by_day,
)


def _make_incident(
    ts: str,
    inc_type: IncidentType = IncidentType.TEMPERATURE_HIGH,
    severity: IncidentSeverity = IncidentSeverity.WARNING,
    value: float = 28.0,
    threshold: float = 26.0,
) -> Incident:
    return Incident(
        id=f"test_{ts}",
        timestamp=datetime.fromisoformat(ts),
        type=inc_type,
        severity=severity,
        metric_name="T°C AMBIANTE",
        metric_value=value,
        threshold_violated=threshold,
    )


class TestSeverityRank:
    def test_ordering(self):
        assert severity_rank(IncidentSeverity.INFO) < severity_rank(IncidentSeverity.WARNING)
        assert severity_rank(IncidentSeverity.WARNING) < severity_rank(IncidentSeverity.CRITICAL)
        assert severity_rank(IncidentSeverity.CRITICAL) < severity_rank(IncidentSeverity.EMERGENCY)


class TestGroupIncidentsByDay:
    def test_empty_list(self):
        assert group_incidents_by_day([]) == []

    def test_single_incident(self):
        inc = _make_incident("2024-01-15T10:00:00")
        result = group_incidents_by_day([inc])
        assert len(result) == 1
        assert result[0].timestamp.date().isoformat() == "2024-01-15"

    def test_same_day_grouped(self):
        incidents = [
            _make_incident("2024-01-15T08:00:00"),
            _make_incident("2024-01-15T12:00:00"),
            _make_incident("2024-01-15T16:00:00"),
        ]
        result = group_incidents_by_day(incidents)
        assert len(result) == 1  # All same day → 1 merged incident

    def test_different_days_separate(self):
        incidents = [
            _make_incident("2024-01-15T10:00:00"),
            _make_incident("2024-01-16T10:00:00"),
        ]
        result = group_incidents_by_day(incidents)
        assert len(result) == 2

    def test_mixed_types_pick_root_cause(self):
        incidents = [
            _make_incident("2024-01-15T10:00:00", IncidentType.TEMPERATURE_HIGH),
            _make_incident(
                "2024-01-15T10:15:00",
                IncidentType.CLIM_FAILURE,
                IncidentSeverity.CRITICAL,
                value=0,
                threshold=1,
            ),
        ]
        result = group_incidents_by_day(incidents)
        assert len(result) == 1
        # Should pick CLIM_FAILURE as primary (root cause), not temperature
        assert result[0].type == IncidentType.CLIM_FAILURE

    def test_highest_severity_preserved(self):
        incidents = [
            _make_incident("2024-01-15T10:00:00", severity=IncidentSeverity.WARNING),
            _make_incident("2024-01-15T11:00:00", severity=IncidentSeverity.EMERGENCY),
        ]
        result = group_incidents_by_day(incidents)
        assert result[0].severity == IncidentSeverity.EMERGENCY
