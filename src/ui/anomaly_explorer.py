"""
Anomaly Explorer UI - Interactive root cause analysis for temperature anomalies
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np

from ..analysis.anomaly_analyzer import AnomalyAnalyzer
from ..config.constants import METRICS, LABELS
from ..utils import create_time_series_plot


def render_anomaly_explorer_section(data: pd.DataFrame):
    """Render the Anomaly Explorer section with configurable analysis"""
    
    st.header("🔍 Explorateur d'Anomalies - Analyse des Causes Racines")
    
    st.markdown("""
    Cette section permet d'analyser les anomalies de température sur une période donnée 
    et d'identifier automatiquement les causes probables avec un niveau de confiance.
    """)
    
    # Configuration section
    st.subheader("⚙️ Configuration de l'Analyse")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Date range selection
        st.markdown("**📅 Période d'analyse**")
        start_date = st.date_input(
            "Date de début",
            value=data.index.min().date(),
            min_value=data.index.min().date(),
            max_value=data.index.max().date(),
            key="anomaly_start"
        )
        
        end_date = st.date_input(
            "Date de fin",
            value=data.index.max().date(),
            min_value=data.index.min().date(),
            max_value=data.index.max().date(),
            key="anomaly_end"
        )
        
    with col2:
        # Temperature threshold configuration
        st.markdown("**🌡️ Seuils de température normale**")
        
        # Calculate suggestions based on historical data
        if 'T°C AMBIANTE' in data.columns:
            temp_stats = data['T°C AMBIANTE'].describe()
            suggested_min = temp_stats['25%']
            suggested_max = temp_stats['75%']
        else:
            suggested_min, suggested_max = 20.0, 24.0
        
        min_temp = st.number_input(
            "Température minimale normale (°C)",
            min_value=10.0,
            max_value=30.0,
            value=float(suggested_min),
            step=0.5,
            help=f"Suggestion basée sur les données: {suggested_min:.1f}°C"
        )
        
        max_temp = st.number_input(
            "Température maximale normale (°C)",
            min_value=min_temp + 1,
            max_value=35.0,
            value=float(suggested_max),
            step=0.5,
            help=f"Suggestion basée sur les données: {suggested_max:.1f}°C"
        )
    
    # Advanced options
    with st.expander("🔧 Options avancées"):
        lookback_minutes = st.slider(
            "Fenêtre d'analyse des causes (minutes avant l'anomalie)",
            min_value=15,
            max_value=120,
            value=60,
            step=15,
            help="Période à analyser avant chaque anomalie pour identifier les causes"
        )
        
        confidence_threshold = st.slider(
            "Seuil de confiance minimum pour afficher les causes (%)",
            min_value=0,
            max_value=100,
            value=50,
            step=10,
            help="Ne montrer que les causes avec une confiance supérieure à ce seuil"
        )
    
    # Run analysis button
    if st.button("🚀 Lancer l'analyse", type="primary"):
        
        # Convert dates to timestamps
        start_timestamp = pd.Timestamp(start_date)
        end_timestamp = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        # Initialize analyzer
        analyzer = AnomalyAnalyzer(data)
        
        with st.spinner("Analyse en cours..."):
            # Generate analysis report
            report = analyzer.generate_analysis_report(
                start_timestamp,
                end_timestamp,
                min_temp,
                max_temp
            )
        
        # Display results
        display_analysis_results(data, report, confidence_threshold, min_temp, max_temp)
        
        # Store results in session state for export
        st.session_state['anomaly_analysis_report'] = report


def display_analysis_results(data: pd.DataFrame, 
                           report: dict, 
                           confidence_threshold: float,
                           min_temp: float,
                           max_temp: float):
    """Display the analysis results in an organized way"""
    
    # Summary section
    st.subheader("📊 Résumé de l'Analyse")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Anomalies détectées",
            report['summary']['total_anomalies'],
            help="Nombre total d'anomalies trouvées"
        )
    
    with col2:
        st.metric(
            "Durée totale",
            f"{report['summary']['total_anomaly_duration_minutes']} min",
            help="Temps cumulé en anomalie"
        )
    
    with col3:
        st.metric(
            "Sévérité moyenne",
            f"{report['summary']['average_severity']:.1%}",
            help="Gravité moyenne des anomalies"
        )
    
    with col4:
        st.metric(
            "Taux d'anomalie",
            f"{report['summary']['anomaly_rate']:.1f}/jour",
            help="Nombre moyen d'anomalies par jour"
        )
    
    # Visualization of temperature with anomalies
    st.subheader("📈 Visualisation des Anomalies")
    
    # Create temperature plot with threshold bands and anomalies
    fig = create_temperature_anomaly_plot(
        data,
        report,
        min_temp,
        max_temp,
        report['period']['start'],
        report['period']['end']
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed anomaly analysis
    if report['detailed_results']:
        st.subheader("🔬 Analyse Détaillée des Anomalies")
        
        # Create tabs for each anomaly
        if len(report['detailed_results']) > 5:
            st.info(f"Affichage des 5 premières anomalies sur {len(report['detailed_results'])} détectées")
            results_to_show = report['detailed_results'][:5]
        else:
            results_to_show = report['detailed_results']
        
        for i, result in enumerate(results_to_show):
            anomaly = result['anomaly']
            root_causes = result['root_causes']
            
            # Create expandable section for each anomaly
            anomaly_type_emoji = {
                'high': '🔴',
                'low': '🔵',
                'spike': '📈',
                'drop': '📉'
            }
            
            with st.expander(
                f"{anomaly_type_emoji.get(anomaly.anomaly_type, '⚠️')} "
                f"Anomalie {i+1}: {anomaly.timestamp.strftime('%d/%m/%Y %H:%M')} - "
                f"{anomaly.value:.1f}°C ({anomaly.anomaly_type})",
                expanded=(i == 0)  # Expand first anomaly by default
            ):
                
                # Anomaly details
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.markdown("**📋 Détails de l'anomalie**")
                    st.markdown(f"- **Type:** {anomaly.anomaly_type}")
                    st.markdown(f"- **Valeur:** {anomaly.value:.1f}°C")
                    st.markdown(f"- **Sévérité:** {anomaly.severity:.1%}")
                    st.markdown(f"- **Durée:** {anomaly.duration_minutes} minutes")
                
                with col2:
                    st.markdown("**🎯 Causes Racines Identifiées**")
                    
                    if root_causes:
                        # Filter by confidence threshold
                        filtered_causes = [c for c in root_causes if c.confidence >= confidence_threshold]
                        
                        if filtered_causes:
                            for cause in filtered_causes:
                                # Confidence indicator
                                if cause.confidence >= 80:
                                    conf_color = "🟢"
                                elif cause.confidence >= 60:
                                    conf_color = "🟡"
                                else:
                                    conf_color = "🔴"
                                
                                st.markdown(f"{conf_color} **{cause.description}** ({cause.confidence:.0f}% de confiance)")
                                
                                # Show evidence in a collapsible section
                                with st.container():
                                    st.markdown("*Preuves:*")
                                    for evidence in cause.evidence:
                                        st.markdown(f"  - {evidence}")
                                
                                st.markdown("---")
                        else:
                            st.warning(f"Aucune cause avec une confiance ≥ {confidence_threshold}%")
                    else:
                        st.info("Aucune cause racine identifiée pour cette anomalie")
        
        # Root cause frequency analysis
        if report['cause_frequency']:
            st.subheader("📊 Fréquence des Causes Racines")
            
            # Create bar chart of cause frequencies
            cause_df = pd.DataFrame(
                list(report['cause_frequency'].items()),
                columns=['Cause', 'Fréquence']
            )
            
            fig_causes = go.Figure(data=[
                go.Bar(
                    x=cause_df['Cause'],
                    y=cause_df['Fréquence'],
                    marker_color='lightblue'
                )
            ])
            
            fig_causes.update_layout(
                title="Distribution des causes racines principales",
                xaxis_title="Type de cause",
                yaxis_title="Nombre d'occurrences",
                height=400
            )
            
            st.plotly_chart(fig_causes, use_container_width=True)
    
    else:
        st.success("✅ Aucune anomalie détectée dans la période sélectionnée avec les seuils définis")
    
    # Export options
    st.subheader("📥 Export des Résultats")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 Exporter le rapport détaillé (Excel)"):
            # Create detailed Excel report
            excel_data = create_detailed_excel_report(report)
            st.download_button(
                label="Télécharger le rapport Excel",
                data=excel_data,
                file_name=f"anomaly_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col2:
        if st.button("📄 Exporter le résumé (PDF)"):
            st.info("Export PDF en cours de développement")


def create_temperature_anomaly_plot(data: pd.DataFrame,
                                  report: dict,
                                  min_temp: float,
                                  max_temp: float,
                                  start_date: pd.Timestamp,
                                  end_date: pd.Timestamp) -> go.Figure:
    """Create a plot showing temperature data with anomaly highlights"""
    
    # Filter data to the analysis period
    mask = (data.index >= start_date) & (data.index <= end_date)
    plot_data = data[mask].copy()
    
    fig = go.Figure()
    
    # Add temperature line
    if 'T°C AMBIANTE' in plot_data.columns:
        fig.add_trace(go.Scatter(
            x=plot_data.index,
            y=plot_data['T°C AMBIANTE'],
            mode='lines',
            name='Température Ambiante',
            line=dict(color='blue', width=2)
        ))
    
    # Add threshold bands
    fig.add_hrect(
        y0=min_temp, y1=max_temp,
        fillcolor="green", opacity=0.1,
        layer="below", line_width=0,
        annotation_text="Zone Normale",
        annotation_position="right"
    )
    
    # Add threshold lines
    fig.add_hline(
        y=max_temp, 
        line_dash="dash", 
        line_color="red",
        annotation_text=f"Seuil Max: {max_temp}°C"
    )
    
    fig.add_hline(
        y=min_temp, 
        line_dash="dash", 
        line_color="blue",
        annotation_text=f"Seuil Min: {min_temp}°C"
    )
    
    # Highlight anomalies
    for result in report['detailed_results']:
        anomaly = result['anomaly']
        
        # Determine color based on anomaly type
        if anomaly.anomaly_type == 'high':
            color = 'red'
        elif anomaly.anomaly_type == 'low':
            color = 'blue'
        elif anomaly.anomaly_type == 'spike':
            color = 'orange'
        else:  # drop
            color = 'purple'
        
        # Add vertical line at anomaly time
        fig.add_vline(
            x=anomaly.timestamp,
            line_dash="dot",
            line_color=color,
            opacity=0.5
        )
        
        # Add anomaly marker
        fig.add_trace(go.Scatter(
            x=[anomaly.timestamp],
            y=[anomaly.value],
            mode='markers',
            marker=dict(
                size=12,
                color=color,
                symbol='x',
                line=dict(width=2)
            ),
            name=f"Anomalie {anomaly.anomaly_type}",
            showlegend=False,
            hovertext=f"Anomalie: {anomaly.value:.1f}°C<br>Type: {anomaly.anomaly_type}<br>Sévérité: {anomaly.severity:.1%}"
        ))
    
    # Update layout
    fig.update_layout(
        title="Température Ambiante avec Anomalies Détectées",
        xaxis_title="Date/Heure",
        yaxis_title="Température (°C)",
        height=500,
        hovermode='x unified',
        showlegend=True
    )
    
    return fig


def create_detailed_excel_report(report: dict) -> bytes:
    """Create an Excel report with multiple sheets"""
    import io
    
    # Create Excel writer
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary sheet
        summary_df = pd.DataFrame([report['summary']])
        summary_df.to_excel(writer, sheet_name='Résumé', index=False)
        
        # Anomalies detail sheet
        anomalies_data = []
        for result in report['detailed_results']:
            anomaly = result['anomaly']
            primary_cause = result['root_causes'][0] if result['root_causes'] else None
            
            anomalies_data.append({
                'Timestamp': anomaly.timestamp,
                'Type': anomaly.anomaly_type,
                'Valeur (°C)': anomaly.value,
                'Sévérité': f"{anomaly.severity:.1%}",
                'Durée (min)': anomaly.duration_minutes,
                'Cause Principale': primary_cause.description if primary_cause else 'Non identifiée',
                'Confiance (%)': f"{primary_cause.confidence:.0f}" if primary_cause else 'N/A'
            })
        
        if anomalies_data:
            anomalies_df = pd.DataFrame(anomalies_data)
            anomalies_df.to_excel(writer, sheet_name='Anomalies', index=False)
        
        # Root causes frequency
        if report['cause_frequency']:
            causes_df = pd.DataFrame(
                list(report['cause_frequency'].items()),
                columns=['Type de Cause', 'Fréquence']
            )
            causes_df.to_excel(writer, sheet_name='Fréquence Causes', index=False)
    
    output.seek(0)
    return output.read()