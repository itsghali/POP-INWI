"""
Onglet 1 : Vue d'ensemble du système
"""
import streamlit as st
import plotly.graph_objects as go


def render_tab(filtered_merged_data, start_date, end_date):
    """
    Render l'onglet Vue d'ensemble
    
    Args:
        filtered_merged_data: DataFrame filtré avec toutes les données
        start_date: Date de début de la période
        end_date: Date de fin de la période
    """
    st.header("📊 Vue d'ensemble du système")
    
    if not filtered_merged_data.empty and 'Timestamp' in filtered_merged_data.columns:
        # Display current unified period
        st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
        
        # Use the already filtered data from unified selector
        filtered_data = filtered_merged_data
        
        if not filtered_data.empty:
            # Métriques importantes
            st.subheader("📊 Métriques clés pour la période sélectionnée")
            
            # Fonction pour calculer les statistiques
            def calculate_stats(data, column):
                if column in data.columns:
                    # Filtrer les valeurs non-NaN
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
            temp_amb_stats = calculate_stats(filtered_data, 'Temp_Ambiante')
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
            temp_ext_stats = calculate_stats(filtered_data, 'Temp_Exterieure')
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
            puiss_it_stats = calculate_stats(filtered_data, 'Puissance_IT')
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
            clim_columns = [col for col in filtered_data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
            for clim_col in sorted(clim_columns):
                clim_name = clim_col.replace('_Status', '').replace('_', ' ')
                available_metrics[clim_col] = f'❄️ État {clim_name}'
            
            # Filtrer les métriques disponibles
            available_cols = [col for col in available_metrics.keys() if col in filtered_data.columns]
            
            # Afficher des informations sur la disponibilité des données
            with st.expander("ℹ️ Informations sur les données disponibles"):
                for col in available_cols:
                    valid_count = filtered_data[col].notna().sum()
                    total_count = len(filtered_data)
                    percentage = (valid_count / total_count * 100) if total_count > 0 else 0
                    st.text(f"{available_metrics[col]}: {valid_count}/{total_count} points ({percentage:.1f}%)")
            
            # Boutons de sélection rapide
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("🌡️ Toutes Températures", key="tab1_all_temp"):
                    temp_metrics = [col for col in available_cols if 'Temp' in col]
                    st.session_state['selected_metrics'] = temp_metrics
            with col2:
                if st.button("⚡ Toutes Puissances", key="tab1_all_power"):
                    power_metrics = [col for col in available_cols if 'Puissance' in col]
                    st.session_state['selected_metrics'] = power_metrics
            with col3:
                if st.button("❄️ Tous CLIMs", key="tab1_all_clims"):
                    clim_metrics = [col for col in available_cols if 'CLIM' in col and 'Status' in col]
                    st.session_state['selected_metrics'] = clim_metrics
            with col4:
                if st.button("📊 Tout Sélectionner", key="tab1_select_all"):
                    st.session_state['selected_metrics'] = available_cols
            
            selected_metrics = st.multiselect(
                "Sélectionner les données à afficher dans le graphique:",
                available_cols,
                key="tab1_metrics_selector",
                default=st.session_state.get('selected_metrics', ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT'] if all(col in available_cols for col in ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT']) else available_cols[:3]),
                format_func=lambda x: available_metrics[x]
            )
            
            if selected_metrics:
                # Créer un graphique unifié avec axes secondaires si nécessaire
                fig = go.Figure()
                
                # Nouvelles couleurs optimisées pour la superposition avec transparence
                # Couleurs sémantiques et contrastées pour une meilleure visibilité en superposition
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
                has_status = any('Status' in m for m in selected_metrics)
                
                # Séparer les données continues des données binaires
                continuous_metrics = [m for m in selected_metrics if 'Status' not in m]
                binary_metrics = [m for m in selected_metrics if 'Status' in m]
                
                # Option d'affichage pour les données binaires
                col1, col2 = st.columns([3, 1])
                with col2:
                    binary_display = st.selectbox(
                        "Affichage binaires:",
                        ["Superposées transparentes", "Séparées classiques"],
                        key="tab1_binary_display",
                        help="Superposées: données binaires empilées avec transparence par-dessus les continues. Séparées: affichage classique."
                    )
                
                # 1. COUCHE DE FOND : Tracer d'abord toutes les données continues normalement
                for idx, metric in enumerate(continuous_metrics):
                    # Obtenir les couleurs pour cette métrique
                    if metric in color_scheme:
                        colors_data = color_scheme[metric]
                    else:
                        colors_data = fallback_colors[idx % len(fallback_colors)]
                    
                    # Déterminer l'axe Y approprié
                    if 'Temp' in metric:
                        yaxis = 'y'
                    elif 'Puissance' in metric:
                        yaxis = 'y2' if has_temp else 'y'
                    
                    # Préparer les données
                    mask_valid = filtered_data[metric].notna()
                    x_data = filtered_data.loc[mask_valid, 'Timestamp']
                    y_data = filtered_data.loc[mask_valid, metric]
                    
                    if len(x_data) > 0:
                        # Tracer les données continues normalement (pas de transparence)
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
                
                # 2. COUCHE SUPERPOSÉE : Tracer les données binaires par-dessus
                if binary_metrics and binary_display == "Superposées transparentes":
                    # Calculer la plage des données continues pour normaliser les binaires
                    if continuous_metrics:
                        # Trouver min/max global des données continues pour la normalisation
                        all_continuous_values = []
                        for metric in continuous_metrics:
                            mask_valid = filtered_data[metric].notna()
                            if mask_valid.any():
                                all_continuous_values.extend(filtered_data.loc[mask_valid, metric].values)
                        
                        if all_continuous_values:
                            y_min, y_max = min(all_continuous_values), max(all_continuous_values)
                            y_range = y_max - y_min if y_max != y_min else 1
                            band_height = y_range * 0.15  # Chaque bande binaire = 15% de la plage
                        else:
                            y_min, y_max, y_range, band_height = 0, 1, 1, 0.2
                    else:
                        y_min, y_max, y_range, band_height = 0, 1, 1, 0.2
                    
                    # Tracer chaque donnée binaire comme une bande transparente empilée
                    for idx, metric in enumerate(binary_metrics):
                        # Couleurs pour les binaires avec forte transparence
                        binary_colors = [
                            {'color': '#4ECDC4', 'fill': 'rgba(78, 205, 196, 0.4)'},
                            {'color': '#45B7D1', 'fill': 'rgba(69, 183, 209, 0.4)'},
                            {'color': '#96CEB4', 'fill': 'rgba(150, 206, 180, 0.4)'},
                            {'color': '#FECA57', 'fill': 'rgba(254, 202, 87, 0.4)'},
                            {'color': '#6C5CE7', 'fill': 'rgba(108, 92, 231, 0.4)'}
                        ]
                        colors_data = binary_colors[idx % len(binary_colors)]
                        
                        # Préparer les données binaires
                        mask_valid = filtered_data[metric].notna()
                        x_data = filtered_data.loc[mask_valid, 'Timestamp']
                        binary_values = filtered_data.loc[mask_valid, metric]
                        
                        if len(x_data) > 0:
                            # Créer des bandes empilées pour les binaires
                            # Base de la bande actuelle
                            band_bottom = y_max + (idx * band_height * 0.6)  # Espacement entre bandes
                            
                            # Convertir les 0/1 en zones remplies
                            y_bottom = [band_bottom] * len(x_data)
                            y_top = [band_bottom + (band_height * 0.5 * val) for val in binary_values]
                            
                            # Trace pour le bas de la bande (invisible)
                            fig.add_trace(go.Scatter(
                                x=x_data,
                                y=y_bottom,
                                name=f"{available_metrics[metric]} (base)",
                                mode='lines',
                                line=dict(color='rgba(0,0,0,0)', width=0),
                                showlegend=False,
                                yaxis='y' if (continuous_metrics and 'Temp' in continuous_metrics[0]) else 'y',
                                hoverinfo='skip'
                            ))
                            
                            # Trace pour le haut de la bande (visible avec remplissage)
                            fig.add_trace(go.Scatter(
                                x=x_data,
                                y=y_top,
                                name=available_metrics[metric],
                                mode='lines',
                                line=dict(color=colors_data['color'], width=1),
                                fill='tonexty',  # Remplir entre cette trace et la précédente
                                fillcolor=colors_data['fill'],
                                yaxis='y' if (continuous_metrics and 'Temp' in continuous_metrics[0]) else 'y',
                                connectgaps=False,
                                hovertemplate='<b>%{fullData.name}</b><br>Valeur: %{customdata}<br>Temps: %{x}<extra></extra>',
                                customdata=binary_values
                            ))
                
                elif binary_metrics and binary_display == "Séparées classiques":
                    # Mode classique pour les binaires
                    for idx, metric in enumerate(binary_metrics):
                        if metric in color_scheme:
                            colors_data = color_scheme[metric]
                        else:
                            colors_data = fallback_colors[(len(continuous_metrics) + idx) % len(fallback_colors)]
                        
                        yaxis = 'y3' if (has_temp and has_power) else ('y2' if (has_temp or has_power) else 'y')
                        
                        mask_valid = filtered_data[metric].notna()
                        x_data = filtered_data.loc[mask_valid, 'Timestamp']
                        y_data = filtered_data.loc[mask_valid, metric]
                        
                        if len(x_data) > 0:
                            fig.add_trace(go.Scatter(
                                x=x_data,
                                y=y_data,
                                name=available_metrics[metric],
                                mode='lines',
                                line=dict(shape='hv', color=colors_data['color'], width=2),
                                yaxis=yaxis,
                                connectgaps=False
                            ))
                
                # Vérifier s'il y a des traces ajoutées
                if len(fig.data) == 0:
                    st.warning("Aucune donnée valide trouvée pour les métriques sélectionnées dans la période choisie.")
                else:
                    # Configuration améliorée du layout pour la superposition
                    layout_config = {
                        'title': dict(
                            text=f'📈 Évolution temporelle - {binary_display}',
                            font=dict(size=18, color='#2C3E50')
                        ),
                        'xaxis': dict(
                            title='Temps',
                            showgrid=True,
                            gridcolor='rgba(128,128,128,0.2)',
                            zeroline=False
                        ),
                        'hovermode': 'x unified',
                        'height': 700,
                        'plot_bgcolor': 'rgba(0,0,0,0)',
                        'paper_bgcolor': 'rgba(0,0,0,0)',
                        'legend': dict(
                            orientation="v",
                            yanchor="top",
                            y=1,
                            xanchor="left",
                            x=1.02,
                            bgcolor="rgba(255,255,255,0.8)",
                            bordercolor="rgba(128,128,128,0.3)",
                            borderwidth=1
                        ),
                        'margin': dict(r=200)  # Plus d'espace pour la légende
                    }
                
                    # Configuration des axes Y pour le nouveau système de couches
                    # L'axe Y principal est toujours pour les données continues
                    if has_temp:
                        layout_config['yaxis'] = dict(
                            title=dict(text='Température (°C)', font=dict(color='#2E86AB')),
                            side='left',
                            showgrid=True,
                            gridcolor='rgba(128,128,128,0.2)',
                            zeroline=True,
                            zerolinecolor='rgba(128,128,128,0.4)'
                        )
                    
                    # Axe Y secondaire pour les puissances
                    if has_power and has_temp:
                        layout_config['yaxis2'] = dict(
                            title=dict(text='Puissance (kW)', font=dict(color='#F18F01')),
                            overlaying='y',
                            side='right',
                            showgrid=False,
                            zeroline=False
                        )
                    elif has_power:
                        layout_config['yaxis'] = dict(
                            title=dict(text='Puissance (kW)', font=dict(color='#F18F01')),
                            side='left',
                            showgrid=True,
                            gridcolor='rgba(128,128,128,0.2)',
                            zeroline=True,
                            zerolinecolor='rgba(128,128,128,0.4)'
                        )
                    
                    # Ajouter troisième axe pour binaires séparées si nécessaire
                    if binary_display == "Séparées classiques" and binary_metrics:
                        if has_status and (has_temp or has_power):
                            if has_temp and has_power:
                                layout_config['yaxis3'] = dict(
                                    title='État (0=OFF, 1=ON)',
                                    overlaying='y',
                                    side='right',
                                    position=0.85,
                                    anchor='free',
                                    tickvals=[0, 1],
                                    ticktext=['OFF', 'ON']
                                )
                                layout_config['xaxis']['domain'] = [0, 0.85]
                            else:
                                layout_config['yaxis2'] = dict(
                                    title='État (0=OFF, 1=ON)',
                                    overlaying='y',
                                    side='right',
                                    tickvals=[0, 1],
                                    ticktext=['OFF', 'ON']
                                )
                    
                    fig.update_layout(**layout_config)
                    
                    # Ajouter des fonctionnalités interactives supplémentaires
                    fig.update_layout(
                        # Configuration pour interactions de type TradingView
                        dragmode='zoom',
                        selectdirection='h',  # 'h' pour horizontal
                        showlegend=True,
                    )
                    
                    # Configurer les interactions
                    fig.update_xaxes(
                        rangeslider_visible=False,  # Pas de rangeslider pour éviter l'encombrement
                        showspikes=True,
                        spikecolor="gray",
                        spikesnap="cursor",
                        spikemode="across",
                        spikethickness=1
                    )
                    
                    fig.update_yaxes(
                        showspikes=True,
                        spikecolor="gray",
                        spikethickness=1
                    )
                    
                    # Afficher le graphique avec configuration étendue
                    config = {
                        'displayModeBar': True,
                        'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape'],
                        'toImageButtonOptions': {
                            'format': 'png',
                            'filename': f'evolution_temporelle_{binary_display.lower().replace(" ", "_")}',
                            'height': 700,
                            'width': 1200,
                            'scale': 2
                        }
                    }
                    st.plotly_chart(fig, use_container_width=True, config=config, key="temporal_analysis_main")
                    
                    # Ajouter une légende des couleurs pour référence
                    if binary_display == "Superposées transparentes" and binary_metrics:
                        with st.expander("🎨 Guide du système de couches"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**📊 Couche de fond (Données continues):**")
                                st.markdown("- <span style='color:#2E86AB'>**Température Ambiante**</span> - Ligne pleine", unsafe_allow_html=True)
                                st.markdown("- <span style='color:#A23B72'>**Température Extérieure**</span> - Ligne pleine", unsafe_allow_html=True)
                                st.markdown("- <span style='color:#F18F01'>**Puissance IT**</span> - Ligne pleine", unsafe_allow_html=True)
                                st.markdown("- <span style='color:#C73E1D'>**Puissance Générale**</span> - Ligne pleine", unsafe_allow_html=True)
                                st.markdown("- <span style='color:#FF6B6B'>**Puissance CLIM**</span> - Ligne pleine", unsafe_allow_html=True)
                            with col2:
                                st.markdown("**🔧 Couche superposée (États binaires):**")
                                # Générer dynamiquement la légende pour tous les CLIMs détectés
                                clim_status_cols = [m for m in selected_metrics if m.startswith('CLIM_') and m.endswith('_Status')]
                                for clim_col in sorted(clim_status_cols):
                                    if clim_col in color_scheme:
                                        color = color_scheme[clim_col]['color']
                                        clim_name = clim_col.replace('_Status', '').replace('_', ' ')
                                        st.markdown(f"- <span style='color:{color}'>**{clim_name}**</span> - Zones transparentes empilées", unsafe_allow_html=True)
                                if 'Porte_Status' in selected_metrics:
                                    st.markdown("- <span style='color:#6C5CE7'>**Porte**</span> - Zones transparentes empilées", unsafe_allow_html=True)
                                st.markdown("\n**💡 Les zones colorées = ON, transparent = OFF**")
            else:
                st.info("Veuillez sélectionner au moins une métrique à afficher.")
        else:
            st.warning("Aucune donnée disponible pour la période sélectionnée.")
    else:
        st.error("Aucune donnée disponible.")
