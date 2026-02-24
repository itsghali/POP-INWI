@echo off
REM Script de lancement du scheduler auto-sync
REM À placer dans Windows Task Scheduler

cd /d "C:\Users\Admin\POP-INWI"

REM Activer l'environnement virtuel
call venv\Scripts\activate.bat

REM Lancer le scheduler
python scripts/auto_sync_scheduler.py

REM Garder la fenêtre ouverte en cas d'erreur
pause
