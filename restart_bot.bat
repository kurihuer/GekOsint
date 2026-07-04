@echo off
echo ========================================
echo    REINICIANDO GEKOSINT v4.0
echo ========================================
echo.

echo [1/4] Deteniendo procesos Python...
taskkill /F /IM python.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo [2/4] Limpiando cache de Python...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul

echo [3/4] Verificando cambios...
python -c "from modules.tracking_templates import get_template; html = get_template('TEST', '123', 'geo'); assert 'WhatsApp' in html, 'Template no actualizado'; print('✓ Templates OK')"
python -c "from modules.phone_lookup import analyze_phone; result = analyze_phone('+525555555555'); assert 'location' in result, 'Phone lookup no actualizado'; print('✓ Phone lookup OK')"

echo [4/4] Iniciando bot...
echo.
echo ========================================
echo Bot iniciado con cambios aplicados
echo Presiona Ctrl+C para detener
echo ========================================
echo.

python bot.py
