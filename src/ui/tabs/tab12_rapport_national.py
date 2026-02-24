import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

from data_cleaning import DataCleaner
from src.core.data_loader import load_multiple_pops_optimized


def render_tab(filtered_merged_data, start_date, end_date, selected_region, selected_pop):
    """Render the National Report tab with national-level analysis."""
    
    # Add title with region and POP name
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="color: black; font-size: 2.5rem; margin-bottom: 5px; font-weight: bold;">Rapport National " Toutes les Régions du Maroc "</h1>
        <h3 style="color: black; font-size: 1.3rem; margin-top: 0; font-weight: normal;">📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    
    # Initialize the data cleaner for national analysis
    national_cleaner = DataCleaner(auto_sync=False)
    
    # Get all regions and POPs (same logic as "Toutes les régions" in Multi-POP)
    all_pops_national = []
    region_stats_national = {}
    
    for region in national_cleaner.get_regions():
        region_pops = national_cleaner.get_pops(region)
        region_stats_national[region] = len(region_pops)
        for pop in region_pops:
            all_pops_national.append((region, pop))
    
    total_available_national = len(all_pops_national)
    total_regions_national = len(region_stats_national)
    
    if total_available_national > 0:
        # Display national overview (copied from "Toutes les régions")
        st.markdown("### 🌍 Vue d'ensemble Nationale")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🌍 Régions", total_regions_national)
        with col2:
            st.metric("📊 POPs Total", total_available_national)
        with col3:
            avg_pops_national = total_available_national / total_regions_national if total_regions_national > 0 else 0
            st.metric("📈 Moyenne POPs/Région", f"{avg_pops_national:.1f}")
        
        # Regional breakdown table (copied from "Toutes les régions")
        with st.expander("📋 Résumé par région", expanded=True):
            region_df_national = pd.DataFrame([
                {"Région": region, "Nombre de POPs": count}
                for region, count in region_stats_national.items()
            ])
            st.dataframe(region_df_national, use_container_width=True, hide_index=True)
        
        # Configuration section
        st.markdown("### ⚙️ Configuration de l'Analyse Nationale")
        
        # Region selection for national analysis
        available_regions = list(region_stats_national.keys())
        selected_regions_national = st.multiselect(
            "Sélectionner les régions",
            available_regions,
            default=available_regions,  # All regions selected by default
            key="tab12_national_regions_selector",
            help="Choisissez les régions à inclure dans l'analyse nationale"
        )
        
        if selected_regions_national:
            # Calculate POPs for selected regions
            pops_to_load_national = []
            total_selected_pops = 0
            
            for region in selected_regions_national:
                region_pops = national_cleaner.get_pops(region)
                for pop in region_pops:
                    pops_to_load_national.append((region, pop))
                total_selected_pops += len(region_pops)
            
            # Display selection summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🌍 Régions sélectionnées", len(selected_regions_national))
            with col2:
                st.metric("📊 POPs à analyser", total_selected_pops)
            with col3:
                coverage = (len(selected_regions_national) / total_regions_national) * 100
                st.metric("📈 Couverture nationale", f"{coverage:.1f}%")
            
            st.success(f"✅ Sélection: **{len(pops_to_load_national)} POPs** dans **{len(selected_regions_national)} régions**")
        else:
            st.warning("⚠️ Veuillez sélectionner au moins une région pour l'analyse")
            pops_to_load_national = []
        
        # Initialize cache for national analysis
        if 'national_multi_pop_cache' not in st.session_state:
            st.session_state.national_multi_pop_cache = {}
        
        # Button to launch national analysis (copied from Multi-POP analysis)
        if st.button("🚀 Lancer l'analyse nationale", key="tab12_launch_national_multi_pop"):
            if pops_to_load_national:
                # Start timing for national analysis
                national_start_time = time.time()
                st.info(f"🔄 **Analyse nationale**: {len(pops_to_load_national)} POPs sur {total_regions_national} régions")
                
                with st.spinner(f"Chargement optimisé de {len(pops_to_load_national)} POPs..."):
                    # Use optimized loading that reuses cached data
                    load_start = time.time()
                    national_pops_data, cached_count, fresh_load_count = load_multiple_pops_optimized(pops_to_load_national)
                    load_time = time.time() - load_start
                    
                    if national_pops_data:
                        # Show simplified performance info
                        st.success(f"✅ **Données chargées en {load_time:.2f} secondes** ({len(national_pops_data)} POPs)")
                        # Calculate correlations for all POPs
                        correlation_start = time.time()
                        period = (start_date, end_date) if start_date and end_date else None
                        national_correlation_df = national_cleaner.calculate_pop_correlations(
                            national_pops_data, 
                            metric='Temp_Ambiante',
                            period=period
                        )
                        correlation_time = time.time() - correlation_start
                        
                        # Calculate total time
                        total_national_time = time.time() - national_start_time
                        
                        if not national_correlation_df.empty:
                            
                            # National overview (copied from Multi-POP analysis)
                            st.markdown("### 📊 Vue d'ensemble Nationale")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("POPs analysés", len(national_correlation_df))
                            with col2:
                                avg_temp_national = national_correlation_df['Temp_Ambiante_Mean'].mean()
                                st.metric("Temp. moyenne nationale", f"{avg_temp_national:.1f}°C")
                            with col3:
                                regions_count_national = national_correlation_df['Region'].nunique()
                                st.metric("Régions couvertes", regions_count_national)
                            
                            # Create detailed correlation table (copied from Multi-POP analysis)
                            st.markdown("### 🎯 Dashboard de Performance Nationale")
                            st.markdown("### 📊 Tableau Détaillé des Corrélations")
                            
                            # Select relevant columns for display
                            display_columns_national = ['Region', 'POP', 'Temp_Ambiante_Mean']
                            
                            # Add Spearman correlation columns (excluding Puissance_CLIM)
                            corr_columns_national = [col for col in national_correlation_df.columns if 'Spearman' in col and col != 'Puissance_CLIM_Spearman']
                            display_columns_national.extend(corr_columns_national)
                            
                            # Create display DataFrame
                            display_df_national = national_correlation_df[display_columns_national].copy()
                            
                            # Rename columns for clarity
                            rename_dict_national = {
                                'Temp_Ambiante_Mean': 'Temp Moy (°C)',
                                'Temp_Exterieure_Spearman': 'Corr. Temp Ext',
                                'Puissance_IT_Spearman': 'Corr. Puissance IT',
                                'Porte_Status_Spearman': 'Corr. Porte'
                            }
                            
                            for col in corr_columns_national:
                                if 'CLIM_' in col and '_Status_Spearman' in col:
                                    clim_name = col.replace('_Status_Spearman', '').replace('_', ' ')
                                    rename_dict_national[col] = f'Corr. {clim_name}'
                                elif 'CLIM_' in col and '_Spearman' in col:
                                    clim_name = col.replace('_Spearman', '').replace('_', ' ')
                                    rename_dict_national[col] = f'Corr. {clim_name}'
                                elif '_Spearman' in col and col not in rename_dict_national:
                                    base_name = col.replace('_Spearman', '').replace('_', ' ')
                                    rename_dict_national[col] = f'Corr. {base_name}'
                            
                            display_df_national.rename(columns=rename_dict_national, inplace=True)
                            
                            # Display all POPs without filtering
                            filtered_display_df_national = display_df_national.copy()
                            
                            # Function to get door state for a POP (copied from Multi-POP analysis)
                            def get_door_state_for_pop_national(region, pop):
                                if not national_pops_data:
                                    return None
                                
                                if (region, pop) not in national_pops_data:
                                    return None
                                    
                                pop_data = national_pops_data[(region, pop)]
                                
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
                            
                            # Advanced correlation coloring function (copied from Multi-POP analysis)
                            def color_correlation_national(val):
                                if isinstance(val, str):
                                    if val in ['Toujours Ouverte', 'Toujours OFF']:
                                        return 'background-color: #ffebee; color: #d32f2f; font-weight: bold'
                                    elif val in ['Toujours Fermée', 'Toujours ON']:
                                        return 'background-color: #e8f4fd; color: #1976d2; font-weight: bold'
                                    else:
                                        return 'background-color: #e8f4fd; color: #1976d2; font-weight: bold'
                                elif pd.isna(val):
                                    return 'background-color: #f5f5f5; color: #999999'
                                elif val > 0.8:
                                    return 'background-color: #d32f2f; color: white; font-weight: bold'
                                elif val > 0.7:
                                    return 'background-color: #f44336; color: white; font-weight: bold'
                                elif val > 0.5:
                                    return 'background-color: #ff7043; color: white'
                                elif val > 0.3:
                                    return 'background-color: #ffab40; color: black'
                                elif val > 0.1:
                                    return 'background-color: #fff3c4; color: black'
                                elif val < -0.8:
                                    return 'background-color: #1b5e20; color: white; font-weight: bold'
                                elif val < -0.7:
                                    return 'background-color: #2e7d32; color: white; font-weight: bold'
                                elif val < -0.5:
                                    return 'background-color: #4caf50; color: white'
                                elif val < -0.3:
                                    return 'background-color: #81c784; color: black'
                                elif val < -0.1:
                                    return 'background-color: #c8e6c9; color: black'
                                else:
                                    return 'background-color: #ffffff; color: black'
                            
                            # Create copy for modifications
                            display_df_copy_national = filtered_display_df_national.copy()
                            
                            # Replace None/NaN values in door correlation column with actual door state
                            door_col_national = None
                            for col in display_df_copy_national.columns:
                                if 'Porte' in col and any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                    door_col_national = col
                                    break
                            
                            if door_col_national is not None:
                                for idx, row in display_df_copy_national.iterrows():
                                    current_val = row[door_col_national] 
                                    if pd.isna(current_val) or current_val == "None" or str(current_val).lower() == "none":
                                        region = row['Region'] if 'Region' in row else ''
                                        pop = row['POP'] if 'POP' in row else ''
                                        door_state = get_door_state_for_pop_national(region, pop)
                                        
                                        if door_state is not None:
                                            display_df_copy_national.at[idx, door_col_national] = door_state
                            
                            # Convert ALL correlation columns to strings for Arrow compatibility
                            for col in display_df_copy_national.columns:
                                if any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                    display_df_copy_national[col] = display_df_copy_national[col].apply(
                                        lambda x: (
                                            x if isinstance(x, str) else
                                            "N/A" if pd.isna(x) else
                                            f"{x:.1%}" if isinstance(x, (int, float)) else
                                            str(x)
                                        )
                                    )
                            
                            # Create advanced styling (copied from Multi-POP analysis)
                            format_dict_national = {
                                'Temp Moy (°C)': '{:.2f}°C'
                            }
                            
                            styled_df_national = display_df_copy_national.style.format(format_dict_national)
                            
                            # Apply color coding to correlation columns
                            for col in display_df_copy_national.columns:
                                if any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                    def color_correlation_string_national(val):
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
                                    
                                    styled_df_national = styled_df_national.applymap(color_correlation_string_national, subset=[col])
                            
                            # Apply general table styles
                            styled_df_national = styled_df_national.set_table_styles([
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
                            
                            st.markdown("*Analyse des corrélations pour tous les POPs au niveau national*")
                            
                            # Display the table with fixed height for better readability
                            st.dataframe(
                                styled_df_national, 
                                use_container_width=True,
                                height=400
                            )
                            
                            # Calculate priorities automatically BEFORE using variables (copied from Multi-POP analysis)
                            urgent_pops_national = []
                            warning_pops_national = []
                            
                            for idx, row in national_correlation_df.iterrows():
                                pop_name = f"{row['Region']}-{row['POP']}"
                                
                                urgent_correlations = []
                                warning_correlations = []
                                
                                for col in national_correlation_df.columns:
                                    # Exclude Puissance_CLIM_Spearman from priorities (same as table display)
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
                                    urgent_pops_national.append((pop_name, urgent_correlations))
                                if warning_correlations:
                                    warning_pops_national.append((pop_name, warning_correlations))
                            
                            # National priorities and recommendations
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
                                st.markdown("### 🎯 Priorités d'Action Nationales")
                                
                                if urgent_pops_national:
                                    st.markdown("#### 🚨 **Action Urgente**")
                                    for pop, issues in urgent_pops_national:
                                        with st.expander(f"🔴 {pop}", expanded=False):
                                            st.markdown("**Problèmes détectés:**")
                                            for issue in issues:
                                                st.markdown(f"- {issue}")
                                
                                if warning_pops_national:
                                    st.markdown("#### ⚠️ **Surveillance Renforcée**")
                                    for pop, issues in warning_pops_national:
                                        with st.expander(f"🟡 {pop}", expanded=False):
                                            st.markdown("**À surveiller:**")
                                            for issue in issues:
                                                st.markdown(f"- {issue}")
                                
                                if not urgent_pops_national and not warning_pops_national:
                                    st.success("✅ **Tous les POPs nationaux fonctionnent normalement**")
                            
                            # National statistics
                            st.markdown("### 📈 Statistiques Nationales")
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                total_pops_filtered_national = len(filtered_display_df_national)
                                st.metric("📊 POPs Analysés", total_pops_filtered_national)
                                
                            with col2:
                                total_issues_national = 0
                                corr_cols_national = [col for col in national_correlation_df.columns if 'Spearman' in col and col != 'Puissance_CLIM_Spearman']
                                for idx, row in national_correlation_df.iterrows():
                                    for col in corr_cols_national:
                                        if (not pd.isna(row[col]) and 
                                            isinstance(row[col], (int, float)) and 
                                            row[col] >= 0.5):
                                            total_issues_national += 1
                                st.metric("⚠️ Corrélations à surveiller", total_issues_national)
                                
                            with col3:
                                avg_temp_display_national = filtered_display_df_national['Temp Moy (°C)'].mean()
                                temp_str_national = f"{avg_temp_display_national:.1f}°C" if not pd.isna(avg_temp_display_national) else "N/A"
                                st.metric("🌡️ Temp Moyenne Nationale", temp_str_national)
                            
                            with col4:
                                # Best performing region
                                region_temps = national_correlation_df.groupby('Region')['Temp_Ambiante_Mean'].mean()
                                best_region = region_temps.idxmin()
                                best_temp = region_temps.min()
                                st.metric("⭐ Meilleure Région", f"{best_region} ({best_temp:.1f}°C)")
                            
                            # National visualizations
                            st.markdown("### 📈 Visualisations Nationales")
                            
                            # Regional temperature comparison
                            fig_national = go.Figure()
                            
                            # Group by region and calculate average temperature
                            region_temp_stats = national_correlation_df.groupby('Region')['Temp_Ambiante_Mean'].mean().sort_values()
                            
                            fig_national.add_trace(go.Bar(
                                x=region_temp_stats.index,
                                y=region_temp_stats.values,
                                marker_color=['red' if temp > 25 else 'orange' if temp > 23 else 'green' 
                                             for temp in region_temp_stats.values],
                                text=[f"{temp:.1f}°C" for temp in region_temp_stats.values],
                                textposition='outside'
                            ))
                            
                            fig_national.add_hline(y=24, line_dash="dash", line_color="red",
                                                  annotation_text="Seuil recommandé: 24°C")
                            
                            fig_national.update_layout(
                                title="Température Moyenne par Région - Vue Nationale",
                                xaxis_title="Région",
                                yaxis_title="Température (°C)",
                                height=500,
                                xaxis_tickangle=-45
                            )
                            
                            st.plotly_chart(fig_national, use_container_width=True, key="tab12_national_analysis")
                            
                            # National recommendations by region
                            st.markdown("### 💡 Recommandations par Région")
                            
                            national_region_stats = national_correlation_df.groupby('Region').agg({
                                'Temp_Ambiante_Mean': 'mean',
                                'Temp_Ambiante_Std': 'mean',
                                'Data_Points': 'sum'
                            }).round(2)
                            
                            for region in national_region_stats.index:
                                region_data = national_correlation_df[national_correlation_df['Region'] == region]
                                avg_temp = national_region_stats.loc[region, 'Temp_Ambiante_Mean']
                                
                                with st.expander(f"📍 {region} - Temp. moy: {avg_temp:.1f}°C"):
                                    if avg_temp > 25:
                                        st.error(f"⚠️ Température moyenne élevée ({avg_temp:.1f}°C)")
                                        st.markdown("""
                                        **Actions recommandées:**
                                        - Augmenter la capacité de refroidissement
                                        - Vérifier l'efficacité des unités CLIM
                                        - Optimiser la circulation d'air
                                        """)
                                    elif avg_temp > 23:
                                        st.warning(f"⚡ Température à surveiller ({avg_temp:.1f}°C)")
                                        st.markdown("""
                                        **Actions préventives:**
                                        - Surveiller l'évolution
                                        - Planifier la maintenance préventive
                                        - Optimiser les réglages CLIM
                                        """)
                                    else:
                                        st.success(f"✅ Température optimale ({avg_temp:.1f}°C)")
                                    
                                    st.write(f"**POPs dans cette région:** {len(region_data)}")
                                    for _, pop_data in region_data.iterrows():
                                        st.write(f"- {pop_data['POP']}: {pop_data['Temp_Ambiante_Mean']:.1f}°C")
                            
                            # Export national results
                            st.markdown("### 💾 Export des Résultats Nationaux")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                csv_national = national_correlation_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Télécharger rapport national CSV",
                                    data=csv_national,
                                    file_name=f"rapport_national_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                            
                            with col2:
                                # Summary text for national report
                                summary_national = f"Rapport National - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                                summary_national += f"Période: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}\n"
                                summary_national += f"POPs analysés: {len(national_correlation_df)}\n"
                                summary_national += f"Régions couvertes: {regions_count_national}\n"
                                summary_national += f"Température moyenne nationale: {avg_temp_national:.1f}°C\n"
                                if urgent_pops_national:
                                    summary_national += f"POPs avec action urgente: {len(urgent_pops_national)}\n"
                                if warning_pops_national:
                                    summary_national += f"POPs sous surveillance: {len(warning_pops_national)}\n"
                                
                                if st.button("📋 Copier Résumé National", key="tab12_copy_summary_national"):
                                    st.info("📋 Résumé national prêt à copier-coller !")
                                    st.code(summary_national, language="text")
                            
                        else:
                            total_national_time = time.time() - national_start_time
                            st.error("❌ Aucune donnée de corrélation disponible pour l'analyse nationale")
                            st.info(f"⏱️ **Temps écoulé**: {total_national_time:.2f} secondes")
                    else:
                        total_national_time = time.time() - national_start_time
                        st.error("❌ Impossible de charger les données nationales")
                        st.info(f"⏱️ **Temps écoulé**: {total_national_time:.2f} secondes")
            else:
                st.warning("⚠️ Veuillez sélectionner au moins un POP pour l'analyse nationale")
        else:
            st.info("👆 Configurez les paramètres et cliquez sur 'Lancer l'analyse nationale' pour commencer")
    else:
        st.error("❌ Aucun POP trouvé dans les données nationales")
        st.markdown("**Vérifiez la configuration de vos données.**")
