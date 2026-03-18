"""Tests for src.domain.data_models."""
import pandas as pd
import pytest

from src.domain.data_models import (
    PopDataset,
    make_pop_id,
    validate_required_columns,
)


class TestPopDataset:
    def test_empty_dataset(self):
        ds = PopDataset(region="Test", pop="POP1", pop_id="Test_POP1", merged=pd.DataFrame())
        assert ds.is_empty
        assert ds.available_metrics == set()
        assert ds.time_min is None

    def test_dataset_with_data(self):
        df = pd.DataFrame({
            "Timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "Temp_Ambiante": [22.0, 23.0],
            "Puissance_IT": [10.0, 11.0],
        })
        ds = PopDataset(region="Casa", pop="BEN", pop_id="Casa_BEN", merged=df)
        assert not ds.is_empty
        assert "Temp_Ambiante" in ds.available_metrics
        assert "Puissance_IT" in ds.available_metrics
        assert ds.time_min is not None

    def test_inject_metadata(self):
        df = pd.DataFrame({"Timestamp": [1], "Temp_Ambiante": [22.0]})
        ds = PopDataset(region="R", pop="P", pop_id="R_P", merged=df)
        result = ds.inject_metadata()
        assert result["Region"].iloc[0] == "R"
        assert result["POP"].iloc[0] == "P"
        assert result["POP_ID"].iloc[0] == "R_P"
        # Original should not be modified
        assert "Region" not in ds.merged.columns


class TestMakePopId:
    def test_format(self):
        assert make_pop_id("Casablanca", "BEN-MCO") == "Casablanca_BEN-MCO"


class TestValidateRequiredColumns:
    def test_valid(self):
        df = pd.DataFrame({"Timestamp": [1], "Temp_Ambiante": [22.0]})
        valid, missing = validate_required_columns(df)
        assert valid
        assert missing == []

    def test_missing(self):
        df = pd.DataFrame({"Timestamp": [1]})
        valid, missing = validate_required_columns(df)
        assert not valid
        assert "Temp_Ambiante" in missing

    def test_empty_df(self):
        valid, missing = validate_required_columns(pd.DataFrame())
        assert not valid
