"""
Tab 5: Analyse de l'impact de l'ouverture de porte
Analyse l'évolution de la température pendant les cycles d'ouverture et fermeture de porte.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
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
        # Informations sur les données de porte
        st.subheader("📊 État actuel des données de porte")
       
        porte_data_raw = merged_data[['Timestamp', 'Porte_Status', 'Temp_Ambiante']].copy()
        
        # Statistiques des données de porte
        open_records = porte_data_raw['Porte_Status'].notna().sum()
        st.metric("Événements d'ouverture", open_records)
        
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
       
        # Paramètres de détection ajustables
        st.subheader("⚙️ Paramètres de détection des cycles")
        col1, col2, col3 = st.columns(3)
        with col1:
            min_duration = st.number_input(
                "Durée min (secondes)", 
                min_value=0, 
                max_value=3600, 
                value=0,
                help="Durée minimale pour qu'un cycle soit considéré valide (0 = pas de filtre)"
            )
        with col2:
            max_duration = st.number_input(
                "Durée max (heures)", 
                min_value=1, 
                max_value=48, 
                value=24,
                help="Durée maximale d'un cycle"
            )
        with col3:
            detection_mode = st.selectbox(
                "Mode de détection",
                ["Automatique", "Événements individuels", "Groupes stricts"],
                help="Automatique: s'adapte aux données. Événements: chaque entrée 'Ouverte' est un cycle. Groupes: transitions uniquement."
            )
        
        # Informations debug
        with st.expander("🔍 Debug - Analyse détaillée des données de porte", expanded=False):
            st.write("### Données brutes")
            st.write(f"- Shape: {porte_data_raw.shape}")
            st.write(f"- Colonnes: {porte_data_raw.columns.tolist()}")
            
            # Analyser les valeurs de Porte_Status
            st.write("\n### Analyse de Porte_Status")
            st.write(f"- Type de données: {porte_data_raw['Porte_Status'].dtype}")
            st.write(f"- Nombre total de valeurs: {len(porte_data_raw)}")
            st.write(f"- Valeurs non-NaN: {porte_data_raw['Porte_Status'].notna().sum()}")
            st.write(f"- Valeurs NaN: {porte_data_raw['Porte_Status'].isna().sum()}")
            
            if len(porte_data_clean) > 0:
                st.write(f"\n### Après filtrage des NaN: {len(porte_data_clean)} lignes")
                unique_vals = porte_data_clean['Porte_Status'].unique()
                st.write(f"- Valeurs uniques: {sorted(unique_vals)}")
                
                # Si les valeurs sont du texte, afficher le mapping
                if pd.api.types.is_string_dtype(porte_data_clean['Porte_Status']):
                    st.write("\n### Mapping des valeurs textuelles:")
                    st.write("- 'Ouverte' → 1 (porte ouverte)")
                    st.write("- 'Fermé' → 0 (porte fermée)")
                
                # Distribution des valeurs
                value_counts = porte_data_clean['Porte_Status'].value_counts().sort_index()
                st.write("\n### Distribution des valeurs:")
                for val, count in value_counts.items():
                    st.write(f"  - {val}: {count} ({count/len(porte_data_clean)*100:.1f}%)")
                
                # Vérifier les transitions
                porte_sorted = porte_data_clean.sort_values('Timestamp').copy()
                porte_sorted['prev_status'] = porte_sorted['Porte_Status'].shift(1)
                transitions = porte_sorted[porte_sorted['Porte_Status'] != porte_sorted['prev_status']]
                
                st.write(f"\n### Transitions détectées: {len(transitions)}")
                if len(transitions) > 0:
                    st.write("Premières transitions:")
                    st.dataframe(transitions[['Timestamp', 'prev_status', 'Porte_Status']].head(10))
                    
                    # Calculer les durées entre transitions (protégé contre NaT)
                    transitions['time_diff'] = transitions['Timestamp'].diff().dt.total_seconds()
                    st.write(f"\n### Durées entre transitions (secondes):")
                    st.write(f"- Moyenne: {transitions['time_diff'].mean():.1f}s")
                    st.write(f"- Médiane: {transitions['time_diff'].median():.1f}s")
                    st.write(f"- Min: {transitions['time_diff'].min():.1f}s")
                    st.write(f"- Max: {transitions['time_diff'].max():.1f}s")
        
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
            
            st.write(f"\n### Résultat de la détection: {len(cycles_df)} cycles")
            if len(cycles_df) > 0:
                st.write("Cycles détectés:")
                # Create a display copy and ensure all data is properly converted
                cycles_display = cycles_df.copy()
                # Clear any pandas attrs that might contain non-serializable objects (e.g., DataFrames)
                try:
                    cycles_display.attrs = {}
                    for c in cycles_display.columns:
                        try:
                            cycles_display[c].attrs = {}
                        except Exception:
                            pass
                except Exception:
                    pass
                # Ensure simple column/index types
                try:
                    cycles_display.columns = cycles_display.columns.map(str)
                except Exception:
                    pass
                try:
                    cycles_display = cycles_display.reset_index(drop=True)
                except Exception:
                    pass
                
                # First convert timestamps to strings
                if 'open_ts' in cycles_display.columns:
                    cycles_display['open_ts'] = pd.to_datetime(cycles_display['open_ts']).dt.strftime('%Y-%m-%d %H:%M:%S')
                if 'close_ts' in cycles_display.columns:
                    cycles_display['close_ts'] = pd.to_datetime(cycles_display['close_ts']).dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                # Add duration in minutes
                cycles_display['duration_min'] = cycles_display['duration_sec'].astype(float) / 60
                
                # Ensure all numeric columns are float
                numeric_cols = ['duration_sec', 'duration_min']
                for col in numeric_cols:
                    if col in cycles_display.columns:
                        cycles_display[col] = cycles_display[col].astype(float)
                
                # Convert any remaining object columns to string
                for col in cycles_display.columns:
                    if cycles_display[col].dtype == 'object':
                        cycles_display[col] = cycles_display[col].astype(str)
                        
                st.dataframe(cycles_display)
        else:
            st.warning("Aucune donnée de porte valide trouvée")
            cycles_df = pd.DataFrame(columns=['open_ts', 'close_ts', 'duration_sec'])
        
        # Debug: Afficher les cycles détectés
        with st.expander("🔍 Debug - Cycles détectés"):
            st.write(f"Nombre de cycles trouvés: {len(cycles_df)}")
            
            # Afficher les données brutes pour debug
            if hasattr(cycles_df, 'attrs') and 'debug_df' in cycles_df.attrs:
                st.write("\n### Échantillon des données brutes:")
                debug_df = cycles_df.attrs['debug_df']
                # Ajouter une colonne pour mieux voir les états
                debug_df_display = debug_df.copy()
                debug_df_display['État'] = debug_df_display['state'].map({0: '🔴 Fermé', 1: '🟢 Ouvert'})
                st.dataframe(debug_df_display[['Timestamp', 'Porte_Status', 'État']].head(50))
            
            if len(cycles_df) > 0:
                st.write("\n### Cycles détectés:")
                display_df = cycles_df.copy()
                # Sanitize attrs and structure to avoid JSON-serialization issues
                try:
                    display_df.attrs = {}
                    for c in display_df.columns:
                        try:
                            display_df[c].attrs = {}
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    display_df.columns = display_df.columns.map(str)
                except Exception:
                    pass
                try:
                    display_df = display_df.reset_index(drop=True)
                except Exception:
                    pass
                display_df['duration_min'] = display_df['duration_sec'] / 60
                display_df['open_time'] = pd.to_datetime(display_df['open_ts']).dt.strftime('%Y-%m-%d %H:%M')
                display_df['close_time'] = pd.to_datetime(display_df['close_ts']).dt.strftime('%Y-%m-%d %H:%M')
                
                # Afficher tous les cycles si moins de 50, sinon les 50 premiers
                n_display = min(len(display_df), 50)
                display_cols = display_df[['open_time', 'close_time', 'duration_min']].copy()
                st.dataframe(display_cols.head(n_display))
                
                # Statistiques
                st.write("\n### Statistiques des cycles:")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Durée moyenne", f"{display_df['duration_min'].mean():.1f} min")
                with col2:
                    st.metric("Durée médiane", f"{display_df['duration_min'].median():.1f} min")
                with col3:
                    st.metric("Total cycles", len(display_df))
                
                # Distribution des durées
                st.write("\n### Distribution des durées:")
                st.write(f"- < 1 min: {len(display_df[display_df['duration_min'] < 1])} cycles")
                st.write(f"- 1-10 min: {len(display_df[(display_df['duration_min'] >= 1) & (display_df['duration_min'] < 10)])} cycles")
                st.write(f"- 10-60 min: {len(display_df[(display_df['duration_min'] >= 10) & (display_df['duration_min'] < 60)])} cycles")
                st.write(f"- > 60 min: {len(display_df[display_df['duration_min'] >= 60])} cycles")
        
        # Visualisation de l'état de la porte dans le temps
        if len(porte_data_clean) > 0:
            st.subheader("📊 État de la porte dans le temps")
            
            # Créer une figure pour l'état de la porte
            fig_status = go.Figure()
            
            # Préparer les données pour la visualisation
            plot_data = porte_data_clean.copy()
            plot_data = plot_data.sort_values('Timestamp')
            
            # Convertir le statut en numérique si nécessaire
            if pd.api.types.is_string_dtype(plot_data['Porte_Status']):
                status_map = {'ouverte': 1, 'ouvert': 1, 'fermé': 0, 'ferme': 0, 'fermée': 0}
                plot_data['Status_Numeric'] = plot_data['Porte_Status'].str.lower().map(status_map).fillna(0)
            else:
                plot_data['Status_Numeric'] = pd.to_numeric(plot_data['Porte_Status'], errors='coerce').fillna(0)
            
            # Ajouter la ligne d'état
            fig_status.add_trace(go.Scatter(
                x=plot_data['Timestamp'],
                y=plot_data['Status_Numeric'],
                mode='lines',
                line=dict(shape='hv', color='blue', width=2),
                fill='tozeroy',
                fillcolor='rgba(0, 100, 255, 0.3)',
                name='État porte',
                hovertemplate='%{x}<br>État: %{y}<extra></extra>'
            ))
            
            # Ajouter des zones colorées pour les cycles détectés
            for i, row in cycles_df.iterrows():
                fig_status.add_vrect(
                    x0=row['open_ts'], x1=row['close_ts'],
                    fillcolor="red", opacity=0.2,
                    layer="below", line_width=0,
                    annotation_text=f"C{i+1}",
                    annotation_position="top left"
                )
            
            fig_status.update_layout(
                title="État de la porte et cycles détectés",
                xaxis_title="Temps",
                yaxis_title="État (0=Fermé, 1=Ouvert)",
                height=400,
                yaxis=dict(
                    tickmode='array',
                    tickvals=[0, 1],
                    ticktext=['Fermé', 'Ouvert'],
                    range=[-0.1, 1.1]
                ),
                showlegend=False
            )
            
            st.plotly_chart(fig_status, width='stretch', key="door_status_timeline")
        
        # Visualisation Timeline des cycles de porte
        if len(cycles_df) > 0:
            st.subheader("📅 Timeline des cycles de porte")
            
            # Créer une figure pour la timeline
            fig_timeline = go.Figure()
            
            # Ajouter chaque cycle comme une barre horizontale
            for i, row in cycles_df.iterrows():
                fig_timeline.add_trace(go.Scatter(
                    x=[row['open_ts'], row['close_ts']],
                    y=[i, i],
                    mode='lines',
                    line=dict(color='red', width=10),
                    name=f"Cycle {i+1}",
                    hovertemplate=(
                        f"Cycle {i+1}<br>" +
                        "Ouverture: %{x|%Y-%m-%d %H:%M:%S}<br>" +
                        f"Durée: {row['duration_sec']/60:.1f} min<extra></extra>"
                    ),
                    showlegend=False
                ))
                
                # Ajouter des marqueurs pour début et fin
                fig_timeline.add_trace(go.Scatter(
                    x=[row['open_ts'], row['close_ts']],
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
        st.subheader("📈 Analyse de l'évolution de température pendant l'ouverture de porte")
        
        # Utiliser les événements d'ouverture détectés pour créer des cycles
        door_cycles = []
        all_door_cycles = []  # Nouveau: garder tous les cycles même sans température
        
        if len(cycles_df) > 0:
            st.write(f"**Traitement de {len(cycles_df)} cycles détectés...**")
            
            # NOUVELLE APPROCHE: Prétraiter les données de température
            # 1. Créer une copie pour le traitement
            temp_processed = merged_data[['Timestamp', 'Temp_Ambiante']].copy()
            temp_processed = temp_processed.sort_values('Timestamp')
            
            # 2. Statistiques avant traitement
            nan_before = temp_processed['Temp_Ambiante'].isna().sum()
            total_rows = len(temp_processed)
            st.write(f"**Données température - Avant traitement:** {total_rows - nan_before}/{total_rows} valeurs valides ({nan_before} NaN)")
            
            # 3. Remplir les NaN intelligemment
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
            
            # 4. Statistiques après traitement
            nan_after = temp_processed['Temp_Ambiante_Final'].isna().sum()
            st.write(f"**Données température - Après traitement:** {total_rows - nan_after}/{total_rows} valeurs valides")
            
            # 5. Remplacer dans filtered_merged_data (merge sur Timestamp)
            merged_temp = temp_processed[['Timestamp', 'Temp_Ambiante_Final']].copy()
            merged_temp = merged_temp.rename(columns={'Temp_Ambiante_Final': 'Temp_Ambiante_Filled'})
            merged_with_temp = pd.merge(merged_data, merged_temp, on='Timestamp', how='left')
            merged_with_temp['Temp_Ambiante'] = merged_with_temp['Temp_Ambiante_Filled']
            # Utiliser merged_with_temp pour les extractions de température
            processed_data = merged_with_temp.copy()
            
            # Debug counters
            cycles_with_no_temp_data = 0
            cycles_with_invalid_temps = 0
            
            # Pour chaque cycle, analyser l'impact sur la température
            for i, cycle in cycles_df.iterrows():
                open_time = cycle['open_ts']
                close_time = cycle['close_ts']
                cycle_duration = cycle['duration_sec'] / 60  # Convertir en minutes
                
                # Limiter les cycles très longs (plus de 2 heures)
                if cycle_duration > 120:
                    close_time = open_time + timedelta(minutes=120)
                    cycle_duration = 120
                
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
                
                # Debug pour les premiers cycles
                if i < 3:
                    with st.expander(f"🔍 Debug température cycle {i+1}"):
                        st.write(f"Ouverture: {open_time}, Fermeture: {close_time}")
                        st.write(f"Fenêtre avant: {before_window_start} à {before_window_end}")
                        st.write(f"Points de données avant: {len(before_data)}")
                        st.write(f"Temp avant: {temp_before:.2f}°C" if pd.notna(temp_before) else "Temp avant: NaN")
                        st.write(f"Fenêtre après: {after_window_start} à {after_window_end}")
                        st.write(f"Points de données après: {len(after_data)}")
                        st.write(f"Temp après (max): {temp_after:.2f}°C" if pd.notna(temp_after) else "Temp après: NaN")
                
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
                else:
                    if pd.isna(temp_before) or pd.isna(temp_after):
                        cycles_with_invalid_temps += 1
                    else:
                        cycles_with_no_temp_data += 1
            
            st.write(f"**Total de cycles détectés:** {len(all_door_cycles)}")
            st.write(f"**Cycles avec données de température:** {len(door_cycles)}")
            
            # Debug résumé
            with st.expander("🔍 Debug - Résumé du traitement des cycles"):
                st.write("**Nouvelle approche de traitement:**")
                st.write("1. ✅ Interpolation des NaN dans les données de température")
                st.write("2. ✅ Fenêtres de temps flexibles (30 min avant, cycle + 10 min après)")
                st.write("3. ✅ Température avant = moyenne des 5 dernières minutes")
                st.write("4. ✅ Température après = maximum pendant le cycle")
                st.write("")
                st.write(f"Total cycles détectés (après filtrage): {len(cycles_df)}")
                st.write(f"Total cycles créés: {len(all_door_cycles)}")
                st.write(f"Cycles sans données de température: {cycles_with_no_temp_data}")
                st.write(f"Cycles avec températures invalides: {cycles_with_invalid_temps}")
                st.write(f"**Cycles avec données de température complètes: {len(door_cycles)}**")
                
            # Afficher tous les cycles dans un tableau
            with st.expander("📊 Voir tous les cycles détectés"):
                if all_door_cycles:
                    df_all_cycles = pd.DataFrame(all_door_cycles)
                    df_all_cycles['Open_Time'] = pd.to_datetime(df_all_cycles['Open_Time'])
                    df_all_cycles['Close_Time'] = pd.to_datetime(df_all_cycles['Close_Time'])
                    
                    # Ajouter des colonnes formatées pour l'affichage
                    df_all_cycles['Ouverture'] = df_all_cycles['Open_Time'].dt.strftime('%d/%m/%Y %H:%M')
                    df_all_cycles['Fermeture'] = df_all_cycles['Close_Time'].dt.strftime('%d/%m/%Y %H:%M')
                    df_all_cycles['Durée (min)'] = df_all_cycles['Duration_min'].round(1)
                    df_all_cycles['Cycle complet'] = df_all_cycles['Is_Complete_Cycle'].map({True: '✓', False: '✗'})
                    df_all_cycles['Données temp.'] = df_all_cycles['Has_Temp_Data'].map({True: '✓', False: '✗'})
                    
                    # Afficher le tableau
                    st.dataframe(
                        df_all_cycles[['Ouverture', 'Fermeture', 'Durée (min)', 'Cycle complet', 'Données temp.']],
                        width='stretch'
                    )
                    
                    # Statistiques supplémentaires
                    st.write(f"**Statistiques des cycles:**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Durée moyenne", f"{df_all_cycles['Duration_min'].mean():.1f} min")
                    with col2:
                        cycles_with_temp = df_all_cycles['Has_Temp_Data'].sum()
                        pct_with_temp = (cycles_with_temp / len(df_all_cycles)) * 100
                        st.metric("% avec données temp.", f"{pct_with_temp:.1f}%")
                    with col3:
                        complete_cycles = df_all_cycles['Is_Complete_Cycle'].sum()
                        st.metric("Cycles complets", f"{complete_cycles}/{len(df_all_cycles)}")
        
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
            
            st.write(f"**Cycles valides après nettoyage:** {len(door_impacts)}")
            
            if door_impacts and len(door_impacts) > 0:
                df_impacts = pd.DataFrame(door_impacts)
                
                # Debug temporaire: Afficher les données pour vérifier
                with st.expander("🔍 Débogage - Voir les données"):
                    st.write(f"Shape df_impacts: {df_impacts.shape}")
                    st.write("Colonnes:", df_impacts.columns.tolist())
                    st.write("Premières lignes:")
                    st.dataframe(df_impacts.head())
                    st.write("Valeurs NaN par colonne:")
                    st.write(df_impacts.isnull().sum())
                
                # Graphiques d'analyse (sélection individuelle)
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
                            st.metric("Variation", f"{selected_cycle['Delta_Temp']:.2f}°C",
                                    delta=f"{'↑' if selected_cycle['Delta_Temp'] > 0 else '↓'} {abs(selected_cycle['Delta_Temp']):.2f}°C")
                        with col4:
                            st.metric("Durée", f"{selected_cycle['Duration_min']:.1f} min")
                
                # Vue d'ensemble comparatif (limité à 10 cycles pour lisibilité)
                st.subheader("📊 Comparaison de tous les cycles")
                
                fig = go.Figure()
                colors = px.colors.qualitative.Set3
                for i, cycle in enumerate(door_cycles[:10]):
                    cycle_data = cycle['Cycle_Data']
                    if len(cycle_data) > 0:
                        relative_time = [(t - cycle['Open_Time']).total_seconds() / 60 
                                       for t in cycle_data['Timestamp']]
                        
                        fig.add_trace(go.Scatter(
                            x=relative_time,
                            y=cycle_data['Temp_Ambiante'],
                            mode='lines+markers',
                            name=f"Cycle {i+1} ({cycle['Open_Time'].strftime('%m-%d %H:%M')})",
                            line=dict(color=colors[i % len(colors)], width=2),
                            marker=dict(size=6),
                            hovertemplate='Temps: %{x:.1f} min<br>Temp: %{y:.1f}°C<extra></extra>'
                        ))
                        
                        fig.add_vline(
                            x=0, 
                            line_dash="dash", 
                            line_color="red",
                            opacity=0.7,
                            annotation_text=f"Ouverture {i+1}",
                            annotation_position="top"
                        )
                
                fig.update_layout(
                    title="Évolution de température pendant les cycles d'ouverture",
                    xaxis_title="Temps depuis ouverture (minutes)",
                    yaxis_title="Température ambiante (°C)",
                    height=500,
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, width='stretch', key="door_temp_evolution")
                
                # Corrélation durée vs ΔT
                st.subheader("📊 Analyse de corrélation")
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=df_impacts['Duree_Analyse'],
                    y=df_impacts['Delta_Temp'],
                    mode='markers',
                    marker=dict(size=10, color='darkblue', opacity=0.7),
                    name='Cycles',
                    text=[f"Cycle {i+1}<br>Durée: {d:.1f} min<br>ΔT: {t:.2f}°C" 
                          for i, (d, t) in enumerate(zip(df_impacts['Duree_Analyse'], df_impacts['Delta_Temp']))],
                    hovertemplate='%{text}<extra></extra>'
                ))
                
                fig.add_hline(y=0, line_dash="dash", line_color="gray")
                
                fig.update_layout(
                    title="Durée vs Changement température",
                    xaxis_title="Durée d'ouverture (min)",
                    yaxis_title="ΔT (°C)",
                    height=400
                )
                
                st.plotly_chart(fig, width='stretch', key="door_duration_correlation")
                
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
                
                with st.expander("📋 Détail des cycles d'ouverture-fermeture"):
                    st.dataframe(
                        df_impacts.style.format({
                            'Duree_Analyse': '{:.0f} min',
                            'Temp_Avant': '{:.1f}°C',
                            'Temp_Apres': '{:.1f}°C',
                            'Delta_Temp': '{:.2f}°C'
                        }),
                        width='stretch'
                    )
                
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
                st.info(f"ℹ️ Cependant, {len(all_door_cycles)} cycles de porte ont été détectés. Consultez l'onglet 'Voir tous les cycles détectés' ci-dessus pour plus de détails.")
    else:
        st.warning("Données de porte ou de température manquantes pour l'analyse.")