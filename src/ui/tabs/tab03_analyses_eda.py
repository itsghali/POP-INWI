"""
Onglet 3 : Analyses exploratoires (EDA)
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy import stats


def render_tab(filtered_merged_data, start_date, end_date):
    """
    Render l'onglet Analyses EDA
    
    Args:
        filtered_merged_data: DataFrame filtré avec toutes les données
        start_date: Date de début de la période
        end_date: Date de fin de la période
    """
    st.header("🔬 Analyses exploratoires (EDA)")
    
    # Display current unified period
    st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
    
    if not filtered_merged_data.empty and 'Timestamp' in filtered_merged_data.columns:
        # Sélection des métriques (multi-sélection)
        numeric_cols = ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT', 
                       'Puissance_Generale', 'Puissance_CLIM']
        available_numeric = [col for col in numeric_cols if col in filtered_merged_data.columns]
        
        metric_labels = {
            'Temp_Ambiante': '🌡️ Température Ambiante',
            'Temp_Exterieure': '🌤️ Température Extérieure',
            'Puissance_IT': '💻 Puissance IT',
            'Puissance_Generale': '⚡ Puissance Générale',
            'Puissance_CLIM': '❄️ Puissance CLIM'
        }
        
        selected_metrics = st.multiselect(
            "Sélectionner les métriques à analyser:",
            available_numeric,
            default=[available_numeric[0]] if available_numeric else [],
            format_func=lambda x: metric_labels.get(x, x)
        )
        
        # Use unified filtered data
        filtered_data = filtered_merged_data
    
        
        # Afficher les analyses pour chaque métrique sélectionnée
        if selected_metrics and not filtered_data.empty:
            for metric in selected_metrics:
                st.markdown("---")
                st.subheader(f"📊 Analyse complète: {metric_labels.get(metric, metric)}")
                
                # Vérifier la disponibilité des données
                metric_data = filtered_data[metric].dropna()
                if len(metric_data) == 0:
                    st.warning(f"Aucune donnée disponible pour {metric_labels.get(metric, metric)} dans la période sélectionnée.")
                    continue
                
                # 1. STATISTIQUES GÉNÉRALES
                with st.expander(f"📈 Statistiques et informations - {metric_labels.get(metric, metric)}", expanded=True):
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.markdown("**Informations générales**")
                        total_points = len(filtered_data)
                        valid_points = len(metric_data)
                        missing_points = total_points - valid_points
                        
                        st.metric("Points totaux", f"{total_points:,}")
                        st.metric("Points valides", f"{valid_points:,}")
                        st.metric("Données manquantes", f"{missing_points:,} ({missing_points/total_points*100:.1f}%)")
                    
                    with col2:
                        st.markdown("**Statistiques descriptives**")
                        stats_data = {
                            'Statistique': ['Minimum', 'Maximum', 'Moyenne', 'Médiane', 'Écart-type', 'Asymétrie', 'Aplatissement'],
                            'Valeur': [
                                f"{metric_data.min():.2f}",
                                f"{metric_data.max():.2f}",
                                f"{metric_data.mean():.2f}",
                                f"{metric_data.median():.2f}",
                                f"{metric_data.std():.2f}",
                                f"{stats.skew(metric_data):.2f}",
                                f"{stats.kurtosis(metric_data):.2f}"
                            ]
                        }
                        st.dataframe(pd.DataFrame(stats_data), hide_index=True, use_container_width=True)
                
                # 2. VISUALISATIONS DE DISTRIBUTION
                st.markdown(f"#### 📊 Distribution - {metric_labels.get(metric, metric)}")
                col1, col2 = st.columns(2)
                
                with col1:
                    # Histogramme avec KDE
                    fig_hist = go.Figure()
                    
                    # Histogramme
                    fig_hist.add_trace(go.Histogram(
                        x=metric_data,
                        name='Fréquence',
                        nbinsx=30,
                        marker_color='lightblue',
                        opacity=0.7
                    ))
                    
                    # KDE
                    kde_x = np.linspace(metric_data.min(), metric_data.max(), 100)
                    kde = stats.gaussian_kde(metric_data)
                    kde_y = kde(kde_x) * len(metric_data) * (metric_data.max() - metric_data.min()) / 30
                    
                    fig_hist.add_trace(go.Scatter(
                        x=kde_x,
                        y=kde_y,
                        mode='lines',
                        name='Densité (KDE)',
                        line=dict(color='red', width=2),
                        yaxis='y2'
                    ))
                    
                    fig_hist.update_layout(
                        title=f"Histogramme - {metric}",
                        xaxis_title=metric,
                        yaxis_title="Fréquence",
                        yaxis2=dict(overlaying='y', side='right', title='Densité'),
                        height=400,
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig_hist, use_container_width=True, key=f"eda_histogram_{metric}")
                
                with col2:
                    # Boîte à moustaches
                    fig_box = go.Figure()
                    fig_box.add_trace(go.Box(
                        y=metric_data,
                        name=metric,
                        boxpoints='outliers',
                        marker_color='lightcoral',
                        line_color='darkred'
                    ))
                    
                    fig_box.update_layout(
                        title=f"Boîte à moustaches - {metric}",
                        yaxis_title=metric,
                        height=400
                    )
                    
                    st.plotly_chart(fig_box, use_container_width=True, key=f"eda_boxplot_{metric}")
                    
                    # Statistiques des quartiles
                    q1 = metric_data.quantile(0.25)
                    q3 = metric_data.quantile(0.75)
                    iqr = q3 - q1
                    
                    st.caption("**Quartiles:**")
                    st.caption(f"Q1 (25%): {q1:.2f} | Q3 (75%): {q3:.2f} | IQR: {iqr:.2f}")
                
                # 3. ANALYSES TEMPORELLES
                st.markdown(f"#### 📈 Analyses temporelles - {metric_labels.get(metric, metric)}")
                
                # Série temporelle brute
                with st.expander("Série temporelle complète", expanded=True):
                    fig_ts = go.Figure()
                    fig_ts.add_trace(go.Scatter(
                        x=filtered_data['Timestamp'],
                        y=filtered_data[metric],
                        mode='lines',
                        name=metric,
                        line=dict(color='green', width=1)
                    ))
                    
                    fig_ts.update_layout(
                        title=f"Évolution temporelle - {metric}",
                        xaxis_title="Date et heure",
                        yaxis_title=metric,
                        height=400,
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig_ts, use_container_width=True, key=f"eda_timeseries_{metric}")
                
                # Moyennes journalières et profil horaire côte à côte
                col1, col2 = st.columns(2)
                
                with col1:
                    # Moyennes journalières
                    daily_data = filtered_data.copy()
                    daily_data['Date'] = daily_data['Timestamp'].dt.date
                    daily_avg = daily_data.groupby('Date')[metric].mean().reset_index()
                    
                    if len(daily_avg) > 0:
                        fig_daily = go.Figure()
                        fig_daily.add_trace(go.Scatter(
                            x=daily_avg['Date'],
                            y=daily_avg[metric],
                            mode='lines+markers',
                            name='Moyenne journalière',
                            line=dict(color='blue', width=2),
                            marker=dict(size=6)
                        ))
                        
                        fig_daily.update_layout(
                            title=f"Moyennes journalières - {metric}",
                            xaxis_title="Date",
                            yaxis_title=f"Moyenne {metric}",
                            height=350
                        )
                        
                        st.plotly_chart(fig_daily, use_container_width=True, key=f"eda_daily_avg_{metric}")
                
                with col2:
                    # Profil horaire
                    hourly_data = filtered_data.copy()
                    hourly_data['Heure'] = hourly_data['Timestamp'].dt.hour
                    hourly_avg = hourly_data.groupby('Heure')[metric].agg(['mean', 'std']).reset_index()
                    
                    if len(hourly_avg) > 0:
                        fig_hourly = go.Figure()
                        
                        # Moyenne
                        fig_hourly.add_trace(go.Scatter(
                            x=hourly_avg['Heure'],
                            y=hourly_avg['mean'],
                            mode='lines+markers',
                            name='Moyenne',
                            line=dict(color='darkblue', width=3),
                            marker=dict(size=8)
                        ))
                        
                        # Bande d'écart-type
                        fig_hourly.add_trace(go.Scatter(
                            x=list(hourly_avg['Heure']) + list(hourly_avg['Heure'][::-1]),
                            y=list(hourly_avg['mean'] + hourly_avg['std']) + list((hourly_avg['mean'] - hourly_avg['std'])[::-1]),
                            fill='toself',
                            fillcolor='rgba(0,100,250,0.2)',
                            line=dict(color='rgba(255,255,255,0)'),
                            name='± Écart-type',
                            showlegend=True
                        ))
                        
                        fig_hourly.update_layout(
                            title=f"Profil horaire moyen - {metric}",
                            xaxis_title="Heure",
                            yaxis_title=metric,
                            height=350,
                            xaxis=dict(tickmode='linear', tick0=0, dtick=2)
                        )
                        
                        st.plotly_chart(fig_hourly, use_container_width=True, key=f"eda_hourly_profile_{metric}")
        
        elif not selected_metrics:
            st.info("👆 Veuillez sélectionner au moins une métrique à analyser.")
        else:
            st.warning("Aucune donnée disponible pour la période sélectionnée.")
    
    else:
        st.error("Aucune donnée disponible.")
