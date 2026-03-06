# Scripts

Ce dossier contient les scripts utilitaires pour la gestion des données.

## Scripts disponibles

### `csv_to_sqlite.py`
Convertit les fichiers CSV du dossier `data/` en base SQLite (`data_raw.db`).

**Usage :**
```bash
python scripts/csv_to_sqlite.py
```

### `sync_missing_pops_to_db.py`
Synchronise les POPs manquants dans la base de données SQLite.

**Usage :**
```bash
python scripts/sync_missing_pops_to_db.py
```

## Remarque
Ces scripts doivent être exécutés depuis la racine du projet pour que les chemins relatifs fonctionnent correctement.
