"""Tests for src.services.data_merger."""
import pandas as pd
import numpy as np
import pytest

from src.services.data_merger import merge_cleaned_data


def _metric_df(timestamps, values, value_col="Value"):
    return pd.DataFrame({"Timestamp": pd.to_datetime(timestamps), value_col: values})


class TestMergeCleanedData:
    def test_empty_input(self):
        assert merge_cleaned_data({}).empty

    def test_single_metric(self):
        cleaned = {
            "temp_ambiante": _metric_df(
                ["2024-01-01 00:00", "2024-01-01 01:00"],
                [22.0, 23.0],
            )
        }
        result = merge_cleaned_data(cleaned)
        assert len(result) == 2
        assert "Temp_Ambiante" in result.columns
        assert "Timestamp" in result.columns

    def test_two_metrics_merge(self):
        cleaned = {
            "temp_ambiante": _metric_df(
                ["2024-01-01 00:00", "2024-01-01 01:00"],
                [22.0, 23.0],
            ),
            "temp_exterieure": _metric_df(
                ["2024-01-01 00:00", "2024-01-01 01:00"],
                [15.0, 16.0],
            ),
        }
        result = merge_cleaned_data(cleaned)
        assert "Temp_Ambiante" in result.columns
        assert "Temp_Exterieure" in result.columns
        assert len(result) == 2

    def test_power_it_derived(self):
        cleaned = {
            "puissance_generale": _metric_df(
                ["2024-01-01 00:00"], [10.0]
            ),
            "puissance_clim": _metric_df(
                ["2024-01-01 00:00"], [4.0]
            ),
        }
        result = merge_cleaned_data(cleaned)
        assert "Puissance_IT" in result.columns
        assert result["Puissance_IT"].iloc[0] == pytest.approx(6.0)

    def test_power_it_no_negative(self):
        cleaned = {
            "puissance_generale": _metric_df(
                ["2024-01-01 00:00"], [3.0]
            ),
            "puissance_clim": _metric_df(
                ["2024-01-01 00:00"], [5.0]
            ),
        }
        result = merge_cleaned_data(cleaned)
        assert result["Puissance_IT"].iloc[0] == 0

    def test_clim_status_columns(self):
        cleaned = {
            "clim_a": _metric_df(["2024-01-01 00:00"], [1]),
            "clim_b": _metric_df(["2024-01-01 00:00"], [0]),
        }
        result = merge_cleaned_data(cleaned)
        assert "CLIM_A_Status" in result.columns
        assert "CLIM_B_Status" in result.columns

    def test_outer_merge_different_timestamps(self):
        cleaned = {
            "temp_ambiante": _metric_df(
                ["2024-01-01 00:00", "2024-01-01 01:00"],
                [22.0, 23.0],
            ),
            "temp_exterieure": _metric_df(
                ["2024-01-01 00:30", "2024-01-01 01:30"],
                [15.0, 16.0],
            ),
        }
        result = merge_cleaned_data(cleaned)
        # Outer merge: 4 unique timestamps
        assert len(result) == 4

    def test_sorted_by_timestamp(self):
        cleaned = {
            "temp_ambiante": _metric_df(
                ["2024-01-01 02:00", "2024-01-01 00:00"],
                [23.0, 22.0],
            ),
        }
        result = merge_cleaned_data(cleaned)
        timestamps = result["Timestamp"].tolist()
        assert timestamps == sorted(timestamps)
