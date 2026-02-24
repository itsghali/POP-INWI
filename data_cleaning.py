import os
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import pytz
import traceback
import time
import warnings

class DataCleaner:
    """Système de nettoyage des données pour les POPs"""
    
    def __init__(self, data_dir="data", auto_sync=True):
        # Convertir en chemin absolu si c'est un chemin relatif
        if not Path(data_dir).is_absolute():
            self.data_dir = Path.cwd() / data_dir
        else:
            self.data_dir = Path(data_dir)
        self.db_path = Path.cwd() / 'data_raw.db'
        print(f"🔍 Chemin absolu du dossier data : {self.data_dir}")
        
        # Auto-sync CSV to DB if enabled
        if auto_sync:
            self.auto_sync_csv_to_db()
    
    def _get_csv_files(self):
        """Retourne tous les fichiers CSV avec leurs métadonnées"""
        csv_files = []
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith(".csv"):
                    file_path = Path(root) / file
                    csv_files.append({
                        'path': file_path,
                        'mtime': file_path.stat().st_mtime,
                        'rel_path': file_path.relative_to(self.data_dir.parent)
                    })
        return csv_files
    
    def _get_db_last_updated(self):
        """Retourne le timestamp de dernière modification de la DB"""
        if not self.db_path.exists():
            return 0
        return self.db_path.stat().st_mtime
    
    def _import_csv_to_db(self, file_path, conn):
        """Importe un fichier CSV dans la base de données"""
        try:
            # Colonnes standard attendues
            standard_columns = ["Timestamp", "Trend Flags", "Status", "Value"]
            
            # Extraire metadata region/pop depuis le chemin
            rel_path = file_path.relative_to(self.data_dir)
            parts = rel_path.parts
            region = parts[0] if len(parts) >= 2 else ''
            pop = parts[1] if len(parts) >= 3 else ''
            filename = file_path.name
            
            table_name = file_path.stem.replace(" ", "_").replace("-", "_")
            
            print(f"   📥 Import: {region}/{pop}/{filename}")
            
            # Trouver la ligne d'en-tête
            with open(file_path, encoding="utf-8", errors='ignore') as f:
                lines = f.readlines()
            
            header_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith("Timestamp"):
                    header_idx = i
                    break
            
            if header_idx is None:
                print(f"   ⚠️ Pas d'en-tête 'Timestamp' trouvé dans {filename}")
                return False
            
            # Lire le CSV
            df = pd.read_csv(file_path, skiprows=header_idx, encoding='utf-8', on_bad_lines='skip')
            
            # Nettoyage des noms de colonnes
            df.columns = [c.strip() for c in df.columns]
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
            
            # Créer DataFrame avec colonnes standard
            for std in standard_columns:
                if std not in col_map:
                    df[std] = pd.NA
            
            # Sélectionner colonnes
            df_sel = pd.DataFrame()
            for std in standard_columns:
                if std in col_map:
                    df_sel[std] = df[col_map[std]]
                else:
                    df_sel[std] = pd.NA
            
            # Ajouter metadata
            df_sel['region'] = region
            df_sel['pop'] = pop
            
            # Nettoyer Timestamp
            ts = df_sel['Timestamp'].astype(str).str.replace(r"\s+\w+$", '', regex=True).str.strip()
            df_sel['Timestamp'] = pd.to_datetime(ts, format="%d-%b-%y %I:%M:%S %p", errors='coerce')
            
            mask_na = df_sel['Timestamp'].isna()
            if mask_na.any():
                df_sel.loc[mask_na, 'Timestamp'] = pd.to_datetime(ts[mask_na], format="%d-%b-%y %H:%M:%S", errors='coerce')
            
            mask_na = df_sel['Timestamp'].isna()
            if mask_na.any():
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    df_sel.loc[mask_na, 'Timestamp'] = pd.to_datetime(ts[mask_na], errors='coerce')
            
            # Nettoyer les valeurs vides
            df_sel = df_sel.replace(r'^\s*$', pd.NA, regex=True)
            df_sel = df_sel.replace(['nan', 'NaN', 'None', 'NONE', 'NULL', 'null'], pd.NA)
            df_sel = df_sel.dropna(axis=1, how='all')
            
            # Supprimer les entrées existantes pour cette region/pop/table
            conn.execute(f'DELETE FROM "{table_name}" WHERE region = ? AND pop = ?', (region, pop))
            
            # Écrire dans la DB
            if df_sel.shape[0] > 0:
                df_sel.to_sql(table_name, conn, if_exists="append", index=False)
                print(f"   ✅ {len(df_sel)} lignes importées pour {filename}")
                return True
            else:
                print(f"   ⚠️ Aucune ligne valide dans {filename}")
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur import {file_path.name}: {str(e)}")
            return False
    
    def auto_sync_csv_to_db(self, force=False):
        """
        Synchronise automatiquement les CSV vers la base de données.
        
        Args:
            force: Si True, force la synchronisation même si la DB est à jour
        """
        csv_files = self._get_csv_files()
        
        if not csv_files:
            print("ℹ️ Aucun fichier CSV trouvé")
            return
        
        db_last_updated = self._get_db_last_updated()
        
        # Vérifier si des CSV sont plus récents que la DB
        newer_csvs = [f for f in csv_files if force or f['mtime'] > db_last_updated]
        
        if not newer_csvs and not force:
            print("✅ Base de données à jour")
            return
        
        print(f"\n🔄 Synchronisation: {len(newer_csvs)} fichier(s) à importer...")
        
        # Créer/connecter à la DB
        conn = sqlite3.connect(str(self.db_path))
        
        imported = 0
        for csv_info in newer_csvs:
            if self._import_csv_to_db(csv_info['path'], conn):
                imported += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Synchronisation terminée: {imported}/{len(newer_csvs)} fichiers importés\n")
        
    def get_regions(self):
        """Retourne la liste des régions disponibles"""
        if self.db_path.exists():
            return self._get_regions_from_db()
        return [d.name for d in self.data_dir.iterdir() if d.is_dir()]
    
    def get_pops(self, region):
        """Retourne la liste des POPs disponibles pour une région donnée"""
        if self.db_path.exists():
            return self._get_pops_from_db(region)
        region_path = self.data_dir / region
        if not region_path.exists():
            return []
        return [d.name for d in region_path.iterdir() if d.is_dir()]
        
    def get_pop_path(self, region, pop):
        """Retourne le chemin complet vers un POP spécifique"""
        return self.data_dir / region / pop

    def _get_table_candidates(self, filename):
        table_name = os.path.splitext(filename)[0].replace(' ', '_').replace('-', '_')
        candidates = [table_name]
        try:
            import unicodedata
            ascii_name = unicodedata.normalize('NFKD', table_name).encode('ascii', 'ignore').decode()
            if ascii_name != table_name:
                candidates.append(ascii_name)
        except Exception:
            pass
        return candidates

    def _get_tables_with_region_pop(self, conn):
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        result = []
        for (tname,) in tables:
            cols = conn.execute(f"PRAGMA table_info(\"{tname}\")").fetchall()
            col_names = {str(c[1]).lower() for c in cols}
            if {'region', 'pop'}.issubset(col_names):
                result.append(tname)
        return result

    def _get_regions_from_db(self):
        try:
            conn = sqlite3.connect(str(self.db_path))
            tables = self._get_tables_with_region_pop(conn)
            if not tables:
                conn.close()
                return []
            regions = set()
            for table in tables:
                rows = conn.execute(
                    f"SELECT DISTINCT region FROM \"{table}\" WHERE region IS NOT NULL",
                ).fetchall()
                regions.update(r[0] for r in rows if r and r[0] is not None)
            conn.close()
            return sorted(regions)
        except Exception:
            return []

    def _get_pops_from_db(self, region):
        try:
            conn = sqlite3.connect(str(self.db_path))
            tables = self._get_tables_with_region_pop(conn)
            if not tables:
                conn.close()
                return []
            pops = set()
            for table in tables:
                rows = conn.execute(
                    f"SELECT DISTINCT pop FROM \"{table}\" WHERE region = ? AND pop IS NOT NULL",
                    (region,),
                ).fetchall()
                pops.update(r[0] for r in rows if r and r[0] is not None)
            conn.close()
            return sorted(pops)
        except Exception:
            return []

    def has_pop_data(self, region, pop, required_files=None):
        """Retourne True si les tables requises existent et contiennent des lignes pour ce POP."""
        if not self.db_path.exists():
            return False
        required_files = required_files or [
            'Température Ambiante.csv',
            'Température Extérieure.csv',
            'P.Active CLIM.csv',
            'P.Active Générale.csv'
        ]
        try:
            conn = sqlite3.connect(str(self.db_path))
            for filename in required_files:
                found = False
                for tname in self._get_table_candidates(filename):
                    q = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
                    if conn.execute(q, (tname,)).fetchone():
                        count = conn.execute(
                            f"SELECT 1 FROM \"{tname}\" WHERE region=? AND pop=? LIMIT 1",
                            (region, pop)
                        ).fetchone()
                        if count:
                            found = True
                            break
                if not found:
                    conn.close()
                    return False
            conn.close()
            return True
        except Exception:
            return False
        
    def _read_file_header(self, file_path, encoding='ISO-8859-1', num_lines=5):
        """Lit les premières lignes du fichier pour analyse"""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = [f.readline().strip() for _ in range(num_lines)]
            return lines
        except Exception:
            return []
            
    def _detect_format(self, lines):
        """Détecte le format du fichier basé sur ses premières lignes"""
        if not lines:
            return None, None, []
        
        # Chercher la première ligne qui ressemble à un en-tête
        header_idx = None
        for idx, line in enumerate(lines):
            clean_line = line.replace('ï»¿', '').replace('\ufeff', '')
            if any(x in clean_line for x in ["Timestamp", "Value", "Valeur"]):
                header_idx = idx
                break
        
        if header_idx is not None:
            header_line = lines[header_idx].replace('ï»¿', '').replace('\ufeff', '')
            
            # Détecter le délimiteur initial du header
            columns = None
            delimiter = ';'  # Fallback initial
            if ';' in header_line:
                columns = [col.strip() for col in header_line.split(';')]
                delimiter = ';'
            elif ',' in header_line:
                columns = [col.strip() for col in header_line.split(',')]
                delimiter = ','
            
            # Optional: Vérifier et ajuster le délimiteur basé sur la ligne de données suivante
            if header_idx + 1 < len(lines):
                data_line = lines[header_idx + 1]
                comma_count = data_line.count(',')
                semicolon_count = data_line.count(';')
                if comma_count > semicolon_count and comma_count >= 3:
                    delimiter = ','  # Changer en virgule si plus commun
            
            # Retourner avec le délimiteur final
            return columns, delimiter, header_idx + 1
        
        # Par défaut, utiliser le point-virgule si aucun header trouvé
        return None, ';', 0

    def load_and_clean_csv(self, file_path, encoding='ISO-8859-1'):
        """Charge et nettoie un fichier CSV"""
        try:
            print(f"\n📄 Traitement du fichier : {file_path.name}")
            
            # Essayer différents encodages
            encodings = ['ISO-8859-1', 'utf-8', 'utf-8-sig']
            lines = []
            used_encoding = None
            
            for enc in encodings:
                try:
                    lines = self._read_file_header(file_path, enc, num_lines=10)
                    if lines:
                        used_encoding = enc
                        break
                except UnicodeDecodeError:
                    continue
            
            if not lines:
                print("❌ Impossible de lire le fichier avec les encodages standards")
                return pd.DataFrame()
            
            # Afficher les premières lignes pour debug
            print("   ℹ️ Premières lignes du fichier :")
            for i, line in enumerate(lines):
                print(f"   {i+1}: {line}")
            
            # Détecter le format
            columns, delimiter, skiprows = self._detect_format(lines)
            print(f"   📊 Délimiteur détecté : '{delimiter}'")
            # Ne pas prédéfinir le nom de colonne, laisser le CSV déterminer
            # Les colonnes seront automatiquement lues du fichier
            
            # Lecture du fichier selon son format
            try:
                if columns:
                    df = pd.read_csv(
                        file_path,
                        delimiter=delimiter,
                        names=columns,
                        skiprows=skiprows,
                        encoding=used_encoding,
                        on_bad_lines='skip',
                        quoting=1  # Pour gérer les valeurs entre guillemets
                    )
                else:
                    df = pd.read_csv(
                        file_path,
                        delimiter=delimiter,
                        encoding=used_encoding,
                        on_bad_lines='skip',
                        quoting=1
                    )
            except Exception as e:
                print(f"   ❌ Première tentative échouée : {str(e)}")
                try:
                    # Deuxième tentative sans le mode quoting
                    if columns:
                        df = pd.read_csv(
                            file_path,
                            delimiter=delimiter,
                            names=columns,
                            skiprows=skiprows,
                            encoding=used_encoding,
                            on_bad_lines='skip'
                        )
                    else:
                        df = pd.read_csv(
                            file_path,
                            delimiter=delimiter,
                            encoding=used_encoding,
                            on_bad_lines='skip'
                        )
                except Exception as e2:
                    print(f"   ❌ Deuxième tentative échouée : {str(e2)}")
                    return pd.DataFrame()
            
            # Nettoyer les noms de colonnes
            df.columns = df.columns.str.strip()
            df.columns = [col.replace('\ufeff', '').replace('ï»¿', '') for col in df.columns]
            print(f"   📊 Colonnes nettoyées : {df.columns.tolist()}")
            
            # Traitement plus flexible du Status
            if 'Status' in df.columns:
                df['Status'] = df['Status'].astype(str)
                # Garder les lignes qui ne contiennent pas d'erreur explicite
                error_keywords = ['error', 'failure', 'failed', 'invalid']
                mask = ~df['Status'].str.lower().str.contains('|'.join(error_keywords))
                df = df[mask]
            
            # Gérer les dates avec support des fuseaux horaires
            if 'Timestamp' in df.columns:
                # Supprimer les suffixes de fuseau horaire et nettoyer
                df['Timestamp'] = (df['Timestamp']
                    .astype(str)
                    .str.replace(r'\s+(WEST|WET|GMT|UTC|CET|CEST)$', '', regex=True)
                    .str.strip())
                # Convertir en datetime avec gestion des erreurs
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                # Supprimer les lignes avec des dates invalides
                df = df.dropna(subset=['Timestamp'])
            
            # Traiter les valeurs
            for col in df.columns:
                if 'Value' in col:
                    # Convertir en string pour le nettoyage initial
                    df[col] = df[col].astype(str).str.strip()
                    
                    if 'CLIM' in file_path.name and 'Etat' in file_path.name:
                        # Nettoyer et standardiser les valeurs ON/OFF
                        df[col] = df[col].str.upper()
                        on_values = ['ON', 'MARCHE', '1', 'TRUE', 'VRAI']
                        off_values = ['OFF', 'ARRET', 'ARRÊT', '0', 'FALSE', 'FAUX']
                        
                        # Créer le mapping
                        value_map = {v: 1 for v in on_values}
                        value_map.update({v: 0 for v in off_values})
                        df[col] = df[col].map(value_map)
                        
                    elif 'Porte' in file_path.name:
                        df[col] = df[col].str.upper()
                        # Mapping étendu pour les états de porte
                        door_map = {
                            'OUVERTE': 1, 'OUVERT': 1, 'OPEN': 1,
                            'FERMÉ': 0, 'FERMÉE': 0, 'FERME': 0, 'FERMEE': 0,
                            'FERMÃ©': 0, 'FERMÃ‰': 0, 'CLOSED': 0, 'CLOSE': 0,
                            '1': 1, '0': 0, 'TRUE': 1, 'FALSE': 0
                        }
                        df[col] = df[col].map(door_map)
                        
                    elif any(unit in col for unit in ['°C', 'kW']):
                        # Nettoyer les valeurs numériques
                        df[col] = (df[col]
                            .str.replace(',', '.')  # Remplacer la virgule par le point décimal
                            .str.replace(r'[^\d.-]+', '', regex=True)  # Garder uniquement les chiffres, le point et le signe
                        )
                        # Convertir en numérique et gérer les erreurs
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        # Filtrer les valeurs aberrantes pour la température et la puissance
                        if '°C' in col:
                            df.loc[df[col] > 60, col] = np.nan  # Température max 60°C
                            df.loc[df[col] < -10, col] = np.nan  # Température min -10°C
                        elif 'kW' in col:
                            df.loc[df[col] < 0, col] = 0  # Puissance ne peut pas être négative
                        
                    # Vérifier si la colonne est entièrement vide après conversion
                    if df[col].isna().all():
                        print(f"⚠️ La colonne {col} est vide après conversion")
                    else:
                        valid_count = df[col].notna().sum()
                        print(f"✓ {valid_count} valeurs valides dans {col}")
            
            print(f"✅ Fichier chargé avec succès ({len(df)} lignes)")
            #ajout
            return self.make_streamlit_safe(df)
            
        except Exception as e:
            print(f"❌ Erreur générale : {str(e)}")
            #ajout
            return pd.DataFrame()

    def _clean_df_from_db(self, df, filename):
        """Nettoie et normalise un DataFrame chargé depuis la DB.

        Mirrors CSV cleaning but operates on DataFrames coming from SQLite.
        """
        try:
            df = df.copy()
            # drop importer metadata
            for meta in ('region', 'pop'):
                if meta in df.columns:
                    df.drop(columns=[meta], inplace=True)

            # normalize column names
            df.columns = [str(c).strip().replace('\ufeff', '').replace('ï»¿', '') for c in df.columns]

            # find timestamp
            ts_col = None
            for c in df.columns:
                if 'timestamp' in str(c).lower():
                    ts_col = c
                    break
            if ts_col is None and len(df.columns) > 0:
                ts_col = df.columns[0]
            if ts_col != 'Timestamp':
                df.rename(columns={ts_col: 'Timestamp'}, inplace=True)

            if 'Timestamp' in df.columns:
                df['Timestamp'] = df['Timestamp'].astype(str).str.replace(r"\s+(WEST|WET|GMT|UTC|CET|CEST)$", '', regex=True).str.strip()
                for fmt in ("%d-%b-%y %I:%M:%S %p", "%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        parsed = pd.to_datetime(df['Timestamp'], format=fmt, errors='coerce')
                        if parsed.notna().sum() > 0:
                            df['Timestamp'] = parsed
                            break
                    except Exception:
                        continue
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                df = df.dropna(subset=['Timestamp'])

            # find value column
            value_col = None
            for c in df.columns:
                if any(x in str(c).lower() for x in ['value', 'valeur']):
                    value_col = c
                    break

            if value_col:
                df.rename(columns={value_col: 'Value'}, inplace=True)
                df['Value'] = df['Value'].astype(str).str.strip()
                fname = filename.lower()
                if 'etat' in fname and 'clim' in fname:
                    df['Value'] = df['Value'].str.upper()
                    on_values = ['ON', 'MARCHE', '1', 'TRUE', 'VRAI']
                    off_values = ['OFF', 'ARRET', 'ARRÊT', '0', 'FALSE', 'FAUX']
                    m = {v: 1 for v in on_values}
                    m.update({v: 0 for v in off_values})
                    df['Value'] = df['Value'].map(m)
                elif 'porte' in fname:
                    df['Value'] = df['Value'].str.upper()
                    door_map = {
                        'OUVERTE': 1, 'OUVERT': 1, 'OPEN': 1,
                        'FERMÉ': 0, 'FERMÉE': 0, 'FERME': 0, 'FERMEE': 0,
                        'CLOSED': 0, 'CLOSE': 0,
                        '1': 1, '0': 0, 'TRUE': 1, 'FALSE': 0
                    }
                    df['Value'] = df['Value'].map(door_map)
                else:
                    df['Value'] = df['Value'].str.replace(',', '.', regex=False)
                    df['Value'] = df['Value'].str.replace(r'[^0-9eE+\-\.]+', '', regex=True)
                    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
                    if 'temp' in fname or 'température' in fname or '°c' in fname:
                        df.loc[df['Value'] > 60, 'Value'] = np.nan
                        df.loc[df['Value'] < -10, 'Value'] = np.nan
                    if 'p.active' in fname or 'puissance' in fname or 'kw' in fname:
                        df.loc[df['Value'] < 0, 'Value'] = 0

            # drop empty cols
            for col in list(df.columns):
                if df[col].isna().all():
                    df.drop(columns=[col], inplace=True)

            # dedupe on Timestamp
            if 'Timestamp' in df.columns:
                df = df.sort_values('Timestamp').drop_duplicates(subset=['Timestamp'], keep='last')

            # put Timestamp first
            cols = df.columns.tolist()
            if 'Timestamp' in cols:
                cols = ['Timestamp'] + [c for c in cols if c != 'Timestamp']
                df = df[cols]

            return df
        except Exception as e:
            print(f"❌ Erreur _clean_df_from_db: {e}")
            return pd.DataFrame()

    def _load_single_pop(self, region=None, pop=None):
        """Load and clean data for a single POP using `data_raw.db` (SQLite)."""
        db_path = getattr(self, 'db_path', Path.cwd() / 'data_raw.db')
        if not db_path.exists():
            print(f"❌ Base SQLite non trouvée ({db_path}). Chargement depuis DB uniquement.")
            return {}

        conn = sqlite3.connect(str(db_path))

        data_files = {
            'temp_ambiante': 'Température Ambiante.csv',
            'temp_exterieure': 'Température Extérieure.csv',
            'puissance_clim': 'P.Active CLIM.csv',
            'puissance_generale': 'P.Active Générale.csv',
            'clim_a': 'Etat CLIM A.csv',
            'clim_b': 'Etat CLIM B.csv',
            'clim_c': 'Etat CLIM C.csv',
            'clim_d': 'Etat CLIM D.csv',
            'clim_e': 'Etat CLIM E.csv',
            'clim_f': 'Etat CLIM F.csv',
            'clim_g': 'Etat CLIM G.csv',
            'clim_h': 'Etat CLIM H.csv',
            'porte': 'Etat Porte.csv'
        }

        cleaned_data = {}
        print(f"\n⏱️ Début du chargement depuis DB: {datetime.now().strftime('%H:%M:%S')}")

        for i, (key, filename) in enumerate(data_files.items(), 1):
            df = pd.DataFrame()
            found = False
            for tname in self._get_table_candidates(filename):
                q = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
                cur = conn.execute(q, (tname,))
                if cur.fetchone():
                    sql = f"SELECT * FROM \"{tname}\" WHERE region=? AND pop=?"
                    try:
                        df = pd.read_sql_query(sql, conn, params=(region, pop))
                        found = True
                        break
                    except Exception as e:
                        print(f"   ❌ Erreur lecture table {tname}: {e}")
                        continue

            if not found:
                print(f"⚠️ Table pour {filename} non trouvée dans la DB: {region}/{pop}")
                continue

            if not df.empty:
                df_clean = self._clean_df_from_db(df, filename)
                if not df_clean.empty:
                    cleaned_data[key] = df_clean
                    print(f"✅ {filename} chargé depuis DB ({len(df_clean)} lignes)")
                else:
                    print(f"⚠️ {filename} vide après nettoyage")

        conn.close()
        print(f"\n✅ Chargement depuis DB terminé: {len(cleaned_data)} fichiers chargés")
        return {k: self.make_streamlit_safe(v) for k, v in cleaned_data.items() if not v.empty}

    def load_pops_data(self, pop_list=None, regions=None, region=None, pop=None):
        """
        Charge les données pour un ou plusieurs POPs.
        
        Args:
            pop_list: Liste de tuples (region, pop) pour plusieurs POPs.
            regions: Liste de régions pour charger tous les POPs de ces régions.
            region: Région pour un seul POP (utilisé avec pop).
            pop: POP pour un seul POP (utilisé avec region).
        
        Returns:
            Dict avec clé (region, pop) et valeur les données fusionnées (ou dict simple pour un seul POP).
        """
        all_pops_data = {}
        
        # Cas 1: Un seul POP spécifié via region/pop
        if region and pop and not pop_list and not regions:
            print(f"\n📍 Traitement d'un seul POP: {region}/{pop}")
            cleaned_data = self._load_single_pop(region=region, pop=pop)
            if cleaned_data:
                merged_data = self.merge_all_data(cleaned_data)
                if not merged_data.empty:
                    merged_data['Region'] = region
                    merged_data['POP'] = pop
                    merged_data['POP_ID'] = f"{region}_{pop}"
                    return cleaned_data, merged_data
            return {}, pd.DataFrame()
        
        # Cas 2: Générer pop_list à partir de regions ou tout charger si rien spécifié
        if not pop_list:
            pop_list = []
            target_regions = regions if regions else self.get_regions()
            for reg in target_regions:
                pops = self.get_pops(reg)
                for p in pops:
                    pop_list.append((reg, p))
        
        print(f"\n🔄 Chargement de {len(pop_list)} POPs...")
        
        for reg, p in pop_list:
            print(f"\n📍 Traitement de {reg}/{p}...")
            try:
                cleaned_data = self._load_single_pop(region=reg, pop=p)
                if cleaned_data:
                    merged_data = self.merge_all_data(cleaned_data)
                    if not merged_data.empty:
                        merged_data['Region'] = reg
                        merged_data['POP'] = p
                        merged_data['POP_ID'] = f"{reg}_{p}"
                        all_pops_data[(reg, p)] = merged_data
                        print(f"✅ {reg}/{p}: {len(merged_data)} lignes chargées")
                    else:
                        print(f"⚠️ {reg}/{p}: Données vides après fusion")
                else:
                    print(f"⚠️ {reg}/{p}: Aucune donnée trouvée")
            except Exception as e:
                print(f"❌ Erreur lors du chargement de {reg}/{p}: {str(e)}")
                continue
        
        print(f"\n✅ {len(all_pops_data)} POPs chargés avec succès sur {len(pop_list)}")
        return all_pops_data
    
        
    def merge_all_data(self, cleaned_data):
        """Fusionne toutes les données sur Timestamp"""
        if not cleaned_data:
            return pd.DataFrame()
        
        dfs_to_merge = []
        
        # Fonction helper pour trouver la colonne de valeur
        def find_value_column(df):
            value_cols = [col for col in df.columns 
                         if any(x in col.lower() for x in ['value', 'valeur']) and 
                            any(x in col for x in ['°C', 'kW', 'Â°C'])]
            if not value_cols:
                # Fallback to any column with 'Value' in the name
                value_cols = [col for col in df.columns if 'Value' in col]
            return value_cols[0] if value_cols else None
        
        if isinstance(cleaned_data, pd.DataFrame):
            # Si c'est déjà un DataFrame fusionné, le retourner
            return cleaned_data
    
        if not isinstance(cleaned_data, dict) or not cleaned_data:
            raise ValueError("cleaned_data doit être un dictionnaire non vide de DataFrames")
    
        # Vérifications des clés attendues
        required_keys = ['temp_ambiante', 'temp_exterieure', 'puissance_generale']



        # Température ambiante
        if 'temp_ambiante' in cleaned_data:
            df = cleaned_data['temp_ambiante'].copy()
            value_col = find_value_column(df)
            if value_col and 'Timestamp' in df.columns:
                df = df[['Timestamp', value_col]]
                df.rename(columns={value_col: 'Temp_Ambiante'}, inplace=True)
                dfs_to_merge.append(df)
        
        # Température extérieure
        if 'temp_exterieure' in cleaned_data:
            df = cleaned_data['temp_exterieure'].copy()
            value_col = find_value_column(df)
            if value_col and 'Timestamp' in df.columns:
                df = df[['Timestamp', value_col]]
                df.rename(columns={value_col: 'Temp_Exterieure'}, inplace=True)
                dfs_to_merge.append(df)
        
        # Traitement des puissances et calcul de la Puissance IT
        if 'puissance_generale' in cleaned_data and 'puissance_clim' in cleaned_data:
            # Préparer les DataFrames de puissance
            df_gen = cleaned_data['puissance_generale'].copy()
            df_clim = cleaned_data['puissance_clim'].copy()
            
            value_col_gen = find_value_column(df_gen)
            value_col_clim = find_value_column(df_clim)
            
            if value_col_gen and value_col_clim and 'Timestamp' in df_gen.columns:
                # Préparer DataFrame de puissance générale
                df_gen = df_gen[['Timestamp', value_col_gen]]
                df_gen.rename(columns={value_col_gen: 'Puissance_Generale'}, inplace=True)
                
                # Préparer DataFrame de puissance CLIM
                df_clim = df_clim[['Timestamp', value_col_clim]]
                df_clim.rename(columns={value_col_clim: 'Puissance_CLIM'}, inplace=True)
                
                # Fusionner les données de puissance
                puissance_df = pd.merge(df_gen, df_clim, on='Timestamp', how='outer')
                
                # Convertir en numérique et gérer les valeurs manquantes
                puissance_df['Puissance_Generale'] = pd.to_numeric(puissance_df['Puissance_Generale'], errors='coerce')
                puissance_df['Puissance_CLIM'] = pd.to_numeric(puissance_df['Puissance_CLIM'], errors='coerce')
                
                # Calculer la Puissance IT
                puissance_df['Puissance_IT'] = puissance_df['Puissance_Generale'] - puissance_df['Puissance_CLIM']
                
                # Nettoyer les valeurs aberrantes
                puissance_df.loc[puissance_df['Puissance_IT'] < 0, 'Puissance_IT'] = 0
                
                # Ajouter les colonnes de puissance au DataFrame à fusionner (une seule fois)
                dfs_to_merge.append(puissance_df[['Timestamp', 'Puissance_Generale', 'Puissance_CLIM', 'Puissance_IT']])
                
                # Afficher les statistiques
                valid_data = puissance_df['Puissance_IT'].notna().sum()
                if valid_data > 0:
                    print(f"\n✅ Puissance IT calculée avec succès:")
                    print(f"   - {valid_data} points de données valides")
                    print(f"   - Min: {puissance_df['Puissance_IT'].min():.2f} kW")
                    print(f"   - Max: {puissance_df['Puissance_IT'].max():.2f} kW")
                    print(f"   - Moyenne: {puissance_df['Puissance_IT'].mean():.2f} kW")
        elif 'puissance_generale' in cleaned_data:
            # Si on a seulement puissance générale (sans CLIM)
            df = cleaned_data['puissance_generale'].copy()
            value_col = find_value_column(df)
            if value_col and 'Timestamp' in df.columns:
                df = df[['Timestamp', value_col]]
                df.rename(columns={value_col: 'Puissance_Generale'}, inplace=True)
                dfs_to_merge.append(df)
        elif 'puissance_clim' in cleaned_data:
            # Si on a seulement puissance CLIM (sans générale)
            df = cleaned_data['puissance_clim'].copy()
            value_col = find_value_column(df)
            if value_col and 'Timestamp' in df.columns:
                df = df[['Timestamp', value_col]]
                df.rename(columns={value_col: 'Puissance_CLIM'}, inplace=True)
                dfs_to_merge.append(df)
        
        # États CLIM (A-H)
        for clim in ['clim_a', 'clim_b', 'clim_c', 'clim_d', 'clim_e', 'clim_f', 'clim_g', 'clim_h']:
            if clim in cleaned_data:
                df = cleaned_data[clim].copy()
                value_col = find_value_column(df)
                if value_col and 'Timestamp' in df.columns:
                    df = df[['Timestamp', value_col]]
                    df.rename(columns={value_col: f"CLIM_{clim[-1].upper()}_Status"}, inplace=True)
                    dfs_to_merge.append(df)
        
        # État Porte
        if 'porte' in cleaned_data:
            df = cleaned_data['porte'].copy()
            value_col = find_value_column(df)
            if value_col and 'Timestamp' in df.columns:
                df = df[['Timestamp', value_col]]
                df.rename(columns={value_col: 'Porte_Status'}, inplace=True)
                dfs_to_merge.append(df)
        
        # Fusionner tous les DataFrames
        if dfs_to_merge:
            try:
                merge_start_time = time.time()
                print(f"\n🔄 Fusion des données... ({datetime.now().strftime('%H:%M:%S')})")
                print(f"📊 {len(dfs_to_merge)} DataFrames à fusionner")
                
                # Afficher un aperçu des DataFrames avant la fusion
                for i, df in enumerate(dfs_to_merge):
                    print(f"\nDataFrame {i+1}:")
                    print(f"Colonnes: {df.columns.tolist()}")
                    print(f"Période: {df['Timestamp'].min()} à {df['Timestamp'].max()}")
                    print(f"Nombre de lignes: {len(df)}")
                
                # Fusion progressive avec vérification et timing
                merge_step_start = time.time()
                merged = dfs_to_merge[0]
                print(f"\nBase DataFrame: {len(merged)} lignes")
                
                for i, df in enumerate(dfs_to_merge[1:], 1):
                    step_start = time.time()
                    before_merge = len(merged)
                    merged = pd.merge(merged, df, on='Timestamp', how='outer')
                    after_merge = len(merged)
                    step_time = time.time() - step_start
                    
                    print(f"\nFusion {i}: {before_merge} → {after_merge} lignes ({step_time:.2f}s)")
                    if after_merge == 0:
                        print("⚠️ La fusion a résulté en 0 lignes!")
                        # Vérifier les plages de dates
                        print(f"Plage de dates du DataFrame principal: {merged['Timestamp'].min()} à {merged['Timestamp'].max()}")
                        print(f"Plage de dates du DataFrame à fusionner: {df['Timestamp'].min()} à {df['Timestamp'].max()}")
                
                # Trier par Timestamp
                merged = merged.sort_values('Timestamp').reset_index(drop=True)
                
                # Forward-fill pour les données continues
                continuous_cols = ['Temp_Ambiante', 'Temp_Exterieure', 
                                 'Puissance_CLIM', 'Puissance_Generale', 'Puissance_IT']
                for col in continuous_cols:
                    if col in merged.columns:
                        nulls_before = merged[col].isna().sum()
                        merged[col] = merged[col].ffill(limit=30)
                        nulls_after = merged[col].isna().sum()
                        if nulls_before - nulls_after > 0:
                            print(f"\n{col}: {nulls_before - nulls_after} valeurs comblées")
                
                # Vérification finale
                total_merge_time = time.time() - merge_start_time
                print(f"\n✅ Fusion terminée en {total_merge_time:.2f} secondes")
                print(f"⏱️ Fin de fusion: {datetime.now().strftime('%H:%M:%S')}")
                print(f"Nombre total de lignes: {len(merged)}")
                print(f"Période couverte: {merged['Timestamp'].min()} à {merged['Timestamp'].max()}")
                print("Colonnes disponibles:")
                for col in merged.columns:
                    non_null = merged[col].notna().sum()
                    print(f"- {col}: {non_null} valeurs non-null ({non_null/len(merged)*100:.1f}%)")
                
                #ajout
                return self.make_streamlit_safe(merged)
                
            except Exception as e:
                print(f"\n❌ Erreur lors de la fusion: {str(e)}")
                print("Détails de l'erreur:")
                import traceback
                print(traceback.format_exc())
                return pd.DataFrame()
        
        return pd.DataFrame()
    
    def _get_door_state_label(self, door_state_value):
        """Convert door state value to readable label"""
        door_mapping = {
            'Open': 1, 'Ouvert': 1, 'open': 1, '1': 1, 1: 1,
            'Close': 0, 'Fermé': 0, 'closed': 0, '0': 0, 0: 0,
            'Closed': 0, 'OPEN': 1, 'CLOSE': 0, 'CLOSED': 0
        }
        
        if door_state_value not in door_mapping:
            return None
        
        numeric_state = door_mapping[door_state_value]
        return "Toujours Ouverte" if numeric_state == 1 else "Toujours Fermée"

    def _find_last_known_door_state(self, data, period_start):
        """Find the most recent door state before the given period"""
        if 'Timestamp' not in data.columns or 'Porte_Status' not in data.columns:
            return None
        
        before_period = data[data['Timestamp'] < period_start]
        if before_period.empty:
            return None
        
        door_data = before_period[['Timestamp', 'Porte_Status']].dropna()
        if door_data.empty:
            return None
        
        last_state = door_data.sort_values('Timestamp', ascending=False).iloc[0]['Porte_Status']
        return self._get_door_state_label(last_state)

    def _check_constant_door_state(self, door_data):
        """Check if door has constant state across all data"""
        door_mapping = {
            'Open': 1, 'Ouvert': 1, 'open': 1, '1': 1, 1: 1,
            'Close': 0, 'Fermé': 0, 'closed': 0, '0': 0, 0: 0,
            'Closed': 0, 'OPEN': 1, 'CLOSE': 0, 'CLOSED': 0
        }
        
        door_numeric = door_data.map(door_mapping)
        door_numeric = pd.to_numeric(door_numeric, errors='coerce').dropna()
        
        if len(door_numeric) == 0:
            return None
        
        unique_values = door_numeric.unique()
        if len(unique_values) == 1:
            return "Toujours Ouverte" if unique_values[0] == 1 else "Toujours Fermée"
        
        return None

    def _set_door_correlation(self, pop_correlations, corr_metric, original_data, period):
        """Set door correlation values with proper fallback logic"""
        door_state_found = False
        
        # Try to find last known door state before the selected period
        if period and 'Timestamp' in original_data.columns:
            start_date = period[0]
            door_label = self._find_last_known_door_state(original_data, start_date)
            
            if door_label:
                pop_correlations[f'{corr_metric}_Spearman'] = door_label
                pop_correlations[f'{corr_metric}_Pearson'] = door_label
                pop_correlations[f'{corr_metric}_Count'] = 1
                door_state_found = True
        
        # Fallback: Check door state from full original data
        if not door_state_found and 'Porte_Status' in original_data.columns:
            door_data = original_data['Porte_Status'].dropna()
            if len(door_data) > 0:
                constant_state = self._check_constant_door_state(door_data)
                if constant_state:
                    pop_correlations[f'{corr_metric}_Spearman'] = constant_state
                    pop_correlations[f'{corr_metric}_Pearson'] = constant_state
                    pop_correlations[f'{corr_metric}_Count'] = len(door_data)
                    door_state_found = True
        
        # If no door state found, set to None
        if not door_state_found:
            pop_correlations[f'{corr_metric}_Pearson'] = None
            pop_correlations[f'{corr_metric}_Spearman'] = None
            pop_correlations[f'{corr_metric}_Count'] = 0

    def _check_constant_status(self, status_data, metric_name):
        """Check if a status metric (CLIM or Door) has constant values"""
        unique_values = status_data.dropna().unique()
        
        if len(unique_values) != 1:
            return None
        
        value = unique_values[0]
        
        # For CLIM status
        if 'CLIM' in metric_name:
            if value == 1:
                return "Toujours ON"
            elif value == 0:
                return "Toujours OFF"
            else:
                return f"Toujours {value}"
        
        # For door status
        elif 'Porte' in metric_name:
            if value == 1:
                return "Toujours Ouverte"
            elif value == 0:
                return "Toujours Fermée"
            else:
                return f"Toujours {value}"
        
        return None

    def _calculate_correlation(self, corr_data, metric, corr_metric):
        """Calculate Pearson and Spearman correlations between two metrics"""
        try:
            pearson_corr = corr_data[metric].corr(corr_data[corr_metric], method='pearson')
            spearman_corr = corr_data[metric].corr(corr_data[corr_metric], method='spearman')
            return pearson_corr, spearman_corr, len(corr_data)
        except:
            return None, None, 0

    def _convert_status_to_numeric(self, corr_data, corr_metric):
        """Convert status columns (Door/CLIM) to numeric values"""
        if corr_metric == 'Porte_Status' and corr_data[corr_metric].dtype == 'object':
            corr_data[corr_metric] = corr_data[corr_metric].map({
                'Open': 1, 'Ouvert': 1, 'open': 1, '1': 1, 1: 1,
                'Close': 0, 'Fermé': 0, 'closed': 0, '0': 0, 0: 0
            })
        
        if 'CLIM' in corr_metric and 'Status' in corr_metric:
            if corr_data[corr_metric].dtype == 'object':
                corr_data[corr_metric] = corr_data[corr_metric].map({
                    'ON': 1, 'on': 1, 'On': 1, '1': 1, 1: 1,
                    'OFF': 0, 'off': 0, 'Off': 0, '0': 0, 0: 0
                })
        
        return corr_data

    def calculate_pop_correlations(self, all_pops_data, metric='Temp_Ambiante', period=None):
        """
        Calcule les corrélations entre un métrique donné et d'autres métriques pour tous les POPs
        
        Args:
            all_pops_data: Dict avec les données de tous les POPs
            metric: Métrique principal pour la corrélation (défaut: Temp_Ambiante)
            period: Tuple (start_date, end_date) pour filtrer la période
        
        Returns:
            DataFrame avec les corrélations pour chaque POP
        """
        correlation_results = []
        
        # Liste des métriques de base à corréler avec la métrique principale
        base_correlation_metrics = ['Temp_Exterieure', 'Puissance_IT', 'Puissance_CLIM', 'Porte_Status']
        
        # Détecter automatiquement tous les CLIMs disponibles dans toutes les données
        all_clim_units = set()
        for (region, pop), data in all_pops_data.items():
            clim_cols = [col for col in data.columns if col.startswith('CLIM_') and col.endswith('_Status')]
            all_clim_units.update(clim_cols)
        
        # Combiner les métriques de base avec tous les CLIMs détectés
        correlation_metrics = base_correlation_metrics + sorted(list(all_clim_units))
        
        for (region, pop), data in all_pops_data.items():
            # Keep original data for door state analysis
            original_data = data.copy()
            
            # Filtrer par période si spécifiée
            if period and 'Timestamp' in data.columns:
                start_date, end_date = period
                mask = (data['Timestamp'] >= start_date) & (data['Timestamp'] <= end_date)
                data = data[mask]
            
            # Initialize correlation results for this POP
            pop_correlations = {
                'Region': region,
                'POP': pop,
                'POP_ID': f"{region}_{pop}",
                'Data_Points': len(data),
                'Period_Start': data['Timestamp'].min() if 'Timestamp' in data.columns and len(data) > 0 else None,
                'Period_End': data['Timestamp'].max() if 'Timestamp' in data.columns and len(data) > 0 else None
            }
            
            # Handle case where insufficient data for correlation
            if len(data) < 10:
                # Still check door state using helper method
                if 'Porte_Status' in original_data.columns:
                    self._set_door_correlation(pop_correlations, 'Porte_Status', original_data, period)
                
                # Set other metrics to None
                for corr_metric in correlation_metrics:
                    if corr_metric != 'Porte_Status':
                        pop_correlations[f'{corr_metric}_Pearson'] = None
                        pop_correlations[f'{corr_metric}_Spearman'] = None
                        pop_correlations[f'{corr_metric}_Count'] = 0
                
                # Set metric stats to None
                if metric in original_data.columns:
                    pop_correlations[f'{metric}_Mean'] = None
                    pop_correlations[f'{metric}_Std'] = None
                    pop_correlations[f'{metric}_Min'] = None
                    pop_correlations[f'{metric}_Max'] = None
                
                correlation_results.append(pop_correlations)
                continue
            
            # Vérifier que la métrique principale existe
            if metric not in data.columns:
                continue
            
            # Calculer la corrélation avec chaque métrique
            for corr_metric in correlation_metrics:
                if corr_metric in data.columns:
                    # Préparer les données pour la corrélation
                    corr_data = data[[metric, corr_metric]].dropna()
                    
                    if len(corr_data) >= 10:
                        # Convert status columns to numeric
                        corr_data = self._convert_status_to_numeric(corr_data, corr_metric)
                        
                        # Check if status metric has constant values
                        constant_state = self._check_constant_status(corr_data[corr_metric], corr_metric)
                        
                        if constant_state:
                            # Constant value - show the actual state instead of correlation
                            pop_correlations[f'{corr_metric}_Spearman'] = constant_state
                            pop_correlations[f'{corr_metric}_Pearson'] = constant_state
                            pop_correlations[f'{corr_metric}_Count'] = len(corr_data)
                        else:
                            # Variable values - calculate correlation
                            pearson, spearman, count = self._calculate_correlation(corr_data, metric, corr_metric)
                            pop_correlations[f'{corr_metric}_Pearson'] = pearson
                            pop_correlations[f'{corr_metric}_Spearman'] = spearman
                            pop_correlations[f'{corr_metric}_Count'] = count
                    else:
                        # Insufficient data in the period - use helper for door status
                        if corr_metric == 'Porte_Status':
                            self._set_door_correlation(pop_correlations, corr_metric, original_data, period)
                        else:
                            pop_correlations[f'{corr_metric}_Pearson'] = None
                            pop_correlations[f'{corr_metric}_Spearman'] = None
                            pop_correlations[f'{corr_metric}_Count'] = 0
                else:
                    # Metric not in filtered data - use helper for door status
                    if corr_metric == 'Porte_Status':
                        self._set_door_correlation(pop_correlations, corr_metric, original_data, period)
                    else:
                        pop_correlations[f'{corr_metric}_Pearson'] = None
                        pop_correlations[f'{corr_metric}_Spearman'] = None
                        pop_correlations[f'{corr_metric}_Count'] = 0
            
            # Calculer aussi les statistiques de base pour la métrique principale
            pop_correlations[f'{metric}_Mean'] = data[metric].mean()
            pop_correlations[f'{metric}_Std'] = data[metric].std()
            pop_correlations[f'{metric}_Min'] = data[metric].min()
            pop_correlations[f'{metric}_Max'] = data[metric].max()
            
            correlation_results.append(pop_correlations)
        
        # Créer un DataFrame avec tous les résultats
        if correlation_results:
            return self.make_streamlit_safe(pd.DataFrame(correlation_results))
        else:
            return pd.DataFrame()


# === AJOUT ===
    def make_streamlit_safe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        df = df.copy()
        for col in df.select_dtypes(include=['datetime64[ns]', 'datetimetz']).columns:
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.where(pd.notnull(df), None)
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).replace({'nan': None, '<NA>': None, 'None': None})
        return df





if __name__ == "__main__":
    # Test du système de nettoyage
    cleaner = DataCleaner()
    
    # ⭐⭐ CORRECTION : Récupérer les DEUX valeurs
    cleaned_data, merged_data = cleaner.load_pops_data()
    
    print(f"\n📊 Données nettoyées: {len(cleaned_data)} fichiers")
    print(f"📊 Données fusionnées: {len(merged_data)} lignes")
    
    # Afficher les fichiers nettoyés
    if cleaned_data:
        print("\n📁 Fichiers nettoyés chargés:")
        for key, df in cleaned_data.items():
            print(f"   - {key}: {len(df)} lignes")
    
    # Afficher les données fusionnées
    if not merged_data.empty:
        print(f"\n✅ Données fusionnées: {merged_data.shape}")
        print("\nColonnes disponibles:")
        for col in merged_data.columns:
            non_null = merged_data[col].notna().sum()
            print(f"  - {col}: {non_null} valeurs non-null")
    else:
        print("\n❌ Aucune donnée fusionnée disponible")