"""Tests for src.services.data_cleaner."""
import pandas as pd
import numpy as np
import pytest

from src.services.data_cleaner import clean_raw_dataframe, clean_all


def _make_raw_df(timestamps, values, ts_col="Timestamp", val_col="Value"):
    return pd.DataFrame({ts_col: timestamps, val_col: values})


class TestCleanRawDataframe:
    def test_empty_dataframe(self):
        result = clean_raw_dataframe(pd.DataFrame(), "temp_ambiante")
        assert result.empty

    def test_basic_numeric_cleaning(self):
        df = _make_raw_df(
            ["2024-01-01 00:00:00", "2024-01-01 01:00:00"],
            ["22.5", "23.1"],
        )
        result = clean_raw_dataframe(df, "temp_ambiante")
        assert len(result) == 2
        assert "Timestamp" in result.columns
        assert "Value" in result.columns
        assert result["Value"].iloc[0] == pytest.approx(22.5)

    def test_clim_on_off_mapping(self):
        df = _make_raw_df(
            ["2024-01-01 00:00:00", "2024-01-01 01:00:00", "2024-01-01 02:00:00"],
            ["ON", "OFF", "MARCHE"],
        )
        result = clean_raw_dataframe(df, "clim_a")
        assert result["Value"].tolist() == [1, 0, 1]

    def test_door_status_mapping(self):
        df = _make_raw_df(
            ["2024-01-01 00:00:00", "2024-01-01 01:00:00"],
            ["OUVERTE", "FERMÉE"],
        )
        result = clean_raw_dataframe(df, "porte")
        assert result["Value"].tolist() == [1, 0]

    def test_temperature_outlier_clamping(self):
        df = _make_raw_df(
            ["2024-01-01 00:00:00", "2024-01-01 01:00:00", "2024-01-01 02:00:00"],
            ["22.0", "99.0", "-20.0"],
        )
        result = clean_raw_dataframe(df, "temp_ambiante")
        assert result["Value"].iloc[0] == pytest.approx(22.0)
        assert pd.isna(result["Value"].iloc[1])  # > 60 → NaN
        assert pd.isna(result["Value"].iloc[2])  # < -10 → NaN

    def test_power_negative_clamped_to_zero(self):
        df = _make_raw_df(
            ["2024-01-01 00:00:00", "2024-01-01 01:00:00"],
            ["5.0", "-1.0"],
        )
        result = clean_raw_dataframe(df, "puissance_generale")
        assert result["Value"].iloc[1] == 0

    def test_drops_region_pop_columns(self):
        df = pd.DataFrame({
            "Timestamp": ["2024-01-01 00:00:00"],
            "Value": ["22.0"],
            "region": ["Casablanca"],
            "pop": ["BEN-MCO"],
        })
        result = clean_raw_dataframe(df, "temp_ambiante")
        assert "region" not in result.columns
        assert "pop" not in result.columns

    def test_deduplicates_on_timestamp(self):
        df = _make_raw_df(
            ["2024-01-01 00:00:00", "2024-01-01 00:00:00"],
            ["22.0", "23.0"],
        )
        result = clean_raw_dataframe(df, "temp_ambiante")
        assert len(result) == 1
        # Keeps last
        assert result["Value"].iloc[0] == pytest.approx(23.0)


class TestCleanAll:
    def test_excludes_empty_results(self):
        raw = {
            "temp_ambiante": _make_raw_df(
                ["2024-01-01 00:00:00"], ["22.0"]
            ),
            "temp_exterieure": pd.DataFrame(),  # Empty
        }
        result = clean_all(raw)
        assert "temp_ambiante" in result
        assert "temp_exterieure" not in result
