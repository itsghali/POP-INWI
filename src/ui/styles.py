"""
UI Styles and Theme Configuration Module
Centralizes all CSS styles, color schemes, and theme-related configurations
"""
import streamlit as st


def apply_custom_css():
    """Apply custom CSS styling to the Streamlit app"""
    st.markdown("""
    <style>
        .main {
            padding: 0rem 1rem;
        }
        .stTitle {
            color: #1E3A8A;
            font-size: 2.5rem !important;
            text-align: center;
            margin-bottom: 2rem;
        }
        .metric-container {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
        }
        .stPlotlyChart {
            background-color: white;
            border-radius: 0.5rem;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)


def apply_print_styles():
    """Apply CSS for print media (hide sidebar and controls)"""
    st.markdown("""
    <style>
    @media print {
        /* Hide sidebar and Streamlit controls when printing */
        [data-testid="stSidebar"], .stSidebar, header, footer {
            display: none !important;
        }
        .block-container {
            margin-left: 0 !important;
            width: 100vw !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def render_page_header(selected_pop: str, selected_region: str):
    """Render the centered page header with POP and region information"""
    st.markdown(f"""
        <div style="text-align: center;">
            <h1>Centre de données INWI - {selected_pop}</h1>
            <h3>Région : {selected_region}</h3>
        </div>
    """, unsafe_allow_html=True)


def render_title_with_logo():
    """Render the main title with INWI logo"""
    col_title, col_spacer, col_logo = st.columns([5, 0.5, 1])
    with col_title:
        st.markdown("<h1 style='margin-top: 0; padding-top: 20px;'>🏢 Centre de Données - Tableau de Bord de Surveillance</h1>", unsafe_allow_html=True)
    with col_spacer:
        st.empty()
    with col_logo:
        st.markdown("<div style='text-align: right; padding-top: 10px; padding-right: 20px;'>", unsafe_allow_html=True)
        try:
            st.image("logo_inwi.png", width=200)
        except FileNotFoundError:
            st.markdown("<p style='text-align: right; font-size: 1.5rem;'>📡</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def get_theme_colors():
    """
    Get theme-based colors for plots based on Streamlit's current theme
    
    Returns:
        dict: Dictionary containing plot_bgcolor, paper_bgcolor, and grid_color
    """
    theme_base = st.get_option("theme.base")  # returns 'light' or 'dark'
    
    if theme_base == "light":
        return {
            'plot_bgcolor': "#ffffff",
            'paper_bgcolor': "#ffffff",
            'grid_color': "rgba(128,128,128,0.15)"
        }
    elif theme_base == "dark":
        return {
            'plot_bgcolor': "#0e1117",
            'paper_bgcolor': "#0e1117",
            'grid_color': "rgba(255,255,255,0.1)"
        }
    else:
        # Default to light theme
        return {
            'plot_bgcolor': "#ffffff",
            'paper_bgcolor': "#ffffff",
            'grid_color': "rgba(128,128,128,0.15)"
        }


def get_color_scheme(detected_columns=None):
    """
    Get comprehensive color scheme for all metrics and CLIM units
    
    Args:
        detected_columns: List of column names to automatically assign CLIM colors
        
    Returns:
        dict: Color scheme mapping metric names to color and fill values
    """
    # Base color scheme for standard metrics
    color_scheme = {
        # Températures - tons bleus/cyan
        'Temp_Ambiante': {'color': '#2E86AB', 'fill': 'rgba(46, 134, 171, 0.4)'},
        'Temp_Exterieure': {'color': '#A23B72', 'fill': 'rgba(162, 59, 114, 0.3)'},
        
        # Puissances - tons orange/rouge
        'Puissance_IT': {'color': '#F18F01', 'fill': 'rgba(241, 143, 1, 0.5)'},
        'Puissance_Generale': {'color': '#C73E1D', 'fill': 'rgba(199, 62, 29, 0.4)'},
        'Puissance_CLIM': {'color': '#FF6B6B', 'fill': 'rgba(255, 107, 107, 0.3)'},
        
        # Porte - ton violet
        'Porte_Status': {'color': '#6C5CE7', 'fill': 'rgba(108, 92, 231, 0.7)'}
    }
    
    # CLIM unit colors (12 distinct colors for up to 12 CLIM units)
    clim_colors = [
        {'color': '#4ECDC4', 'fill': 'rgba(78, 205, 196, 0.6)'},   # CLIM A
        {'color': '#45B7D1', 'fill': 'rgba(69, 183, 209, 0.6)'},   # CLIM B
        {'color': '#96CEB4', 'fill': 'rgba(150, 206, 180, 0.6)'},  # CLIM C
        {'color': '#FECA57', 'fill': 'rgba(254, 202, 87, 0.6)'},   # CLIM D
        {'color': '#00b894', 'fill': 'rgba(0, 184, 148, 0.6)'},    # CLIM E
        {'color': '#00cec9', 'fill': 'rgba(0, 206, 201, 0.6)'},    # CLIM F
        {'color': '#fdcb6e', 'fill': 'rgba(253, 203, 110, 0.6)'},  # CLIM G
        {'color': '#e17055', 'fill': 'rgba(225, 112, 85, 0.6)'},   # CLIM H
        {'color': '#74b9ff', 'fill': 'rgba(116, 185, 255, 0.6)'},  # CLIM I
        {'color': '#fd79a8', 'fill': 'rgba(253, 121, 168, 0.6)'},  # CLIM J
        {'color': '#6c5ce7', 'fill': 'rgba(108, 92, 231, 0.6)'},   # CLIM K
        {'color': '#a29bfe', 'fill': 'rgba(162, 155, 254, 0.6)'}   # CLIM L
    ]
    
    # Automatically assign colors to detected CLIM columns
    if detected_columns:
        detected_clims = [col for col in detected_columns if col.startswith('CLIM_') and col.endswith('_Status')]
        for i, clim_col in enumerate(sorted(detected_clims)):
            color_index = i % len(clim_colors)
            color_scheme[clim_col] = clim_colors[color_index]
    
    return color_scheme


def get_fallback_colors():
    """
    Get fallback colors for undefined metrics
    
    Returns:
        list: List of color dictionaries for fallback use
    """
    return [
        {'color': '#FF9F43', 'fill': 'rgba(255, 159, 67, 0.4)'},
        {'color': '#10AC84', 'fill': 'rgba(16, 172, 132, 0.4)'},
        {'color': '#EE5A24', 'fill': 'rgba(238, 90, 36, 0.4)'},
        {'color': '#0984e3', 'fill': 'rgba(9, 132, 227, 0.4)'},
        {'color': '#a29bfe', 'fill': 'rgba(162, 155, 254, 0.4)'},
        {'color': '#fd79a8', 'fill': 'rgba(253, 121, 168, 0.4)'},
        {'color': '#fdcb6e', 'fill': 'rgba(253, 203, 110, 0.4)'},
        {'color': '#6c5ce7', 'fill': 'rgba(108, 92, 231, 0.4)'}
    ]
