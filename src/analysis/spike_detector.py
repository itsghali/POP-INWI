import pandas as pd

def detect_spikes(df: pd.DataFrame, column: str, is_high: bool, global_range_params: dict, min_excursion: float):
    """
    Detects high or low spikes in a given column of a DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame with 'Timestamp' and the target column.
        column (str): The name of the column to detect spikes in (e.g., 'Temp_Ambiante').
        is_high (bool): True for high spikes, False for low spikes.
        global_range_params (dict): Dictionary containing 'global_max' and 'global_min'.
        min_excursion (float): Minimum excursion from the global range to be considered a spike.

    Returns:
        pd.DataFrame: A DataFrame of detected spikes with relevant information.
    """
    if df.empty or column not in df.columns:
        return pd.DataFrame()

    global_max = global_range_params.get('global_max', 0)
    global_min = global_range_params.get('global_min', 0)

    if is_high:
        candidates = df[df[column] > global_max + min_excursion].copy()
    else:
        candidates = df[df[column] < global_min - min_excursion].copy()

    if candidates.empty:
        return pd.DataFrame()

    candidates = candidates.sort_values('Timestamp')
    candidates['gap'] = candidates['Timestamp'].diff() > pd.Timedelta(minutes=30)
    candidates['cluster'] = candidates['gap'].cumsum()

    spikes_list = []
    for _, cluster in candidates.groupby('cluster'):
        if is_high:
            peak_row = cluster.loc[cluster[column].idxmax()]
            excursion = peak_row[column] - global_max
        else:
            peak_row = cluster.loc[cluster[column].idxmin()]
            excursion = global_min - peak_row[column]

        duration = (cluster['Timestamp'].max() - cluster['Timestamp'].min()).total_seconds() / 60
        spikes_list.append({
            'spike_time': peak_row['Timestamp'],
            'spike_temp': peak_row[column],
            'duration_min': duration,
            'range_max' if is_high else 'range_min': global_max if is_high else global_min,
            'excursion': excursion
        })

    return pd.DataFrame(spikes_list)

def calculate_temperature_range_and_excursion(df: pd.DataFrame, column: str, window_size: int = 10, std_multiplier: float = 1.5, quantile_high: float = 0.85, quantile_low: float = 0.15, min_excursion_factor: float = 0.1):
    """
    Calculates the global temperature range and minimum excursion for spike detection.

    Args:
        df (pd.DataFrame): The input DataFrame with 'Timestamp' and the target column.
        column (str): The name of the temperature column (e.g., 'Temp_Ambiante').
        window_size (int): Rolling window size for standard deviation calculation.
        std_multiplier (float): Multiplier for median standard deviation to determine stability threshold.
        quantile_high (float): Quantile for global max if stable data is insufficient.
        quantile_low (float): Quantile for global min if stable data is insufficient.
        min_excursion_factor (float): Factor to calculate MIN_EXCURSION from range amplitude.

    Returns:
        tuple: (global_max, global_min, MIN_EXCURSION)
    """
    if df.empty or column not in df.columns:
        return 0, 0, 0

    df_sorted = df.sort_values("Timestamp").reset_index(drop=True)
    df_sorted['rolling_std'] = df_sorted[column].rolling(window=window_size, center=True).std()
    std_threshold = df_sorted['rolling_std'].median() * std_multiplier
    df_sorted['is_ranging'] = df_sorted['rolling_std'] < std_threshold

    stable_data = df_sorted[df_sorted['is_ranging']]
    if not stable_data.empty and len(stable_data) >= window_size:
        global_max = stable_data[column].max()
        global_min = stable_data[column].min()
    else:
        global_max = df_sorted[column].quantile(quantile_high)
        global_min = df_sorted[column].quantile(quantile_low)

    range_amplitude = global_max - global_min
    min_excursion = max(0.5, range_amplitude * min_excursion_factor)

    return global_max, global_min, min_excursion
