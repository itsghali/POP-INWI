import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_tab(filtered_merged_data, start_date, end_date):
    """Render the energy cost simulation and analysis tab."""
    st.header("💰 Simulation et Analyse des Coûts Énergétiques")
    st.info(f"📅 Période sélectionnée: {start_date.strftime('%Y-%m-%d %H:%M')} - {end_date.strftime('%Y-%m-%d %H:%M')}")
    
    # Explication
    st.info("""
    💡 **Cette section vous permet de:**
    - Calculer vos coûts énergétiques actuels
    - Simuler des économies potentielles
    - Comparer différents scénarios d'optimisation
    - Analyser l'impact financier du PUE
    """)
    
    if all(col in filtered_merged_data.columns for col in ['Puissance_IT', 'Puissance_CLIM', 'Puissance_Generale']):
        # Configuration des tarifs électriques par période
        st.subheader("⚡ Configuration des Tarifs Électriques")
        
        # Default to MAD (Moroccan Dirham)
        currency = "MAD (DH)"
        currency_symbol = "DH"
        
        # Choice between single or variable pricing
        pricing_mode = st.radio(
            "Mode de tarification:",
            ["Tarif unique", "Tarifs variables par période de la journée"],
            help="Choisissez entre un tarif unique ou des tarifs variables selon les heures"
        )
        
        if pricing_mode == "Tarif unique":
            # Single rate input
            electricity_rate = st.number_input(
                "💵 Tarif électrique (DH/kWh)",
                min_value=0.01,
                max_value=10.0,
                value=1.2,
                step=0.01,
                help="Entrez votre tarif électrique actuel en dirhams marocains"
            )
            # Create hourly rates array (same rate for all hours)
            hourly_rates = [electricity_rate] * 24
        else:
            # Variable pricing by time periods
            st.info("💡 Configurez les tarifs électriques et les plages horaires pour différentes périodes de la journée (24h format)")
            
            # Time range configuration section
            st.subheader("⏰ Configuration des Plages Horaires")
            st.write("Définissez les heures de début et de fin pour chaque période tarifaire:")
            
            time_col1, time_col2, time_col3 = st.columns(3)
            
            with time_col1:
                st.markdown("##### 🌙 Heures Creuses")
                off_peak_start = st.number_input(
                    "Heure de début (0-23)",
                    min_value=0,
                    max_value=23,
                    value=22,
                    step=1,
                    key="off_peak_start",
                    help="Heure de début des heures creuses (format 24h)"
                )
                off_peak_end = st.number_input(
                    "Heure de fin (0-23)", 
                    min_value=0,
                    max_value=23,
                    value=6,
                    step=1,
                    key="off_peak_end",
                    help="Heure de fin des heures creuses (format 24h)"
                )
                
            with time_col2:
                st.markdown("##### 🌅 Heures Normales")
                normal_start = st.number_input(
                    "Heure de début (0-23)",
                    min_value=0,
                    max_value=23,
                    value=6,
                    step=1,
                    key="normal_start",
                    help="Heure de début des heures normales (format 24h)"
                )
                normal_end = st.number_input(
                    "Heure de fin (0-23)",
                    min_value=0,
                    max_value=23,
                    value=18,
                    step=1,
                    key="normal_end",
                    help="Heure de fin des heures normales (format 24h)"
                )
                
            with time_col3:
                st.markdown("##### 🔥 Heures de Pointe")
                peak_start = st.number_input(
                    "Heure de début (0-23)",
                    min_value=0,
                    max_value=23,
                    value=18,
                    step=1,
                    key="peak_start",
                    help="Heure de début des heures de pointe (format 24h)"
                )
                peak_end = st.number_input(
                    "Heure de fin (0-23)",
                    min_value=0,
                    max_value=23,
                    value=22,
                    step=1,
                    key="peak_end",
                    help="Heure de fin des heures de pointe (format 24h)"
                )
            
            # Function to check if hour is in range (handles overnight ranges)
            def is_in_time_range(hour, start_hour, end_hour):
                if start_hour <= end_hour:
                    return start_hour <= hour < end_hour
                else:  # Overnight range (e.g., 22h-6h)
                    return hour >= start_hour or hour < end_hour
            
            # Validate time ranges
            def validate_time_ranges():
                # Create array to track which hours are covered
                covered_hours = [False] * 24
                conflicts = []
                
                # Check off-peak coverage
                for hour in range(24):
                    if is_in_time_range(hour, off_peak_start, off_peak_end):
                        if covered_hours[hour]:
                            conflicts.append(hour)
                        covered_hours[hour] = True
                
                # Check normal coverage  
                for hour in range(24):
                    if is_in_time_range(hour, normal_start, normal_end):
                        if covered_hours[hour]:
                            conflicts.append(hour)
                        covered_hours[hour] = True
                
                # Check peak coverage
                for hour in range(24):
                    if is_in_time_range(hour, peak_start, peak_end):
                        if covered_hours[hour]:
                            conflicts.append(hour)
                        covered_hours[hour] = True
                
                uncovered_hours = [h for h, covered in enumerate(covered_hours) if not covered]
                
                return conflicts, uncovered_hours
            
            conflicts, uncovered = validate_time_ranges()
            
            if conflicts:
                st.error(f"⚠️ Conflit détecté: Les heures {conflicts} sont couvertes par plusieurs périodes!")
            if uncovered:
                st.error(f"⚠️ Heures non couvertes: {uncovered}. Toutes les heures (0-23) doivent être assignées à une période.")
            
            if not conflicts and not uncovered:
                st.success("✅ Configuration des plages horaires valide!")
            
            # Define time periods with user-configured ranges
            col1, col2, col3 = st.columns(3)
            
            with col1:
                hours_count = sum(1 for h in range(24) if is_in_time_range(h, off_peak_start, off_peak_end))
                st.markdown(f"#### 🌙 Heures creuses ({off_peak_start}h-{off_peak_end}h)")
                off_peak_rate = st.number_input(
                    "Tarif heures creuses (DH/kWh)",
                    min_value=0.01,
                    max_value=10.0,
                    value=0.8,
                    step=0.01,
                    key="off_peak",
                    help="Généralement le tarif le plus bas"
                )
                st.caption(f"{off_peak_start:02d}h00 - {off_peak_end:02d}h00 ({hours_count} heures)")
            
            with col2:
                hours_count = sum(1 for h in range(24) if is_in_time_range(h, normal_start, normal_end))
                st.markdown(f"#### 🌅 Heures normales ({normal_start}h-{normal_end}h)")
                normal_rate = st.number_input(
                    "Tarif heures normales (DH/kWh)",
                    min_value=0.01,
                    max_value=10.0,
                    value=1.2,
                    step=0.01,
                    key="normal",
                    help="Tarif de base pendant la journée"
                )
                st.caption(f"{normal_start:02d}h00 - {normal_end:02d}h00 ({hours_count} heures)")
            
            with col3:
                hours_count = sum(1 for h in range(24) if is_in_time_range(h, peak_start, peak_end))
                st.markdown(f"#### 🔥 Heures de pointe ({peak_start}h-{peak_end}h)")
                peak_rate = st.number_input(
                    "Tarif heures de pointe (DH/kWh)",
                    min_value=0.01,
                    max_value=10.0,
                    value=1.8,
                    step=0.01,
                    key="peak",
                    help="Généralement le tarif le plus élevé"
                )
                st.caption(f"{peak_start:02d}h00 - {peak_end:02d}h00 ({hours_count} heures)")
            
            # Create hourly rates array based on user-defined ranges
            hourly_rates = []
            for hour in range(24):
                if is_in_time_range(hour, off_peak_start, off_peak_end):
                    hourly_rates.append(off_peak_rate)
                elif is_in_time_range(hour, normal_start, normal_end):
                    hourly_rates.append(normal_rate)
                elif is_in_time_range(hour, peak_start, peak_end):
                    hourly_rates.append(peak_rate)
                else:
                    # Fallback to normal rate if hour is not covered (shouldn't happen with validation)
                    hourly_rates.append(normal_rate)
            
            # Show rate schedule visualization
            st.markdown("#### 📊 Visualisation des tarifs par heure")
            
            rate_df = pd.DataFrame({
                'Heure': list(range(24)),
                'Tarif (DH/kWh)': hourly_rates,
                'Période': [
                    'Heures creuses' if is_in_time_range(h, off_peak_start, off_peak_end) else 
                    'Heures normales' if is_in_time_range(h, normal_start, normal_end) else 
                    'Heures de pointe' 
                    for h in range(24)
                ]
            })
            
            fig_rates = px.bar(
                rate_df, 
                x='Heure', 
                y='Tarif (DH/kWh)', 
                color='Période',
                title="Tarifs électriques par heure de la journée",
                color_discrete_map={
                    'Heures creuses': '#2E8B57',
                    'Heures normales': '#4682B4', 
                    'Heures de pointe': '#DC143C'
                }
            )
            fig_rates.update_layout(height=300)
            st.plotly_chart(fig_rates, width='stretch', key="energy_rates_chart")
        
        # Calculs de base
        st.subheader("📊 Analyse des Coûts Actuels")
        
        # Calcul des consommations
        time_range = (filtered_merged_data['Timestamp'].max() - filtered_merged_data['Timestamp'].min()).total_seconds() / 3600
        
        # Consommations moyennes
        avg_it_power = filtered_merged_data['Puissance_IT'].mean()
        avg_clim_power = filtered_merged_data['Puissance_CLIM'].mean()
        avg_total_power = filtered_merged_data['Puissance_Generale'].mean()
        avg_pue = avg_total_power / avg_it_power if avg_it_power > 0 else 0
        
        # Calculate variable costs based on actual data hourly consumption
        if pricing_mode == "Tarifs variables par période de la journée":
            # Add hour column to data
            data_with_hour = filtered_merged_data.copy()
            data_with_hour['Hour'] = data_with_hour['Timestamp'].dt.hour
            
            # Calculate hourly consumption and costs
            hourly_consumption = data_with_hour.groupby('Hour').agg({
                'Puissance_IT': 'mean',
                'Puissance_CLIM': 'mean', 
                'Puissance_Generale': 'mean'
            }).fillna(0)
            
            # Calculate costs for each hour using variable rates
            total_hourly_cost = 0
            hourly_costs_detail = []
            
            for hour in range(24):
                if hour in hourly_consumption.index:
                    consumption = hourly_consumption.loc[hour, 'Puissance_Generale']
                else:
                    consumption = avg_total_power  # Use average if no data for that hour
                
                hour_cost = consumption * hourly_rates[hour]
                total_hourly_cost += hour_cost
                hourly_costs_detail.append({
                    'hour': hour,
                    'consumption': consumption,
                    'rate': hourly_rates[hour],
                    'cost': hour_cost
                })
            
            # Average hourly cost (total daily cost / 24)
            hourly_cost = total_hourly_cost / 24
            daily_cost = total_hourly_cost
            
        else:
            # Single rate calculation (existing logic)
            hourly_cost = avg_total_power * hourly_rates[0]  # Use first rate (all same)
            daily_cost = hourly_cost * 24
        
        monthly_cost = daily_cost * 30
        annual_cost = daily_cost * 365
        
        # Affichage des métriques de coût
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "💸 Coût Horaire",
                f"{currency_symbol}{hourly_cost:.2f}",
                help="Coût moyen par heure de fonctionnement"
            )
        with col2:
            st.metric(
                "📅 Coût Journalier",
                f"{currency_symbol}{daily_cost:.2f}",
                delta=f"{currency_symbol}{daily_cost - (avg_it_power * 24 * (sum(hourly_rates)/24)):.2f} non-IT"
            )
        with col3:
            st.metric(
                "📆 Coût Mensuel",
                f"{currency_symbol}{monthly_cost:,.2f}",
                help="Estimation sur 30 jours"
            )
        with col4:
            st.metric(
                "🗓️ Coût Annuel",
                f"{currency_symbol}{annual_cost:,.2f}",
                help="Projection sur 365 jours"
            )
        
        # Répartition des coûts
        st.subheader("📊 Répartition des Coûts par Composant")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Camembert de répartition
            avg_rate = sum(hourly_rates) / 24  # Average rate across all hours
            it_cost = avg_it_power * avg_rate
            clim_cost = avg_clim_power * avg_rate
            other_cost = (avg_total_power - avg_it_power - avg_clim_power) * avg_rate
            
            fig_pie = go.Figure(data=[go.Pie(
                labels=['IT', 'Climatisation', 'Autres (éclairage, etc.)'],
                values=[it_cost, clim_cost, other_cost],
                hole=.3,
                marker_colors=['#1f77b4', '#ff7f0e', '#2ca02c']
            )])
            
            fig_pie.update_layout(
                title=f"Répartition des coûts horaires ({currency_symbol}/h)",
                height=400
            )
            st.plotly_chart(fig_pie, width='stretch', key="cost_breakdown_pie")
        
        with col2:
            # Tableau de détail
            cost_breakdown = pd.DataFrame({
                'Composant': ['Équipements IT', 'Climatisation', 'Infrastructure', 'Total'],
                'Puissance (kW)': [avg_it_power, avg_clim_power, 
                                 avg_total_power - avg_it_power - avg_clim_power, avg_total_power],
                f'Coût/heure ({currency_symbol})': [it_cost, clim_cost, other_cost, hourly_cost],
                f'Coût/mois ({currency_symbol})': [it_cost * 720, clim_cost * 720, other_cost * 720, monthly_cost],
                '% du Total': [it_cost/hourly_cost * 100, clim_cost/hourly_cost * 100, 
                             other_cost/hourly_cost * 100, 100]
            })
            
            st.dataframe(
                cost_breakdown.style.format({
                    'Puissance (kW)': '{:.2f}',
                    f'Coût/heure ({currency_symbol})': '{:.2f}',
                    f'Coût/mois ({currency_symbol})': '{:,.2f}',
                    '% du Total': '{:.1f}%'
                }),
                width='stretch'
            )
        
        # Show detailed hourly analysis for variable pricing
        if pricing_mode == "Tarifs variables par période de la journée":
            st.subheader("📊 Analyse Détaillée des Coûts par Heure")
            
            # Create detailed hourly cost dataframe
            hourly_detail_df = pd.DataFrame(hourly_costs_detail)
            hourly_detail_df['Période'] = hourly_detail_df['hour'].apply(
                lambda h: 'Heures creuses' if is_in_time_range(h, off_peak_start, off_peak_end) else 
                         'Heures normales' if is_in_time_range(h, normal_start, normal_end) else 
                         'Heures de pointe'
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Hourly cost chart
                fig_hourly = px.bar(
                    hourly_detail_df,
                    x='hour',
                    y='cost',
                    color='Période',
                    title="Coûts par heure de la journée",
                    labels={'hour': 'Heure', 'cost': f'Coût ({currency_symbol})', 'Période': 'Période'},
                    color_discrete_map={
                        'Heures creuses': '#2E8B57',
                        'Heures normales': '#4682B4', 
                        'Heures de pointe': '#DC143C'
                    }
                )
                fig_hourly.update_layout(height=400)
                st.plotly_chart(fig_hourly, width='stretch', key="hourly_cost_profile")
            
            with col2:
                # Cost by period summary
                period_summary = hourly_detail_df.groupby('Période').agg({
                    'cost': ['sum', 'mean'],
                    'hour': 'count'
                }).round(2)
                period_summary.columns = ['Coût Total (DH)', 'Coût Moyen/h (DH)', 'Nb Heures']
                period_summary['% du Total'] = (period_summary['Coût Total (DH)'] / daily_cost * 100).round(1)
                
                st.markdown("**Résumé par période:**")
                st.dataframe(
                    period_summary.style.format({
                        'Coût Total (DH)': '{:.2f}',
                        'Coût Moyen/h (DH)': '{:.2f}',
                        '% du Total': '{:.1f}%'
                    }),
                    width='stretch'
                )
                
                # Show potential savings tip
                peak_cost = period_summary.loc['Heures de pointe', 'Coût Total (DH)'] if 'Heures de pointe' in period_summary.index else 0
                off_peak_cost = period_summary.loc['Heures creuses', 'Coût Total (DH)'] if 'Heures creuses' in period_summary.index else 0
                
                if peak_cost > 0:
                    st.info(f"💡 **Optimisation suggérée:** Les heures de pointe représentent {(peak_cost/daily_cost*100):.1f}% du coût quotidien. Considérez décaler certaines charges non-critiques vers les heures creuses.")
        
        # Simulation d'optimisation
        st.subheader("🚀 Simulation d'Optimisation")
        
        # Add simulate button
        st.info("💡 Ajustez les paramètres ci-dessous et cliquez sur 'Simuler' pour voir les économies potentielles.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Ensure max_value is at least greater than min_value
            max_pue = max(avg_pue, 2.5)
            default_pue = 1.5 if avg_pue > 1.5 else max(1.2, avg_pue * 0.9)
            
            target_pue = st.slider(
                "PUE cible pour simulation",
                min_value=1.1,
                max_value=max_pue,
                value=default_pue,
                step=0.01,
                format="%.2f",
                help="Simulez l'impact d'une amélioration du PUE"
            )
        
        with col2:
            temp_increase = st.slider(
                "Augmentation température (°C)",
                min_value=0,
                max_value=5,
                value=2,
                step=1,
                help="Impact d'une augmentation de la température de consigne"
            )
        
        # Add simulate button
        simulate_button = st.button("🔄 Simuler les Économies", type="primary", width='stretch')
        
        if simulate_button:
            # Calcul des économies potentielles
            new_total_power = avg_it_power * target_pue
            power_savings = avg_total_power - new_total_power
            
            # Estimation de l'impact de la température (règle empirique : 4% d'économie par °C)
            temp_savings_percent =1- temp_increase * 0.04
            clim_savings = avg_clim_power * temp_savings_percent
            total_savings = power_savings + clim_savings
            
            # Affichage des économies
            st.subheader("💰 Économies Potentielles")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                avg_rate = sum(hourly_rates) / 24  # Use average rate for savings calculation
                hourly_savings = total_savings * avg_rate
                st.metric(
                    "Économies/heure",
                    f"{currency_symbol}{hourly_savings:.2f}",
                    delta=f"-{(total_savings/avg_total_power)*100:.1f}%"
                )
            
            with col2:
                monthly_savings = hourly_savings * 720
                st.metric(
                    "Économies/mois",
                    f"{currency_symbol}{monthly_savings:,.2f}",
                    help="Sur base de 720 heures"
                )
            
            with col3:
                annual_savings = hourly_savings * 8760
                st.metric(
                    "Économies/an",
                    f"{currency_symbol}{annual_savings:,.2f}",
                    help="Sur base de 8760 heures"
                )
        
            # Graphique de comparaison
            fig_comparison = go.Figure()
            
            categories = ['Actuel', f'PUE {target_pue}', f'+{temp_increase}°C', 'Optimisé']
            it_costs = [avg_it_power * avg_rate] * 4
            clim_costs = [avg_clim_power * avg_rate,
                         avg_clim_power * avg_rate,
                         avg_clim_power * (1 - temp_savings_percent) * avg_rate,
                         (new_total_power - avg_it_power - clim_savings) * avg_rate]
            other_costs = [(avg_total_power - avg_it_power - avg_clim_power) * avg_rate,
                          (new_total_power - avg_it_power - avg_clim_power) * avg_rate,
                          (avg_total_power - avg_it_power - avg_clim_power) * avg_rate,
                          0]
        
            fig_comparison.add_trace(go.Bar(name='IT', x=categories, y=it_costs, marker_color='#1f77b4'))
            fig_comparison.add_trace(go.Bar(name='Climatisation', x=categories, y=clim_costs, marker_color='#ff7f0e'))
            fig_comparison.add_trace(go.Bar(name='Autres', x=categories, y=other_costs, marker_color='#2ca02c'))
            
            fig_comparison.update_layout(
                title=f"Comparaison des scénarios de coûts ({currency_symbol}/heure)",
                barmode='stack',
                yaxis_title=f"Coût ({currency_symbol}/h)",
                height=400
            )
            
            st.plotly_chart(fig_comparison, width='stretch', key="cost_scenario_comparison")
            
            # ROI et temps de retour
            st.subheader("📈 Retour sur Investissement")
            
            investment = st.number_input(
                f"💼 Investissement estimé pour optimisation ({currency_symbol})",
                min_value=0,
                value=50000,
                step=1000,
                help="Coût estimé des améliorations (isolation, free cooling, etc.)"
            )
            
            if annual_savings > 0 and investment > 0:
                roi_years = investment / annual_savings
                roi_months = roi_years * 12
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "⏱️ Temps de retour",
                        f"{roi_years:.1f} ans",
                        help="Durée pour récupérer l'investissement"
                    )
                
                with col2:
                    roi_percent = (annual_savings / investment) * 100
                    st.metric(
                        "📊 ROI annuel",
                        f"{roi_percent:.1f}%",
                        help="Retour sur investissement par an"
                    )
                
                with col3:
                    five_year_profit = (annual_savings * 5) - investment
                    st.metric(
                        "💵 Profit sur 5 ans",
                        f"{currency_symbol}{five_year_profit:,.0f}",
                        help="Économies nettes après investissement"
                    )
        
        # Recommandations personnalisées
        st.subheader("🎯 Recommandations Personnalisées")
        
        if avg_pue > 2.0:
            st.error("""
            **Actions prioritaires pour réduire les coûts:**
            1. 🔧 Audit énergétique complet du système de refroidissement
            2. 🌡️ Augmentation progressive de la température de consigne
            3. 💨 Mise en place du free cooling si possible
            4. 🔌 Consolidation des serveurs sous-utilisés
            """)
        elif avg_pue > 1.5:
            st.warning("""
            **Opportunités d'économies identifiées:**
            1. 📊 Optimisation de la distribution d'air (containment)
            2. 🌡️ Ajustement fin des paramètres de climatisation
            3. 💡 Passage à l'éclairage LED si pas déjà fait
            4. 🔄 Mise à jour des équipements les moins efficaces
            """)
        else:
            st.success("""
            **Maintenir l'excellence énergétique:**
            1. ✅ Surveillance continue des métriques
            2. 🔄 Maintenance préventive régulière
            3. 📈 Benchmarking avec les meilleures pratiques
            4. 🌱 Explorer les énergies renouvelables
            """)
        
    else:
        st.warning("Données de puissance manquantes pour l'analyse des coûts.")

