import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


def render_tab(filtered_merged_data, start_date, end_date, merged_data=None):
    """Render the POP Report tab."""
    # Add title with region and POP name
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="color: black; font-size: 2.5rem; margin-bottom: 5px; font-weight: bold;">RAPPORT POP</h1>
        <h3 style="color: black; font-size: 1.3rem; margin-top: 0; font-weight: normal;">📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.header("📋 Rapport POP")
    
    if not filtered_merged_data.empty and 'Timestamp' in filtered_merged_data.columns:
        # Use the already filtered data from unified selector
        filtered_data = filtered_merged_data
        
        if not filtered_data.empty:
            # Métriques importantes
            st.subheader("📊 Métriques clés pour la période sélectionnée")
            
            # Fonction pour calculer les statistiques
            def calculate_stats_rapport(data, column):
                if column in data.columns:
                    valid_data = data[column].dropna()
                    if len(valid_data) > 0:
                        return {
                            'min': valid_data.min(),
                            'max': valid_data.max(),
                            'mean': valid_data.mean(),
                            'median': valid_data.median()
                        }
                return {'min': 0, 'max': 0, 'mean': 0, 'median': 0}
            
            # Température Ambiante
            st.markdown("### 🌡️ Température Ambiante")
            temp_amb_stats = calculate_stats_rapport(filtered_data, 'Temp_Ambiante')
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Min", f"{temp_amb_stats['min']:.1f}°C")
            with col2:
                st.metric("Max", f"{temp_amb_stats['max']:.1f}°C")
            with col3:
                st.metric("Moyenne", f"{temp_amb_stats['mean']:.1f}°C")
            with col4:
                st.metric("Médiane", f"{temp_amb_stats['median']:.1f}°C")
            
            # Température Extérieure
            st.markdown("### 🌤️ Température Extérieure")
            temp_ext_stats = calculate_stats_rapport(filtered_data, 'Temp_Exterieure')
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Min", f"{temp_ext_stats['min']:.1f}°C")
            with col2:
                st.metric("Max", f"{temp_ext_stats['max']:.1f}°C")
            with col3:
                st.metric("Moyenne", f"{temp_ext_stats['mean']:.1f}°C")
            with col4:
                st.metric("Médiane", f"{temp_ext_stats['median']:.1f}°C")
            
            # Puissance IT
            st.markdown("### 💻 Puissance IT")
            puiss_it_stats = calculate_stats_rapport(filtered_data, 'Puissance_IT')
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Min", f"{puiss_it_stats['min']:.1f} kW")
            with col2:
                st.metric("Max", f"{puiss_it_stats['max']:.1f} kW")
            with col3:
                st.metric("Moyenne", f"{puiss_it_stats['mean']:.1f} kW")
            with col4:
                st.metric("Médiane", f"{puiss_it_stats['median']:.1f} kW")
            
            # Graphique temporel unifié
            st.subheader("📈 Évolution temporelle")
            
            # Sélection des données à afficher
            available_metrics = {
                'Temp_Ambiante': '🌡️ Température Ambiante (°C)',
                'Temp_Exterieure': '🌤️ Température Extérieure (°C)',
                'Puissance_IT': '💻 Puissance IT (kW)',
                'Puissance_Generale': '⚡ Puissance Générale (kW)',
                'Puissance_CLIM': '❄️ Puissance CLIM (kW)',
                'Porte_Status': '🚪 État Porte'
            }
            
            # Détecter automatiquement tous les CLIMs disponibles dans les données
            clim_columns_rapport = [col for col in filtered_data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
            for clim_col in sorted(clim_columns_rapport):
                clim_name = clim_col.replace('_Status', '').replace('_', ' ')
                available_metrics[clim_col] = f'❄️ État {clim_name}'
            
            # Filtrer les métriques disponibles
            available_cols_rapport = [col for col in available_metrics.keys() if col in filtered_data.columns]
            
            selected_metrics_rapport = st.multiselect(
                "Sélectionner les données à afficher dans le graphique:",
                available_cols_rapport,
                default=st.session_state.get('selected_metrics_rapport', ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT'] if all(col in available_cols_rapport for col in ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT']) else available_cols_rapport[:3]),
                format_func=lambda x: available_metrics[x],
                key="tab10_multiselect_metrics"
            )
            
            if selected_metrics_rapport:
                # Créer un graphique unifié avec axes secondaires si nécessaire
                fig_rapport = go.Figure()
                
                # Couleurs sémantiques et contrastées
                color_scheme_rapport = {
                    'Temp_Ambiante': {'color': '#2E86AB', 'fill': 'rgba(46, 134, 171, 0.4)'},
                    'Temp_Exterieure': {'color': '#A23B72', 'fill': 'rgba(162, 59, 114, 0.3)'},
                    'Puissance_IT': {'color': '#F18F01', 'fill': 'rgba(241, 143, 1, 0.5)'},
                    'Puissance_Generale': {'color': '#C73E1D', 'fill': 'rgba(199, 62, 29, 0.4)'},
                    'Puissance_CLIM': {'color': '#FF6B6B', 'fill': 'rgba(255, 107, 107, 0.3)'},
                    'Porte_Status': {'color': '#6C5CE7', 'fill': 'rgba(108, 92, 231, 0.7)'}
                }
                
                # Couleurs pour les CLIMs
                clim_colors_rapport = [
                    {'color': '#4ECDC4', 'fill': 'rgba(78, 205, 196, 0.6)'},
                    {'color': '#45B7D1', 'fill': 'rgba(69, 183, 209, 0.6)'},
                    {'color': '#96CEB4', 'fill': 'rgba(150, 206, 180, 0.6)'},
                    {'color': '#FECA57', 'fill': 'rgba(254, 202, 87, 0.6)'},
                    {'color': '#00b894', 'fill': 'rgba(0, 184, 148, 0.6)'},
                    {'color': '#00cec9', 'fill': 'rgba(0, 206, 201, 0.6)'},
                    {'color': '#fdcb6e', 'fill': 'rgba(253, 203, 110, 0.6)'},
                    {'color': '#e17055', 'fill': 'rgba(225, 112, 85, 0.6)'},
                    {'color': '#74b9ff', 'fill': 'rgba(116, 185, 255, 0.6)'},
                    {'color': '#fd79a8', 'fill': 'rgba(253, 121, 168, 0.6)'},
                    {'color': '#6c5ce7', 'fill': 'rgba(108, 92, 231, 0.6)'},
                    {'color': '#a29bfe', 'fill': 'rgba(162, 155, 254, 0.6)'}
                ]
                
                # Assigner couleurs aux CLIMs détectés
                detected_clims_rapport = [col for col in filtered_data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
                for i, clim_col in enumerate(sorted(detected_clims_rapport)):
                    color_index = i % len(clim_colors_rapport)
                    color_scheme_rapport[clim_col] = clim_colors_rapport[color_index]
                
                # Séparer données continues et binaires
                continuous_metrics_rapport = [m for m in selected_metrics_rapport if 'Status' not in m]
                binary_metrics_rapport = [m for m in selected_metrics_rapport if 'Status' in m]
                
                # Option d'affichage pour les données binaires
                col1, col2 = st.columns([3, 1])
                with col2:
                    binary_display_rapport = st.selectbox(
                        "Affichage binaires:",
                        ["Superposées transparentes", "Séparées classiques"],
                        key="tab10_binary_display"
                    )
                
                # Tracer données continues
                for idx, metric in enumerate(continuous_metrics_rapport):
                    if metric in filtered_data.columns:
                        colors = color_scheme_rapport.get(metric, {'color': '#808080', 'fill': 'rgba(128, 128, 128, 0.4)'})
                        fig_rapport.add_trace(go.Scatter(
                            x=filtered_data['Timestamp'],
                            y=filtered_data[metric],
                            name=available_metrics.get(metric, metric),
                            mode='lines',
                            line=dict(color=colors['color'], width=1.5),
                            fill='tozeroy' if idx == 0 else None,
                            fillcolor=colors['fill'],
                            hovertemplate='<b>%{fullData.name}</b><br>Valeur: %{y:.2f}<br>Temps: %{x}<extra></extra>',
                            yaxis='y1' if any(t in metric for t in ['Temp', 'Puissance']) else 'y2'
                        ))
                
                # Tracer données binaires
                if binary_metrics_rapport and binary_display_rapport == "Superposées transparentes":
                    for metric in binary_metrics_rapport:
                        if metric in filtered_data.columns:
                            colors = color_scheme_rapport.get(metric, {'color': '#808080', 'fill': 'rgba(128, 128, 128, 0.4)'})
                            fig_rapport.add_trace(go.Scatter(
                                x=filtered_data['Timestamp'],
                                y=filtered_data[metric],
                                name=available_metrics.get(metric, metric),
                                mode='markers',
                                marker=dict(size=8, color=colors['color']),
                                hovertemplate='<b>%{fullData.name}</b><br>État: %{y}<br>Temps: %{x}<extra></extra>'
                            ))
                
                # Vérifier s'il y a des traces
                if len(fig_rapport.data) > 0:
                    fig_rapport.update_layout(
                        title="Évolution temporelle",
                        xaxis_title="Temps",
                        yaxis_title="Valeur",
                        height=500,
                        hovermode='x unified',
                        template='plotly_white'
                    )
                    st.plotly_chart(fig_rapport, use_container_width=True, key="tab10_main_chart")
            else:
                st.info("Veuillez sélectionner au moins une métrique à afficher.")
            
            # Profil Horaire Moyen
            st.subheader("📊 Profil Horaire Moyen Unifié")
            st.write("Visualisation comparative des profils horaires moyens pour Température Ambiante, Puissance IT et Température Extérieure")
            
            if not filtered_data.empty:
                # Prepare hourly data
                hourly_data_rapport = filtered_data.copy()
                hourly_data_rapport['Heure'] = hourly_data_rapport['Timestamp'].dt.hour
                
                # Create figure with secondary y-axis
                fig_hourly = make_subplots(specs=[[{"secondary_y": True}]])
                
                # Temperature Ambiante
                if 'Temp_Ambiante' in hourly_data_rapport.columns:
                    hourly_avg_ambiante_rapport = hourly_data_rapport.groupby('Heure').agg({'Temp_Ambiante': 'mean'}).reset_index()
                    hourly_avg_ambiante_rapport.columns = ['Heure', 'mean']
                    fig_hourly.add_trace(
                        go.Scatter(x=hourly_avg_ambiante_rapport['Heure'], y=hourly_avg_ambiante_rapport['mean'],
                                  name='Temp Ambiante', mode='lines+markers', line=dict(color='#2E86AB', width=2)),
                        secondary_y=False
                    )
                
                # Temperature Extérieure
                if 'Temp_Exterieure' in hourly_data_rapport.columns:
                    hourly_avg_ext_rapport = hourly_data_rapport.groupby('Heure').agg({'Temp_Exterieure': 'mean'}).reset_index()
                    hourly_avg_ext_rapport.columns = ['Heure', 'mean']
                    fig_hourly.add_trace(
                        go.Scatter(x=hourly_avg_ext_rapport['Heure'], y=hourly_avg_ext_rapport['mean'],
                                  name='Temp Extérieure', mode='lines+markers', line=dict(color='#A23B72', width=2)),
                        secondary_y=False
                    )
                
                # Puissance IT
                if 'Puissance_IT' in hourly_data_rapport.columns:
                    hourly_avg_it_rapport = hourly_data_rapport.groupby('Heure').agg({'Puissance_IT': 'mean'}).reset_index()
                    hourly_avg_it_rapport.columns = ['Heure', 'mean']
                    fig_hourly.add_trace(
                        go.Scatter(x=hourly_avg_it_rapport['Heure'], y=hourly_avg_it_rapport['mean'],
                                  name='Puissance IT', mode='lines+markers', line=dict(color='#F18F01', width=2)),
                        secondary_y=True
                    )
                
                # Update layout
                fig_hourly.update_xaxes(title_text="Heure de la journée", tickmode='linear', tick0=0, dtick=2, range=[-0.5, 23.5])
                fig_hourly.update_yaxes(title_text="Température (°C)", secondary_y=False, gridcolor='rgba(128,128,128,0.2)')
                fig_hourly.update_yaxes(title_text="Puissance IT (kW)", secondary_y=True, gridcolor='rgba(128,128,128,0.1)')
                fig_hourly.update_layout(
                    title="Profil Horaire Moyen - Vue Comparative",
                    height=500,
                    hovermode='x unified',
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                    template='plotly_white',
                    margin=dict(l=50, r=50, t=50, b=100)
                )
                fig_hourly.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                st.plotly_chart(fig_hourly, use_container_width=True, key="tab10_hourly_profile")
            
            # Analyse de corrélation
            st.subheader("🔗 Analyse des Relations entre Variables")
            st.write("Identification des facteurs qui influencent la température ambiante pour optimiser les performances")
            
            # Sélection des variables pour la corrélation
            numeric_vars_rapport = ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT', 'Porte_Status']
            clim_status_columns_rapport = [col for col in filtered_data.columns if 'CLIM' in col and 'Status' in col]
            numeric_vars_rapport.extend(clim_status_columns_rapport)
            available_vars_rapport = [var for var in numeric_vars_rapport if var in filtered_data.columns]
            
            if len(available_vars_rapport) >= 2:
                # Calculate correlations
                temp_correlations_rapport = {}
                
                if 'Temp_Ambiante' in filtered_data.columns:
                    for metric in available_vars_rapport:
                        if metric != 'Temp_Ambiante':
                            corr_data = filtered_data[['Temp_Ambiante', metric]].dropna()
                            
                            if len(corr_data) >= 10:
                                try:
                                    spearman_corr = corr_data['Temp_Ambiante'].corr(corr_data[metric], method='spearman')
                                    temp_correlations_rapport[metric] = spearman_corr
                                except:
                                    temp_correlations_rapport[metric] = None
                            else:
                                temp_correlations_rapport[metric] = None
                
                temp_correlations_rapport = pd.Series(temp_correlations_rapport)
                
                if len(temp_correlations_rapport) > 0:
                    # Display correlations
                    st.markdown("### 📊 Valeurs de Corrélation")
                    correlation_display = []
                    impact_display = []
                    
                    for val in temp_correlations_rapport.values:
                        if isinstance(val, (int, float)) and pd.notna(val):
                            correlation_display.append(f"{val:.1%}")
                            impact_display.append('Positif' if val > 0 else 'Négatif')
                        else:
                            correlation_display.append("N/A")
                            impact_display.append('Neutre')
                    
                    tech_df = pd.DataFrame({
                        'Variable': temp_correlations_rapport.index,
                        'Corrélation': correlation_display,
                        'Impact': impact_display
                    })
                    
                    st.dataframe(tech_df, use_container_width=True)
            else:
                st.warning("Au moins 2 variables sont nécessaires pour l'analyse de corrélation.")
        else:
            st.warning("Aucune donnée disponible pour la période sélectionnée.")
    else:
        st.error("Aucune donnée disponible.")
