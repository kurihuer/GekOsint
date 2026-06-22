@echo off
echo Deteniendo GekOsint Bot...
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq bot.py*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq bot.py*" 2>nul
echo Bot detenido.
timeout /t 3
