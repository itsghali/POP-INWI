"""
Data Preprocessor for Incident Lens
Optimizes data loading, cleaning, and preparation for fast analysis
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from pathlib import Path
import glob
import re
''
logger = logging.getLogger(__name__)


class DataPreprocessor:
    """
    High-performance data preprocessor for BGU-ONE data center monitoring
    Handles data loading, cleaning, validation, and optimization for analysis
    """
    
    def __init__(self, data_directory: str = "data", region: str = "Marrakech", site: str = "BGU-ONE"):
        """
        Initialize preprocessor
        
        Args:
            data_directory: Path to directory containing CSV files
            region: Region name (e.g., "Marrakech")
            site: Site name (e.g., "BGU-ONE")
        """
        self.data_dir = Path(data_directory)
        self.region = region
        self.site = site
        self.cached_data = None
        self.last_load_time = None
        self.file_mapping = self._discover_data_files()
        
    def _discover_data_files(self) -> Dict[str, str]:
        """Discover and map available data files"""
        if not self.data_dir.exists():
            logger.warning(f"Data directory not found: {self.data_dir}")
            return {}
            
        # Try new hierarchical structure first
        site_dir = self.data_dir / self.region / self.site
        if site_dir.exists():
            logger.info(f"Using hierarchical structure: {site_dir}")
            return self._discover_files_hierarchical(site_dir)
        else:
            logger.info(f"Site directory not found: {site_dir}, trying flat structure")
            return self._discover_files_flat()
    
    def _discover_files_hierarchical(self, site_dir: Path) -> Dict[str, str]:
        """Discover files in new hierarchical structure"""
        # New file patterns for hierarchical structure
        file_patterns = {
            'temperature_ambient': 'Température Ambiante.csv',
            'temperature_external': 'Température Extérieure.csv',
            'door_state': 'Etat Porte.csv',
            'clim_a': 'Etat CLIM A.csv',
            'clim_b': 'Etat CLIM B.csv',
            'clim_c': 'Etat CLIM C.csv',
            'clim_d': 'Etat CLIM D.csv',
            'power_clim': 'P.Active CLIM.csv',
            'power_general': 'P.Active Générale.csv',
            # 'power_it' will be calculated from total - clim power
            'generator': 'Etat GE.csv'
        }
        
        discovered_files = {}
        
        for data_type, filename in file_patterns.items():
            file_path = site_dir / filename
            if file_path.exists():
                discovered_files[data_type] = str(file_path)
                logger.info(f"Found {data_type}: {filename}")
            else:
                logger.debug(f"No file found: {filename}")
                
        return discovered_files
        
    def _discover_files_flat(self) -> Dict[str, str]:
        """Discover files in old flat structure (backward compatibility)"""
        # Old file patterns for flat structure
        file_patterns = {
            'temperature_ambient': '*T°C AMBIANTE*.csv',
            'temperature_external': '*T°C EXTERIEURE*.csv',
            'door_state': '*Etat de porte*.csv',
            'clim_a': '*Etat CLIM A*.csv',
            'clim_b': '*Etat CLIM B*.csv',
            'clim_c': '*Etat CLIM C*.csv',
            'clim_d': '*Etat CLIM D*.csv',
            'power_clim': '*P_Active CLIM*.csv',
            'power_general': '*P_Active G*n*ral*.csv',  # Handle accent variations
            # 'power_it' will be calculated from total - clim power
            'generator': '*Etat GE*.csv'
        }
        
        discovered_files = {}
        
        for data_type, pattern in file_patterns.items():
            matching_files = list(self.data_dir.glob(pattern))
            if matching_files:
                # Use the first matching file
                discovered_files[data_type] = str(matching_files[0])
                logger.info(f"Found {data_type}: {matching_files[0].name}")
            else:
                logger.debug(f"No file found for pattern: {pattern}")
                
        return discovered_files
        
    def load_data(self, 
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None,
                  force_reload: bool = False) -> pd.DataFrame:
        """
        Load and preprocess all available data files
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            force_reload: Force reload even if data is cached
            
        Returns:
            Preprocessed DataFrame with all metrics
        """
        # Check if we can use cached data
        if (not force_reload and 
            self.cached_data is not None and 
            self.last_load_time and 
            (datetime.now() - self.last_load_time).seconds < 300):  # 5 minute cache
            logger.info("Using cached data")
            return self._filter_by_date(self.cached_data, start_date, end_date)
            
        logger.info("Loading data from CSV files...")
        
        if not self.file_mapping:
            logger.error("No data files found")
            return pd.DataFrame()
            
        all_data = {}
        
        # Load each data file
        for data_type, file_path in self.file_mapping.items():
            try:
                df = self._load_single_file(file_path, data_type)
                if not df.empty:
                    all_data[data_type] = df
                    logger.debug(f"Loaded {data_type}: {len(df)} rows")
            except Exception as e:
                logger.error(f"Error loading {data_type} from {file_path}: {e}")
                
        if not all_data:
            logger.error("No data could be loaded")
            return pd.DataFrame()
            
        try:
            # Merge all data on timestamp
            merged_data = self._merge_data_sources(all_data)
            
            # Clean and validate
            cleaned_data = self._clean_data(merged_data)
            
            # Add derived metrics
            enriched_data = self._add_derived_metrics(cleaned_data)
            
        except Exception as e:
            logger.error(f"Error in data processing pipeline: {e}")
            # Return a basic merged dataset without derived metrics if processing fails
            try:
                merged_data = self._merge_data_sources(all_data)
                enriched_data = merged_data
            except Exception as e2:
                logger.error(f"Even basic merging failed: {e2}")
                # Return the first available dataset
                if all_data:
                    enriched_data = list(all_data.values())[0]
                else:
                    return pd.DataFrame()
        
        # Cache the result
        self.cached_data = enriched_data
        self.last_load_time = datetime.now()
        
        logger.info(f"Data loading complete: {len(enriched_data)} rows, {len(enriched_data.columns)} columns")
        
        return self._filter_by_date(enriched_data, start_date, end_date)
        
    def _load_single_file(self, file_path: str, data_type: str) -> pd.DataFrame:
        """Load and parse a single CSV file with robust format detection"""
        try:
            df = None
            file_name = Path(file_path).name
            logger.debug(f"Loading {file_name} as {data_type}")
            
            # Try multiple parsing strategies in order of likelihood
            parsing_strategies = [
                # Strategy 1: Latin-1 with history header (for temperature files)
                {'encoding': 'latin-1', 'sep': ';', 'skiprows': 2, 'header': 0},
                # Strategy 2: UTF-8-sig with history header (standard BGU-ONE)
                {'encoding': 'utf-8-sig', 'sep': ';', 'skiprows': 2, 'header': 0},
                # Strategy 3: Pipe-separated format (like CLIM D)
                {'encoding': 'utf-8-sig', 'sep': '|', 'skiprows': 0, 'header': 0},
                # Strategy 4: Direct formats without skiprows
                {'encoding': 'latin-1', 'sep': ';', 'skiprows': 0, 'header': 0},
                {'encoding': 'utf-8-sig', 'sep': ';', 'skiprows': 0, 'header': 0},
                {'encoding': 'utf-8', 'sep': ';', 'skiprows': 0, 'header': 0},
                {'encoding': 'cp1252', 'sep': ';', 'skiprows': 0, 'header': 0},
                {'encoding': 'iso-8859-1', 'sep': ';', 'skiprows': 2, 'header': 0},
            ]
            
            for strategy in parsing_strategies:
                try:
                    df = pd.read_csv(file_path, **strategy)
                    
                    # Validate the result - be more lenient
                    if (len(df.columns) >= 2 and 
                        len(df) > 0):
                        
                        # Check for timestamp-like column
                        has_timestamp = any(
                            any(keyword in str(col).lower() for keyword in ['timestamp', 'time', 'date']) 
                            for col in df.columns
                        )
                        
                        if has_timestamp:
                            logger.debug(f"Successfully parsed {file_name} with strategy: {strategy}")
                            break
                        else:
                            logger.debug(f"No timestamp column found in {file_name} with strategy {strategy}")
                        
                except Exception as e:
                    logger.debug(f"Strategy {strategy} failed for {file_name}: {e}")
                    continue
            else:
                raise ValueError(f"Could not parse {file_name} with any strategy")
                
            # Clean and standardize the parsed data
            df = self._clean_and_standardize_dataframe(df, data_type, file_name)
            
            if df.empty:
                logger.warning(f"Empty file after processing: {file_name}")
                return pd.DataFrame()
                
            logger.info(f"Successfully loaded {file_name}: {len(df)} rows, columns: {list(df.columns)}")
            
            # Debug logging for status files
            if data_type in ['clim_a', 'clim_b', 'clim_c', 'clim_d']:
                logger.debug(f"{data_type} sample data after loading:")
                logger.debug(df.head())
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return pd.DataFrame()
            
    def _clean_and_standardize_dataframe(self, df: pd.DataFrame, data_type: str, file_name: str) -> pd.DataFrame:
        """Clean and standardize a parsed dataframe"""
        try:
            # Skip empty rows and reset index
            df = df.dropna(how='all').reset_index(drop=True)
            
            # Find timestamp column (handle variations)
            timestamp_col = None
            for col in df.columns:
                if any(keyword in str(col).lower() for keyword in ['timestamp', 'time', 'date']):
                    timestamp_col = col
                    break
            
            if timestamp_col is None:
                logger.error(f"No timestamp column found in {file_name}. Columns: {list(df.columns)}")
                return pd.DataFrame()
            
            # Clean and parse timestamps
            df = self._parse_timestamps_robust(df, timestamp_col)
            
            # Find and clean value column
            df = self._extract_and_clean_values(df, data_type, file_name)
            
            # Add standard columns and metadata
            df = self._add_standard_columns(df, data_type)
            
            return df
            
        except Exception as e:
            logger.error(f"Error cleaning dataframe for {file_name}: {e}")
            return pd.DataFrame()
    
    def _parse_timestamps_robust(self, df: pd.DataFrame, timestamp_col: str) -> pd.DataFrame:
        """Robustly parse timestamps with multiple format support"""
        try:
            # Clean the timestamp column
            df[timestamp_col] = df[timestamp_col].astype(str)
            
            # Remove timezone info that causes issues (WEST, WET)
            df[timestamp_col] = df[timestamp_col].str.replace(r'\s+(WEST|WET)$', '', regex=True)
            
            # Parse timestamps with error handling
            df['Timestamp'] = pd.to_datetime(df[timestamp_col], errors='coerce', dayfirst=True)
            
            # Remove rows with invalid timestamps
            df = df.dropna(subset=['Timestamp'])
            
            # Drop original timestamp column if it's different from 'Timestamp'
            if timestamp_col != 'Timestamp' and timestamp_col in df.columns:
                df = df.drop(columns=[timestamp_col])
                
            return df
            
        except Exception as e:
            logger.error(f"Error parsing timestamps: {e}")
            return df
    
    def _extract_and_clean_values(self, df: pd.DataFrame, data_type: str, file_name: str) -> pd.DataFrame:
        """Extract and clean value columns"""
        try:
            # Find value column (handle variations)
            value_col = None
            for col in df.columns:
                if any(keyword in str(col).lower() for keyword in ['value', 'val']):
                    value_col = col
                    break
            
            if value_col is None:
                logger.warning(f"No value column found in {file_name}. Using last column.")
                value_col = df.columns[-1]
            
            # For status-type data (CLIM, door, etc), keep original values
            if data_type in ['clim_a', 'clim_b', 'clim_c', 'clim_d', 'door_state', 'generator']:
                df['Value'] = df[value_col]  # Keep as-is for later mapping
            else:
                # Extract numeric values for other types
                df['Value'] = pd.to_numeric(df[value_col], errors='coerce')
            
            # Extract unit from column name
            unit = self._extract_unit_from_column(value_col, data_type)
            df['Unit'] = unit
            
            # Clean status column if present
            if 'Status' in df.columns:
                df = df[df['Status'].astype(str).str.contains('ok', case=False, na=False)]
            
            # Drop original value column if different from 'Value'
            if value_col != 'Value' and value_col in df.columns:
                df = df.drop(columns=[value_col])
                
            return df
            
        except Exception as e:
            logger.error(f"Error extracting values from {file_name}: {e}")
            return df
    
    def _extract_unit_from_column(self, column_name: str, data_type: str) -> str:
        """Extract unit from column name or infer from data type"""
        # Extract unit from parentheses in column name
        unit_match = re.search(r'\(([^)]+)\)', str(column_name))
        if unit_match:
            return unit_match.group(1)
        
        # Infer unit from data type
        unit_mapping = {
            'temperature_ambient': '°C',
            'temperature_external': '°C',
            'power_clim': 'kW',
            'power_general': 'kW',
            'clim_a': 'status',
            'clim_b': 'status',
            'clim_c': 'status',
            'clim_d': 'status',
            'door_state': 'status',
            'generator': 'status'
        }
        
        return unit_mapping.get(data_type, 'unknown')
    
    def _add_standard_columns(self, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """Add standard columns and clean data"""
        try:
            # Convert status values to numeric for status type data
            if data_type in ['clim_a', 'clim_b', 'clim_c', 'clim_d', 'door_state', 'generator']:
                # Map text status to numeric
                status_mapping = {
                    'ON': 1, 'OFF': 0, 'OPEN': 1, 'CLOSED': 0,
                    'OUVERT': 1, 'FERME': 0, '1': 1, '0': 0,
                    1: 1, 0: 0, True: 1, False: 0
                }
                
                # Debug logging
                logger.debug(f"Processing {data_type}: Original values sample: {df['Value'].head()}")
                
                df['Value'] = df['Value'].astype(str).str.upper().map(status_mapping)
                
                # Debug logging
                logger.debug(f"After mapping {data_type}: {df['Value'].head()}")
                
                df['Value'] = df['Value'].fillna(0).astype(int)
                
                # Debug logging
                logger.debug(f"Final values for {data_type}: {df['Value'].head()}")
            
            # Add data type for reference
            df['data_type'] = data_type
            
            # Set timestamp as index
            if 'Timestamp' in df.columns:
                df = df.set_index('Timestamp')
            
            # Keep only essential columns
            essential_cols = ['Value', 'Unit', 'data_type']
            if 'Status' in df.columns:
                essential_cols.append('Status')
                
            df = df[[col for col in essential_cols if col in df.columns]]
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding standard columns: {e}")
            return df
            
    def _standardize_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize timestamp columns"""
        # Common timestamp column names
        timestamp_cols = ['timestamp', 'datetime', 'date', 'time', 'Date', 'Time', 'DateTime']
        
        timestamp_col = None
        for col in df.columns:
            if any(ts_name in col.lower() for ts_name in ['time', 'date']):
                timestamp_col = col
                break
                
        if timestamp_col is None and len(df.columns) > 0:
            # Assume first column is timestamp
            timestamp_col = df.columns[0]
            
        if timestamp_col:
            try:
                # Try to parse timestamp
                df[timestamp_col] = pd.to_datetime(df[timestamp_col])
                df = df.set_index(timestamp_col)
                df.index.name = 'timestamp'
                
                # Remove any duplicate timestamps
                df = df[~df.index.duplicated(keep='first')]
                
                # Sort by timestamp
                df = df.sort_index()
                
            except Exception as e:
                logger.warning(f"Could not parse timestamps in column {timestamp_col}: {e}")
                
        return df
        
    def _standardize_values(self, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """Standardize value columns based on data type"""
        # Map data types to expected column names
        column_mapping = {
            'temperature_ambient': 'T°C AMBIANTE',
            'temperature_external': 'T°C EXTERIEURE', 
            'door_state': 'Etat de porte',
            'clim_a': 'CLIM_A_Status',
            'clim_b': 'CLIM_B_Status',
            'clim_c': 'CLIM_C_Status',
            'clim_d': 'CLIM_D_Status',
            'power_clim': 'P_Active CLIM',
            'power_general': 'P_Active Générale',
            'power_it': 'Puissance_IT',
            'generator': 'GE_Status'
        }
        
        target_column = column_mapping.get(data_type, data_type)
        
        # Find the value column (usually the last or second column)
        value_columns = [col for col in df.columns if col != 'timestamp']
        
        if value_columns:
            # Use the first numeric column as the main value
            for col in value_columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    # Rename to standard name
                    if col != target_column:
                        df = df.rename(columns={col: target_column})
                    break
                except:
                    continue
                    
        return df
        
    def _merge_data_sources(self, all_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Merge all data sources with standardized column naming"""
        if not all_data:
            logger.warning("No data sources provided for merging")
            return pd.DataFrame()
            
        # Filter out empty DataFrames and ensure all have datetime indices
        valid_data = {}
        for k, v in all_data.items():
            if not v.empty and isinstance(v.index, pd.DatetimeIndex) and len(v.columns) > 0:
                valid_data[k] = v
                logger.debug(f"Valid data source {k}: {len(v)} rows, columns: {list(v.columns)}")
            else:
                logger.debug(f"Skipping {k}: empty={v.empty}, datetime_index={isinstance(v.index, pd.DatetimeIndex)}, columns={len(v.columns) if not v.empty else 0}")
        
        if not valid_data:
            logger.warning("No valid data sources found after filtering")
            return pd.DataFrame()
            
        logger.info(f"Merging {len(valid_data)} valid data sources: {list(valid_data.keys())}")
        
        # Create merged dataframe with proper column names
        merged_dfs = []
        column_mapping = {
            'temperature_ambient': 'T°C AMBIANTE',
            'temperature_external': 'T°C EXTERIEURE', 
            'power_clim': 'P_Active CLIM',
            'power_general': 'P_Active Générale',
            # 'power_it' will be calculated later from total - clim power
            'clim_a': 'CLIM_A_Status',
            'clim_b': 'CLIM_B_Status',
            'clim_c': 'CLIM_C_Status',
            'clim_d': 'CLIM_D_Status',
            'door_state': 'Etat de porte',
            'generator': 'GE_Status'
        }
        
        # Process each data source
        seen_columns = set()
        for data_type, df in valid_data.items():
            try:
                # Create a clean copy with standardized column name
                clean_df = df[['Value']].copy()
                target_column = column_mapping.get(data_type, data_type)
                
                # Skip if we've already processed this column (e.g., power_it and power_general both map to same)
                if target_column in seen_columns:
                    logger.debug(f"Skipping duplicate column mapping: {data_type} -> {target_column}")
                    continue
                    
                clean_df.columns = [target_column]
                seen_columns.add(target_column)
                
                merged_dfs.append(clean_df)
                logger.debug(f"Prepared {data_type} -> {target_column}: {len(clean_df)} rows, sample values: {clean_df[target_column].head()}")
                
            except Exception as e:
                logger.warning(f"Error processing {data_type}: {e}")
                continue
        
        if not merged_dfs:
            logger.error("No data sources could be processed for merging")
            return pd.DataFrame()
        
        # Merge all dataframes
        try:
            merged = merged_dfs[0]
            for df in merged_dfs[1:]:
                merged = merged.join(df, how='outer')
                
            logger.info(f"Successfully merged data: {len(merged)} rows, {len(merged.columns)} columns")
            logger.debug(f"Final columns: {list(merged.columns)}")
            
            # Calculate Puissance_IT properly: IT Power = Total Power - CLIM Power
            # Always recalculate to ensure correct values
            if ('P_Active Générale' in merged.columns and 
                'P_Active CLIM' in merged.columns):
                
                # Convert to numeric to handle any string values
                total_power = pd.to_numeric(merged['P_Active Générale'], errors='coerce')
                clim_power = pd.to_numeric(merged['P_Active CLIM'], errors='coerce')
                
                # Calculate IT power as Total - CLIM (with minimum of 0)
                merged['Puissance_IT'] = (total_power - clim_power).clip(lower=0)
                logger.debug("Calculated Puissance_IT as Total Power - CLIM Power")
            elif 'P_Active Générale' in merged.columns:
                # Fallback: use total power if CLIM power not available
                merged['Puissance_IT'] = merged['P_Active Générale']
                logger.debug("Using P_Active Générale as Puissance_IT (CLIM power not available)")
            
            return merged
            
        except Exception as e:
            logger.error(f"Error during final merge: {e}")
            return pd.DataFrame()
        
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate the data"""
        if df.empty:
            return df
            
        cleaned = df.copy()
        
        # Remove completely empty rows
        cleaned = cleaned.dropna(how='all')
        
        # Handle temperature data
        temp_cols = ['T°C AMBIANTE', 'T°C EXTERIEURE']
        for col in temp_cols:
            if col in cleaned.columns:
                # Remove impossible temperature values
                cleaned.loc[cleaned[col] < -50, col] = np.nan
                cleaned.loc[cleaned[col] > 70, col] = np.nan
                
                # Forward fill small gaps (up to 2 consecutive missing values) 
                cleaned[col] = cleaned[col].ffill(limit=2)
                
        # Handle binary status columns (CLIM, door, etc.)
        binary_cols = [col for col in cleaned.columns if any(x in col for x in ['CLIM', 'Etat', 'Status'])]
        for col in binary_cols:
            if col in cleaned.columns:
                # Debug logging
                logger.debug(f"Cleaning binary column {col}: sample before: {cleaned[col].head()}")
                
                # Ensure binary values (0 or 1) - only for numeric values
                # Don't round/clip if values are already 0 or 1
                cleaned[col] = pd.to_numeric(cleaned[col], errors='coerce')
                cleaned[col] = cleaned[col].round().clip(0, 1)
                
                # Forward fill status (assume status doesn't change rapidly)
                cleaned[col] = cleaned[col].ffill()
                
                # Debug logging
                logger.debug(f"Cleaning binary column {col}: sample after: {cleaned[col].head()}")
                
        # Handle power data
        power_cols = [col for col in cleaned.columns if 'Puissance' in col or 'P_Active' in col]
        for col in power_cols:
            if col in cleaned.columns:
                # Remove negative power values
                cleaned.loc[cleaned[col] < 0, col] = np.nan
                # Remove unreasonably high values (>100kW for this facility)
                cleaned.loc[cleaned[col] > 100, col] = np.nan
                # Interpolate small gaps
                cleaned[col] = cleaned[col].interpolate(method='linear', limit=3)
                
        return cleaned
        
    def _add_derived_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add computed metrics for faster analysis"""
        enriched = df.copy()
        
        
        # CLIM metrics
        clim_cols = ['CLIM_A_Status', 'CLIM_B_Status', 'CLIM_C_Status', 'CLIM_D_Status']
        available_clim = [col for col in clim_cols if col in enriched.columns]
        
        if available_clim:
            try:
                # Ensure numeric data for CLIM columns
                clim_data = enriched[available_clim].copy()
                for col in available_clim:
                    clim_data[col] = pd.to_numeric(clim_data[col], errors='coerce').fillna(0)
                
                # Count active CLIM units
                enriched['clim_active_count'] = clim_data.sum(axis=1)
                enriched['clim_availability_pct'] = (enriched['clim_active_count'] / len(available_clim)) * 100
                
                # CLIM failure indicators
                enriched['clim_total_failure'] = (enriched['clim_active_count'] == 0).astype(int)
                enriched['clim_partial_failure'] = (enriched['clim_active_count'] < len(available_clim)/2).astype(int)
            except Exception as e:
                logger.warning(f"Could not calculate CLIM metrics: {e}")
                enriched['clim_active_count'] = 0
                enriched['clim_availability_pct'] = 0
                enriched['clim_total_failure'] = 0
                enriched['clim_partial_failure'] = 0
            
        # Temperature metrics
        if 'T°C AMBIANTE' in enriched.columns and 'T°C EXTERIEURE' in enriched.columns:
            try:
                # Ensure numeric data
                temp_ambient = pd.to_numeric(enriched['T°C AMBIANTE'], errors='coerce')
                temp_external = pd.to_numeric(enriched['T°C EXTERIEURE'], errors='coerce')
                
                enriched['temp_differential'] = temp_ambient - temp_external
                
                # Rolling statistics for anomaly detection
                enriched['temp_rolling_mean'] = temp_ambient.rolling(window=4, min_periods=1).mean()
                enriched['temp_rolling_std'] = temp_ambient.rolling(window=4, min_periods=1).std()
                
                # Temperature deviation from normal
                enriched['temp_deviation'] = abs(temp_ambient - enriched['temp_rolling_mean'])
            except Exception as e:
                logger.warning(f"Could not calculate temperature metrics: {e}")
                enriched['temp_differential'] = np.nan
                enriched['temp_rolling_mean'] = np.nan
                enriched['temp_rolling_std'] = np.nan
                enriched['temp_deviation'] = np.nan
            
        # Door metrics
        if 'Etat de porte' in enriched.columns:
            try:
                # Ensure numeric data
                door_status = pd.to_numeric(enriched['Etat de porte'], errors='coerce').fillna(0)
                
                # Door open duration (rolling count)
                enriched['door_open_duration'] = door_status.rolling(window=8, min_periods=1).sum() * 15  # minutes
                
                # Door state changes (for detecting frequent opening)
                enriched['door_state_changes'] = door_status.diff().abs().rolling(window=8).sum()
            except Exception as e:
                logger.warning(f"Could not calculate door metrics: {e}")
                enriched['door_open_duration'] = 0
                enriched['door_state_changes'] = 0
            
        # Power metrics - check for both possible column names
        power_col = None
        if 'Puissance_IT' in enriched.columns:
            power_col = 'Puissance_IT'
        elif 'P_Active Générale' in enriched.columns:
            power_col = 'P_Active Générale'
            
        if power_col:
            # Ensure numeric data and handle missing values
            power_numeric = pd.to_numeric(enriched[power_col], errors='coerce')
            
            # Power change rate
            enriched['power_change_rate'] = power_numeric.diff()
            enriched['power_change_abs'] = enriched['power_change_rate'].abs()
            
            # Power level classification - only for valid numeric values
            try:
                valid_power = power_numeric.dropna()
                if len(valid_power) > 0:
                    enriched['power_level'] = pd.cut(
                        power_numeric, 
                        bins=[0, 8, 12, 15, float('inf')],
                        labels=['low', 'normal', 'high', 'critical'],
                        include_lowest=True
                    )
                else:
                    enriched['power_level'] = 'unknown'
            except Exception as e:
                logger.warning(f"Could not create power level classification: {e}")
                enriched['power_level'] = 'unknown'
            
        # PUE calculation - Since we're using P_Active Générale as IT power, 
        # PUE would be 1.0 (total/IT where total=IT)
        # In a real scenario, we would need separate IT power measurement
        if 'P_Active Générale' in enriched.columns:
            try:
                # For now, assume a typical PUE value
                # This should be replaced with actual calculation when IT power is available separately
                enriched['PUE'] = 1.8  # Typical data center PUE
                logger.info("Using default PUE value of 1.8 (separate IT power measurement not available)")
            except Exception as e:
                logger.warning(f"Could not set PUE: {e}")
                enriched['PUE'] = np.nan
            
        # Cooling efficiency
        if 'P_Active CLIM' in enriched.columns and 'P_Active Générale' in enriched.columns:
            try:
                # Ensure numeric data
                clim_power = pd.to_numeric(enriched['P_Active CLIM'], errors='coerce')
                total_power = pd.to_numeric(enriched['P_Active Générale'], errors='coerce')
                
                total_power_safe = total_power.replace(0, np.nan)
                enriched['cooling_efficiency'] = clim_power / total_power_safe
            except Exception as e:
                logger.warning(f"Could not calculate cooling efficiency: {e}")
                enriched['cooling_efficiency'] = np.nan
            
        # Time-based features (only if index is datetime)
        if isinstance(enriched.index, pd.DatetimeIndex):
            enriched['hour'] = enriched.index.hour
            enriched['day_of_week'] = enriched.index.dayofweek
            enriched['is_weekend'] = (enriched['day_of_week'] >= 5).astype(int)
        else:
            logger.warning("Index is not DatetimeIndex, skipping time-based features")
        
        return enriched
        
    def _filter_by_date(self, df: pd.DataFrame, start_date: Optional[datetime], end_date: Optional[datetime]) -> pd.DataFrame:
        """Filter DataFrame by date range"""
        if df.empty:
            return df
            
        try:
            filtered = df.copy()
            
            # Ensure index is datetime
            if not isinstance(filtered.index, pd.DatetimeIndex):
                if 'Timestamp' in filtered.columns:
                    filtered = filtered.set_index('Timestamp')
                else:
                    logger.warning("No datetime index or Timestamp column found")
                    return filtered
            
            if start_date:
                start_date = pd.to_datetime(start_date)
                filtered = filtered[filtered.index >= start_date]
                
            if end_date:
                end_date = pd.to_datetime(end_date)
                filtered = filtered[filtered.index <= end_date]
                
            return filtered
            
        except Exception as e:
            logger.warning(f"Could not filter by date: {e}")
            return df
        
    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get summary statistics about the loaded data"""
        if df.empty:
            return {'error': 'No data available'}
            
        summary = {
            'total_records': len(df),
            'date_range': {
                'start': df.index.min().isoformat() if not df.empty else None,
                'end': df.index.max().isoformat() if not df.empty else None,
                'duration_hours': (df.index.max() - df.index.min()).total_seconds() / 3600 if len(df) > 1 else 0
            },
            'columns': {
                'total': len(df.columns),
                'temperature': len([col for col in df.columns if 'T°C' in col]),
                'clim': len([col for col in df.columns if 'CLIM' in col]),
                'power': len([col for col in df.columns if any(x in col for x in ['Puissance', 'P_Active'])]),
                'derived': len([col for col in df.columns if any(x in col for x in ['_count', '_pct', '_rate', '_level'])])
            },
            'data_quality': {
                'completeness': (1 - df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100,
                'missing_data_points': df.isnull().sum().sum(),
                'columns_with_missing_data': df.columns[df.isnull().any()].tolist()
            }
        }
        
        # Add specific metric summaries if available
        if 'T°C AMBIANTE' in df.columns:
            temp_data = df['T°C AMBIANTE'].dropna()
            summary['temperature_ambient'] = {
                'min': float(temp_data.min()),
                'max': float(temp_data.max()),
                'mean': float(temp_data.mean()),
                'std': float(temp_data.std())
            }
            
        if 'clim_active_count' in df.columns:
            clim_data = df['clim_active_count'].dropna()
            summary['clim_status'] = {
                'avg_active_units': float(clim_data.mean()),
                'min_active_units': int(clim_data.min()),
                'max_active_units': int(clim_data.max()),
                'total_failure_events': int((clim_data == 0).sum())
            }
            
        return summary
        
    def validate_data_for_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate that data is suitable for incident analysis"""
        validation = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'recommendations': []
        }
        
        if df.empty:
            validation['is_valid'] = False
            validation['errors'].append('No data available')
            return validation
            
        # Check for minimum required columns
        required_cols = ['T°C AMBIANTE']
        missing_required = [col for col in required_cols if col not in df.columns]
        
        if missing_required:
            validation['is_valid'] = False
            validation['errors'].append(f'Missing required columns: {missing_required}')
            
        # Check data completeness
        completeness = (1 - df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
        
        if completeness < 70:
            validation['warnings'].append(f'Low data completeness: {completeness:.1f}%')
            validation['recommendations'].append('Consider extending the analysis period or checking data sources')
            
        # Check time coverage
        if len(df) < 4:  # Less than 1 hour of 15-min data
            validation['warnings'].append('Very short time series - results may be unreliable')
            validation['recommendations'].append('Use at least 4 hours of data for reliable analysis')
            
        # Check for sensor issues
        for col in ['T°C AMBIANTE', 'T°C EXTERIEURE']:
            if col in df.columns:
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    if col_data.std() < 0.1:  # Very low variation
                        validation['warnings'].append(f'{col} sensor may be stuck - very low variation detected')
                        
        return validation
        
    def clear_cache(self):
        """Clear cached data to force reload"""
        self.cached_data = None
        self.last_load_time = None
        logger.info("Data cache cleared")
        
    def get_available_metrics(self) -> List[str]:
        """Get list of available metrics in the data"""
        if self.cached_data is not None:
            return list(self.cached_data.columns)
        else:
            # Return expected metrics based on discovered files
            metrics = []
            for data_type in self.file_mapping.keys():
                if data_type == 'temperature_ambient':
                    metrics.append('T°C AMBIANTE')
                elif data_type == 'temperature_external':
                    metrics.append('T°C EXTERIEURE')
                elif data_type.startswith('clim_'):
                    metrics.append(f'CLIM_{data_type[-1].upper()}_Status')
                # Add more mappings as needed
            return metrics