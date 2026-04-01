import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

from src.services import cache_service
from src.services.preload_service import (
    PreloadedStore,
    get_load_revision,
    get_preload_snapshot,
    is_pop_loaded,
)


def render_tab(
    filtered_merged_data,
    start_date,
    end_date,
    selected_region,
    selected_pop,
    store: PreloadedStore | None = None,
):
    """Render the Custom POP Comparison tab."""
    
    # Add title with region and POP name
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="color: black; font-size: 2.5rem; margin-bottom: 5px; font-weight: bold;">Rapport National " Analyse Comparative Personnalisée "</h1>
        <h3 style="color: black; font-size: 1.3rem; margin-top: 0; font-weight: normal;">📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    Cette section vous permet de comparer des POPs spécifiques de votre choix à travers différentes régions. 
    Sélectionnez les régions et POPs que vous souhaitez analyser pour obtenir une comparaison détaillée.
    """)
    
    if store is None:
        st.error("❌ Store préchargé indisponible pour la comparaison.")
        return
    
    # Custom selection interface (copied from "Sélection personnalisée")
    st.markdown("### ⚙️ Sélection des POPs à Comparer")
    
    # Multi-region/POP selection interface
    selected_regions_comparison = st.multiselect(
        "Sélectionner les régions",
        store.all_regions,
        default=[selected_region],
        key="tab13_comparison_regions_selector",
        help="Choisissez les régions d'où sélectionner les POPs à comparer"
    )
    
    pops_to_load_comparison = []
    
    if selected_regions_comparison:
        # For each selected region, allow POP selection
        st.markdown("#### 🏢 Sélection des POPs par Région")
        
        comparison_summary = []
        
        for region in selected_regions_comparison:
            available_pops = store.catalog_by_region.get(region, [])
            if available_pops:
                with st.expander(f"🗺️ {region} - {len(available_pops)} POPs disponibles", expanded=True):
                    selected_pops_comparison = st.multiselect(
                        f"POPs de {region}",
                        available_pops,
                        default=available_pops[:min(3, len(available_pops))],
                        key=f"tab13_comparison_pops_{region}",
                        help=f"Sélectionnez les POPs de {region} à inclure dans la comparaison"
                    )
                    
                    if selected_pops_comparison:
                        st.success(f"✅ {len(selected_pops_comparison)} POPs sélectionnés dans {region}")
                        comparison_summary.append(f"**{region}**: {len(selected_pops_comparison)} POPs")
                        
                        for pop in selected_pops_comparison:
                            pops_to_load_comparison.append((region, pop))
                    else:
                        st.warning(f"⚠️ Aucun POP sélectionné dans {region}")
            else:
                st.error(f"❌ Aucun POP disponible dans {region}")
        
        # Display selection summary
        if pops_to_load_comparison:
            st.markdown("### 📊 Résumé de la Sélection")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🌍 Régions sélectionnées", len(selected_regions_comparison))
            with col2:
                st.metric("📊 POPs à comparer", len(pops_to_load_comparison))
            with col3:
                avg_pops_per_region = len(pops_to_load_comparison) / len(selected_regions_comparison) if selected_regions_comparison else 0
                st.metric("📈 Moyenne POPs/Région", f"{avg_pops_per_region:.1f}")

            ready_now = sum(
                1 for region, pop in pops_to_load_comparison
                if is_pop_loaded(store, region, pop)
            )
            st.caption(
                f"POPs prêts: {ready_now}/{len(pops_to_load_comparison)} | "
                f"en cours: {len(pops_to_load_comparison) - ready_now}"
            )
            
            st.success(f"✅ **{len(pops_to_load_comparison)} POPs** sélectionnés dans **{len(selected_regions_comparison)} régions** prêts pour la comparaison")
        else:
            st.warning("⚠️ Aucun POP sélectionné pour la comparaison")
    else:
        st.info("👆 Sélectionnez d'abord les régions pour accéder aux POPs")
        pops_to_load_comparison = []
    
    # Initialize cache for comparison analysis
    if 'comparison_analysis_cache' not in st.session_state:
        st.session_state.comparison_analysis_cache = {}
    
    # Button to launch comparison analysis (copied from Multi-POP analysis)
    if st.button("🚀 Lancer la comparaison des POPs", key="tab13_launch_comparison_analysis"):
        if pops_to_load_comparison:
            # Start timing for comparison analysis
            comparison_start_time = time.time()
            st.info(f"🔄 **Comparaison de POPs**: {len(pops_to_load_comparison)} POPs dans {len(selected_regions_comparison)} régions")
            
            with st.spinner(f"Chargement optimisé de {len(pops_to_load_comparison)} POPs pour comparaison..."):
                ready_pairs = [
                    pair
                    for pair in pops_to_load_comparison
                    if is_pop_loaded(store, pair[0], pair[1])
                ]
                ready_set = set(ready_pairs)
                pending_pairs = [
                    pair
                    for pair in pops_to_load_comparison
                    if pair not in ready_set
                ]

                if pending_pairs:
                    snapshot = get_preload_snapshot(store)
                    st.info(
                        f"⏳ {len(pending_pairs)} POP(s) encore en chargement."
                    )
                    if snapshot.loading_pop_id:
                        st.caption(
                            f"Chargement en cours: {snapshot.loading_pop_id}"
                        )

                if not ready_pairs:
                    st.warning(
                        "Aucun POP prêt pour la comparaison pour le moment."
                    )
                    return

                load_revision = get_load_revision(store)
                # Load from preloaded memory + cache
                load_start = time.time()
                comparison_pops_data = cache_service.get_cached_multi_pop_data(
                    pop_pairs=ready_pairs,
                    start_date=start_date,
                    end_date=end_date,
                    db_version=store.db_version,
                    load_revision=load_revision,
                )
                load_time = time.time() - load_start
                
                if comparison_pops_data:
                    # Show simplified performance info
                    st.success(f"✅ **Données chargées en {load_time:.2f} secondes** ({len(comparison_pops_data)} POPs)")
                    
                    # Calculate correlations for all selected POPs
                    correlation_start = time.time()
                    comparison_correlation_df = cache_service.get_cached_pop_correlations(
                        pop_pairs=ready_pairs,
                        metric='Temp_Ambiante',
                        start_date=start_date,
                        end_date=end_date,
                        db_version=store.db_version,
                        load_revision=load_revision,
                    )
                    correlation_time = time.time() - correlation_start
                    
                    # Calculate total time
                    total_comparison_time = time.time() - comparison_start_time
                    
                    if not comparison_correlation_df.empty:
                        
                        # Comparison overview (copied from Multi-POP analysis)
                        st.markdown("### 📊 Vue d'ensemble de la Comparaison")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("POPs comparés", len(comparison_correlation_df))
                        with col2:
                            avg_temp_comparison = comparison_correlation_df['Temp_Ambiante_Mean'].mean()
                            st.metric("Temp. moyenne", f"{avg_temp_comparison:.1f}°C")
                        with col3:
                            regions_count_comparison = comparison_correlation_df['Region'].nunique()
                            st.metric("Régions incluses", regions_count_comparison)
                        with col4:
                            st.metric("Temps d'analyse", f"{total_comparison_time:.2f}s")
                        
                        # Create detailed correlation table (copied from Multi-POP analysis)
                        st.markdown("### 🎯 Dashboard de Comparaison des POPs")
                        st.markdown("### 📊 Tableau Détaillé des Corrélations")
                        
                        # Select relevant columns for display
                        display_columns_comparison = ['Region', 'POP', 'Temp_Ambiante_Mean']
                        
                        # Add Spearman correlation columns (excluding Puissance_CLIM)
                        corr_columns_comparison = [col for col in comparison_correlation_df.columns if 'Spearman' in col and col != 'Puissance_CLIM_Spearman']
                        display_columns_comparison.extend(corr_columns_comparison)
                        
                        # Create display DataFrame
                        display_df_comparison = comparison_correlation_df[display_columns_comparison].copy()
                        
                        # Rename columns for clarity
                        rename_dict_comparison = {
                            'Temp_Ambiante_Mean': 'Temp Moy (°C)',
                            'Temp_Exterieure_Spearman': 'Corr. Temp Ext',
                            'Puissance_IT_Spearman': 'Corr. Puissance IT',
                            'Porte_Status_Spearman': 'Corr. Porte'
                        }
                        
                        for col in corr_columns_comparison:
                            if 'CLIM_' in col and '_Status_Spearman' in col:
                                clim_name = col.replace('_Status_Spearman', '').replace('_', ' ')
                                rename_dict_comparison[col] = f'Corr. {clim_name}'
                            elif 'CLIM_' in col and '_Spearman' in col:
                                clim_name = col.replace('_Spearman', '').replace('_', ' ')
                                rename_dict_comparison[col] = f'Corr. {clim_name}'
                            elif '_Spearman' in col and col not in rename_dict_comparison:
                                base_name = col.replace('_Spearman', '').replace('_', ' ')
                                rename_dict_comparison[col] = f'Corr. {base_name}'
                        
                        display_df_comparison.rename(columns=rename_dict_comparison, inplace=True)
                        
                        # Function to get door state for a POP (copied from Multi-POP analysis)
                        def get_door_state_for_pop_comparison(region, pop):
                            if not comparison_pops_data:
                                return None
                            
                            if (region, pop) not in comparison_pops_data:
                                return None
                                
                            pop_data = comparison_pops_data[(region, pop)]
                            
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
                        display_df_copy_comparison = display_df_comparison.copy()
                        
                        # Replace None/NaN values in door correlation column with actual door state
                        door_col_comparison = None
                        for col in display_df_copy_comparison.columns:
                            if 'Porte' in col and any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                door_col_comparison = col
                                break
                        
                        if door_col_comparison is not None:
                            for idx, row in display_df_copy_comparison.iterrows():
                                current_val = row[door_col_comparison] 
                                if pd.isna(current_val) or current_val == "None" or str(current_val).lower() == "none":
                                    region = row['Region'] if 'Region' in row else ''
                                    pop = row['POP'] if 'POP' in row else ''
                                    door_state = get_door_state_for_pop_comparison(region, pop)
                                    
                                    if door_state is not None:
                                        display_df_copy_comparison.at[idx, door_col_comparison] = door_state
                        
                        # Convert ALL correlation columns to strings for Arrow compatibility
                        for col in display_df_copy_comparison.columns:
                            if any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                display_df_copy_comparison[col] = display_df_copy_comparison[col].apply(
                                    lambda x: (
                                        x if isinstance(x, str) else
                                        "N/A" if pd.isna(x) else
                                        f"{x:.1%}" if isinstance(x, (int, float)) else
                                        str(x)
                                    )
                                )
                        
                        # Create advanced styling (copied from Multi-POP analysis)
                        format_dict_comparison = {
                            'Temp Moy (°C)': '{:.2f}°C'
                        }
                        
                        styled_df_comparison = display_df_copy_comparison.style.format(format_dict_comparison)
                        
                        # Apply color coding to correlation columns
                        for col in display_df_copy_comparison.columns:
                            if any(keyword in col for keyword in ['Corr.', 'Spearman', 'correlation']):
                                def color_correlation_string_comparison(val):
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
                                
                                styled_df_comparison = styled_df_comparison.applymap(color_correlation_string_comparison, subset=[col])
                        
                        # Apply general table styles
                        styled_df_comparison = styled_df_comparison.set_table_styles([
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
                        
                        st.markdown("*Comparaison détaillée des corrélations pour les POPs sélectionnés*")
                        
                        # Display the table with fixed height for better readability
                        st.dataframe(
                            styled_df_comparison, 
                            width='stretch',
                            height=400
                        )
                        
                        # Calculate priorities for comparison
                        urgent_pops_comparison = []
                        warning_pops_comparison = []
                        
                        for idx, row in comparison_correlation_df.iterrows():
                            pop_name = f"{row['Region']}-{row['POP']}"
                            
                            urgent_correlations = []
                            warning_correlations = []
                            
                            for col in comparison_correlation_df.columns:
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
                                urgent_pops_comparison.append((pop_name, urgent_correlations))
                            if warning_correlations:
                                warning_pops_comparison.append((pop_name, warning_correlations))
                        
                        # Comparison priorities and recommendations
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.markdown("### 📚 Guide d'Interprétation")
                            st.markdown("""
                            - 🔴 **> 70 %**: Très forte corrélation positive - **Action urgente requise**
                            - 🟠 **50 % - 70 %**: Forte corrélation positive - **Surveillance étroite**
                            - 🟡 **30 % - 50 %**: Corrélation modérée - **À surveiller**
                            - ⚪ **10 % - 30 %**: Corrélation faible - **Acceptable**
                            - ⚪ **-10 % à 10 %**: Aucune corrélation - **Neutre**
                            - 🟢 **< -10 %**: Corrélation négative - **Bon signe**
                            """)
                            
                        with col2:
                            st.markdown("### 🎯 Priorités d'Action - Comparaison")
                            
                            if urgent_pops_comparison:
                                st.markdown("#### 🚨 **Action Urgente**")
                                for pop, issues in urgent_pops_comparison:
                                    with st.expander(f"🔴 {pop}", expanded=False):
                                        st.markdown("**Problèmes détectés:**")
                                        for issue in issues:
                                            st.markdown(f"- {issue}")
                            
                            if warning_pops_comparison:
                                st.markdown("#### ⚠️ **Surveillance Renforcée**")
                                for pop, issues in warning_pops_comparison:
                                    with st.expander(f"🟡 {pop}", expanded=False):
                                        st.markdown("**À surveiller:**")
                                        for issue in issues:
                                            st.markdown(f"- {issue}")
                            
                            if not urgent_pops_comparison and not warning_pops_comparison:
                                st.success("✅ **Tous les POPs comparés fonctionnent normalement**")
                        
                        # Comparison statistics
                        st.markdown("### 📈 Statistiques de Comparaison")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            total_pops_filtered_comparison = len(display_df_comparison)
                            st.metric("📊 POPs Comparés", total_pops_filtered_comparison)
                            
                        with col2:
                            total_issues_comparison = 0
                            corr_cols_comparison = [col for col in comparison_correlation_df.columns if 'Spearman' in col and col != 'Puissance_CLIM_Spearman']
                            for idx, row in comparison_correlation_df.iterrows():
                                for col in corr_cols_comparison:
                                    if (not pd.isna(row[col]) and 
                                        isinstance(row[col], (int, float)) and 
                                        row[col] >= 0.5):
                                        total_issues_comparison += 1
                            st.metric("⚠️ Corrélations à surveiller", total_issues_comparison)
                            
                        with col3:
                            avg_temp_display_comparison = display_df_comparison['Temp Moy (°C)'].mean()
                            temp_str_comparison = f"{avg_temp_display_comparison:.1f}°C" if not pd.isna(avg_temp_display_comparison) else "N/A"
                            st.metric("🌡️ Temp Moyenne Groupe", temp_str_comparison)
                        
                        with col4:
                            # Best performing POP in comparison
                            best_pop_comparison = comparison_correlation_df.loc[comparison_correlation_df['Temp_Ambiante_Mean'].idxmin()]
                            st.metric("⭐ Meilleur POP", f"{best_pop_comparison['POP']} ({best_pop_comparison['Temp_Ambiante_Mean']:.1f}°C)")
                        
                        # Comparison visualizations
                        st.markdown("### 📈 Visualisations Comparatives")
                        
                        # POP temperature comparison chart
                        fig_comparison = go.Figure()
                        
                        sorted_comparison_df = comparison_correlation_df.sort_values('Temp_Ambiante_Mean')
                        
                        fig_comparison.add_trace(go.Bar(
                            x=[f"{row['Region']}/{row['POP']}" for _, row in sorted_comparison_df.iterrows()],
                            y=sorted_comparison_df['Temp_Ambiante_Mean'],
                            marker_color=['red' if temp > 25 else 'orange' if temp > 23 else 'green' 
                                         for temp in sorted_comparison_df['Temp_Ambiante_Mean']],
                            text=[f"{temp:.1f}°C" for temp in sorted_comparison_df['Temp_Ambiante_Mean']],
                            textposition='outside'
                        ))
                        
                        fig_comparison.add_hline(y=24, line_dash="dash", line_color="red",
                                              annotation_text="Seuil recommandé: 24°C")
                        
                        fig_comparison.update_layout(
                            title="Comparaison des Températures - POPs Sélectionnés",
                            xaxis_title="POP",
                            yaxis_title="Température (°C)",
                            height=500,
                            xaxis_tickangle=-45
                        )
                        
                        st.plotly_chart(fig_comparison, width='stretch', key="tab13_multi_pop_comparison")
                        
                        # Regional comparison (if multiple regions)
                        if len(selected_regions_comparison) > 1:
                            st.markdown("### 🗺️ Comparaison par Région")
                            
                            region_comparison_stats = comparison_correlation_df.groupby('Region').agg({
                                'Temp_Ambiante_Mean': ['mean', 'min', 'max', 'count'],
                                'Data_Points': 'sum'
                            }).round(2)
                            
                            region_comparison_stats.columns = ['Temp Moy', 'Temp Min', 'Temp Max', 'Nb POPs', 'Points Data']
                            region_comparison_stats = region_comparison_stats.sort_values('Temp Moy', ascending=False)
                            
                            st.dataframe(region_comparison_stats, width='stretch')
                        
                        # Export comparison results
                        st.markdown("### 💾 Export des Résultats de Comparaison")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            csv_comparison = comparison_correlation_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Télécharger comparaison CSV",
                                data=csv_comparison,
                                file_name=f"comparaison_pops_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        
                        with col2:
                            # Summary text for comparison
                            summary_comparison = f"Comparaison POPs - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                            summary_comparison += f"Période: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}\n"
                            summary_comparison += f"POPs comparés: {len(comparison_correlation_df)}\n"
                            summary_comparison += f"Régions incluses: {regions_count_comparison}\n"
                            summary_comparison += f"Température moyenne: {avg_temp_comparison:.1f}°C\n"
                            if urgent_pops_comparison:
                                summary_comparison += f"POPs avec action urgente: {len(urgent_pops_comparison)}\n"
                            if warning_pops_comparison:
                                summary_comparison += f"POPs sous surveillance: {len(warning_pops_comparison)}\n"
                            
                            if st.button("📋 Copier Résumé Comparaison", key="tab13_copy_summary_comparison"):
                                st.info("📋 Résumé de comparaison prêt à copier-coller !")
                                st.code(summary_comparison, language="text")
                        
                    else:
                        total_comparison_time = time.time() - comparison_start_time
                        st.error("❌ Aucune donnée de corrélation disponible pour la comparaison")
                        st.info(f"⏱️ **Temps écoulé**: {total_comparison_time:.2f} secondes")
                else:
                    total_comparison_time = time.time() - comparison_start_time
                    st.error("❌ Impossible de charger les données pour la comparaison")
                    st.info(f"⏱️ **Temps écoulé**: {total_comparison_time:.2f} secondes")
        else:
            st.warning("⚠️ Veuillez sélectionner au moins un POP pour la comparaison")
    else:
        st.info("👆 Sélectionnez vos POPs et cliquez sur 'Lancer la comparaison des POPs' pour commencer")

