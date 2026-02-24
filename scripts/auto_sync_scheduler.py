"""
Auto-sync scheduler - Synchronise les CSV chaque jour à 2h du matin
Exécution: python scripts/auto_sync_scheduler.py

Sans dépendances externes! Utilise uniquement le Python standard.
"""
import time
import logging
from pathlib import Path
from datetime import datetime
import sys
import os

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_cleaning import DataCleaner

# Configuration du logging
Path('logs').mkdir(exist_ok=True)
logging.basicConfig(
    filename='logs/auto_sync.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def should_run_sync():
    """Vérifie si on doit faire la synchro à 2h du matin"""
    now = datetime.now()
    
    # Entre 02:00 et 02:59
    return now.hour == 2 and 0 <= now.minute <= 59

def sync_job():
    """Fonction de synchronisation"""
    try:
        print(f"\n{'='*60}")
        print(f"🔄 SYNCHRONISATION AUTO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        logging.info("Début de la synchronisation automatique")
        
        # Créer l'instance DataCleaner et lancer la synchro
        cleaner = DataCleaner("data")
        cleaner.auto_sync_csv_to_db(force=True)
        
        logging.info("✅ Synchronisation réussie")
        print(f"✅ Synchronisation réussie à {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        error_msg = f"❌ Erreur lors de la synchronisation: {str(e)}"
        print(error_msg)
        logging.error(error_msg)

def run_scheduler(target_hour=2):
    """
    Boucle infinie du scheduler
    
    Args:
        target_hour: Heure cible pour la synchronisation (0-23)
    """
    print("📅 Scheduler démarré (Python pur, sans dépendances)")
    print(f"⏰ Synchronisation programmée à {target_hour:02d}:00 chaque jour")
    logging.info(f"Scheduler démarré - Sync à {target_hour:02d}:00")
    
    last_run_date = None
    
    # Boucle infinie
    while True:
        try:
            now = datetime.now()
            
            # Vérifier si c'est l'heure et si on n'a pas déjà fait la synchro aujourd'hui
            if now.hour == target_hour and now.day != last_run_date:
                if 0 <= now.minute <= 59:  # Entre XX:00 et XX:59
                    print(f"\n⏰ Heure de synchronisation: {now.strftime('%H:%M:%S')}")
                    sync_job()
                    last_run_date = now.day  # Marquer que la synchro a eu lieu aujourd'hui
                    
                    # Attendre 1 minute pour éviter de relancer la synchro
                    time.sleep(60)
            
            # Attendre 10 secondes avant de vérifier à nouveau
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n👋 Scheduler arrêté par l'utilisateur")
            logging.info("Scheduler arrêté")
            break
        except Exception as e:
            error_msg = f"❌ Erreur dans le scheduler: {str(e)}"
            print(error_msg)
            logging.error(error_msg)
            time.sleep(60)  # Attendre 1 minute avant de réessayer

if __name__ == "__main__":
    print("🚀 Démarrage du scheduler de synchronisation automatique")
    print(f"   Heure actuelle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Prochain sync: 02:00 (chaque jour)")
    print("\n💡 Appuyez sur Ctrl+C pour arrêter\n")
    
    # Parser les arguments
    target_hour = 2  # Par défaut 2h du matin
    if len(sys.argv) > 1:
        try:
            target_hour = int(sys.argv[1])
            if not 0 <= target_hour <= 23:
                print("❌ L'heure doit être entre 0 et 23")
                sys.exit(1)
        except ValueError:
            print("❌ Heure invalide")
            sys.exit(1)
    
    run_scheduler(target_hour=target_hour)
