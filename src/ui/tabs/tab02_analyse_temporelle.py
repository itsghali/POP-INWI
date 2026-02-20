"""
Onglet 2 : Analyse temporelle interactive
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import pandas as pd


def render_tab(filtered_merged_data, start_date, end_date):
    """
    Render l'onglet Analyse temporelle interactive
    
    Args:
        filtered_merged_data: DataFrame filtré avec toutes les données
        start_date: Date de début de la période
        end_date: Date de fin de la période
    """
    st.header("📈 Analyse temporelle interactive")
    
    # Display current unified period
    st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
    
    # Sélection des données
    # Multi-sélection des données à afficher
    available_metrics = {
        'Temp_Ambiante': '🌡️ Température Ambiante (°C)',
        'Temp_Exterieure': '🌤️ Température Extérieure (°C)',
        'Puissance_IT': '💻 Puissance IT (kW)',
        'Puissance_Generale': '⚡ Puissance Générale (kW)',
        'Puissance_CLIM': '❄️ Puissance CLIM (kW)',
        'Porte_Status': '🚪 État Porte'
    }
    
    # Détecter automatiquement tous les CLIMs disponibles dans les données
    clim_columns = [col for col in filtered_merged_data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
    for clim_col in sorted(clim_columns):
        clim_name = clim_col.replace('_Status', '').replace('_', ' ')
        available_metrics[clim_col] = f'❄️ État {clim_name}'
    
    # Filtrer les métriques disponibles
    available_cols = [col for col in available_metrics.keys() if col in filtered_merged_data.columns]
    
    selected_metrics = st.multiselect(
        "Sélectionner les données à afficher:",
        available_cols,
        default=available_cols[:3] if len(available_cols) >= 3 else available_cols,
        format_func=lambda x: available_metrics[x]
    )
    
    # Use unified filtered data
    if selected_metrics and not filtered_merged_data.empty:
        filtered_data = filtered_merged_data
        
        # Création du graphique interactif
        fig = make_subplots(
            rows=len(selected_metrics),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=[available_metrics[m] for m in selected_metrics]
        )
        
        colors = px.colors.qualitative.Set3
        fill_colors = [
            'rgba(141, 211, 199, 0.3)',
            'rgba(255, 255, 179, 0.3)',
            'rgba(190, 186, 218, 0.3)',
            'rgba(251, 128, 114, 0.3)',
            'rgba(128, 177, 211, 0.3)',
            'rgba(253, 180, 98, 0.3)',
            'rgba(179, 222, 105, 0.3)',
            'rgba(252, 205, 229, 0.3)',
            'rgba(217, 217, 217, 0.3)',
            'rgba(188, 128, 189, 0.3)'
        ]
        
        for idx, metric in enumerate(selected_metrics):
            # Déterminer le type de graphique selon la métrique
            if 'Status' in metric:
                # Pour les statuts, utiliser un graphique en escalier
                fig.add_trace(
                    go.Scatter(
                        x=filtered_data['Timestamp'],
                        y=filtered_data[metric],
                        name=available_metrics[metric],
                        mode='lines',
                        line=dict(shape='hv', color=colors[idx % len(colors)]),
                        fill='tozeroy',
                        fillcolor=fill_colors[idx % len(fill_colors)]
                    ),
                    row=idx+1, col=1
                )
            else:
                # Pour les métriques continues
                fig.add_trace(
                    go.Scatter(
                        x=filtered_data['Timestamp'],
                        y=filtered_data[metric],
                        name=available_metrics[metric],
                        mode='lines',
                        line=dict(color=colors[idx % len(colors)], width=2),
                        hovertemplate='%{y:.2f}<br>%{x}<extra></extra>'
                    ),
                    row=idx+1, col=1
                )
            
            # Mise à jour des axes Y
            fig.update_yaxes(title_text=metric.split('_')[0], row=idx+1, col=1)
        
        # Mise à jour de la mise en page
        fig.update_layout(
            height=200 * len(selected_metrics),
            showlegend=False,
            hovermode='x unified',
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        fig.update_xaxes(title_text="Date et heure", row=len(selected_metrics), col=1)
        
        st.plotly_chart(fig, use_container_width=True, key="temporal_analysis_subplots")
        
        # Options d'export
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("📊 Exporter en PNG"):
                fig.write_image("export_analyse_temporelle.png")
                st.success("Graphique exporté!")
        
        with col2:
            if st.button("📄 Exporter en CSV"):
                export_data = filtered_data[['Timestamp'] + selected_metrics]
                export_data.to_csv("export_donnees.csv", index=False)
                st.success("Données exportées!")
    
    # Profile Horaire Moyen Unifié
    st.subheader("📊 Profil Horaire Moyen Unifié")
    st.write("Visualisation comparative des profils horaires moyens pour Température Ambiante, Puissance IT et Température Extérieure")
    
    if not filtered_merged_data.empty:
        # Prepare hourly data for the three metrics
        hourly_data = filtered_merged_data.copy()
        hourly_data['Heure'] = hourly_data['Timestamp'].dt.hour
        
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Temperature Ambiante
        if 'Temp_Ambiante' in hourly_data.columns:
            hourly_avg_ambiante = hourly_data.groupby('Heure')['Temp_Ambiante'].agg(['mean', 'std']).reset_index()
            
            # Add mean line
            fig.add_trace(
                go.Scatter(
                    x=hourly_avg_ambiante['Heure'],
                    y=hourly_avg_ambiante['mean'],
                    mode='lines+markers',
                    name='Température Ambiante (°C)',
                    line=dict(color='#FF6B6B', width=3),
                    marker=dict(size=8),
                    yaxis='y'
                ),
                secondary_y=False
            )
            
            # Add std band
            fig.add_trace(
                go.Scatter(
                    x=list(hourly_avg_ambiante['Heure']) + list(hourly_avg_ambiante['Heure'][::-1]),
                    y=list(hourly_avg_ambiante['mean'] + hourly_avg_ambiante['std']) + list((hourly_avg_ambiante['mean'] - hourly_avg_ambiante['std'])[::-1]),
                    fill='toself',
                    fillcolor='rgba(255,107,107,0.15)',
                    line=dict(color='rgba(255,255,255,0)'),
                    name='± Écart-type Temp Ambiante',
                    showlegend=False,
                    yaxis='y'
                ),
                secondary_y=False
            )
        
        # Temperature Extérieure
        if 'Temp_Exterieure' in hourly_data.columns:
            hourly_avg_ext = hourly_data.groupby('Heure')['Temp_Exterieure'].agg(['mean', 'std']).reset_index()
            
            # Add mean line
            fig.add_trace(
                go.Scatter(
                    x=hourly_avg_ext['Heure'],
                    y=hourly_avg_ext['mean'],
                    mode='lines+markers',
                    name='Température Extérieure (°C)',
                    line=dict(color='#4ECDC4', width=3),
                    marker=dict(size=8),
                    yaxis='y'
                ),
                secondary_y=False
            )
            
            # Add std band
            fig.add_trace(
                go.Scatter(
                    x=list(hourly_avg_ext['Heure']) + list(hourly_avg_ext['Heure'][::-1]),
                    y=list(hourly_avg_ext['mean'] + hourly_avg_ext['std']) + list((hourly_avg_ext['mean'] - hourly_avg_ext['std'])[::-1]),
                    fill='toself',
                    fillcolor='rgba(78,205,196,0.15)',
                    line=dict(color='rgba(255,255,255,0)'),
                    name='± Écart-type Temp Extérieure',
                    showlegend=False,
                    yaxis='y'
                ),
                secondary_y=False
            )
        
        # Puissance IT (on secondary y-axis)
        if 'Puissance_IT' in hourly_data.columns:
            hourly_avg_it = hourly_data.groupby('Heure')['Puissance_IT'].agg(['mean', 'std']).reset_index()
            
            # Add mean line
            fig.add_trace(
                go.Scatter(
                    x=hourly_avg_it['Heure'],
                    y=hourly_avg_it['mean'],
                    mode='lines+markers',
                    name='Puissance IT (kW)',
                    line=dict(color='#6C5CE7', width=3, dash='dot'),
                    marker=dict(size=8, symbol='square'),
                    yaxis='y2'
                ),
                secondary_y=True
            )
            
            # Add std band
            fig.add_trace(
                go.Scatter(
                    x=list(hourly_avg_it['Heure']) + list(hourly_avg_it['Heure'][::-1]),
                    y=list(hourly_avg_it['mean'] + hourly_avg_it['std']) + list((hourly_avg_it['mean'] - hourly_avg_it['std'])[::-1]),
                    fill='toself',
                    fillcolor='rgba(108,92,231,0.15)',
                    line=dict(color='rgba(255,255,255,0)'),
                    name='± Écart-type Puissance IT',
                    showlegend=False,
                    yaxis='y2'
                ),
                secondary_y=True
            )
        
        # Update layout
        fig.update_xaxes(
            title_text="Heure de la journée",
            tickmode='linear',
            tick0=0,
            dtick=2,
            range=[-0.5, 23.5]
        )
        
        fig.update_yaxes(
            title_text="Température (°C)",
            secondary_y=False,
            gridcolor='rgba(128,128,128,0.2)'
        )
        
        fig.update_yaxes(
            title_text="Puissance IT (kW)",
            secondary_y=True,
            gridcolor='rgba(128,128,128,0.1)'
        )
        
        fig.update_layout(
            title="Profil Horaire Moyen - Vue Comparative",
            height=500,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5
            ),
            template='plotly_white',
            margin=dict(l=50, r=50, t=50, b=100)
        )
        
        # Add grid
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        
        st.plotly_chart(fig, use_container_width=True, key="temporal_analysis_hourly")
        
        # Add insights
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'Temp_Ambiante' in hourly_data.columns and not hourly_avg_ambiante['mean'].isna().all():
                peak_idx_amb = hourly_avg_ambiante['mean'].idxmax()
                if pd.notna(peak_idx_amb):
                    peak_hour_amb = hourly_avg_ambiante.loc[peak_idx_amb, 'Heure']
                    peak_temp_amb = hourly_avg_ambiante['mean'].max()
                    st.metric(
                        "🌡️ Pic Temp Ambiante",
                        f"{peak_temp_amb:.1f}°C",
                        f"à {int(peak_hour_amb)}h"
                    )
                else:
                    st.metric("🌡️ Pic Temp Ambiante", "N/A", "Données insuffisantes")
            elif 'Temp_Ambiante' in hourly_data.columns:
                st.metric("🌡️ Pic Temp Ambiante", "N/A", "Données insuffisantes")
        
        with col2:
            if 'Puissance_IT' in hourly_data.columns and not hourly_avg_it['mean'].isna().all():
                peak_idx_it = hourly_avg_it['mean'].idxmax()
                if pd.notna(peak_idx_it):
                    peak_hour_it = hourly_avg_it.loc[peak_idx_it, 'Heure']
                    peak_power_it = hourly_avg_it['mean'].max()
                    st.metric(
                        "💻 Pic Puissance IT",
                        f"{peak_power_it:.1f} kW",
                        f"à {int(peak_hour_it)}h"
                    )
                else:
                    st.metric("💻 Pic Puissance IT", "N/A", "Données insuffisantes")
            elif 'Puissance_IT' in hourly_data.columns:
                st.metric("💻 Pic Puissance IT", "N/A", "Données insuffisantes")
        
        with col3:
            if 'Temp_Exterieure' in hourly_data.columns and not hourly_avg_ext['mean'].isna().all():
                peak_idx_ext = hourly_avg_ext['mean'].idxmax()
                if pd.notna(peak_idx_ext):
                    peak_hour_ext = hourly_avg_ext.loc[peak_idx_ext, 'Heure']
                    peak_temp_ext = hourly_avg_ext['mean'].max()
                    st.metric(
                        "🌤️ Pic Temp Extérieure",
                        f"{peak_temp_ext:.1f}°C",
                        f"à {int(peak_hour_ext)}h"
                    )
                else:
                    st.metric("🌤️ Pic Temp Extérieure", "N/A", "Données insuffisantes")
            elif 'Temp_Exterieure' in hourly_data.columns:
                st.metric("🌤️ Pic Temp Extérieure", "N/A", "Données insuffisantes")
