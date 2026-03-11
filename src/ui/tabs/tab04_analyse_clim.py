"""
Onglet 4 : Analyse de l'impact des CLIMs sur la température
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import timedelta


def render_tab(filtered_merged_data, start_date, end_date):
    """
    Render l'onglet Analyse CLIM
    
    Args:
        filtered_merged_data: DataFrame filtré avec toutes les données
        start_date: Date de début de la période
        end_date: Date de fin de la période
    """
    st.header("❄️ Analyse de l'impact des CLIMs sur la température")
    st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
    
    # Préparer les données CLIM
    clim_columns = [col for col in filtered_merged_data.columns if 'CLIM' in col and 'Status' in col]
    
    if clim_columns and 'Temp_Ambiante' in filtered_merged_data.columns:
        # Info sur les données disponibles
        st.info(f"**CLIMs détectées:** {', '.join(clim_columns)}")
        
        # Vérifier l'état des CLIMs
        '''clim_status_summary = []
        for clim in clim_columns:
            if clim in filtered_merged_data.columns:
                total_points = len(filtered_merged_data)
                on_points = (filtered_merged_data[clim] == 1).sum()
                off_points = (filtered_merged_data[clim] == 0).sum()
                clim_status_summary.append({
                    'CLIM': clim,
                    'Total Points': total_points,
                    'ON': on_points,
                    'OFF': off_points,
                    '% ON': (on_points / total_points * 100) if total_points > 0 else 0
                })
        
        if clim_status_summary:
            df_clim_summary = pd.DataFrame(clim_status_summary)
            st.dataframe(df_clim_summary.style.format({
                '% ON': '{:.1f}%'
            }), width='stretch')
        '''
        # Analyse de la température après arrêt CLIM
        st.subheader("📉 Évolution de la température après arrêt des CLIMs")
        
        # Paramètres
        col1, col2 = st.columns(2)
        with col1:
            minutes_after = st.slider("Minutes après l'arrêt", 5, 60, 30, 5)
        with col2:
            selected_clim = st.selectbox("Sélectionner un CLIM", clim_columns)
        
        # Détecter les arrêts de CLIM (passage de 1 à 0)
        filtered_merged_data['CLIM_Stop'] = (filtered_merged_data[selected_clim].shift(1) == 1) & (filtered_merged_data[selected_clim] == 0)
        
        # Points d'arrêt
        stop_points = filtered_merged_data[filtered_merged_data['CLIM_Stop']]['Timestamp'].tolist()
        
        # Debug info
        with st.expander("🔍 Informations de débogage"):
            st.write(f"Total de points de données: {len(filtered_merged_data)}")
            st.write(f"Points avec température valide: {filtered_merged_data['Temp_Ambiante'].notna().sum()}")
            st.write(f"Valeurs uniques de {selected_clim}: {filtered_merged_data[selected_clim].value_counts().to_dict()}")
            st.write(f"Transitions détectées (1→0): {len(stop_points)}")
            if stop_points:
                st.write(f"Premiers arrêts: {[t.strftime('%Y-%m-%d %H:%M') for t in stop_points[:5]]}")
        
        if stop_points:
            # Analyser chaque arrêt
            temp_changes = []
            
            st.write(f"**{len(stop_points)} arrêts détectés pour {selected_clim}**")
            st.write(f"**Analyse de tous les {len(stop_points)} arrêts...**")
            
            # Progress bar for large datasets
            progress_bar = st.progress(0)
            
            for i, stop_time in enumerate(stop_points):  # Analyser tous les événements
                # Température au moment de l'arrêt
                temp_at_stop_idx = filtered_merged_data[filtered_merged_data['Timestamp'] <= stop_time]['Temp_Ambiante'].last_valid_index()
                
                if temp_at_stop_idx is not None:
                    temp_at_stop = filtered_merged_data.loc[temp_at_stop_idx, 'Temp_Ambiante']
                    
                    # Température après X minutes
                    time_after = stop_time + timedelta(minutes=minutes_after)
                    after_mask = (filtered_merged_data['Timestamp'] > stop_time) & \
                                (filtered_merged_data['Timestamp'] <= time_after)
                    temps_after = filtered_merged_data[after_mask]['Temp_Ambiante'].dropna()
                    
                    if len(temps_after) > 0:
                        # Prendre la dernière température dans la fenêtre
                        temp_final = temps_after.iloc[-1]
                        temp_change = temp_final - temp_at_stop
                        
                        temp_changes.append({
                            'Timestamp': stop_time,
                            'Temp_Initial': temp_at_stop,
                            'Temp_Final': temp_final,
                            'Delta_Temp': temp_change,
                            'CLIM': selected_clim,
                            'Duration_min': minutes_after,
                            'Num_Points': len(temps_after)
                        })
                    else:
                        # Même si pas de données après, enregistrer ce qu'on a
                        temp_changes.append({
                            'Timestamp': stop_time,
                            'Temp_Initial': temp_at_stop,
                            'Temp_Final': temp_at_stop,  # Pas de changement
                            'Delta_Temp': 0.0,
                            'CLIM': selected_clim,
                            'Duration_min': minutes_after,
                            'Num_Points': 0
                        })
                
                # Update progress bar
                progress_bar.progress((i + 1) / len(stop_points))
            
            # Clear progress bar
            progress_bar.empty()
            
            st.write(f"**Cycles valides trouvés:** {len(temp_changes)}")
            
            if temp_changes:
                # Graphique des changements de température
                df_changes = pd.DataFrame(temp_changes)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_changes.index,
                    y=df_changes['Delta_Temp'],
                    mode='markers',
                    marker=dict(
                        size=10,
                        color=df_changes['Delta_Temp'],
                        colorscale='RdYlBu_r',
                        showscale=True,
                        colorbar=dict(title="ΔT (°C)")
                    ),
                    text=[f"Arrêt: {t.strftime('%Y-%m-%d %H:%M')}<br>ΔT: {d:.2f}°C" 
                          for t, d in zip(df_changes['Timestamp'], df_changes['Delta_Temp'])],
                    hovertemplate='%{text}<extra></extra>'
                ))
                
                # Ligne de référence à zéro
                fig.add_hline(y=0, line_dash="dash", line_color="gray")
                
                # Ligne de tendance moyenne
                avg_change = df_changes['Delta_Temp'].mean()
                fig.add_hline(y=avg_change, line_dash="solid", line_color="red",
                            annotation_text=f"Moyenne: {avg_change:.2f}°C")
                
                fig.update_layout(
                    title=f"Changement de température {minutes_after} min après arrêt - {selected_clim}",
                    xaxis_title="Événement d'arrêt",
                    yaxis_title="Changement de température (°C)",
                    height=500
                )
                
                st.plotly_chart(fig, width='stretch', key="clim_impact_analysis")
                
                # Tableau récapitulatif détaillé
                st.subheader("📊 Résumé statistique complet")
                
                # Première ligne de métriques
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("ΔT Moyen", f"{df_changes['Delta_Temp'].mean():.2f}°C")
                with col2:
                    st.metric("ΔT Médian", f"{df_changes['Delta_Temp'].median():.2f}°C")
                with col3:
                    st.metric("ΔT Min", f"{df_changes['Delta_Temp'].min():.2f}°C")
                with col4:
                    st.metric("ΔT Max", f"{df_changes['Delta_Temp'].max():.2f}°C")
                with col5:
                    st.metric("Écart-type", f"{df_changes['Delta_Temp'].std():.2f}°C")
                
                # Deuxième ligne de métriques
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Amplitude", f"{df_changes['Delta_Temp'].max() - df_changes['Delta_Temp'].min():.2f}°C")
                with col2:
                    positive_changes = df_changes[df_changes['Delta_Temp'] > 0]
                    st.metric("Augmentations", f"{len(positive_changes)} ({len(positive_changes)/len(df_changes)*100:.1f}%)")
                with col3:
                    negative_changes = df_changes[df_changes['Delta_Temp'] < 0]
                    st.metric("Diminutions", f"{len(negative_changes)} ({len(negative_changes)/len(df_changes)*100:.1f}%)")
                with col4:
                    zero_changes = df_changes[df_changes['Delta_Temp'] == 0]
                    st.metric("Sans changement", f"{len(zero_changes)} ({len(zero_changes)/len(df_changes)*100:.1f}%)")
                
                # Tableau détaillé de tous les événements
                st.subheader("📋 Détail de tous les arrêts CLIM")
                
                # Préparer les données pour l'affichage
                display_df = df_changes.copy()
                display_df['Timestamp'] = display_df['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                display_df['Temp_Initial'] = display_df['Temp_Initial'].round(2)
                display_df['Temp_Final'] = display_df['Temp_Final'].round(2)
                display_df['Delta_Temp'] = display_df['Delta_Temp'].round(2)
                
                # Ajouter une colonne pour l'index
                display_df.insert(0, 'N°', range(1, len(display_df) + 1))
                
                # Renommer les colonnes pour l'affichage
                display_df = display_df.rename(columns={
                    'Timestamp': 'Date/Heure arrêt',
                    'Temp_Initial': 'T° initiale (°C)',
                    'Temp_Final': f'T° après {minutes_after}min (°C)',
                    'Delta_Temp': 'ΔT (°C)',
                    'Num_Points': 'Points de données'
                })
                
                # Sélectionner les colonnes à afficher
                columns_to_display = ['N°', 'Date/Heure arrêt', 'T° initiale (°C)', 
                                     f'T° après {minutes_after}min (°C)', 'ΔT (°C)', 'Points de données']
                
                # Utiliser un expander si il y a beaucoup d'événements
                if len(display_df) > 20:
                    with st.expander(f"Voir tous les {len(display_df)} événements"):
                        st.dataframe(
                            display_df[columns_to_display],
                            width='stretch',
                            hide_index=True
                        )
                else:
                    st.dataframe(
                        display_df[columns_to_display],
                        width='stretch',
                        hide_index=True
                    )
                
                # Bouton pour télécharger les données
                csv = display_df[columns_to_display].to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Télécharger les données en CSV",
                    data=csv,
                    file_name=f"analyse_arrets_{selected_clim}_{minutes_after}min.csv",
                    mime="text/csv"
                )
                
                # Visualisations supplémentaires des distributions
                st.subheader("📊 Distribution des changements de température")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Histogramme des changements de température
                    fig_hist = go.Figure()
                    fig_hist.add_trace(go.Histogram(
                        x=df_changes['Delta_Temp'],
                        nbinsx=20,
                        name='Distribution',
                        marker_color='lightblue',
                        opacity=0.7
                    ))
                    
                    # Ajouter une ligne verticale pour la moyenne
                    mean_delta = df_changes['Delta_Temp'].mean()
                    fig_hist.add_vline(x=mean_delta, line_dash="dash", line_color="red",
                                      annotation_text=f"Moyenne: {mean_delta:.2f}°C")
                    
                    # Ajouter une ligne verticale pour la médiane
                    median_delta = df_changes['Delta_Temp'].median()
                    fig_hist.add_vline(x=median_delta, line_dash="dot", line_color="green",
                                      annotation_text=f"Médiane: {median_delta:.2f}°C")
                    
                    fig_hist.update_layout(
                        title="Histogramme des ΔT",
                        xaxis_title="Changement de température (°C)",
                        yaxis_title="Fréquence",
                        showlegend=False,
                        height=400
                    )
                    st.plotly_chart(fig_hist, width='stretch', key="clim_temp_change_histogram")
                
                with col2:
                    # Box plot des changements de température
                    fig_box = go.Figure()
                    fig_box.add_trace(go.Box(
                        y=df_changes['Delta_Temp'],
                        name='ΔT',
                        boxpoints='outliers',
                        marker_color='lightgreen',
                        line_color='darkgreen'
                    ))
                    
                    fig_box.update_layout(
                        title="Box Plot des ΔT",
                        yaxis_title="Changement de température (°C)",
                        showlegend=False,
                        height=400
                    )
                    
                    # Ajouter des annotations pour les quartiles
                    q1 = df_changes['Delta_Temp'].quantile(0.25)
                    q3 = df_changes['Delta_Temp'].quantile(0.75)
                    iqr = q3 - q1
                    
                    fig_box.add_annotation(
                        x=0.5, y=q1,
                        text=f"Q1: {q1:.2f}°C",
                        showarrow=True,
                        arrowhead=2,
                        xref="paper"
                    )
                    
                    fig_box.add_annotation(
                        x=0.5, y=q3,
                        text=f"Q3: {q3:.2f}°C",
                        showarrow=True,
                        arrowhead=2,
                        xref="paper"
                    )
                    
                    st.plotly_chart(fig_box, width='stretch', key="clim_temp_change_boxplot")
                
                # Graphique temporel
                st.subheader("📈 Évolution temporelle de la température")
                
                # Sélectionner un événement à visualiser
                event_idx = st.selectbox(
                    "Sélectionner un arrêt à visualiser",
                    range(len(df_changes)),
                    format_func=lambda x: f"Arrêt {x+1} - {df_changes.iloc[x]['Timestamp'].strftime('%Y-%m-%d %H:%M')} (ΔT: {df_changes.iloc[x]['Delta_Temp']:.2f}°C)"
                )
                
                if event_idx is not None:
                    selected_event = df_changes.iloc[event_idx]
                    stop_time = selected_event['Timestamp']
                    
                    # Récupérer les données pour visualiser
                    viz_start = stop_time - timedelta(minutes=15)
                    viz_end = stop_time + timedelta(minutes=minutes_after + 10)
                    
                    viz_mask = (filtered_merged_data['Timestamp'] >= viz_start) & \
                              (filtered_merged_data['Timestamp'] <= viz_end)
                    viz_data = filtered_merged_data[viz_mask].copy()
                    
                    if len(viz_data) > 0:
                        fig_timeline = go.Figure()
                        
                        # Température
                        fig_timeline.add_trace(go.Scatter(
                            x=viz_data['Timestamp'],
                            y=viz_data['Temp_Ambiante'],
                            mode='lines',
                            name='Température',
                            line=dict(color='red', width=2)
                        ))
                        
                        # État du CLIM
                        fig_timeline.add_trace(go.Scatter(
                            x=viz_data['Timestamp'],
                            y=viz_data[selected_clim] * viz_data['Temp_Ambiante'].max() * 0.95,
                            mode='lines',
                            name=f'{selected_clim} (ON/OFF)',
                            line=dict(color='blue', width=2, dash='dash'),
                            yaxis='y2'
                        ))
                        
                        # Marquer l'arrêt avec add_shape au lieu de add_vline
                        fig_timeline.add_shape(
                            type="line",
                            x0=stop_time, x1=stop_time,
                            y0=0, y1=1,
                            yref="paper",
                            line=dict(color="green", width=2, dash="dash")
                        )
                        fig_timeline.add_annotation(
                            x=stop_time,
                            y=1.05,
                            yref="paper",
                            text="Arrêt CLIM",
                            showarrow=False
                        )
                        
                        # Marquer la fin de la fenêtre d'analyse
                        end_time = stop_time + timedelta(minutes=minutes_after)
                        fig_timeline.add_shape(
                            type="line",
                            x0=end_time, x1=end_time,
                            y0=0, y1=1,
                            yref="paper",
                            line=dict(color="orange", width=1, dash="dot")
                        )
                        fig_timeline.add_annotation(
                            x=end_time,
                            y=1.05,
                            yref="paper",
                            text=f"+{minutes_after} min",
                            showarrow=False
                        )
                        
                        fig_timeline.update_layout(
                            title=f"Évolution autour de l'arrêt du {stop_time.strftime('%Y-%m-%d %H:%M')}",
                            xaxis_title="Temps",
                            yaxis_title="Température (°C)",
                            yaxis2=dict(
                                title="État CLIM",
                                overlaying='y',
                                side='right',
                                showticklabels=False
                            ),
                            height=400
                        )
                        
                        st.plotly_chart(fig_timeline, width='stretch', key="clim_temp_timeline")
                
                # Tableau détaillé
                with st.expander("📋 Voir le détail des événements"):
                    st.dataframe(
                        df_changes.style.format({
                            'Temp_Initial': '{:.1f}°C',
                            'Temp_Final': '{:.1f}°C',
                            'Delta_Temp': '{:.2f}°C'
                        })
                    )
            else:
                st.info(f"Aucun changement de température mesuré après les arrêts de {selected_clim}.")
        else:
            st.warning(f"Aucun arrêt détecté pour {selected_clim} dans la période sélectionnée.")