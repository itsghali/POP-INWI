import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from data_cleaning import DataCleaner
from src.core.data_loader import load_multiple_pops_optimized
import time


def render_tab(filtered_merged_data, start_date, end_date, selected_region, selected_pop):
    """Render the Regional Report tab."""
    # Add title with region and POP name
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="color: black; font-size: 2.5rem; margin-bottom: 5px; font-weight: bold;">Rapport Région " {selected_region} "</h1>
        <h3 style="color: black; font-size: 1.3rem; margin-top: 0; font-weight: normal;">📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize the data cleaner for region analysis
    region_cleaner = DataCleaner(auto_sync=False)
    
    # Get all POPs from the current region
    current_region_pops = region_cleaner.get_pops(selected_region)
    
    if current_region_pops:
        # Display region overview
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🏢 Région", selected_region)
        with col2:
            st.metric("📊 POPs Total", len(current_region_pops))
        with col3:
            st.metric("🎯 POP Sélectionné", selected_pop)
        
        # Prepare POPs for loading
        pops_to_load_region = [(selected_region, pop) for pop in current_region_pops]
        
        # Initialize cache for region analysis if not exists
        if 'region_analysis_cache' not in st.session_state:
            st.session_state.region_analysis_cache = {}
        
        # Button to launch region analysis
        if st.button("🔄 Lancer l'analyse régionale", key="launch_region_analysis"):
            if pops_to_load_region:
                # Start timing for region analysis
                region_start_time = time.time()
                st.info(f"🔄 **Analyse de la région {selected_region}**: {len(pops_to_load_region)} POPs")
                
                with st.spinner(f"Chargement des données de la région {selected_region}..."):
                    # Load data for all POPs in the region
                    load_start = time.time()
                    region_pops_data, cached_count, fresh_load_count = load_multiple_pops_optimized(pops_to_load_region)
                    load_time = time.time() - load_start
                    
                    if region_pops_data:
                        st.success(f"✅ **Données chargées en {load_time:.2f} secondes** ({len(region_pops_data)} POPs)")
                        
                        # Calculate correlations for all POPs in the region
                        correlation_start = time.time()
                        period = (start_date, end_date) if start_date and end_date else None
                        region_correlation_df = region_cleaner.calculate_pop_correlations(
                            region_pops_data, 
                            metric='Temp_Ambiante',
                            period=period
                        )
                        correlation_time = time.time() - correlation_start
                        
                        # Calculate total time
                        total_region_time = time.time() - region_start_time
                        
                        if not region_correlation_df.empty:
                            
                            # Vue d'ensemble de la région
                            st.markdown("### 📊 Vue d'ensemble de la Région")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("POPs analysés", len(region_correlation_df))
                            with col2:
                                avg_temp = region_correlation_df['Temp_Ambiante_Mean'].mean()
                                st.metric("Temp. moyenne régionale", f"{avg_temp:.1f}°C")
                            with col3:
                                st.metric("Temps d'analyse", f"{total_region_time:.2f}s")
                            
                            # Create detailed correlation table for the region
                            st.markdown("### 📊 Tableau Détaillé des Corrélations - Région")
                            
                            # Select relevant columns for display
                            display_columns = ['Region', 'POP', 'Temp_Ambiante_Mean']
                            
                            # Add Spearman correlation columns (excluding Puissance_CLIM)
                            corr_columns = [col for col in region_correlation_df.columns if 'Spearman' in col and col != 'Puissance_CLIM_Spearman']
                            display_columns.extend(corr_columns)
                            
                            # Create display DataFrame
                            region_display_df = region_correlation_df[display_columns].copy()
                            
                            # Rename columns for clarity
                            rename_dict = {
                                'Temp_Ambiante_Mean': 'Temp Moy (°C)',
                                'Temp_Exterieure_Spearman': 'Corr. Temp Ext',
                                'Puissance_IT_Spearman': 'Corr. Puissance IT',
                                'Porte_Status_Spearman': 'Corr. Porte'
                            }
                            
                            for col in corr_columns:
                                if 'CLIM_' in col and '_Status_Spearman' in col:
                                    clim_name = col.replace('_Status_Spearman', '').replace('_', ' ')
                                    rename_dict[col] = f'Corr. {clim_name}'
                                elif 'CLIM_' in col and '_Spearman' in col:
                                    clim_name = col.replace('_Spearman', '').replace('_', ' ')
                                    rename_dict[col] = f'Corr. {clim_name}'
                                elif '_Spearman' in col and col not in rename_dict:
                                    base_name = col.replace('_Spearman', '').replace('_', ' ')
                                    rename_dict[col] = f'Corr. {base_name}'
                            
                            region_display_df.rename(columns=rename_dict, inplace=True)
                            
                            # Function to get door state for a POP
                            def get_door_state_for_pop_region(region, pop):
                                if not region_pops_data:
                                    return None
                                
                                if (region, pop) not in region_pops_data:
                                    return None
                                    
                                pop_data = region_pops_data[(region, pop)]
                                
                                if 'Porte_Status' in pop_data.columns:
                                    door_values = pop_data['Porte_Status'].dropna()
                                    if len(door_values) > 0:
                                        door_numeric = door_values.map({
                                            'Open': 1, 'Ouvert': 1, 'open': 1, '1': 1, 1: 1,
                                            'Close': 0, 'Fermé': 0, 'closed': 0, '0': 0, 0: 0,
                                            'Closed': 0, 'OPEN': 1, 'CLOSE': 0, 'CLOSED': 0
                                        })
                                        door_numeric = pd.to_numeric(door_numeric, errors='coerce').dropna()
                                        
                                        if len(door_numeric) > 0:
                                            unique_values = door_numeric.unique()
                                            if len(unique_values) == 1:
                                                if unique_values[0] == 1:
                                                    return "Toujours Ouverte"
                                                else:
                                                    return "Toujours Fermée"
                                            else:
                                                return None
                                return None
                            
                            # Create copy for modifications
                            region_display_df_copy = region_display_df.copy()
                            
                            # Replace None/NaN values in door correlation column with actual door state
                            door_col = None
                            for col in region_display_df_copy.columns:
                                if 'Porte' in col and any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                    door_col = col
                                    break
                            
                            if door_col is not None:
                                for idx, row in region_display_df_copy.iterrows():
                                    current_val = row[door_col] 
                                    if pd.isna(current_val) or current_val == "None" or str(current_val).lower() == "none":
                                        region = row['Region'] if 'Region' in row else ''
                                        pop = row['POP'] if 'POP' in row else ''
                                        door_state = get_door_state_for_pop_region(region, pop)
                                        
                                        if door_state is not None:
                                            region_display_df_copy.at[idx, door_col] = door_state
                            
                            # Convert correlation columns to strings for display
                            for col in region_display_df_copy.columns:
                                if any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                    region_display_df_copy[col] = region_display_df_copy[col].apply(
                                        lambda x: (
                                            x if isinstance(x, str) else
                                            "N/A" if pd.isna(x) else
                                            f"{x:.1%}" if isinstance(x, (int, float)) else
                                            str(x)
                                        )
                                    )
                            
                            # Apply styling
                            format_dict = {
                                'Temp Moy (°C)': '{:.2f}°C'
                            }
                            
                            styled_region_df = region_display_df_copy.style.format(format_dict)
                            
                            # Apply color coding for correlations
                            def color_correlation_region(val):
                                if isinstance(val, str):
                                    if val in ['Toujours Ouverte', 'Toujours OFF']:
                                        return 'background-color: #ffebee; color: #d32f2f; font-weight: bold'
                                    elif val in ['Toujours Fermée', 'Toujours ON']:
                                        return 'background-color: #e8f4fd; color: #1976d2; font-weight: bold'
                                    elif val == 'N/A':
                                        return 'background-color: #f5f5f5; color: #999999'
                                    elif val.endswith('%'):
                                        try:
                                            numeric_val = float(val.replace('%', '')) / 100
                                            if numeric_val > 0.8:
                                                return 'background-color: #d32f2f; color: white; font-weight: bold'
                                            elif numeric_val > 0.7:
                                                return 'background-color: #f44336; color: white; font-weight: bold'
                                            elif numeric_val > 0.5:
                                                return 'background-color: #ff7043; color: white'
                                            elif numeric_val > 0.3:
                                                return 'background-color: #ffab40; color: black'
                                            elif numeric_val > 0.1:
                                                return 'background-color: #fff3c4; color: black'
                                            elif numeric_val < -0.8:
                                                return 'background-color: #1b5e20; color: white; font-weight: bold'
                                            elif numeric_val < -0.7:
                                                return 'background-color: #2e7d32; color: white; font-weight: bold'
                                            elif numeric_val < -0.5:
                                                return 'background-color: #4caf50; color: white'
                                            elif numeric_val < -0.3:
                                                return 'background-color: #81c784; color: black'
                                            elif numeric_val < -0.1:
                                                return 'background-color: #c8e6c9; color: black'
                                            else:
                                                return 'background-color: #ffffff; color: black'
                                        except:
                                            return 'background-color: #ffffff; color: black'
                                    else:
                                        return 'background-color: #ffffff; color: black'
                                return 'background-color: #ffffff; color: black'
                            
                            # Apply color coding to correlation columns
                            for col in region_display_df_copy.columns:
                                if any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                    styled_region_df = styled_region_df.applymap(color_correlation_region, subset=[col])
                            
                            # Apply table styling
                            styled_region_df = styled_region_df.set_table_styles([
                                {'selector': 'thead th', 
                                 'props': [('background-color', '#1f77b4'), 
                                          ('color', 'white'), 
                                          ('font-weight', 'bold'),
                                          ('text-align', 'center'),
                                          ('vertical-align', 'middle'),
                                          ('padding', '12px')]},
                                {'selector': 'tbody td', 
                                 'props': [('text-align', 'center'), 
                                          ('vertical-align', 'middle'),
                                          ('padding', '8px'),
                                          ('border', '1px solid #ddd')]},
                                {'selector': 'td, th', 
                                 'props': [('text-align', 'center !important'),
                                          ('vertical-align', 'middle')]},
                                {'selector': 'tbody tr:nth-child(even)', 
                                 'props': [('background-color', '#f9f9f9')]},
                                {'selector': 'table', 
                                 'props': [('border-collapse', 'collapse'),
                                          ('margin', '25px 0'),
                                          ('font-size', '14px'),
                                          ('border-radius', '5px'),
                                          ('overflow', 'hidden')]}
                            ])
                            
                            st.markdown("*Analyse des corrélations pour tous les POPs de la région*")
                            
                            # Display the styled table
                            st.dataframe(
                                styled_region_df, 
                                use_container_width=True,
                                height=400
                            )
                            
                            # Calculate priorities for the region
                            urgent_pops_region = []
                            warning_pops_region = []
                            
                            for idx, row in region_correlation_df.iterrows():
                                pop_name = f"{row['Region']}-{row['POP']}"
                                
                                urgent_correlations = []
                                warning_correlations = []
                                
                                for col in region_correlation_df.columns:
                                    # Exclude Puissance_CLIM_Spearman from priorities
                                    if 'Spearman' in col and col != 'Puissance_CLIM_Spearman' and not pd.isna(row[col]):
                                        corr_value = row[col]
                                        display_name = col.replace('_Spearman', '').replace('_', ' ')
                                        if 'CLIM_' in col:
                                            display_name = f"Corr. {display_name}"
                                        elif col == 'Temp_Exterieure_Spearman':
                                            display_name = "Corr. Temp Ext"
                                        elif col == 'Puissance_IT_Spearman':
                                            display_name = "Corr. Puissance IT"
                                        elif col == 'Porte_Status_Spearman':
                                            display_name = "Corr. Porte"
                                        
                                        if isinstance(corr_value, (int, float)) and pd.notna(corr_value):
                                            if corr_value >= 0.7:
                                                urgent_correlations.append(f"{display_name}: {corr_value:.1%}")
                                            elif corr_value >= 0.5:
                                                warning_correlations.append(f"{display_name}: {corr_value:.1%}")
                                
                                if urgent_correlations:
                                    urgent_pops_region.append((pop_name, urgent_correlations))
                                if warning_correlations:
                                    warning_pops_region.append((pop_name, warning_correlations))
                            
                            # Display regional priorities and recommendations
                            col1, col2 = st.columns([1, 1])
                            
                            with col1:
                                st.markdown("### 📖 Guide d'Interprétation")
                                st.markdown("""
                                - 🔴 **> 70 %**: Très forte corrélation positive - **Action urgente requise**
                                - 🟠 **50 % - 70 %**: Forte corrélation positive - **Surveillance étroite**
                                - 🟡 **30 % - 50 %**: Corrélation modérée - **À surveiller**
                                - ⚪ **10 % - 30 %**: Corrélation faible - **Acceptable**
                                - ⚪ **-10 % à 10 %**: Aucune corrélation - **Neutre**
                                - 🟢 **< -10 %**: Corrélation négative - **Bon signe**
                                """)
                                
                            with col2:
                                st.markdown("### 🎯 Priorités d'Action - Région")
                                
                                if urgent_pops_region:
                                    st.markdown("#### 🚨 **Action Urgente**")
                                    for pop, issues in urgent_pops_region:
                                        with st.expander(f"🔴 {pop}", expanded=False):
                                            st.markdown("**Problèmes détectés:**")
                                            for issue in issues:
                                                st.markdown(f"- {issue}")
                                
                                if warning_pops_region:
                                    st.markdown("#### ⚠️ **Surveillance Renforcée**")
                                    for pop, issues in warning_pops_region:
                                        with st.expander(f"🟡 {pop}", expanded=False):
                                            st.markdown("**À surveiller:**")
                                            for issue in issues:
                                                st.markdown(f"- {issue}")
                                
                                if not urgent_pops_region and not warning_pops_region:
                                    st.success("✅ **Tous les POPs de la région fonctionnent normalement**")
                            
                            # Regional statistics
                            st.markdown("### 📈 Statistiques Régionales")
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                total_pops_region = len(region_display_df_copy)
                                st.metric("📊 POPs de la Région", total_pops_region)
                                
                            with col2:
                                total_issues_region = 0
                                corr_cols = [col for col in region_correlation_df.columns if 'Spearman' in col and col != 'Puissance_CLIM_Spearman']
                                for idx, row in region_correlation_df.iterrows():
                                    for col in corr_cols:
                                        if (not pd.isna(row[col]) and 
                                            isinstance(row[col], (int, float)) and 
                                            row[col] >= 0.5):
                                            total_issues_region += 1
                                st.metric("⚠️ Corrélations à surveiller", total_issues_region)
                                
                            with col3:
                                avg_temp_region = region_display_df_copy['Temp Moy (°C)'].mean()
                                temp_str_region = f"{avg_temp_region:.1f}°C" if not pd.isna(avg_temp_region) else "N/A"
                                st.metric("🌡️ Temp Moyenne Région", temp_str_region)
                            
                            with col4:
                                # Best performing POP
                                best_pop = region_correlation_df.loc[region_correlation_df['Temp_Ambiante_Mean'].idxmin()]
                                st.metric("⭐ Meilleur POP", f"{best_pop['POP']} ({best_pop['Temp_Ambiante_Mean']:.1f}°C)")
                            
                            # Regional temperature visualization
                            st.markdown("### 📈 Visualisation Régionale")
                            
                            fig_region = go.Figure()
                            
                            sorted_region_df = region_correlation_df.sort_values('Temp_Ambiante_Mean')
                            
                            fig_region.add_trace(go.Bar(
                                x=[row['POP'] for _, row in sorted_region_df.iterrows()],
                                y=sorted_region_df['Temp_Ambiante_Mean'],
                                marker_color=['red' if temp > 25 else 'orange' if temp > 23 else 'green' 
                                             for temp in sorted_region_df['Temp_Ambiante_Mean']],
                                text=[f"{temp:.1f}°C" for temp in sorted_region_df['Temp_Ambiante_Mean']],
                                textposition='outside'
                            ))
                            
                            fig_region.add_hline(y=24, line_dash="dash", line_color="red",
                                              annotation_text="Seuil recommandé: 24°C")
                            
                            fig_region.update_layout(
                                title=f"Température Ambiante par POP - Région {selected_region}",
                                xaxis_title="POP",
                                yaxis_title="Température (°C)",
                                height=500,
                                xaxis_tickangle=-45
                            )
                            
                            st.plotly_chart(fig_region, use_container_width=True, key=f"tab11_regional_analysis_{selected_region}")
                            
                            # Regional recommendations
                            st.markdown("### 💡 Recommandations pour la Région")
                            
                            avg_temp_region = region_correlation_df['Temp_Ambiante_Mean'].mean()
                            
                            if avg_temp_region > 25:
                                st.error(f"⚠️ Température moyenne régionale élevée ({avg_temp_region:.1f}°C)")
                                st.markdown("""
                                **Actions recommandées pour la région:**
                                - Audit énergétique complet de la région
                                - Augmentation de la capacité de refroidissement
                                - Vérification de l'efficacité des unités CLIM dans tous les sites
                                - Optimisation de la circulation d'air régionale
                                - Formation du personnel local sur les bonnes pratiques
                                """)
                            elif avg_temp_region > 23:
                                st.warning(f"⚡ Température régionale à surveiller ({avg_temp_region:.1f}°C)")
                                st.markdown("""
                                **Actions préventives pour la région:**
                                - Surveillance renforcée de l'évolution
                                - Planification de la maintenance préventive régionale
                                - Optimisation des réglages CLIM
                                - Mise en place d'alertes automatiques
                                """)
                            else:
                                st.success(f"✅ Température régionale optimale ({avg_temp_region:.1f}°C)")
                                st.markdown("""
                                **Maintenir les bonnes pratiques:**
                                - Continuer la surveillance régulière
                                - Maintenir les protocoles de maintenance
                                - Documenter les bonnes pratiques pour les autres régions
                                """)
                            
                            # Export regional results
                            st.markdown("### 💾 Export des Résultats Régionaux")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                csv_region = region_correlation_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Télécharger rapport région CSV",
                                    data=csv_region,
                                    file_name=f"region_report_{selected_region}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                            
                            with col2:
                                # Summary text for the region
                                summary_region = f"Rapport Région {selected_region} - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                                summary_region += f"Période: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}\n"
                                summary_region += f"POPs analysés: {len(region_correlation_df)}\n"
                                summary_region += f"Température moyenne: {avg_temp_region:.1f}°C\n"
                                if urgent_pops_region:
                                    summary_region += f"POPs avec action urgente: {len(urgent_pops_region)}\n"
                                if warning_pops_region:
                                    summary_region += f"POPs sous surveillance: {len(warning_pops_region)}\n"
                                
                                if st.button("📋 Copier Résumé Région", key="copy_summary_region"):
                                    st.info("📋 Résumé régional prêt à copier-coller !")
                                    st.code(summary_region, language="text")
                            
                        else:
                            total_region_time = time.time() - region_start_time
                            st.error("❌ Aucune donnée de corrélation disponible pour la région")
                            st.info(f"⏱️ **Temps écoulé**: {total_region_time:.2f} secondes")
                    else:
                        total_region_time = time.time() - region_start_time
                        st.error("❌ Impossible de charger les données de la région")
                        st.info(f"⏱️ **Temps écoulé**: {total_region_time:.2f} secondes")
            else:
                st.warning("⚠️ Aucun POP trouvé dans la région sélectionnée")
        else:
            st.info("👆 Cliquez sur 'Lancer l'analyse régionale' pour analyser tous les POPs de la région")
    else:
        st.error(f"❌ Aucun POP trouvé dans la région {selected_region}")
        
        # Show alternative regions
        all_regions = region_cleaner.get_regions()
        if all_regions:
            st.markdown("### 💡 **Régions disponibles:**")
            for region in all_regions:
                region_pops = region_cleaner.get_pops(region)
                st.write(f"- **{region}**: {len(region_pops)} POPs")
