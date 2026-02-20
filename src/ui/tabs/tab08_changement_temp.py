"""
Tab 8: Analyse des changements de température
Détection et analyse des pics de température (hauts et bas) avec identification des causes.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import scipy.stats
from src.analysis.exterior_cause import power_causes_ambient_spike, exterior_causes_ambient_spike


def render_tab(filtered_merged_data, start_date, end_date):
    """
    Affiche l'analyse des changements de température et détection de pics.
    
    Args:
        filtered_merged_data: DataFrame avec données filtrées
        start_date: Date de début de la période
        end_date: Date de fin de la période
    """
    # ---------- Pré-conditions ----------
    if not filtered_merged_data.empty and 'Timestamp' in filtered_merged_data.columns:
        st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
        # On travaille sur la table unifiée
        filtered_data = filtered_merged_data.copy()

        # 1) Détection des pics Temp_Ambiante
        if 'Temp_Ambiante' in filtered_data.columns:
            df = filtered_data.sort_values("Timestamp").reset_index(drop=True)
            df['rolling_std'] = df['Temp_Ambiante'].rolling(window=10, center=True).std()
            std_threshold = df['rolling_std'].median() * 1.5
            df['is_ranging'] = df['rolling_std'] < std_threshold

            stable_data = df[df['is_ranging']]
            if not stable_data.empty and len(stable_data) >= 10:
                global_max = stable_data['Temp_Ambiante'].max()
                global_min = stable_data['Temp_Ambiante'].min()
            else:
                global_max = df['Temp_Ambiante'].quantile(0.85)
                global_min = df['Temp_Ambiante'].quantile(0.15)

            range_amplitude = global_max - global_min
            MIN_EXCURSION = max(0.5, range_amplitude * 0.1)

            high_candidates = df[df['Temp_Ambiante'] > global_max + MIN_EXCURSION].copy()
            low_candidates  = df[df['Temp_Ambiante'] < global_min - MIN_EXCURSION].copy()

            high_spikes_list = []
            if not high_candidates.empty:
                high_candidates = high_candidates.sort_values('Timestamp')
                high_candidates['gap'] = high_candidates['Timestamp'].diff() > pd.Timedelta(minutes=30)
                high_candidates['cluster'] = high_candidates['gap'].cumsum()
                for _, cluster in high_candidates.groupby('cluster'):
                    start_time = cluster['Timestamp'].min()  # ← DÉBUT DU PIC
                    end_time = cluster['Timestamp'].max()    # ← FIN DU PIC
                    peak_row = cluster.loc[cluster['Temp_Ambiante'].idxmax()]
                    duration = (end_time - start_time).total_seconds() / 60
                    
                    # ✓ MODIFICATION : Si durée = 0, afficher 1h avant le pic
                    if duration == 0:
                        start_time = peak_row['Timestamp'] - pd.Timedelta(hours=1)
                    
                    # Calcul des causes pour ce pic haut
                    context = df[(df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(hours=1)) & (df['Timestamp'] <= peak_row['Timestamp'] + pd.Timedelta(minutes=20))]
                    causes = []

                    # 1. Condition : Porte ouverte
                    if 'Porte_Status' in df.columns:
                        # Création d'un contexte TRES ciblé autour du DÉBUT du pic (+/- 5 minutes)
                        door_context = df[
                            (df['Timestamp'] >= start_time - pd.Timedelta(hours=1)) & 
                            (df['Timestamp'] <= start_time + pd.Timedelta(minutes=20))
                        ]
                        
                        # Vérifie si le statut 'ouvert' (1) est présent sur plus de 5% du temps (minimum d'ouverture)
                        if not door_context.empty and door_context['Porte_Status'].mean() > 0.05:
                            causes.append("Porte ouverte ")
                    local_corr = None 
                    IT_corr = None
                    # 2. Condition : Augmentation Température Extérieure
                    # 2. Condition : Augmentation Température Extérieure ou Puissance IT
                    if 'Temp_Exterieure' in df.columns or 'Puissance_IT' in df.columns:
                        # Logic aligned with get_correlations_for_row

                        # --- Calcul Ext ---
                        if 'Temp_Exterieure' in df.columns:
                            context_temp = df[(df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(hours=1)) & 
                                               (df['Timestamp'] <= peak_row['Timestamp'] + pd.Timedelta(minutes=20))]
                            corr_data_ext = context_temp.dropna(subset=['Temp_Ambiante', 'Temp_Exterieure'])
                            if len(corr_data_ext) >= 5:
                                Ext_corr, _ = scipy.stats.spearmanr(corr_data_ext['Temp_Ambiante'], corr_data_ext['Temp_Exterieure'])
                                if Ext_corr is not None and Ext_corr >= 0.5:
                                    causes.append("Temp Ext. élevée")
                        
                        # --- Calcul IT ---
                        it_debug = None
                        if 'Puissance_IT' in df.columns:
                            context_it = df[(df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(hours=1)) & 
                                               (df['Timestamp'] <= peak_row['Timestamp'] + pd.Timedelta(minutes=20))]
                            corr_data_it = context_it.dropna(subset=['Temp_Ambiante', 'Puissance_IT'])
                            if len(corr_data_it) >= 5:
                                it_flag, it_info = power_causes_ambient_spike(corr_data_it['Temp_Ambiante'].values, corr_data_it['Puissance_IT'].values)
                                it_debug = it_info
                                if it_flag:
                                    reason = it_info.get('decision') or 'criteria'
                                    display_reason = '' if reason == 'diff_corr' else f' ({reason})'
                                    causes.append(f"Puissance IT élevée")

                    # 4. Condition : Toutes les CLIMs éteintes
                    clim_cols = [col for col in df.columns if 'CLIM_' in col and '_Status' in col]
                    clim_cols_in_context = [col for col in clim_cols if col in context.columns]
                    
                    if clim_cols_in_context:
                        # On vérifie si pour chaque CLIM présente, le statut est strictement 0 sur toute la période
                        offline = [
                            col.replace('_Status','').replace('CLIM_','CLIM ') 
                            for col in clim_cols_in_context 
                            if (context[col] == 0).all() 
                        ]

                        # Si le nombre de clims éteintes == nombre total de clims surveillées
                        if len(offline) == len(clim_cols_in_context):
                            causes.append("Toutes les clims éteintes")
                        else: # On ne vérifie que si toutes ne sont pas déjà éteintes
                            clim_shutdown_context = df[
                                (df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(hours=1)) &
                                (df['Timestamp'] < peak_row['Timestamp'])
                            ]
                            if not clim_shutdown_context.empty and len(clim_shutdown_context) > 1:
                                for col in clim_cols_in_context:
                                    series = pd.to_numeric(clim_shutdown_context[col], errors='coerce').dropna()
                                    if len(series) > 1:
                                        # Check for a 1 -> 0 transition
                                        if -1.0 in series.diff().unique():
                                            clim_name = col.replace('_Status','').replace('CLIM_','')
                                            cause_str = f"Arrêt {clim_name}"
                                            if cause_str not in causes:
                                                causes.append(cause_str)

                    high_spikes_list.append({
                        'spike_time': peak_row['Timestamp'],
                        'start_time': start_time,
                        'end_time': end_time,
                        'spike_temp': peak_row['Temp_Ambiante'],
                        'duration_min': duration,
                        'range_max': global_max,
                        'excursion': peak_row['Temp_Ambiante'] - global_max,
                        'type': 'Haut',
                        'causes': causes,
                        'debug': {'it_info': it_debug}
                    })

            low_spikes_list = []
            if not low_candidates.empty:
                low_candidates = low_candidates.sort_values('Timestamp')
                low_candidates['gap'] = low_candidates['Timestamp'].diff() > pd.Timedelta(minutes=30)
                low_candidates['cluster'] = low_candidates['gap'].cumsum()
                for _, cluster in low_candidates.groupby('cluster'):
                    start_time = cluster['Timestamp'].min()  # ← DÉBUT DU PIC (dépassement seuil)
                    end_time = cluster['Timestamp'].max()    # ← FIN DU PIC
                    peak_row = cluster.loc[cluster['Temp_Ambiante'].idxmin()]
                    duration = (end_time - start_time).total_seconds() / 60
                    
                    # ✓ MODIFICATION : Si durée = 0, afficher 1h avant le pic
                    if duration == 0:
                        start_time = peak_row['Timestamp'] - pd.Timedelta(hours=1)
                    
                    # LOGIQUE PICS BAS : CONDITIONS MISES À JOUR
                    context = df[(df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(hours=1)) & (df['Timestamp'] <= peak_row['Timestamp'] + pd.Timedelta(minutes=20))]
                    causes = []

                    # 1. Condition : Porte ouverte
                    if 'Porte_Status' in df.columns:
                        # Création d'un contexte TRES ciblé autour du DÉBUT du pic (+/- 5 minutes)
                        door_context = df[
                            (df['Timestamp'] >= start_time - pd.Timedelta(minutes=5)) & 
                            (df['Timestamp'] <= start_time + pd.Timedelta(minutes=5))
                        ]
                        
                        # Vérifie si le statut 'ouvert' (1) est présent sur plus de 5% du temps (minimum d'ouverture)
                        if not door_context.empty and door_context['Porte_Status'].mean() > 0.05:
                            causes.append("Porte ouverte")
                    local_corr = None 
                    IT_corr = None
                    corr_start = start_time - pd.Timedelta(hours=1)
                    corr_end = end_time + pd.Timedelta(minutes=20)
                    # 2. Condition : Diminution Température Extérieure ou Puissance IT
                    if 'Temp_Exterieure' in df.columns or 'Puissance_IT' in df.columns:
                        # Logic aligned with get_correlations_for_row

                        # --- Calcul Ext ---
                        if 'Temp_Exterieure' in df.columns:
                            context_Ext = df[(df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(minutes=15)) & 
                                               (df['Timestamp'] <= peak_row['Timestamp'] + pd.Timedelta(minutes=20))]
                            corr_data_ext = context_Ext.dropna(subset=['Temp_Ambiante', 'Temp_Exterieure'])
                            if len(corr_data_ext) >= 5:
                                Ext_corr, _ = scipy.stats.spearmanr(corr_data_ext['Temp_Ambiante'], corr_data_ext['Temp_Exterieure'])
                                if Ext_corr is not None and Ext_corr >= 0.5:
                                    causes.append("Temp Ext. faible")
                        
                        # --- Calcul IT ---
                        it_debug = None
                        if 'Puissance_IT' in df.columns:
                            context_it = df[(df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(minutes=20)) & 
                                               (df['Timestamp'] <= peak_row['Timestamp'] + pd.Timedelta(minutes=5))]
                            corr_data_it = context_it.dropna(subset=['Temp_Ambiante', 'Puissance_IT'])
                            if len(corr_data_it) >= 5:
                                it_flag, it_info = power_causes_ambient_spike(corr_data_it['Temp_Ambiante'].values, corr_data_it['Puissance_IT'].values)
                                it_debug = it_info
                                if it_flag:
                                    reason = it_info.get('decision') or 'criteria'
                                    display_reason = '' if reason == 'diff_corr' else f' ({reason})'
                                    causes.append(f"Puissance IT faible")

                    # 4. Condition : Toutes les CLIMs éteintes
                    # (Cas possible si l'air extérieur froid rentre ou inertie thermique)
                    clim_cols = [col for col in df.columns if 'CLIM_' in col and '_Status' in col]
                    clim_cols_in_context = [col for col in clim_cols if col in context.columns]
                    
                    if clim_cols_in_context:
                        # On vérifie si toutes les CLIMs surveillées étaient STRICTEMENT à 0 (OFF)
                        offline = [
                            col.replace('_Status','').replace('CLIM_','CLIM ') 
                            for col in clim_cols_in_context 
                            if (context[col] == 0).all() 
                        ]
                        if len(offline) == len(clim_cols_in_context):
                            causes.append("Toutes les clims éteintes")
                        else: # On ne vérifie que si toutes ne sont pas déjà éteintes
                            clim_shutdown_context = df[
                                (df['Timestamp'] >= peak_row['Timestamp'] - pd.Timedelta(hours=1)) &
                                (df['Timestamp'] < peak_row['Timestamp'])
                            ]
                            if not clim_shutdown_context.empty and len(clim_shutdown_context) > 1:
                                for col in clim_cols_in_context:
                                    series = pd.to_numeric(clim_shutdown_context[col], errors='coerce').dropna()
                                    if len(series) > 1:
                                        # Check for a 1 -> 0 transition
                                        if -1.0 in series.diff().unique():
                                            clim_name = col.replace('_Status','').replace('CLIM_','')
                                            cause_str = f"Arrêt {clim_name}"
                                            if cause_str not in causes:
                                                causes.append(cause_str)

                    low_spikes_list.append({
                        'spike_time': peak_row['Timestamp'],
                        'start_time': start_time,
                        'end_time': end_time,
                        'spike_temp': peak_row['Temp_Ambiante'],
                        'duration_min': duration,
                        'range_min': global_min,
                        'excursion': global_min - peak_row['Temp_Ambiante'],
                        'type': 'Bas',
                        'causes': causes
                    })

            high_spikes_df = pd.DataFrame(high_spikes_list)
            low_spikes_df  = pd.DataFrame(low_spikes_list)
            all_spikes_df = pd.concat([high_spikes_df, low_spikes_df], ignore_index=True) if not high_spikes_df.empty or not low_spikes_df.empty else pd.DataFrame()
        else:
            # Définitions vides si colonne manquante
            df = filtered_data.sort_values("Timestamp").reset_index(drop=True)
            global_max = global_min = MIN_EXCURSION = 0
            high_spikes_df = pd.DataFrame()
            low_spikes_df = pd.DataFrame()
            all_spikes_df = pd.DataFrame()

        # ----------------------------
        # 2) Interface de sélection (inspirée de tab1)
        # ----------------------------
        st.subheader("📈 Visualisation temporelle (sélectionnez les métriques)")
        available_metrics = {
            'Temp_Ambiante': '🌡️ Température Ambiante (°C)',
            'Temp_Exterieure': '🌤️ Température Extérieure (°C)',
            'Puissance_IT': '💻 Puissance IT (kW)',
            'Puissance_Generale': '⚡ Puissance Générale (kW)',
            'Puissance_CLIM': '❄️ Puissance CLIM (kW)',
            'Porte_Status': '🚪 État Porte'
        }
        # détecter CLIMs
        clim_columns = [col for col in filtered_data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
        for clim_col in sorted(clim_columns):
            clim_name = clim_col.replace('_Status', '').replace('_', ' ')
            available_metrics[clim_col] = f'❄️ État {clim_name}'

        available_cols = [col for col in available_metrics.keys() if col in filtered_data.columns]

        # info disponibilité
        with st.expander("ℹ️ Informations sur les données disponibles"):
            for col in available_cols:
                valid_count = filtered_data[col].notna().sum()
                total_count = len(filtered_data)
                percentage = (valid_count / total_count * 100) if total_count > 0 else 0
                st.text(f"{available_metrics[col]}: {valid_count}/{total_count} points ({percentage:.1f}%)")

        # boutons rapides
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("🌡️ Toutes Températures", key="tab8_all_temp"):
                st.session_state['selected_metrics'] = [c for c in available_cols if 'Temp' in c]
        with col2:
            if st.button("⚡ Toutes Puissances", key="tab8_all_power"):
                st.session_state['selected_metrics'] = [c for c in available_cols if 'Puissance' in c]
        with col3:
            if st.button("❄️ Tous CLIMs", key="tab8_all_clims"):
                st.session_state['selected_metrics'] = [c for c in available_cols if 'CLIM' in c and 'Status' in c]
        with col4:
            if st.button("📊 Tout Sélectionner", key="tab8_select_all"):
                st.session_state['selected_metrics'] = available_cols

        selected_metrics = st.multiselect(
            "Sélectionner les données à afficher:",
            available_cols,
            key="metrics_selector_tab8",
            default=st.session_state.get(
                'selected_metrics',
                ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT'] if all(col in available_cols for col in ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT']) else available_cols[:3]
            ),
            format_func=lambda x: available_metrics[x]
        )

        # Color scheme and display configuration for visualizations
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
        
        # Définir automatiquement les couleurs pour tous les CLIMs disponibles
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
        
        # Assigner automatiquement les couleurs aux CLIMs détectés
        detected_clims = [col for col in filtered_data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
        for i, clim_col in enumerate(sorted(detected_clims)):
            color_index = i % len(clim_colors)
            color_scheme[clim_col] = clim_colors[color_index]
        
        # Couleurs de fallback pour métriques non définies
        fallback_colors = [
            {'color': '#FF9F43', 'fill': 'rgba(255, 159, 67, 0.4)'},
            {'color': '#10AC84', 'fill': 'rgba(16, 172, 132, 0.4)'},
            {'color': '#EE5A24', 'fill': 'rgba(238, 90, 36, 0.4)'},
            {'color': '#0984e3', 'fill': 'rgba(9, 132, 227, 0.4)'},
            {'color': '#a29bfe', 'fill': 'rgba(162, 155, 254, 0.4)'},
            {'color': '#fd79a8', 'fill': 'rgba(253, 121, 168, 0.4)'},
            {'color': '#fdcb6e', 'fill': 'rgba(253, 203, 110, 0.4)'},
            {'color': '#6c5ce7', 'fill': 'rgba(108, 92, 231, 0.4)'}
        ]
        
        # Déterminer si on a besoin d'axes secondaires
        has_temp = any('Temp' in m for m in selected_metrics)
        has_power = any('Puissance' in m for m in selected_metrics)
        
        # Option d'affichage pour les données binaires
        binary_display = st.selectbox(
            "Affichage binaires:",
            ["Superposées transparentes", "Séparées classiques"],
            key="tab8_binary_display",
            help="Superposées: données binaires empilées avec transparence. Séparées: affichage classique."
        )

        # NOUVEAU : Sélecteur de pic individuel
        if not all_spikes_df.empty:
            all_spikes_df = all_spikes_df.sort_values('spike_time')
            all_spikes_df['label'] = all_spikes_df.apply(
                lambda r: f"{r['type']} — {r['spike_time'].strftime('%d/%m %H:%M')} — {r['spike_temp']:.1f}°C",
                axis=1
            )
            selected_peak_label = st.selectbox(
                "Mettre en évidence un pic précis (les autres seront masqués)",
                options=["Tous les pics"] + all_spikes_df['label'].tolist(),
                index=0
            )
        else:
            selected_peak_label = "Tous les pics"

        peak_selected = selected_peak_label != "Tous les pics"

        ## 1️⃣ GRAPHIQUE PRINCIPAL : Aperçu de l'Ambiante et des Pics (Période complète)
        st.markdown("---")
        st.markdown("### 🌡 Graphique 1 : Période complète")
        
        fig1 = go.Figure()
        
        # Tracer la Température Ambiante
        if 'Temp_Ambiante' in df.columns:
            colors_data = color_scheme['Temp_Ambiante']
            fig1.add_trace(go.Scatter(
                x=df['Timestamp'], y=df['Temp_Ambiante'], 
                name=available_metrics['Temp_Ambiante'], mode='lines',
                line=dict(color=colors_data['color'], width=2.5), connectgaps=True,
                hovertemplate='<b>%{fullData.name}</b><br>Valeur: %{y:.2f}°C<br>Temps: %{x}<extra></extra>'
            ))
            
            # Ajouter les seuils
            fig1.add_hline(y=global_max, line=dict(color='red', width=1, dash='dash'), annotation_text=f"Seuil Max ({global_max:.1f}°C)", annotation_position="top right", annotation_font_size=10)
            fig1.add_hline(y=global_min, line=dict(color='green', width=1, dash='dash'), annotation_text=f"Seuil Min ({global_min:.1f}°C)", annotation_position="bottom right", annotation_font_size=10)
            
            # Ajouter les marqueurs de Pics
            if not all_spikes_df.empty:
                
                # Mise en évidence du pic sélectionné (si un est choisi)
                if peak_selected:
                    selected_row = all_spikes_df[all_spikes_df['label'] == selected_peak_label].iloc[0]
                    
                    # Zone de zoom sur Fig1
                    fig1.add_vrect(
                        x0=selected_row['start_time'], x1=selected_row['end_time'] + pd.Timedelta(minutes=20),
                        fillcolor="rgba(255, 165, 0, 0.2)", line_width=0,
                        annotation_text="Zone de Zoom (Graphique 2)", annotation_position="top left",
                        annotation_font_size=11, annotation_font_color='black'
                    )
                    
                # Tracé des pics Hauts
                high_to_show = all_spikes_df[all_spikes_df['type'] == 'Haut']
                if not high_to_show.empty:
                    fig1.add_trace(go.Scatter(
                        x=high_to_show['spike_time'], y=high_to_show['spike_temp'], mode='markers', name='Pics Hauts',
                        marker=dict(color='red', size=8, symbol='triangle-up', line=dict(width=1, color='darkred')),
                        hovertemplate='<b>Pic Haut</b><br>Temp: %{y:.1f}°C<br>Heure: %{x}<extra></extra>'
                    ))
                
                # Tracé des pics Bas
                low_to_show = all_spikes_df[all_spikes_df['type'] == 'Bas']
                if not low_to_show.empty:
                    fig1.add_trace(go.Scatter(
                        x=low_to_show['spike_time'], y=low_to_show['spike_temp'], mode='markers', name='Pics Bas',
                        marker=dict(color='darkorange', size=8, symbol='triangle-down', line=dict(width=1, color='darkorange')),
                        hovertemplate='<b>Pic Bas</b><br>Temp: %{y:.1f}°C<br>Heure: %{x}<extra></extra>'
                    ))

        fig1.update_layout(
            title=dict(text=f'Période du {start_date.strftime("%d/%m")} au {end_date.strftime("%d/%m")}'),
            yaxis=dict(title='Température Ambiante (°C)'),
            height=400, hovermode='x unified',
            legend=dict(orientation="h", yanchor="top", y=1.5, xanchor="left", x=0)
        )
        st.plotly_chart(fig1, use_container_width=True, key="tab8_main_overview_chart")
        

        

        # ----------------------------
        # ----------------------------
        # 3) Construction du graphique (continues + binaires)
        # ----------------------------
        
        if peak_selected :
            st.markdown("---")
            st.markdown("### 🌡 Graphique 2 : Détails Pics sélectionnés") 
            if selected_metrics:
                fig = go.Figure()

                # --- DÉBUT DU BLOC 2 : CALCUL DES PLAGES Y ET DE L'ESPACE BINAIRE ---
                # Calcul des min/max des CONTINUES pour positionner les binaires
                y_cont_values = []
                for metric in [m for m in selected_metrics if 'Status' not in m and m in filtered_data.columns]:
                    mask_valid = filtered_data[metric].notna()
                    y_cont_values.extend(filtered_data.loc[mask_valid, metric].values)

                # Détermination des min/max de référence
                if y_cont_values:
                    y_min, y_max = min(y_cont_values), max(y_cont_values)
                else:
                    # Cas où seules les binaires sont sélectionnées : utiliser la plage Ambiante pour référence
                    y_min = df['Temp_Ambiante'].min() if 'Temp_Ambiante' in df.columns and not df['Temp_Ambiante'].empty else 0
                    y_max = df['Temp_Ambiante'].max() if 'Temp_Ambiante' in df.columns and not df['Temp_Ambiante'].empty else 1
                    if y_max <= y_min: y_max = y_min + 1 # Assurer une plage minimale

                # Calcul de l'espace pour les binaires
                binary_metrics_all = [m for m in selected_metrics if 'Status' in m]
                total_binary = len(binary_metrics_all)

                # Paramètres pour les bandes binaires
                band_amplitude = y_max - y_min
                band_height = band_amplitude * 0.08 if band_amplitude > 0.01 else 0.1
                spacing = band_height * 1.2
                
                # Calcul de la marge pour les binaires au fond du graphique
                padding_bottom = (total_binary * spacing) * 1.05 + band_amplitude * 0.05
                padding_top = band_amplitude * 0.15 # Marge pour les annotations de pics

                # Définir y_min_range et y_max_range pour les SHAPES verticales (Porte)
                y_min_range = y_min - padding_bottom
                y_max_range = y_max + padding_top
                # --- FIN DU BLOC 2 ---
                
                if 'Temp_Ambiante' in selected_metrics:
                    fig.add_hline(y=global_max, line=dict(color='red', width=2, dash='dash'),
                                annotation_text=f"Seuil Max ({global_max:.1f}°C)", annotation_position="top right")
                    fig.add_hline(y=global_min, line=dict(color='green', width=2, dash='dash'),
                                annotation_text=f"Seuil Min ({global_min:.1f}°C)", annotation_position="bottom right")




                # --- Tracer lignes continues ---
                for idx, metric in enumerate([m for m in selected_metrics if 'Status' not in m]):
                    colors_data = color_scheme.get(metric, fallback_colors[idx % len(fallback_colors)])
                    # Choisir yaxis
                    if 'Temp' in metric:
                        yaxis = 'y'
                    elif 'Puissance' in metric:
                        yaxis = 'y2' if any('Temp' in m for m in selected_metrics) else 'y'
                    else:
                        yaxis = 'y'

                    mask_valid = filtered_data[metric].notna()
                    x_data = filtered_data.loc[mask_valid, 'Timestamp']
                    y_data = filtered_data.loc[mask_valid, metric]

                    if len(x_data) > 0:
                        fig.add_trace(go.Scatter(
                            x=x_data,
                            y=y_data,
                            name=available_metrics[metric],
                            mode='lines',
                            line=dict(color=colors_data['color'], width=2.5),
                            yaxis=yaxis,
                            connectgaps=True,
                            hovertemplate='<b>%{fullData.name}</b><br>Valeur: %{y:.2f}<br>Temps: %{x}<extra></extra>'
                        ))

                # --- Tracer binaires ---
                # --- Tracer binaires ---
                binary_metrics = [m for m in selected_metrics if 'Status' in m]
                if binary_metrics and binary_display == "Superposées transparentes":
                    # Calcul min/max des continues pour placer les binaires en dessous
                    y_cont_values = []
                    for metric in [m for m in selected_metrics if 'Status' not in m]:
                        mask_valid = filtered_data[metric].notna()
                        y_cont_values.extend(filtered_data.loc[mask_valid, metric].values)
                    y_min, y_max = (min(y_cont_values), max(y_cont_values)) if y_cont_values else (0, 1)

                    # Paramètres pour les bandes binaires
                    band_height = (y_max - y_min) * 0.08 if y_cont_values else 0.1
                    spacing = band_height * 1.2

                    # Traitement standard pour les métriques binaires (CLIMs)
                    for idx, metric in enumerate([m for m in binary_metrics if m != 'Porte_Status']):
                        colors_data = color_scheme.get(metric, fallback_colors[idx % len(fallback_colors)])
                        mask_valid = filtered_data[metric].notna()
                        x_data = filtered_data.loc[mask_valid, 'Timestamp']
                        binary_values = filtered_data.loc[mask_valid, metric]

                        if len(x_data) == 0:
                            continue

                        # Position verticale pour cette métrique (en bas)
                        y_offset = y_min - (len(binary_metrics) - idx - 1) * spacing
                        
                        # Bande inférieure (invisible)
                        fig.add_trace(go.Scatter(
                            x=x_data,
                            y=[y_offset] * len(x_data),
                            mode='lines',
                            line=dict(color='rgba(0,0,0,0)', width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ))

                        # Bande supérieure (visible avec remplissage)
                        fig.add_trace(go.Scatter(
                            x=x_data,
                            y=y_offset + binary_values * band_height,
                            mode='lines',
                            fill='tonexty',
                            fillcolor=colors_data['fill'],
                            line=dict(color=colors_data['color'], width=2),
                            name=available_metrics.get(metric, metric),
                            hovertemplate='<b>%{fullData.name}</b><br>État: ON<br>Temps: %{x}<extra></extra>'
                        ))

                    # 🚪 CAS SPÉCIAL : Porte_Status - Affichage des zones d'ouverture
                    # --- DÉBUT DU BLOC 3 : VISUALISATION DES CYCLES D'OUVERTURE ---
                    # ... (votre code précédent pour filtered_data) ...

                    if 'Porte_Status' in binary_metrics:
                        
                        # 1. PRÉPARATION DES DONNÉES (On garde votre logique de nettoyage robuste)
                        door_data = filtered_data[['Timestamp', 'Porte_Status']].dropna().copy()
                        door_data = door_data.sort_values('Timestamp')

                        # Conversion en numérique (0=fermé, 1=ouvert)
                        if pd.api.types.is_string_dtype(door_data['Porte_Status']):
                            status_map = {'ouverte': 1, 'ouvert': 1, 'fermé': 0, 'ferme': 0, 'fermée': 0}
                            door_data['Status_Numeric'] = door_data['Porte_Status'].astype(str).str.lower().map(status_map).fillna(0)
                        else:
                            door_data['Status_Numeric'] = pd.to_numeric(door_data['Porte_Status'], errors='coerce').fillna(0)

                        # 2. TRACÉ DE LA COURBE (Au lieu des vrect/lignes verticales)
                        fig.add_trace(go.Scatter(
                            x=door_data['Timestamp'],
                            y=door_data['Status_Numeric'],
                            mode='lines',
                            name='État Porte (0/1)',
                            line=dict(
                                color='#6c5ce7',  # Violet (ou la couleur de votre choix)
                                width=2,
                                shape='hv'        # 'hv' = Horizontal-Vertical (marches d'escalier). 
                                                # Enlevez cette ligne si vous voulez des diagonales comme la température.
                            ),
                            # yaxis='y2',         # Décommentez ceci si vous avez un axe secondaire configuré pour séparer les échelles
                            hovertemplate='<b>%{x}</b><br>État: %{y}<extra></extra>'
                        ))

                        # 3. NETTOYAGE
                        # On retire 'Porte_Status' de binary_metrics pour qu'il ne soit pas traité par une boucle générique plus loin
                        binary_metrics.remove('Porte_Status')


                # ----------------------------
                # 4) AJOUT DES PICS (SUR LA MEME FIGURE)
                # ----------------------------
                # On ajoute des marqueurs pour les pics detectés (Temp_Ambiante)
                peaks_to_show = all_spikes_df

                if not all_spikes_df.empty and selected_peak_label != "Tous les pics":
                    selected_row = all_spikes_df[all_spikes_df['label'] == selected_peak_label].iloc[0]
                    peaks_to_show = pd.DataFrame([selected_row])
                    start_zoom = selected_row['start_time'] - pd.Timedelta(hours=1) 
                    end_zoom = selected_row['end_time'] + pd.Timedelta(minutes=20) 
                    fig.update_xaxes(range=[start_zoom, end_zoom])

                if not peaks_to_show.empty and 'Haut' in peaks_to_show['type'].values:
                    high_to_show = peaks_to_show[peaks_to_show['type'] == 'Haut']
                    causes_text = high_to_show.apply(lambda row: "\n".join(row['causes']) if row['causes'] else "Aucune cause évidente", axis=1)
                    hover_causes = high_to_show.apply(lambda row: '<br>'.join(row['causes']) if row['causes'] else 'Aucune cause évidente', axis=1)
                    fig.add_trace(go.Scatter(
                        x=high_to_show['spike_time'],
                        y=high_to_show['spike_temp'],
                        mode='markers+text',
                        name='Pics Hauts',
                        marker=dict(color='red', size=12 if selected_peak_label == "Tous les pics" else 14, symbol='triangle-up', line=dict(width=2, color='darkred')),
                        text=causes_text,
                        textfont=dict(color='darkred'),
                        textposition='top center',
                        hovertemplate='<b>Pic Haut</b><br>Temp: %{y:.1f}°C<br>Heure: %{x}<br>Causes: ' + hover_causes + '<extra></extra>'
                    ))
                if not peaks_to_show.empty and 'Bas' in peaks_to_show['type'].values:
                    low_to_show = peaks_to_show[peaks_to_show['type'] == 'Bas']
                    causes_text = low_to_show.apply(lambda row: "\n".join(row['causes']) if row['causes'] else "Aucune cause évidente", axis=1)
                    hover_causes = low_to_show.apply(lambda row: '<br>'.join(row['causes']) if row['causes'] else 'Aucune cause évidente', axis=1)
                    fig.add_trace(go.Scatter(
                        x=low_to_show['spike_time'],
                        y=low_to_show['spike_temp'],
                        mode='markers+text',
                        name='Pics Bas',
                        marker=dict(color='darkorange', size=12 if selected_peak_label == "Tous les pics" else 14, symbol='triangle-down', line=dict(width=2, color='darkorange')),
                        text=causes_text,
                        textfont=dict(color='darkgreen'),
                        textposition='bottom center',
                        hovertemplate='<b>Pic Bas</b><br>Temp: %{y:.1f}°C<br>Heure: %{x}<br>Causes: ' + hover_causes + '<extra></extra>'
                    ))

                # layout
                layout_config = {
                    'title': dict(text=f'📈 Évolution temporelle', font=dict(size=16)),
                    'xaxis': dict(title={'text':'Temps', 'font': dict(color='black')}, showgrid=True, gridcolor='rgba(128,128,128,0.15)', zeroline=False, tickfont=dict(color='black')),
                    'hovermode': 'x unified',
                    'height': 700,
                    'plot_bgcolor': 'rgba(0,0,0,0)',
                    'paper_bgcolor': 'rgba(0,0,0,0)',
                    'legend': dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
                }
                if has_temp:
                    layout_config['yaxis'] = dict(title=dict(text='Température (°C)', font=dict(color='#2E86AB')), side='left')
                if has_power and has_temp:
                    layout_config['yaxis2'] = dict(title=dict(text='Puissance (kW)', font=dict(color='#F18F01')), overlaying='y', side='right')
                elif has_power:
                    layout_config['yaxis'] = dict(title=dict(text='Puissance (kW)', font=dict(color='#F18F01')), side='left')

                # 3ème axe pour binaires si séparées (optionnel)
                if binary_display == "Séparées classiques" and binary_metrics and (has_temp or has_power):
                    if has_temp and has_power:
                        layout_config['yaxis3'] = dict(title='État (0=OFF,1=ON)', overlaying='y', side='right', position=0.85, anchor='free', tickvals=[0,1], ticktext=['OFF','ON'])
                        layout_config['margin'] = dict(r=220)
                    else:
                        layout_config['yaxis2'] = dict(title='État (0=OFF,1=ON)', overlaying='y', side='right')

                if binary_display == "Superposées transparentes" and binary_metrics_all and (has_temp or has_power):
                    # On utilise la plage Y calculée pour inclure les binaires (Porte et CLIMs)
                    fig.update_yaxes(range=[y_min_range, y_max_range])
                elif has_temp or has_power:
                    # Sinon, on applique juste une petite marge standard
                    fig.update_yaxes(range=[y_min - band_amplitude * 0.05, y_max + band_amplitude * 0.05])
                # --- FIN DU BLOC 5 ---


                fig.update_layout(**layout_config)
                fig.update_layout(dragmode='zoom', selectdirection='h', showlegend=True)
                fig.update_xaxes(rangeslider_visible=False, showspikes=True, spikecolor="gray", spikesnap="cursor", spikemode="across")
                fig.update_yaxes(showspikes=True, spikecolor="gray")

                config = {
                    'displayModeBar': True,
                    'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape'],
                    'toImageButtonOptions': {'format': 'png', 'filename': 'evolution_temporelle', 'height':700, 'width':1200, 'scale':2}
                }
                st.plotly_chart(fig, use_container_width=True, config=config, key="tab8_main_chart")

                st.markdown("##### ⚠️ Causes potentielles identifiées:")
                if selected_row['causes']:
                    for cause in selected_row['causes']:
                        st.markdown(f"* {cause}")
                else:
                    st.info("✅ Aucune cause détectée.")

                # ----------------------------
                # 5) ANALYSE DÉTAILLÉE DES PICS (sous le graphique)
                # ----------------------------
                st.markdown("---")
                
                # --- FONCTION UTILITAIRE POUR LE CALCUL LOCAL DE CORRÉLATION (Réutilisation de la logique) ---
                def get_correlations_for_row(row, df):
                    # Définition de la fenêtre de corrélation pour l'affichage (Zoom + Marge de 1h)
                    corr_start = row['start_time'] - pd.Timedelta(hours=1)
                    corr_end = row['end_time'] + pd.Timedelta(minutes=20)
                    
                    # Contexte -1h/+20min pour les métriques secondaires
                    context_local = df[(df['Timestamp'] >= row['spike_time'] - pd.Timedelta(hours=1)) & 
                                       (df['Timestamp'] <= row['spike_time'] + pd.Timedelta(minutes=20))]
                    
                    corr_ext = None
                    # --- Calcul Ext ---
                    if 'Temp_Exterieure' in df.columns:
                        corr_data_ext = df[(df['Timestamp'] >= corr_start) & (df['Timestamp'] <= corr_end)]
                        corr_data_ext = corr_data_ext.dropna(subset=['Temp_Ambiante', 'Temp_Exterieure'])
                        if len(corr_data_ext) >= 10:
                            corr_ext, _ = scipy.stats.spearmanr(corr_data_ext['Temp_Ambiante'], corr_data_ext['Temp_Exterieure'])
                    
                    corr_it = None
                    # --- Calcul IT ---
                    if 'Puissance_IT' in df.columns:
                        corr_data_it = context_local.dropna(subset=['Temp_Ambiante', 'Puissance_IT'])
                        if len(corr_data_it) >= 5:
                            corr_it, _ = scipy.stats.spearmanr(corr_data_it['Temp_Ambiante'], corr_data_it['Puissance_IT'])

                    return context_local, corr_ext, corr_it
                # ------------------------------------------------------------
                
                if selected_peak_label == "Tous les pics":
                    st.subheader("🔎 Analyse des pics détectés (Température Ambiante)")

                    # Pics hauts
                    st.markdown("### 📈 Pics Hauts")
                    if not high_spikes_df.empty:
                        st.success(f"{len(high_spikes_df)} pic(s) haut(s) détecté(s) ≥ +{MIN_EXCURSION:.1f}°C")
                        for idx, row in high_spikes_df.iterrows():
                            st.markdown("---")
                            st.markdown(f"**Pic Haut #{idx+1} — {row['spike_temp']:.1f}°C (+{row['excursion']:.1f}°C)**")
                            st.write(f"- Heure : {row['spike_time'].strftime('%d/%m %H:%M')}  |  Durée estimée : {row['duration_min']:.0f} min")
                            
                            # CALCULER LES CORRELATIONS POUR CETTE LIGNE (Assure que corr_ext/it existent ici)
                            context, corr_ext, corr_it = get_correlations_for_row(row, df)

                            if row['causes']:
                                st.error(f" Causes : {' || '.join(row['causes'])}") 
                            
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.metric("Temp. max", f"{row['spike_temp']:.1f}°C")
                                st.metric("Excursion", f"+{row['excursion']:.1f}°C")
                            
                            with c2:
                                if 'Temp_Exterieure' in context.columns:
                                    st.metric("Temp. Ext. (moy.)", f"{context['Temp_Exterieure'].mean():.1f}°C")
                                
                                # AFFICHAGE DE LA CORRELATION EXT (st.metric DECIMAL)
                                if corr_ext is not None:
                                    st.metric(label="ρ Ext/Amb",value=f"{corr_ext:.2f}")
                                else:
                                    st.caption("ρ Ext/Amb: N/A")
                                    
                            with c3:
                                if 'Puissance_IT' in context.columns:
                                    st.metric("Puissance IT (moy.)", f"{context['Puissance_IT'].mean():.0f} kW")
                                
                                # AFFICHAGE DE LA CORRELATION IT (st.metric DECIMAL)
                                if corr_it is not None:
                                    st.metric(
                                        label="ρ IT/Amb", 
                                        value=f"{corr_it:.2f}"
                                    )
                                else:
                                    st.caption("ρ IT/Amb: N/A")

                        csv_high = high_spikes_df.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Télécharger pics hauts (CSV)", data=csv_high, file_name=f"pics_hauts_{start_date.strftime('%Y%m%d')}.csv", mime="text/csv")
                    else:
                        st.info("Aucun pic haut détecté.")

                    # Pics bas
                    st.markdown("### 📉 Pics Bas")
                    if not low_spikes_df.empty:
                        st.success(f"{len(low_spikes_df)} pic(s) bas détecté(s) ≥ -{MIN_EXCURSION:.1f}°C")
                        for idx, row in low_spikes_df.iterrows():
                            st.markdown("---")
                            st.markdown(f"**Pic Bas #{idx+1} — {row['spike_temp']:.1f}°C (-{row['excursion']:.1f}°C)**")
                            st.write(f"- Heure : {row['spike_time'].strftime('%d/%m %H:%M')}  |  Durée estimée : {row['duration_min']:.0f} min")
                            
                            # CALCULER LES CORRELATIONS POUR CETTE LIGNE
                            context, corr_ext, corr_it = get_correlations_for_row(row, df)
                            
                            if row['causes']:
                                st.error(f"Causes : {' || '.join(row['causes'])}") 
                            
                            d1, d2, d3 = st.columns(3)
                            with d1:
                                st.metric("Temp. min", f"{row['spike_temp']:.1f}°C")
                                st.metric("Excursion", f"-{row['excursion']:.1f}°C")
                            
                            with d2:
                                if 'Temp_Exterieure' in context.columns:
                                    st.metric("Temp. Ext. (moy.)", f"{context['Temp_Exterieure'].mean():.1f}°C")
                                # AFFICHAGE DE LA CORRELATION EXT (st.metric DECIMAL)
                                if corr_ext is not None:
                                    st.metric(
                                        label="ρ Ext/Amb", 
                                        value=f"{corr_ext:.2f}"
                                    )
                                else:
                                    st.caption("ρ Ext/Amb: N/A")
                                    
                            with d3:
                                if 'Puissance_IT' in context.columns:
                                    st.metric("Puissance IT (moy.)", f"{context['Puissance_IT'].mean():.0f} kW")
                                # AFFICHAGE DE LA CORRELATION IT (st.metric DECIMAL)
                                if corr_it is not None:
                                    st.metric(
                                        label="ρ IT/Amb", 
                                        value=f"{corr_it:.2f}"
                                    )
                                else:
                                    st.caption("ρ IT/Amb: N/A")

                        csv_low = low_spikes_df.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Télécharger pics bas (CSV)", data=csv_low, file_name=f"pics_bas_{start_date.strftime('%Y%m%d')}.csv", mime="text/csv")
                    else:
                        st.info("Aucun pic bas détecté.")
                        
                elif selected_peak_label != "Tous les pics":
                    # --- BLOC PIC SÉLECTIONNÉ (AFFICHAGE UNIQUE) ---
                    selected_row = all_spikes_df[all_spikes_df['label'] == selected_peak_label].iloc[0]
                    type_pic = selected_row['type']
                    
                    # CALCULER LES CORRELATIONS POUR CE PIC
                    context, corr_ext, corr_it = get_correlations_for_row(selected_row, df)
                    
                    st.subheader(f"🔎 Analyse du pic {type_pic} sélectionné")
                    st.markdown(f"**Pic {type_pic} — {selected_row['spike_temp']:.1f}°C ({'+' if type_pic == 'Haut' else '-'}{selected_row['excursion']:.1f}°C)**")
                    st.write(f"- Heure : {selected_row['spike_time'].strftime('%d/%m %H:%M')}  |  Durée estimée : {selected_row['duration_min']:.0f} min")

                    
                    # Affichage des métriques et des corrélations (st.metric)
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric(f"Temp. {'max' if type_pic == 'Haut' else 'min'}", f"{selected_row['spike_temp']:.1f}°C")
                        st.metric("Excursion", f"{'+' if type_pic == 'Haut' else '-'}{selected_row['excursion']:.1f}°C")
                    
                    with c2:
                        if 'Temp_Exterieure' in context.columns:
                            st.metric("Temp. Ext. (moy.)", f"{context['Temp_Exterieure'].mean():.1f}°C")
                        # AFFICHAGE DE LA CORRELATION EXT
                        if corr_ext is not None:
                            st.metric(
                                label="ρ Ext/Amb", 
                                value=f"{corr_ext:.2f}"
                            )
                        else:
                            st.caption("ρ Ext/Amb: N/A")
                            
                    with c3:
                        if 'Puissance_IT' in context.columns:
                            st.metric("Puissance IT (moy.)", f"{context['Puissance_IT'].mean():.0f} kW")
                        # AFFICHAGE DE LA CORRELATION IT
                        if corr_it is not None:
                            st.metric(
                                label="ρ IT/Amb", 
                                value=f"{corr_it:.2f}"
                            )
                        else:
                            st.caption("ρ IT/Amb: N/A")
                            
                    st.markdown("---")

                    # Téléchargement pour ce pic unique
                    single_df = pd.DataFrame([selected_row])
                    csv_single = single_df.to_csv(index=False).encode('utf-8')
                    st.download_button(f"📥 Télécharger ce pic {type_pic.lower()} (CSV)", data=csv_single, file_name=f"pic_{type_pic.lower()}_{selected_row['spike_time'].strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")


            else:
                st.info("Veuillez sélectionner au moins une métrique à afficher.")
    else:
        st.warning("Aucune donnée disponible pour la période sélectionnée.")
