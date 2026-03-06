"""
Script d'import des CSV vers SQLite.

Ce script harmonise les colonnes en conservant une seule colonne `Value`.
La détection string/numérique sera effectuée plus tard par le data-cleaner.
"""

import os
import pandas as pd
import sqlite3
import warnings


data_dir = "data"
db_path = "data_raw.db"

conn = sqlite3.connect(db_path)


# Colonnes standard attendues pour tous les CSV
standard_columns = ["Timestamp", "Trend Flags", "Status", "Value"]

for root, dirs, files in os.walk(data_dir):
    for file in files:
        if file.endswith(".csv"):
            file_path = os.path.join(root, file)
            table_name = os.path.splitext(file)[0].replace(" ", "_").replace("-", "_")
            print(f"Import de {file_path} dans la table {table_name}")
            try:
                # Trouver la ligne d'en-tête
                with open(file_path, encoding="utf-8") as f:
                    lines = f.readlines()
                header_idx = next(i for i, line in enumerate(lines) if line.strip().startswith("Timestamp"))
                df = pd.read_csv(file_path, skiprows=header_idx)

                # Nettoyage/normalisation des noms de colonnes
                df.columns = [c.strip() for c in df.columns]
                # Harmoniser variantes de 'Value' (ex: 'Value (°C)')
                df.columns = [c.replace('Value (°C)', 'Value').replace('Value(°C)', 'Value') for c in df.columns]

                # Identifier les colonnes pertinentes
                col_map = {}
                for c in df.columns:
                    lc = c.lower()
                    if lc.startswith('timestamp'):
                        col_map['Timestamp'] = c
                    elif 'trend' in lc and 'flag' in lc:
                        col_map['Trend Flags'] = c
                    elif lc.startswith('status'):
                        col_map['Status'] = c
                    elif 'value' in lc:
                        col_map['Value'] = c

                # S'assurer que les colonnes standard existent
                for std in standard_columns:
                    if std not in col_map:
                        df[std] = pd.NA

                # Sélectionner/reordonner les colonnes standard
                try:
                    df_sel = df[[col_map.get('Timestamp', 'Timestamp'),
                                 col_map.get('Trend Flags', 'Trend Flags'),
                                 col_map.get('Status', 'Status'),
                                 col_map.get('Value', 'Value')]]
                except Exception:
                    df_sel = df.iloc[:, :4]
                    df_sel.columns = standard_columns[:len(df_sel.columns)]
                    for std in standard_columns:
                        if std not in df_sel.columns:
                            df_sel[std] = pd.NA
                df_sel.columns = standard_columns

                # Extraire metadata region/pop depuis le chemin (data/Region/POP/...)
                rel = os.path.relpath(root, data_dir)
                parts = rel.split(os.path.sep)
                region = parts[0] if len(parts) >= 1 else ''
                pop = parts[1] if len(parts) >= 2 else ''
                df_sel['region'] = region
                df_sel['pop'] = pop

                # Nettoyer Timestamp (enlever tokens timezone comme 'WEST') et parser en datetime
                ts = df_sel['Timestamp'].astype(str).str.replace(r"\s+\w+$", '', regex=True).str.strip()
                # Tenter un format explicite (ex: '15-May-25 12:45:01 PM')
                df_sel['Timestamp'] = pd.to_datetime(ts, format="%d-%b-%y %I:%M:%S %p", errors='coerce')
                # Si des valeurs restent non parsées, essayer une variante 24h
                mask_na = df_sel['Timestamp'].isna()
                if mask_na.any():
                    df_sel.loc[mask_na, 'Timestamp'] = pd.to_datetime(ts[mask_na], format="%d-%b-%y %H:%M:%S", errors='coerce')
                # Dernier recours: utiliser le parseur générique sans alerter l'utilisateur
                mask_na = df_sel['Timestamp'].isna()
                if mask_na.any():
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        df_sel.loc[mask_na, 'Timestamp'] = pd.to_datetime(ts[mask_na], errors='coerce')

                # Conserver une seule colonne 'Value' (type string) pour le cleaning ultérieur
                if 'Value' not in df_sel.columns:
                    df_sel['Value'] = pd.NA

                # Enregistrer uniquement colonnes standard + metadata (sans Value_num)
                out_cols = standard_columns + ['region', 'pop']
                for col in out_cols:
                    if col not in df_sel.columns:
                        df_sel[col] = pd.NA
                df_out = df_sel[out_cols].copy()

                # Normaliser valeurs vides: convertir chaînes vides et 'nan' en NA
                df_out = df_out.replace(r'^\s*$', pd.NA, regex=True)
                df_out = df_out.replace(['nan', 'NaN', 'None', 'NONE', 'NULL', 'null'], pd.NA)

                # Supprimer toute colonne entièrement vide (toutes NA)
                df_out = df_out.dropna(axis=1, how='all')

                # Déterminer si la colonne 'Value' est présente après nettoyage
                has_value = 'Value' in df_out.columns
                value_col = 'Value' if has_value else 'none'

                # Créer/mettre à jour table meta indiquant quel type de valeur est stocké
                conn.execute('''CREATE TABLE IF NOT EXISTS tables_meta (
                                    table_name TEXT PRIMARY KEY,
                                    value_column TEXT
                                )''')
                conn.execute('REPLACE INTO tables_meta (table_name, value_column) VALUES (?, ?)', (table_name, value_col))
                conn.commit()

                # Si après nettoyage il ne reste aucune colonne à écrire (rare), sauter
                if df_out.shape[1] == 0:
                    print(f"Aucune colonne non vide pour {table_name}, saut de l'écriture.")
                else:
                    df_out.to_sql(table_name, conn, if_exists="append", index=False)
            except Exception as e:
                print(f"Erreur avec {file_path}: {e}")

conn.close()
print("Import terminé.")