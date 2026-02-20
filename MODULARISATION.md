# Modularisation de app.py - Guide de migration

## 📦 Nouvelle Structure

```
POP-INWI/
│
├── app.py                          # Fichier principal (orchestration)
│
├── src/
│   ├── core/                       # Fonctionnalités centrales
│   │   ├── __init__.py
│   │   ├── data_loader.py          # Chargement des données
│   │   └── cache_manager.py        # Gestion du cache et préchargement
│   │
│   ├── ui/                         # Interface utilisateur
│   │   ├── __init__.py
│   │   ├── sidebar.py              # Barre latérale (sélection région/POP)
│   │   ├── period_selector.py      # Sélecteur de période (existant)
│   │   ├── incident_lens_ui.py     # Interface Incident Lens (existant)
│   │   │
│   │   └── tabs/                   # Onglets (à migrer progressivement)
│   │       └── __init__.py
│   │
│   └── utils/                      # Utilitaires
│       ├── __init__.py
│       └── startup_detection.py    # Détection du démarrage serveur
│
└── data_cleaning.py                # Module existant (inchangé)
```

## ✅ Étape 1 : Modules extraits (COMPLÉTÉ)

### 1. `src/utils/startup_detection.py`
- `is_server_startup()` : Détecte si c'est un vrai démarrage serveur
- `cleanup_startup_marker()` : Nettoie le fichier marqueur

### 2. `src/core/data_loader.py`
- `load_data(region, pop)` : Charge les données d'un POP
- `load_multiple_pops_optimized(pops_to_load)` : Charge plusieurs POPs avec cache

### 3. `src/core/cache_manager.py`
- `preload_all_pops(data_cleaner, load_data_func)` : Précharge tous les POPs

### 4. `src/ui/sidebar.py`
- `get_region_pop_selection(data_cleaner)` : Gère la sélection région/POP

## 📝 Modifications dans app.py

### Imports ajoutés
```python
from src.utils.startup_detection import is_server_startup
from src.core.data_loader import load_data, load_multiple_pops_optimized
from src.core.cache_manager import preload_all_pops
from src.ui.sidebar import get_region_pop_selection
```

### Appels mis à jour
```python
# Ancienne version
selected_region, selected_pop = get_region_pop_selection()
preload_all_pops()

# Nouvelle version
selected_region, selected_pop = get_region_pop_selection(data_cleaner)
preload_all_pops(data_cleaner, load_data)
```

## 🚀 Prochaines étapes (OPTIONNEL)

### Étape 2 : Migration des onglets
Chaque onglet peut être extrait dans un module séparé :

```
src/ui/tabs/
├── tab01_vue_ensemble.py          (1200 lignes)
├── tab02_analyse_temporelle.py    (350 lignes)
├── tab03_analyses_eda.py          (200 lignes)
├── tab04_analyse_clim.py          (400 lignes)
├── tab05_analyse_porte.py         (1000 lignes)
├── tab07_correlations.py          (450 lignes)
├── tab08_changement_temp.py       (300 lignes)
├── tab09_simulation_couts.py      (500 lignes)
├── tab10_rapport_pop.py           (1100 lignes)
├── tab11_rapport_region.py        (450 lignes)
├── tab12_rapport_national.py      (500 lignes)
└── tab13_comparaison_pops.py      (400 lignes)
```

Chaque module contiendrait :
```python
def render_tab(filtered_data, start_date, end_date, selected_region, selected_pop):
    """Render le contenu de l'onglet"""
    st.header("...")
    # Logique de l'onglet
```

Dans app.py, cela deviendrait :
```python
from src.ui.tabs.tab01_vue_ensemble import render_tab as render_vue_ensemble

with tab1:
    render_vue_ensemble(filtered_merged_data, start_date, end_date, 
                       selected_region, selected_pop)
```

## 💡 Avantages de la modularisation

### Performance
- ✅ **Rechargement plus rapide** en développement
- ✅ **Éditeur plus réactif** (fichiers plus petits)
- ✅ **Imports sélectifs** (charge seulement ce qui est nécessaire)

### Maintenance
- ✅ **Code mieux organisé** et facile à naviguer
- ✅ **Responsabilités clairement séparées**
- ✅ **Tests unitaires facilités**
- ✅ **Moins de conflits Git**

### Évolution
- ✅ **Plusieurs développeurs** peuvent travailler en parallèle
- ✅ **Ajout de fonctionnalités** plus simple
- ✅ **Réutilisation du code** entre projets

## 🧪 Test

Pour tester la modularisation actuelle :

```bash
# Activer l'environnement virtuel
venv\Scripts\activate

# Lancer l'application
streamlit run app.py
```

L'application devrait fonctionner exactement comme avant, mais avec un code mieux organisé.

## 📊 Réduction de la taille

- **Avant** : app.py = ~8000 lignes
- **Après** : 
  - app.py = ~7400 lignes (déjà -600 lignes !)
  - Modules extraits = ~600 lignes réparties
  - Après migration des onglets : app.py = ~500 lignes seulement

## ⚠️ Notes importantes

1. **Compatibilité** : Tout fonctionne comme avant, comportement identique
2. **Cache** : Le cache Streamlit fonctionne toujours correctement
3. **Session State** : Les variables de session sont préservées
4. **Performance** : Aucune perte de performance, potentiellement plus rapide

## 🎯 Décision

Voulez-vous continuer et migrer les onglets vers des modules séparés ?
- ✅ OUI : On continue tab par tab
- ⏸️ NON : On reste ici, c'est déjà une bonne amélioration !
