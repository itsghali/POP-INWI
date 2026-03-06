"""
Tab 7: Analyse des corrélations
Analyse des relations entre les variables et la température ambiante.
"""

import streamlit as st
import pandas as pd


def render_tab(filtered_merged_data, start_date, end_date, merged_data=None):
    """
    Affiche l'analyse des corrélations entre variables.
    
    Args:
        filtered_merged_data: DataFrame avec données filtrées
        start_date: Date de début de la période
        end_date: Date de fin de la période
        merged_data: DataFrame complet (optionnel, pour fallback)
    """
    # Use filtered_merged_data as merged_data if not provided
    if merged_data is None:
        merged_data = filtered_merged_data.copy()
    
    st.header("🔗 Analyse des Relations entre Variables")
    st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
    
    # Analyse du POP actuel (code existant)
    # Sélection des variables pour la corrélation
    numeric_vars = ['Temp_Ambiante', 'Temp_Exterieure', 'Puissance_IT', 'Porte_Status']
    
    # Ajouter les colonnes CLIM individuelles si elles existent
    clim_status_columns = [col for col in filtered_merged_data.columns if 'CLIM' in col and 'Status' in col]
    numeric_vars.extend(clim_status_columns)
    
    available_vars = [var for var in numeric_vars if var in filtered_merged_data.columns]
    
    if len(available_vars) >= 2:
        # Use the same correlation calculation method as multi-POP for consistency
        temp_correlations = {}
        
        # Calculate correlations individually for each metric with Temp_Ambiante
        if 'Temp_Ambiante' in filtered_merged_data.columns:
            for metric in available_vars:
                if metric != 'Temp_Ambiante':
                    # Prepare data for correlation (same logic as data_loader.py)
                    corr_data = filtered_merged_data[['Temp_Ambiante', metric]].dropna()
                    
                    if len(corr_data) >= 10:
                        # Convert status columns to numeric if necessary
                        if metric == 'Porte_Status' and corr_data[metric].dtype == 'object':
                            corr_data[metric] = corr_data[metric].map({
                                'Open': 1, 'Ouvert': 1, 'open': 1, '1': 1, 1: 1,
                                'Close': 0, 'Fermé': 0, 'closed': 0, '0': 0, 0: 0
                            })
                        
                        if 'CLIM' in metric and 'Status' in metric:
                            if corr_data[metric].dtype == 'object':
                                corr_data[metric] = corr_data[metric].map({
                                    'ON': 1, 'on': 1, 'On': 1, '1': 1, 1: 1,
                                    'OFF': 0, 'off': 0, 'Off': 0, '0': 0, 0: 0
                                })
                        
                        # Check if CLIM has constant values (always ON or always OFF)
                        if 'CLIM' in metric and 'Status' in metric:
                            unique_values = corr_data[metric].dropna().unique()
                            if len(unique_values) == 1:
                                # Constant value - show the actual state instead of correlation
                                if unique_values[0] == 1:
                                    temp_correlations[metric] = "Toujours ON"
                                elif unique_values[0] == 0:
                                    temp_correlations[metric] = "Toujours OFF"
                                else:
                                    temp_correlations[metric] = f"Always {unique_values[0]}"
                            else:
                                # Variable values - calculate correlation
                                try:
                                    spearman_corr = corr_data['Temp_Ambiante'].corr(corr_data[metric], method='spearman')
                                    temp_correlations[metric] = spearman_corr
                                except:
                                    temp_correlations[metric] = None
                        # Check if door has constant values (always open or always closed)
                        elif metric == 'Porte_Status':
                            unique_values = corr_data[metric].dropna().unique()
                            if len(unique_values) == 1:
                                # Constant value - show the actual state instead of correlation
                                if unique_values[0] == 1:
                                    temp_correlations[metric] = "Toujours Ouverte"
                                elif unique_values[0] == 0:
                                    temp_correlations[metric] = "Toujours Fermée"
                                else:
                                    temp_correlations[metric] = f"Always {unique_values[0]}"
                            else:
                                # Variable values - calculate correlation
                                try:
                                    spearman_corr = corr_data['Temp_Ambiante'].corr(corr_data[metric], method='spearman')
                                    temp_correlations[metric] = spearman_corr
                                except:
                                    temp_correlations[metric] = None
                        else:
                            # Non-CLIM metrics - calculate correlation normally
                            try:
                                spearman_corr = corr_data['Temp_Ambiante'].corr(corr_data[metric], method='spearman')
                                temp_correlations[metric] = spearman_corr
                            except:
                                temp_correlations[metric] = None
                    else:
                        # Insufficient data in the period - check for last known door state
                        if metric == 'Porte_Status' and metric in merged_data.columns:
                            # Look for door data before the selected period
                            door_state_found = False
                            
                            if 'Timestamp' in merged_data.columns:
                                # Get door data before the period start
                                before_period_data = merged_data[merged_data['Timestamp'] < start_date]
                                
                                if not before_period_data.empty and metric in before_period_data.columns:
                                    # Get door data before the period, sorted by timestamp (most recent first)
                                    door_before_period = before_period_data[['Timestamp', metric]].dropna()
                                    
                                    if not door_before_period.empty:
                                        # Sort by timestamp and get the most recent door state
                                        door_before_period = door_before_period.sort_values('Timestamp', ascending=False)
                                        last_known_state = door_before_period.iloc[0][metric]
                                        
                                        # Convert to numeric to determine state
                                        door_mapping = {
                                            'Open': 1, 'Ouvert': 1, 'open': 1, '1': 1, 1: 1,
                                            'Close': 0, 'Fermé': 0, 'closed': 0, '0': 0, 0: 0,
                                            'Closed': 0, 'OPEN': 1, 'CLOSE': 0, 'CLOSED': 0
                                        }
                                        
                                        if last_known_state in door_mapping:
                                            numeric_state = door_mapping[last_known_state]
                                            if numeric_state == 1:
                                                temp_correlations[metric] = "Toujours Ouverte"
                                            else:
                                                temp_correlations[metric] = "Toujours Fermée"
                                            door_state_found = True
                            
                            # Fallback: check full dataset if no before-period data
                            if not door_state_found:
                                full_door_data = merged_data[metric].dropna()
                                if len(full_door_data) > 0:
                                    # Convert to numeric
                                    door_numeric = full_door_data.map({
                                        'Open': 1, 'Ouvert': 1, 'open': 1, '1': 1, 1: 1,
                                        'Close': 0, 'Fermé': 0, 'closed': 0, '0': 0, 0: 0,
                                        'Closed': 0, 'OPEN': 1, 'CLOSE': 0, 'CLOSED': 0
                                    })
                                    door_numeric = pd.to_numeric(door_numeric, errors='coerce').dropna()
                                    
                                    if len(door_numeric) > 0:
                                        unique_values = door_numeric.unique()
                                        if len(unique_values) == 1:
                                            if unique_values[0] == 1:
                                                temp_correlations[metric] = "Toujours Ouverte"
                                            elif unique_values[0] == 0:
                                                temp_correlations[metric] = "Toujours Fermée"
                                            door_state_found = True
                            
                            # If no door state found, set to None
                            if not door_state_found:
                                temp_correlations[metric] = None
                        else:
                            # For non-door metrics with insufficient data
                            temp_correlations[metric] = None
        
        # Convert to pandas Series for compatibility with existing code
        temp_correlations = pd.Series(temp_correlations)
        
        # Check if we have any correlations to display (numeric or string states)
        if len(temp_correlations) > 0:
            # Check if we have any non-null values (numeric correlations or string states)
            has_data = any(
                isinstance(val, str) or (isinstance(val, (int, float)) and pd.notna(val)) 
                for val in temp_correlations.values
            )
            
            if has_data:
                
                # Function to interpret correlation strength and get priority
                def interpret_correlation(value):
                    abs_val = abs(value)
                    if abs_val >= 0.8:
                        return "très forte", "🔴"
                    elif abs_val >= 0.6:
                        return "forte", "🟠"
                    elif abs_val >= 0.4:
                        return "modérée", "🟡"
                    elif abs_val >= 0.2:
                        return "faible", "🟢"
                    else:
                        return "négligeable", "⚪"
                
                def get_priority_from_correlation(value):
                    abs_val = abs(value)
                    if abs_val >= 0.8:
                        return "Critique", "🔴"
                    elif abs_val >= 0.6:
                        return "Élevée", "🟠"
                    elif abs_val >= 0.4:
                        return "Modérée", "🟡"
                    elif abs_val >= 0.2:
                        return "Faible", "🟢"
                    else:
                        return "Minimale", "⚪"
                
                # Function to get relationship description
                def get_relationship_description(var, corr_value):
                    # Safety check for string values (should not happen with current filtering)
                    if isinstance(corr_value, str):
                        return f"**{var}**: {corr_value}"
                    
                    strength, emoji = interpret_correlation(corr_value)
                    
                    if pd.isna(corr_value) or corr_value is None:
                        return f"{emoji} **{var}**: Données insuffisantes pour établir une relation"
                    
                    if abs(corr_value) < 0.2:
                        return f"{emoji} **{var}**: Aucune relation significative détectée"
                    
                    direction = "augmente" if corr_value > 0 else "diminue"
                    opposite = "augmente" if corr_value > 0 else "diminue"
                    
                    # Custom descriptions for each variable
                    descriptions = {
                        'Temp_Exterieure': {
                            'positive': f"Quand la température extérieure augmente, la température ambiante tend à augmenter également (relation {strength})",
                            'negative': f"Quand la température extérieure augmente, la température ambiante tend à diminuer (relation {strength} - situation inhabituelle)"
                        },
                        'Puissance_IT': {
                            'positive': f"Quand la charge IT augmente, la température ambiante augmente (relation {strength})",
                            'negative': f"Quand la charge IT augmente, la température ambiante diminue (relation {strength} - situation inhabituelle)"
                        },
                        'Porte_Status': {
                            'positive': f"Les ouvertures de porte ont tendance à faire augmenter la température ambiante (relation {strength})",
                            'negative': f"Les ouvertures de porte ont tendance à faire baisser la température ambiante (relation {strength})"
                        }
                    }
                    
                    # For CLIM units
                    if 'CLIM' in var and 'Status' in var:
                        if corr_value < 0:
                            return f"L'activation de {var.replace('_Status', '')} aide à réduire la température (relation {strength})"
                        else:
                            return f"L'activation de {var.replace('_Status', '')} est associée à une hausse de température (relation {strength} - vérifier l'efficacité)"
                    
                    # Get appropriate description
                    if var in descriptions:
                        desc_key = 'positive' if corr_value > 0 else 'negative'
                        base_desc = descriptions[var][desc_key]
                    else:
                        base_desc = f"Relation {strength} {'positive' if corr_value > 0 else 'négative'} avec {var}"
                    
                    return f"{emoji} **{var}**: {base_desc}"
                
                # Main analysis section
                st.markdown("## 📊 Comprendre les Relations avec la Température Ambiante")
                st.markdown("""
                Cette analyse identifie les facteurs qui influencent la température ambiante dans votre centre de données.
                Les relations sont classées par ordre d'importance pour faciliter la prise de décision.
                """)
                
                # Sort correlations by absolute value (only numeric correlations)
                numeric_correlations = temp_correlations[temp_correlations.apply(lambda x: isinstance(x, (int, float)) and not pd.isna(x))]
                if not numeric_correlations.empty:
                    sorted_correlations = numeric_correlations.abs().sort_values(ascending=False)
                else:
                    sorted_correlations = pd.Series(dtype=float)  # Empty series if no numeric correlations
                
                # Key drivers section
                st.markdown("### 🎯 Facteurs Principaux Affectant la Température")
                
                # Identify top drivers (only from numeric correlations)
                top_drivers = []
                for var in sorted_correlations.index:
                    corr_val = temp_correlations[var]
                    if isinstance(corr_val, (int, float)) and not pd.isna(corr_val) and abs(corr_val) >= 0.3:  # Only significant numeric correlations
                        top_drivers.append((var, corr_val))
                
                if top_drivers:
                    st.markdown("**Facteurs ayant un impact significatif (classés par importance):**")
                
                for i, (var, corr_val) in enumerate(top_drivers, 1):
                    strength, emoji = interpret_correlation(corr_val)
                    
                    # Create readable variable names
                    var_display = {
                        'Temp_Exterieure': 'Température Extérieure',
                        'Puissance_IT': 'Charge IT',
                        'Porte_Status': 'État de la Porte',
                        'CLIM_A_Status': 'Climatisation A',
                        'CLIM_B_Status': 'Climatisation B',
                        'CLIM_C_Status': 'Climatisation C',
                        'CLIM_D_Status': 'Climatisation D'
                    }.get(var, var)
                    
                    impact_desc = get_relationship_description(var, corr_val)
                    st.markdown(f"{i}. {impact_desc}")
                else:
                    st.info("Aucun facteur n'a d'impact significatif sur la température pendant cette période.")
                
                # Detailed insights section
                st.markdown("### 💡 Insights Détaillés et Recommandations")
                
                # Create three columns for different categories
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("#### 🌡️ Facteurs Environnementaux")
                    if 'Temp_Exterieure' in temp_correlations:
                        ext_corr = temp_correlations['Temp_Exterieure']
                        if ext_corr is not None and isinstance(ext_corr, (int, float)) and abs(ext_corr) > 0.5:
                            st.error(f"Impact élevé de la température extérieure (corrélation: {ext_corr:.1%})")
                            st.markdown("**Recommandations:**")
                            st.markdown("- Améliorer l'isolation thermique")
                            st.markdown("- Vérifier l'étanchéité du bâtiment")
                            st.markdown("- Installer des pare-soleil si nécessaire")
                        elif ext_corr is not None and isinstance(ext_corr, (int, float)) and abs(ext_corr) > 0.3:
                            st.warning(f"Impact modéré de la température extérieure (corrélation: {ext_corr:.1%})")
                            st.markdown("**Recommandations:**")
                            st.markdown("- Surveiller lors des pics de chaleur")
                            st.markdown("- Planifier la maintenance préventive")
                        elif ext_corr is not None and isinstance(ext_corr, (int, float)):
                            st.success(f"Bonne isolation thermique (corrélation: {ext_corr:.1%})")
                            st.markdown("- L'isolation fonctionne bien")
                            st.markdown("- Maintenir les bonnes pratiques")
                        else:
                            st.info("Données de température extérieure insuffisantes pour l'analyse")
                
                with col2:
                    st.markdown("#### ❄️ Système de Refroidissement")
                    clim_effectiveness = []
                    for col in clim_status_columns:
                        if col in temp_correlations:
                            clim_effectiveness.append((col, temp_correlations[col]))
                    
                    if clim_effectiveness:
                        # Separate numeric correlations from string states
                        effective_units = [unit for unit, corr in clim_effectiveness if isinstance(corr, (int, float)) and corr < -0.2]
                        ineffective_units = [unit for unit, corr in clim_effectiveness if isinstance(corr, (int, float)) and corr >= 0]
                        always_on_units = [unit for unit, corr in clim_effectiveness if corr == "Toujours ON"]
                        always_off_units = [unit for unit, corr in clim_effectiveness if corr == "Toujours OFF"]
                        
                        if effective_units:
                            st.success(f"{len(effective_units)} unité(s) CLIM fonctionnent correctement")
                            for unit in effective_units:
                                unit_name = unit.replace('_Status', '')
                                st.markdown(f"- ✅ {unit_name} réduit efficacement la température")
                        
                        if ineffective_units:
                            st.error(f"{len(ineffective_units)} unité(s) CLIM nécessitent attention")
                            for unit in ineffective_units:
                                unit_name = unit.replace('_Status', '')
                                st.markdown(f"- ⚠️ {unit_name} pourrait nécessiter maintenance")
                        
                        if always_on_units:
                            st.info(f"{len(always_on_units)} unité(s) CLIM en fonctionnement continu")
                            for unit in always_on_units:
                                unit_name = unit.replace('_Status', '')
                                st.markdown(f"- 🔄 {unit_name} fonctionne en continu")
                        
                        if always_off_units:
                            st.warning(f"{len(always_off_units)} unité(s) CLIM arrêtée(s)")
                            for unit in always_off_units:
                                unit_name = unit.replace('_Status', '')
                                st.markdown(f"- ⏹️ {unit_name} est hors service")
                            st.markdown("**Action requise:** Vérifier l'efficacité de ces unités")
                    else:
                        st.info("Données CLIM non disponibles")
                
                with col3:
                    st.markdown("#### 💻 Charge IT et Accès")
                    if 'Puissance_IT' in temp_correlations:
                        it_corr = temp_correlations['Puissance_IT']
                        if it_corr is not None and isinstance(it_corr, (int, float)) and abs(it_corr) > 0.5:
                            st.warning(f"Forte influence de la charge IT (corrélation: {it_corr:.1%})")
                            st.markdown("**Recommandations:**")
                            st.markdown("- Optimiser la distribution de charge")
                            st.markdown("- Considérer l'ajout de capacité de refroidissement")
                        elif it_corr is not None and isinstance(it_corr, (int, float)):
                            st.success(f"Impact IT gérable (corrélation: {it_corr:.1%})")
                        else:
                            st.info("Données de puissance IT insuffisantes pour l'analyse")
                    
                    if 'Porte_Status' in temp_correlations:
                        door_corr = temp_correlations['Porte_Status']
                        if (isinstance(door_corr, (int, float)) and 
                            not pd.isna(door_corr) and 
                            abs(door_corr) > 0.3):
                            st.warning(f"Impact des ouvertures de porte (corrélation: {door_corr:.1%})")
                            st.markdown("**Recommandations:**")
                            st.markdown("- Former le personnel aux bonnes pratiques")
                            st.markdown("- Installer des alertes pour portes ouvertes")
                        elif isinstance(door_corr, str):
                            st.info(f"État de porte: {door_corr}")
                        else:
                            st.success("Impact minimal des portes")
                
                # Summary and action plan
                st.markdown("### 📋 Plan d'Action Prioritaire")
                
                # Generate priority actions based on correlations
                priority_actions = []
                
                # Check external temperature
                if ('Temp_Exterieure' in temp_correlations and 
                    isinstance(temp_correlations['Temp_Exterieure'], (int, float)) and 
                    not pd.isna(temp_correlations['Temp_Exterieure']) and 
                    abs(temp_correlations['Temp_Exterieure']) > 0.2):
                    ext_corr = temp_correlations['Temp_Exterieure']
                    priority, emoji = get_priority_from_correlation(ext_corr)
                    priority_actions.append((priority, emoji, "Améliorer l'isolation thermique du bâtiment", 
                                            f"Impact température extérieure (corrélation: {ext_corr:.1%})"))
                
                # Check CLIM effectiveness
                ineffective_clims_details = []
                for col in clim_status_columns:
                    if col in temp_correlations:
                        corr_value = temp_correlations[col]
                        # Only check numeric correlations that are >= 0 (ineffective)
                        if isinstance(corr_value, (int, float)) and corr_value >= 0:
                            clim_name = col.replace('_Status', '').replace('_', ' ')
                            ineffective_clims_details.append((clim_name, corr_value))
                
                if ineffective_clims_details:
                    ineffective_count = len(ineffective_clims_details)
                    
                    # Generate specific reason based on correlation findings
                    if ineffective_count == 1:
                        clim_name, corr_val = ineffective_clims_details[0]
                        if corr_val > 0.3:
                            reason = f"L'unité {clim_name} augmente la température au lieu de la refroidir (corrélation: +{corr_val:.1%})"
                        else:
                            reason = f"L'unité {clim_name} n'a aucun effet de refroidissement (corrélation: +{corr_val:.1%})"
                    else:
                        avg_corr = sum(corr for _, corr in ineffective_clims_details) / ineffective_count
                        worst_clim = max(ineffective_clims_details, key=lambda x: x[1])
                        if avg_corr > 0.3:
                            reason = f"Plusieurs unités augmentent la température (pire: {worst_clim[0]} +{worst_clim[1]:.2f})"
                        else:
                            reason = f"Plusieurs unités n'ont aucun effet de refroidissement (corrélation moyenne: +{avg_corr:.1%})"
                    
                    # Determine priority based on worst correlation
                    worst_corr = max(corr for _, corr in ineffective_clims_details)
                    priority, emoji = get_priority_from_correlation(worst_corr)
                    priority_actions.append((priority, emoji, f"Maintenance urgente de {ineffective_count} unité(s) CLIM",
                                            reason))
                
                # Check IT load
                if ('Puissance_IT' in temp_correlations and 
                    isinstance(temp_correlations['Puissance_IT'], (int, float)) and 
                    not pd.isna(temp_correlations['Puissance_IT']) and 
                    temp_correlations['Puissance_IT'] > 0.2):
                    it_corr = temp_correlations['Puissance_IT']
                    priority, emoji = get_priority_from_correlation(it_corr)
                    priority_actions.append((priority, emoji, "Optimiser la répartition de la charge IT",
                                            f"Impact charge IT (corrélation: +{it_corr:.1%})"))
                
                # Check door impact
                if ('Porte_Status' in temp_correlations and 
                    isinstance(temp_correlations['Porte_Status'], (int, float)) and 
                    not pd.isna(temp_correlations['Porte_Status']) and 
                    abs(temp_correlations['Porte_Status']) > 0.2):
                    door_corr = temp_correlations['Porte_Status']
                    priority, emoji = get_priority_from_correlation(door_corr)
                    priority_actions.append((priority, emoji, "Réviser les procédures d'accès",
                                            f"Impact ouvertures porte (corrélation: {door_corr:.1%})"))
                
                if priority_actions:
                    st.markdown("**Actions recommandées par ordre de priorité:**")
                    
                    # Sort by priority
                    priority_order = {"Critique": 1, "Élevée": 2, "Modérée": 3, "Faible": 4, "Minimale": 5}
                    priority_actions.sort(key=lambda x: priority_order.get(x[0], 5))
                    
                    for priority, emoji, action, reason in priority_actions:
                        st.markdown(f"{emoji} **Priorité {priority}:** {action}")
                        st.markdown(f"   *Raison: {reason}*")
                else:
                    st.success("✅ Aucune action urgente requise. Le système fonctionne dans des paramètres acceptables.")
                
                # Technical details expander for those who want more info
                with st.expander("📊 Détails Techniques (pour les experts)", expanded=False):
                    st.markdown("#### Valeurs de Corrélation")
                    
                    # Create a clean dataframe for display with consistent string formatting
                    correlation_display = []
                    impact_display = []
                    
                    for val in temp_correlations.values:
                        if isinstance(val, str):
                            # For "Toujours ON/OFF" strings
                            correlation_display.append(val)
                            impact_display.append('Neutre')
                        elif isinstance(val, (int, float)) and pd.notna(val):
                            # For numeric correlations
                            correlation_display.append(f"{val:.1%}")
                            impact_display.append('Positif' if val > 0 else 'Négatif')
                        else:
                            # For missing data
                            correlation_display.append("N/A")
                            impact_display.append('Neutre')
                    
                    tech_df = pd.DataFrame({
                        'Variable': temp_correlations.index,
                        'Corrélation': correlation_display,
                        'Impact': impact_display
                    })
                    
                    # Create a sort key for proper ordering
                    def create_sort_key(row):
                        val = temp_correlations[row.name]  # Get original value for sorting
                        if isinstance(val, str):
                            return (1, 0)  # Put string values at the end with secondary sort of 0
                        elif pd.isna(val):
                            return (2, 0)  # Put NaN at the very end
                        else:
                            return (0, -abs(val))  # Put numeric values first, sorted by absolute value (descending)
                    
                    tech_df['_sort_key'] = tech_df.apply(create_sort_key, axis=1)
                    tech_df = tech_df.sort_values('_sort_key').drop('_sort_key', axis=1).reset_index(drop=True)
                    
                    # Since all correlation values are now pre-formatted as strings, we can apply styling directly
                    # Custom background gradient function that handles both percentages and constant states
                    def background_gradient_for_correlations(s):
                        styles = []
                        for i, val in enumerate(s):
                            if val in ['Toujours Ouverte', 'Toujours OFF']:
                                # Light red for problematic states
                                styles.append('background-color: #ffebee; color: #d32f2f; font-weight: bold')
                            elif val in ['Toujours Fermée', 'Toujours ON']:
                                # Blue for good states
                                styles.append('background-color: #e8f4fd; color: #1976d2; font-weight: bold')
                            elif val.endswith('%'):
                                # Extract numeric value from percentage string
                                try:
                                    numeric_val = float(val.replace('%', '')) / 100
                                    # Create color map
                                    import matplotlib.pyplot as plt
                                    cmap = plt.cm.RdBu_r
                                    norm = plt.Normalize(vmin=-1, vmax=1)
                                    color = cmap(norm(numeric_val))
                                    rgb = f'rgb({int(color[0]*255)}, {int(color[1]*255)}, {int(color[2]*255)})'
                                    styles.append(f'background-color: {rgb}')
                                except:
                                    styles.append('')
                            else:
                                styles.append('')  # No style for other values
                        return styles
                    
                    # Apply styling
                    styled_df = tech_df.style.apply(background_gradient_for_correlations, subset=['Corrélation'])
                    
                    st.dataframe(styled_df, width='stretch')
                    
                    st.markdown("""
                    **Guide d'interprétation:**
                    - **Corrélation positive:** Les deux variables évoluent dans le même sens
                    - **Corrélation négative:** Les variables évoluent en sens opposé
                    - **Valeur absolue:** Indique la force de la relation (0 = aucune, 1 = parfaite)
                    - **Méthode utilisée:** Corrélation de Spearman (robuste aux valeurs extrêmes)
                    """)
        
        else:
            # No valid correlations calculated
            st.error("⚠️ **Analyse de corrélation impossible**")
            st.markdown("""
            **Causes possibles:**
            - Données insuffisantes (moins de 10 points après filtrage)
            - Trop de valeurs manquantes dans les variables sélectionnées
                
                **Solutions:**
                - Sélectionnez une période plus large dans la barre latérale
                - Choisissez un POP avec plus de données (ex: Marrakech > BGU-ONE)
                - Vérifiez la disponibilité des capteurs pour cette période
            """)
            
            # Afficher des statistiques de débogage
            with st.expander("🔍 Diagnostics des données", expanded=False):
                if len(available_vars) >= 2:
                    debug_data = filtered_merged_data[available_vars].copy()
                    st.write(f"**Variables disponibles:** {len(available_vars)}")
                    st.write(f"**Période sélectionnée:** {len(debug_data)} points de données")
                    
                    # Montrer la qualité des données par variable
                    for var in available_vars:
                        non_null_count = debug_data[var].notna().sum()
                        percentage = (non_null_count / len(debug_data) * 100) if len(debug_data) > 0 else 0
                        st.write(f"- **{var}:** {non_null_count} valeurs ({percentage:.1f}%)")
                        
                    # Calculer combien de lignes restent après nettoyage pour chaque métrique
                    st.write("**Points de données disponibles par métrique:**")
                    for var in available_vars:
                        if var != 'Temp_Ambiante':
                            pair_data = filtered_merged_data[['Temp_Ambiante', var]].dropna()
                            st.write(f"- **Temp_Ambiante vs {var}:** {len(pair_data)} points")
                            if len(pair_data) <= 10:
                                st.error(f"❌ Pas assez de données pour {var} (minimum: 10)")
                            else:
                                st.success(f"✅ Suffisant pour {var}")
    
    else:
        st.warning("⚠️ **La variable 'Temp_Ambiante' n'est pas disponible**")
        st.info("Cette analyse nécessite la température ambiante comme référence. Vérifiez que le capteur de température fonctionne correctement.")

