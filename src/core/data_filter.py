"""
Data Filtering Module
Centralizes data filtering logic for the application
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Optional


def _get_period_selector():
    """Lazy-load period selector to avoid module import failures at startup."""
    try:
        from ..ui.period_selector import period_selector
        return period_selector
    except Exception:
        return None


def filter_by_date_range(df: pd.DataFrame, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    Filter dataframe by date range
    
    Args:
        df: DataFrame with Timestamp column
        start_date: Start of date range
        end_date: End of date range
        
    Returns:
        Filtered DataFrame
    """
    if df.empty or 'Timestamp' not in df.columns:
        return df
    
    return df[(df['Timestamp'] >= start_date) & (df['Timestamp'] <= end_date)]


def get_unified_period() -> Tuple[datetime, datetime]:
    """
    Get the unified period from period_selector
    
    Returns:
        Tuple of (start_date, end_date)
    """
    selector = _get_period_selector()
    if selector is not None:
        return selector.render_mini_selector()

    # Fallback period when selector is unavailable
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    return start_date, end_date


def apply_unified_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply unified period filter to dataframe using period_selector
    
    Args:
        df: DataFrame to filter
        
    Returns:
        Filtered DataFrame based on session state period
    """
    if df.empty:
        return df

    selector = _get_period_selector()
    if selector is None:
        return df

    return selector.filter_dataframe(df)


def filter_by_column_values(df: pd.DataFrame, column: str, values: list) -> pd.DataFrame:
    """
    Filter dataframe by specific column values
    
    Args:
        df: DataFrame to filter
        column: Column name to filter on
        values: List of values to keep
        
    Returns:
        Filtered DataFrame
    """
    if df.empty or column not in df.columns:
        return df
    
    return df[df[column].isin(values)]


def filter_by_threshold(df: pd.DataFrame, column: str, min_value: Optional[float] = None, 
                       max_value: Optional[float] = None) -> pd.DataFrame:
    """
    Filter dataframe by threshold values on a numeric column
    
    Args:
        df: DataFrame to filter
        column: Column name to filter on
        min_value: Minimum threshold (inclusive)
        max_value: Maximum threshold (inclusive)
        
    Returns:
        Filtered DataFrame
    """
    if df.empty or column not in df.columns:
        return df
    
    filtered = df.copy()
    if min_value is not None:
        filtered = filtered[filtered[column] >= min_value]
    if max_value is not None:
        filtered = filtered[filtered[column] <= max_value]
    
    return filtered


def get_available_metrics(df: pd.DataFrame) -> dict:
    """
    Get available metrics from dataframe with display names
    
    Args:
        df: DataFrame to extract metrics from
        
    Returns:
        Dictionary mapping column names to display names
    """
    if df.empty:
        return {}
    
    metric_mapping = {
        'Temp_Ambiante': 'Température Ambiante',
        'Temp_Exterieure': 'Température Extérieure',
        'Puissance_IT': 'Puissance IT',
        'Puissance_Generale': 'Puissance Générale',
        'Puissance_CLIM': 'Puissance CLIM',
        'Porte_Status': 'État Porte'
    }
    
    # Add detected metrics
    available = {}
    for col in df.columns:
        if col in metric_mapping:
            available[col] = metric_mapping[col]
        elif col.startswith('CLIM_') and col.endswith('_Status'):
            # Format CLIM names nicely
            clim_name = col.replace('_Status', '').replace('_', ' ')
            available[col] = clim_name
    
    return available


def validate_data_availability(df: pd.DataFrame, required_columns: list) -> Tuple[bool, list]:
    """
    Validate that required columns are present in the dataframe
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        
    Returns:
        Tuple of (is_valid, missing_columns)
    """
    if df.empty:
        return False, required_columns
    
    missing = [col for col in required_columns if col not in df.columns]
    return len(missing) == 0, missing


def get_data_summary(df: pd.DataFrame) -> dict:
    """
    Get summary statistics for the dataframe
    
    Args:
        df: DataFrame to summarize
        
    Returns:
        Dictionary with summary statistics
    """
    if df.empty:
        return {
            'rows': 0,
            'start_date': None,
            'end_date': None,
            'columns': []
        }
    
    summary = {
        'rows': len(df),
        'columns': df.columns.tolist()
    }
    
    if 'Timestamp' in df.columns:
        summary['start_date'] = df['Timestamp'].min()
        summary['end_date'] = df['Timestamp'].max()
        summary['duration_days'] = (summary['end_date'] - summary['start_date']).days
    
    return summary
