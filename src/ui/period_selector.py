"""
Unified Period Selector for BGU-ONE POP Incident Management System
This module provides a centralized period selection mechanism that synchronizes
across all application sections.
"""

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd


class UnifiedPeriodSelector:
    """
    Manages unified period selection across all application sections.
    Uses Streamlit session state to maintain consistency.
    """
    
    def __init__(self):
        self._ensure_unified_period_state()

    def _ensure_unified_period_state(self):
        """Ensure unified period state exists and contains required keys."""
        now = datetime.now()
        defaults = {
            'start_date': now - timedelta(days=7),
            'end_date': now,
            'selection_type': 'Dernière semaine',
            'custom_range': None
        }

        period_state = st.session_state.get('unified_period')
        if not isinstance(period_state, dict):
            st.session_state.unified_period = defaults.copy()
            return

        for key, value in defaults.items():
            if key not in period_state:
                period_state[key] = value

        st.session_state.unified_period = period_state

    def ensure_initialized(self):
        """Public method to guarantee unified_period exists in session state."""
        self._ensure_unified_period_state()
    
    def render_selector(self, key_suffix=""):
        """
        Renders the unified period selector UI component in the sidebar.
        
        Args:
            key_suffix: Optional suffix for unique widget keys
        
        Returns:
            tuple: (start_date, end_date) as datetime objects
        """
        self._ensure_unified_period_state()
              
        # Predefined period options
        period_options = [
            "Dernière heure",
            "Dernières 24 heures",
            "Derniers 3 jours",
            "Dernière semaine",
            "Dernier mois",
            "Derniers 3 mois",
            "Personnalisé"
        ]
        
        # Get current selection and ensure it exists in options
        current_selection = st.session_state.unified_period['selection_type']
        if current_selection not in period_options:
            current_selection = "Dernière semaine"
        
        selected_period = st.sidebar.selectbox(
            "Période prédéfinie",
            period_options,
            index=period_options.index(current_selection),
            key=f"period_select_{key_suffix}",
            help="Sélectionnez une période prédéfinie ou choisissez 'Personnalisé' pour définir vos propres dates"
        )
        
        # Update session state
        st.session_state.unified_period['selection_type'] = selected_period
        
        if selected_period == "Personnalisé":
            # Custom date range selector
            date_range = st.sidebar.date_input(
                "Sélectionner la plage de dates",
                value=(
                    st.session_state.unified_period['start_date'].date(),
                    st.session_state.unified_period['end_date'].date()
                ),
                max_value=datetime.now().date(),
                key=f"date_range_{key_suffix}",
                help="Sélectionnez la date de début et de fin"
            )
            
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date = datetime.combine(date_range[0], datetime.min.time())
                end_date = datetime.combine(date_range[1], datetime.max.time())
                st.session_state.unified_period['custom_range'] = (start_date, end_date)
            else:
                # Use previous values if selection is incomplete
                if st.session_state.unified_period['custom_range']:
                    start_date, end_date = st.session_state.unified_period['custom_range']
                else:
                    start_date = st.session_state.unified_period['start_date']
                    end_date = st.session_state.unified_period['end_date']
        else:
            # Calculate dates based on predefined period
            end_date = datetime.now()
            
            if selected_period == "Dernière heure":
                start_date = end_date - timedelta(hours=1)
            elif selected_period == "Dernières 24 heures":
                start_date = end_date - timedelta(days=1)
            elif selected_period == "Derniers 3 jours":
                start_date = end_date - timedelta(days=3)
            elif selected_period == "Dernière semaine":
                start_date = end_date - timedelta(days=7)
            elif selected_period == "Dernier mois":
                start_date = end_date - timedelta(days=30)
            elif selected_period == "Derniers 3 mois":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = st.session_state.unified_period['start_date']
                end_date = st.session_state.unified_period['end_date']
        
        # Display selected period info in sidebar
        st.sidebar.markdown("**Période active:**")
        st.sidebar.caption(f"Du: {start_date.strftime('%Y-%m-%d %H:%M')}")
        st.sidebar.caption(f"Au: {end_date.strftime('%Y-%m-%d %H:%M')}")
        
        # Update session state with calculated dates
        st.session_state.unified_period['start_date'] = start_date
        st.session_state.unified_period['end_date'] = end_date
        
        # Display data availability indicator
        self._display_data_availability_sidebar(start_date, end_date)
        
        return start_date, end_date
    
    def _display_data_availability(self, start_date, end_date):
        """
        Display a small indicator showing data availability for the selected period.
        """
        duration = end_date - start_date
        days = duration.days
        hours = duration.seconds // 3600
        
        if days > 0:
            duration_str = f"{days} jour{'s' if days > 1 else ''}"
            if hours > 0:
                duration_str += f" et {hours} heure{'s' if hours > 1 else ''}"
        else:
            duration_str = f"{hours} heure{'s' if hours > 1 else ''}"
        
        st.caption(f"📊 Période sélectionnée: {duration_str}")
    
    def _display_data_availability_sidebar(self, start_date, end_date):
        """
        Display a small indicator showing data availability for the selected period in sidebar.
        """
        duration = end_date - start_date
        days = duration.days
        hours = duration.seconds // 3600
        
        if days > 0:
            duration_str = f"{days} jour{'s' if days > 1 else ''}"
            if hours > 0:
                duration_str += f" et {hours} heure{'s' if hours > 1 else ''}"
        else:
            duration_str = f"{hours} heure{'s' if hours > 1 else ''}"
        
        st.sidebar.caption(f"📊 Période sélectionnée: {duration_str}")
    
    def filter_dataframe(self, df, timestamp_column='Timestamp'):
        """
        Filter a dataframe based on the unified period selection.
        
        Args:
            df: pandas DataFrame to filter
            timestamp_column: name of the timestamp column
        
        Returns:
            pandas DataFrame: filtered dataframe
        """
        self._ensure_unified_period_state()

        if df is None or df.empty:
            return df
        
        start_date = st.session_state.unified_period['start_date']
        end_date = st.session_state.unified_period['end_date']
        
        # Ensure timestamp column is datetime
        if timestamp_column in df.columns:
            df[timestamp_column] = pd.to_datetime(df[timestamp_column])
            
            # Filter based on selected period
            mask = (df[timestamp_column] >= start_date) & (df[timestamp_column] <= end_date)
            filtered_df = df[mask].copy()
            
            return filtered_df
        
        return df
    
    def get_current_period(self):
        """
        Get the current selected period.
        
        Returns:
            dict: Dictionary containing start_date, end_date, and selection_type
        """
        self._ensure_unified_period_state()
        return st.session_state.unified_period.copy()
    
    def set_period(self, start_date, end_date, selection_type="Personnalisé"):
        """
        Programmatically set the period selection.
        
        Args:
            start_date: datetime object for start date
            end_date: datetime object for end date
            selection_type: string describing the selection type
        """
        self._ensure_unified_period_state()
        st.session_state.unified_period = {
            'start_date': start_date,
            'end_date': end_date,
            'selection_type': selection_type,
            'custom_range': (start_date, end_date) if selection_type == "Personnalisé" else None
        }
    
    def render_mini_selector(self):
        """
        Renders a compact version of the period selector for sidebar use.
        
        Returns:
            tuple: (start_date, end_date) as datetime objects
        """
        self._ensure_unified_period_state()
        
        with st.sidebar:
            st.markdown("#### 📅 Période Globale")
            
            period_options = [
                "Dernière heure",
                "Dernières 24 heures",
                "Derniers 3 jours",
                "Dernière semaine",
                "Dernier mois",
                "Personnalisé"
            ]
            
            # Get current selection type and ensure it's in the options
            current_selection = st.session_state.unified_period.get('selection_type', 'Dernière semaine')
            if current_selection not in period_options:
                current_selection = 'Dernière semaine'
            
            selected = st.selectbox(
                "Période",
                period_options,
                index=period_options.index(current_selection),
                key="sidebar_period"
            )
            
            if selected == "Personnalisé":
                date_range = st.date_input(
                    "Plage de dates",
                    value=(
                        st.session_state.unified_period['start_date'].date(),
                        st.session_state.unified_period['end_date'].date()
                    ),
                    key="sidebar_dates"
                )
                
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start_date = datetime.combine(date_range[0], datetime.min.time())
                    end_date = datetime.combine(date_range[1], datetime.max.time())
                else:
                    start_date = st.session_state.unified_period['start_date']
                    end_date = st.session_state.unified_period['end_date']
            else:
                end_date = datetime.now()
                
                if selected == "Dernière heure":
                    start_date = end_date - timedelta(hours=1)
                elif selected == "Dernières 24 heures":
                    start_date = end_date - timedelta(days=1)
                elif selected == "Derniers 3 jours":
                    start_date = end_date - timedelta(days=3)
                elif selected == "Dernière semaine":
                    start_date = end_date - timedelta(days=7)
                elif selected == "Dernier mois":
                    start_date = end_date - timedelta(days=30)
                else:
                    start_date = st.session_state.unified_period['start_date']
                    end_date = st.session_state.unified_period['end_date']
            
            # Update session state
            st.session_state.unified_period['start_date'] = start_date
            st.session_state.unified_period['end_date'] = end_date
            st.session_state.unified_period['selection_type'] = selected
            
            # Display period info
            st.caption(f"Du: {start_date.strftime('%d/%m %H:%M')}")
            st.caption(f"Au: {end_date.strftime('%d/%m %H:%M')}")
            
            return start_date, end_date


# Create a singleton instance
period_selector = UnifiedPeriodSelector()