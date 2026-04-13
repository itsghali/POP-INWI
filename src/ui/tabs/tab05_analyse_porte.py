"""
Tab 5: Analyse de l'impact de l'ouverture de porte
Analyse l'évolution de la température pendant les cycles d'ouverture et fermeture de porte.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import timedelta


def render_tab(filtered_merged_data, start_date, end_date):
    """
    Affiche l'analyse de l'impact de l'ouverture de porte sur la température.
    
    Args:
        filtered_merged_data: DataFrame avec données filtrées
        start_date: Date de début de la période
        end_date: Date de fin de la période
    """
    # Assurez-vous que merged_data est disponible (copie de filtered_merged_data)
    merged_data = filtered_merged_data.copy()
    
    st.header("🚪 Analyse de l'impact de l'ouverture de porte")
    
    # Explication d'un cycle
    st.info("💡 **Qu'est-ce qu'un cycle ?** Un cycle correspond à une séquence complète d'ouverture et de fermeture de la porte. Il commence quand la porte passe de l'état fermé à ouvert, et se termine quand elle revient à l'état fermé. L'analyse suit l'évolution de la température pendant chaque cycle.")
    
    # Vérifier la présence des colonnes attendues
    if 'Porte_Status' in merged_data.columns and 'Temp_Ambiante' in merged_data.columns:
        porte_data_raw = merged_data[['Timestamp', 'Porte_Status', 'Temp_Ambiante']].copy()

        # Préparer porte_data_clean dès maintenant pour éviter les références avant assignation
        porte_data_clean = porte_data_raw[porte_data_raw['Porte_Status'].notna()].copy()
        
        # Exemple de debug commenté (préférer # pour éviter les triple-quotes indentées)
        # with st.expander("🔍 Debug - Données de porte brutes (non-NaN uniquement)"):
        #     st.write(f"Nombre d'entrées non-NaN: {len(porte_data_clean)}")
        #     st.write(f"Valeurs uniques dans Porte_Status: {porte_data_clean['Porte_Status'].unique()}")
        #     st.write(f"Nombre de 1 (ouvert): {(porte_data_clean['Porte_Status'] == 1).sum()}")
        #     st.write(f"Nombre de 0 (fermé): {(porte_data_clean['Porte_Status'] == 0).sum()}")
        #     door_events_sorted = porte_data_clean.sort_values('Timestamp')
        #     door_events_sorted['Status_Change'] = door_events_sorted['Porte_Status'] != door_events_sorted['Porte_Status'].shift(1)
        #     transitions = door_events_sorted[door_events_sorted['Status_Change']]
        #     st.write(f"\nTransitions dans les données brutes: {len(transitions)}")
        #     if len(transitions) > 0:
        #         st.dataframe(transitions[['Timestamp', 'Porte_Status']].head(20))
        
        # Fonction robuste de détection des cycles de porte
        def detect_door_cycles(
                df,
                ts_col='Timestamp',
                status_col='Porte_Status',
                min_duration_sec=5,
                max_duration_hours=24,
                assume_close_at_end=True
            ):
            """
            Détecte les cycles d'ouverture/fermeture de porte.
            Approche simple: chaque "Ouverte" est appariée avec le prochain "Fermé".
            """
            # Copie pour éviter de modifier l'original
            df_proc = df.copy()
            
            # 1. Sort by timestamp
            df_proc = df_proc.sort_values(ts_col).reset_index(drop=True)
            
            # 2. Convertir le statut en valeur numérique (1=ouvert, 0=fermé)
            if pd.api.types.is_string_dtype(df_proc[status_col]):
                # Gérer les statuts textuels en français
                clean_status = df_proc[status_col].str.strip().str.lower()
                status_map = {
                    'ouverte': 1, 
                    'ouvert': 1, 
                    'fermé': 0, 
                    'ferme': 0,
                    'fermée': 0
                }
                df_proc['state'] = clean_status.map(status_map)
                df_proc['state'] = df_proc['state'].fillna(0)
            else:
                # Gérer les données numériques
                df_proc['state'] = pd.to_numeric(df_proc[status_col], errors='coerce').fillna(0)
            
            df_proc['state'] = df_proc['state'].astype(int)
            
            # 3. Algorithme corrigé: parcourir et apparier en sautant les ouvertures consécutives
            cycles_list = []
            i = 0
            
            while i < len(df_proc):
                # Chercher une ouverture
                if df_proc.iloc[i]['state'] == 1 and pd.notna(df_proc.iloc[i][ts_col]):
                    open_time = df_proc.iloc[i][ts_col]
                    open_idx = i
                    
                    # Sauter toutes les ouvertures consécutives
                    j = i + 1
                    while j < len(df_proc) and df_proc.iloc[j]['state'] == 1:
                        j += 1
                    
                    # Maintenant j pointe soit sur un 'Fermé' soit sur la fin des données
                    close_time = None
                    close_idx = None
                    
                    if j < len(df_proc) and df_proc.iloc[j]['state'] == 0:
                        close_time = df_proc.iloc[j][ts_col]
                        close_idx = j
                    
                    # Si pas de fermeture trouvée
                    if close_time is None or pd.isna(close_time):
                        if assume_close_at_end and pd.notna(open_time):
                            # Utiliser le dernier timestamp + 30 min ou la durée max
                            last_time = df_proc.iloc[-1][ts_col]
                            if pd.notna(last_time):
                                duration_to_last = (last_time - open_time).total_seconds()
                                
                                if duration_to_last > max_duration_hours * 3600:
                                    close_time = open_time + pd.Timedelta(hours=max_duration_hours)
                                else:
                                    close_time = last_time + pd.Timedelta(minutes=30)
                            else:
                                close_time = open_time + pd.Timedelta(minutes=30)
                            
                            # Créer le cycle avec fermeture assumée
                            duration_sec = (close_time - open_time).total_seconds()
                            if duration_sec >= min_duration_sec:
                                cycles_list.append({
                                    'open_ts': open_time,
                                    'close_ts': close_time,
                                    'duration_sec': duration_sec
                                })
                        
                        # Passer au-delà de toutes les ouvertures
                        i = j
                    else:
                        # Calculer la durée
                        if pd.notna(open_time) and pd.notna(close_time):
                            duration_sec = (close_time - open_time).total_seconds()
                            
                            # Ajouter le cycle si la durée est valide
                            if duration_sec >= min_duration_sec:
                                cycles_list.append({
                                    'open_ts': open_time,
                                    'close_ts': close_time,
                                    'duration_sec': duration_sec
                                })
                        
                        # Continuer après l'événement de fermeture
                        i = close_idx + 1 if close_idx is not None else j
                else:
                    i += 1
            
            # 4. Créer le DataFrame des cycles
            cycles_df = pd.DataFrame(cycles_list)
            
            if len(cycles_df) == 0:
                cycles_df = pd.DataFrame(columns=['open_ts', 'close_ts', 'duration_sec'])
            
            # Store debug info for display
            cycles_df.attrs['debug_df'] = df_proc[[ts_col, status_col, 'state']].head(100)
            
            return cycles_df
       
        # Paramètres de détection conservés en interne (sans affichage UI)
        min_duration = 0
        max_duration = 24
        detection_mode = "Automatique"
        
        # Initialiser cycles_df par défaut
        cycles_df = pd.DataFrame(columns=['open_ts', 'close_ts', 'duration_sec'])
        
        # Utiliser la nouvelle fonction de détection
        if len(porte_data_clean) > 0:
            # Mode événements individuels - traiter chaque "Ouverte" comme un cycle
            if detection_mode == "Événements individuels":
                # Filtrer seulement les événements d'ouverture
                if pd.api.types.is_string_dtype(porte_data_clean['Porte_Status']):
                    open_events_df = porte_data_clean[
                        porte_data_clean['Porte_Status'].str.lower().isin(['ouverte', 'ouvert'])
                    ].copy()
                else:
                    # Données numériques (1 = ouvert, 0 = fermé)
                    open_events_df = porte_data_clean[
                        porte_data_clean['Porte_Status'] == 1
                    ].copy()
                
                cycles_list = []
                for i, row in open_events_df.iterrows():
                    # Assumer une durée fixe ou jusqu'au prochain événement
                    open_time = row['Timestamp']
                    # Chercher le prochain événement pour déterminer la durée
                    next_events = porte_data_clean[porte_data_clean['Timestamp'] > open_time].head(5)
                    
                    if len(next_events) > 0:
                        # Utiliser le prochain timestamp comme fermeture approximative
                        close_time = next_events.iloc[0]['Timestamp']
                        duration = (close_time - open_time).total_seconds()
                        
                        # Si la durée est trop longue, limiter à 1 heure
                        if duration > 3600:
                            close_time = open_time + pd.Timedelta(hours=1)
                            duration = 3600
                    else:
                        # Pas d'événement suivant, assumer 30 minutes
                        close_time = open_time + pd.Timedelta(minutes=30)
                        duration = 1800
                    
                    if duration >= min_duration:
                        cycles_list.append({
                            'open_ts': open_time,
                            'close_ts': close_time,
                            'duration_sec': duration
                        })
                
                cycles_df = pd.DataFrame(cycles_list)
                if len(cycles_df) > 0:
                    cycles_df = cycles_df.sort_values('open_ts').reset_index(drop=True)
                else:
                    cycles_df = pd.DataFrame(columns=['open_ts', 'close_ts', 'duration_sec'])
                    
                st.info(f"Mode événements individuels: {len(open_events_df)} événements 'Ouverte' détectés → {len(cycles_df)} cycles créés")
            else:
                # Mode normal ou automatique
                cycles_df = detect_door_cycles(
                    porte_data_clean,
                    ts_col='Timestamp', 
                    status_col='Porte_Status',
                    min_duration_sec=min_duration,
                    max_duration_hours=max_duration
                )
            
        else:
            st.warning("Aucune donnée de porte valide trouvée")
            cycles_df = pd.DataFrame(columns=['open_ts', 'close_ts', 'duration_sec'])
        
        # Visualisation Timeline des cycles de porte
        if len(cycles_df) > 0:
            st.subheader("📅 Timeline des cycles de porte")
            
            # Créer une figure pour la timeline
            fig_timeline = go.Figure()
            
            # Ajouter chaque cycle comme une barre horizontale
            for i, row in cycles_df.iterrows():
                open_time = row['open_ts']
                close_time = row['close_ts']
                duration_min = row['duration_sec'] / 60

                # Calculer ΔT (température après - température avant) pour l'infobulle
                before_window_start = open_time - timedelta(minutes=30)
                before_window_end = open_time
                before_data = merged_data[
                    (merged_data['Timestamp'] >= before_window_start) &
                    (merged_data['Timestamp'] < before_window_end)
                ].copy()
                before_5min = before_data[
                    before_data['Timestamp'] >= (open_time - timedelta(minutes=5))
                ]

                if len(before_5min) > 0:
                    temp_before = before_5min['Temp_Ambiante'].mean()
                elif len(before_data) > 0:
                    temp_before = before_data.iloc[-1]['Temp_Ambiante']
                else:
                    temp_before = np.nan

                after_data = merged_data[
                    (merged_data['Timestamp'] >= open_time) &
                    (merged_data['Timestamp'] <= close_time + timedelta(minutes=10))
                ].copy()
                temp_after = after_data['Temp_Ambiante'].max() if len(after_data) > 0 else np.nan

                delta_temp = temp_after - temp_before if pd.notna(temp_before) and pd.notna(temp_after) else np.nan
                delta_temp_display = f"{delta_temp:.2f}°C" if pd.notna(delta_temp) else "N/A"
                open_display = pd.to_datetime(open_time).strftime('%Y-%m-%d %H:%M:%S')
                close_display = pd.to_datetime(close_time).strftime('%Y-%m-%d %H:%M:%S')

                fig_timeline.add_trace(go.Scatter(
                    x=[open_time, close_time],
                    y=[i, i],
                    mode='lines',
                    line=dict(color='red', width=10),
                    name=f"Cycle {i+1}",
                    meta=i + 1,
                    customdata=[
                        [open_display, close_display, duration_min, delta_temp_display],
                        [open_display, close_display, duration_min, delta_temp_display]
                    ],
                    hovertemplate=(
                        "Cycle %{meta}<br>"
                        "Ouverture: %{customdata[0]}<br>"
                        "Fermeture: %{customdata[1]}<br>"
                        "Durée: %{customdata[2]:.1f} min<br>"
                        "ΔT: %{customdata[3]}<extra></extra>"
                    ),
                    showlegend=False
                ))
                
                # Ajouter des marqueurs pour début et fin
                fig_timeline.add_trace(go.Scatter(
                    x=[open_time, close_time],
                    y=[i, i],
                    mode='markers',
                    marker=dict(size=12, color=['green', 'red']),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Mise en forme de la timeline
            fig_timeline.update_layout(
                title="Chronologie des ouvertures de porte",
                xaxis_title="Temps",
                yaxis_title="Cycles",
                height=max(300, min(600, 50 + len(cycles_df) * 30)),
                yaxis=dict(
                    tickmode='linear',
                    tick0=0,
                    dtick=1,
                    ticktext=[f"Cycle {i+1}" for i in range(len(cycles_df))],
                    tickvals=list(range(len(cycles_df)))
                ),
                showlegend=False,
                hovermode='closest'
            )
            
            # Ajouter une annotation pour la légende
            fig_timeline.add_annotation(
                text="🟢 Ouverture | 🔴 Fermeture",
                xref="paper", yref="paper",
                x=0.5, y=1.05,
                showarrow=False,
                font=dict(size=12)
            )
            
            st.plotly_chart(fig_timeline, width='stretch', key="door_cycles_timeline")
            
            # Statistiques rapides
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total cycles", len(cycles_df))
            with col2:
                st.metric("Durée moyenne", f"{cycles_df['duration_sec'].mean()/60:.1f} min")
            with col3:
                st.metric("Durée totale", f"{cycles_df['duration_sec'].sum()/60:.1f} min")
            with col4:
                if len(filtered_merged_data) > 0:
                    time_range = (filtered_merged_data['Timestamp'].max() - filtered_merged_data['Timestamp'].min()).total_seconds() / 3600
                    if time_range > 0:
                        freq = len(cycles_df) / time_range
                        st.metric("Fréquence", f"{freq:.2f} cycles/h")
        
        # Convertir en format attendu par le reste du code
        if 'open_ts' in cycles_df.columns:
            open_events = cycles_df['open_ts'].tolist()
            close_events = cycles_df['close_ts'].tolist()
        else:
            open_events = []
            close_events = []
        
        st.write(f"**Cycles valides détectés:** {len(cycles_df)} cycles")
        
        # Analyse des cycles ouverture-fermeture
        # Utiliser les événements d'ouverture détectés pour créer des cycles
        door_cycles = []
        all_door_cycles = []  # Nouveau: garder tous les cycles même sans température
        
        if len(cycles_df) > 0:
            # NOUVELLE APPROCHE: Prétraiter les données de température
            # 1. Créer une copie pour le traitement
            temp_processed = merged_data[['Timestamp', 'Temp_Ambiante']].copy()
            temp_processed = temp_processed.sort_values('Timestamp')
            
            # 2. Remplir les NaN intelligemment
            temp_processed['Temp_Ambiante_Interpolated'] = temp_processed['Temp_Ambiante'].interpolate(
                method='linear', 
                limit=10  # Max 10 points consécutifs
            )
            temp_processed['Temp_Ambiante_Filled'] = temp_processed['Temp_Ambiante_Interpolated'].ffill().bfill()
            global_mean = temp_processed['Temp_Ambiante'].mean()
            if pd.notna(global_mean):
                temp_processed['Temp_Ambiante_Final'] = temp_processed['Temp_Ambiante_Filled'].fillna(global_mean)
            else:
                temp_processed['Temp_Ambiante_Final'] = temp_processed['Temp_Ambiante_Filled']
            
            # 3. Remplacer dans filtered_merged_data (merge sur Timestamp)
            merged_temp = temp_processed[['Timestamp', 'Temp_Ambiante_Final']].copy()
            merged_temp = merged_temp.rename(columns={'Temp_Ambiante_Final': 'Temp_Ambiante_Filled'})
            merged_with_temp = pd.merge(merged_data, merged_temp, on='Timestamp', how='left')
            merged_with_temp['Temp_Ambiante'] = merged_with_temp['Temp_Ambiante_Filled']
            # Utiliser merged_with_temp pour les extractions de température
            processed_data = merged_with_temp.copy()
            
            # Pour chaque cycle, analyser l'impact sur la température
            for i, cycle in cycles_df.iterrows():
                open_time = cycle['open_ts']
                close_time = cycle['close_ts']
                cycle_duration = cycle['duration_sec'] / 60  # Convertir en minutes
                
                # Enregistrer tous les cycles (avec ou sans température)
                all_door_cycles.append({
                    'Open_Time': open_time,
                    'Close_Time': close_time,
                    'Duration_min': cycle_duration,
                    'Is_Complete_Cycle': True,
                    'Has_Temp_Data': False
                })
                
                # 1. Température AVANT l'ouverture (baseline)
                before_window_start = open_time - timedelta(minutes=30)
                before_window_end = open_time
                
                before_data = processed_data[
                    (processed_data['Timestamp'] >= before_window_start) & 
                    (processed_data['Timestamp'] < before_window_end)
                ].copy()
                
                before_5min = before_data[before_data['Timestamp'] >= (open_time - timedelta(minutes=5))]
                if len(before_5min) > 0:
                    temp_before = before_5min['Temp_Ambiante'].mean()
                elif len(before_data) > 0:
                    temp_before = before_data.iloc[-1]['Temp_Ambiante']
                else:
                    temp_before = np.nan
                
                # 2. Température PENDANT/APRÈS le cycle
                after_window_start = open_time
                after_window_end = close_time + timedelta(minutes=10)
                
                after_data = processed_data[
                    (processed_data['Timestamp'] >= after_window_start) & 
                    (processed_data['Timestamp'] <= after_window_end)
                ].copy()
                
                if len(after_data) > 0:
                    temp_after = after_data['Temp_Ambiante'].max()
                else:
                    temp_after = np.nan
                
                # 3. Données complètes pour visualisation
                full_window_start = before_window_start
                full_window_end = after_window_end
                
                full_cycle_data = processed_data[
                    (processed_data['Timestamp'] >= full_window_start) & 
                    (processed_data['Timestamp'] <= full_window_end)
                ].copy()
                
                # Vérifier que les températures sont valides
                if pd.notna(temp_before) and pd.notna(temp_after):
                    # Marquer ce cycle comme ayant des données de température
                    all_door_cycles[-1]['Has_Temp_Data'] = True
                    
                    door_cycles.append({
                        'Open_Time': open_time,
                        'Close_Time': close_time,
                        'Duration_min': cycle_duration,
                        'Temp_Before': temp_before,
                        'Temp_After': temp_after,
                        'Delta_Temp': temp_after - temp_before,
                        'Cycle_Data': full_cycle_data,
                        'Before_Data': before_data,
                        'After_Data': after_data,
                        'Is_Complete_Cycle': True
                    })
        
        # Suite de l'analyse si door_cycles présent ...
        if len(door_cycles) > 0:
            # Convertir en DataFrame pour les statistiques
            door_impacts = []
            for cycle in door_cycles:
                if (pd.notna(cycle['Temp_Before']) and 
                    pd.notna(cycle['Temp_After']) and 
                    pd.notna(cycle['Duration_min'])):
                    
                    door_impacts.append({
                        'Timestamp': cycle['Open_Time'],
                        'Duree_Analyse': cycle['Duration_min'],
                        'Temp_Avant': cycle['Temp_Before'],
                        'Temp_Apres': cycle['Temp_After'],
                        'Delta_Temp': cycle['Delta_Temp']
                    })
            
            if door_impacts and len(door_impacts) > 0:
                df_impacts = pd.DataFrame(door_impacts)

                # Graphique d'analyse (sélection individuelle)
                st.subheader("📈 Évolution temporelle de la température par cycle")

                cycle_idx = st.selectbox(
                    "Sélectionner un cycle à visualiser",
                    range(len(door_cycles)),
                    format_func=lambda x: f"Cycle {x+1} - {door_cycles[x]['Open_Time'].strftime('%Y-%m-%d %H:%M')} (ΔT: {door_cycles[x]['Delta_Temp']:.2f}°C, Durée: {door_cycles[x]['Duration_min']:.1f} min)"
                )

                if cycle_idx is not None:
                    selected_cycle = door_cycles[cycle_idx]
                    cycle_data = selected_cycle['Cycle_Data']

                    if len(cycle_data) > 0:
                        fig_selected = go.Figure()

                        # Température
                        fig_selected.add_trace(go.Scatter(
                            x=cycle_data['Timestamp'],
                            y=cycle_data['Temp_Ambiante'],
                            mode='lines+markers',
                            name='Température',
                            line=dict(color='red', width=2),
                            marker=dict(size=6)
                        ))

                        # Marquer l'ouverture et la fermeture
                        fig_selected.add_shape(
                            type="line",
                            x0=selected_cycle['Open_Time'], x1=selected_cycle['Open_Time'],
                            y0=0, y1=1,
                            yref="paper",
                            line=dict(color="green", width=2, dash="dash")
                        )
                        fig_selected.add_annotation(
                            x=selected_cycle['Open_Time'],
                            y=1.05,
                            yref="paper",
                            text="Ouverture",
                            showarrow=False
                        )

                        fig_selected.add_shape(
                            type="line",
                            x0=selected_cycle['Close_Time'], x1=selected_cycle['Close_Time'],
                            y0=0, y1=1,
                            yref="paper",
                            line=dict(color="orange", width=2, dash="dash")
                        )
                        fig_selected.add_annotation(
                            x=selected_cycle['Close_Time'],
                            y=1.05,
                            yref="paper",
                            text="Fermeture",
                            showarrow=False
                        )

                        # Lignes horizontales avant/après
                        fig_selected.add_hline(
                            y=selected_cycle['Temp_Before'],
                            line_dash="dot",
                            line_color="blue",
                            annotation_text=f"Temp avant: {selected_cycle['Temp_Before']:.1f}°C"
                        )

                        fig_selected.add_hline(
                            y=selected_cycle['Temp_After'],
                            line_dash="dot",
                            line_color="purple",
                            annotation_text=f"Temp après: {selected_cycle['Temp_After']:.1f}°C"
                        )

                        fig_selected.update_layout(
                            title=f"Cycle {cycle_idx+1} - {selected_cycle['Open_Time'].strftime('%Y-%m-%d %H:%M')} (Durée: {selected_cycle['Duration_min']:.1f} min, ΔT: {selected_cycle['Delta_Temp']:.2f}°C)",
                            xaxis_title="Temps",
                            yaxis_title="Température (°C)",
                            height=450,
                            hovermode='x unified'
                        )

                        st.plotly_chart(fig_selected, width='stretch', key=f"door_cycle_detail_{cycle_idx}")

                        # Détails
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Température avant", f"{selected_cycle['Temp_Before']:.1f}°C")
                        with col2:
                            st.metric("Température après", f"{selected_cycle['Temp_After']:.1f}°C")
                        with col3:
                            st.metric(
                                "Variation",
                                f"{selected_cycle['Delta_Temp']:.2f}°C",
                                delta=f"{'↑' if selected_cycle['Delta_Temp'] > 0 else '↓'} {abs(selected_cycle['Delta_Temp']):.2f}°C"
                            )
                        with col4:
                            st.metric("Durée", f"{selected_cycle['Duration_min']:.1f} min")
                
                # Statistiques des cycles
                st.subheader("📊 Statistiques des cycles d'ouverture")
                
                valid_data = df_impacts.dropna(subset=['Delta_Temp', 'Duree_Analyse'])
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Nombre de cycles", len(valid_data))
                with col2:
                    if len(valid_data) > 0:
                        st.metric("ΔT moyen", f"{valid_data['Delta_Temp'].mean():.2f}°C")
                    else:
                        st.metric("ΔT moyen", "N/A")
                with col3:
                    if len(valid_data) > 0:
                        avg_duration = valid_data['Duree_Analyse'].mean()
                        st.metric("Durée moyenne cycle", f"{avg_duration:.0f} min")
                    else:
                        st.metric("Durée moyenne cycle", "N/A")
                with col4:
                    if len(valid_data) > 0:
                        st.metric("ΔT max", f"{valid_data['Delta_Temp'].max():.2f}°C")
                    else:
                        st.metric("ΔT max", "N/A")
                
                # Interprétation
                if len(valid_data) > 0:
                    avg_impact = valid_data['Delta_Temp'].mean()
                    avg_duration = valid_data['Duree_Analyse'].mean()
                    
                    if avg_impact > 0.1:
                        interpretation = f"🔥 Pendant l'ouverture de porte (durée moyenne: {avg_duration:.1f} min), la température tend à **augmenter** de {avg_impact:.2f}°C en moyenne."
                    elif avg_impact < -0.1:
                        interpretation = f"❄️ Pendant l'ouverture de porte (durée moyenne: {avg_duration:.1f} min), la température tend à **diminuer** de {abs(avg_impact):.2f}°C en moyenne."
                    else:
                        interpretation = f"🌡️ Pendant l'ouverture de porte (durée moyenne: {avg_duration:.1f} min), la température reste **relativement stable**."
                else:
                    interpretation = "⚠️ Pas assez de données valides pour faire une interprétation."
                
                st.info(interpretation)
                
            else:
                st.warning("Impossible de calculer l'impact sur la température - données insuffisantes.")
        else:
            st.warning("Aucun cycle d'ouverture valide trouvé. Vérifiez que les données de température sont disponibles pendant les périodes d'ouverture.")
            
            # Si on a détecté des cycles mais aucun avec température
            if len(all_door_cycles) > 0:
                st.info(f"ℹ️ Cependant, {len(all_door_cycles)} cycles de porte ont été détectés.")
    else:
        st.warning("Données de porte ou de température manquantes pour l'analyse.")
