' Lancer le scheduler en arrière-plan (sans fenêtre)
' Créer un raccourci et double-cliquer pour lancer

CreateObject("WScript.Shell").Run "cmd /c cd C:\Users\Admin\POP-INWI && venv\Scripts\activate && python scripts/auto_sync_scheduler.py", 0
