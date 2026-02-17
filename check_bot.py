
import sys
import os
import asyncio
import importlib

print("🔍 Iniciando Diagnóstico de GekOsint...\n")

# 1. Verificar Versión de Python
print(f"🐍 Python Version: {sys.version.split()[0]}")
if sys.version_info < (3, 8):
    print("❌ Error: Se requiere Python 3.8 o superior.")
    sys.exit(1)
else:
    print("✅ Versión de Python correcta.")

# 2. Verificar Archivo .env
print("\n📂 Verificando configuración...")
if not os.path.exists(".env"):
    print("❌ Error: No se encuentra el archivo .env")
    print("   -> Renombra .env.example a .env y configura tu token.")
else:
    print("✅ Archivo .env encontrado.")

# 3. Verificar Dependencias
print("\n📦 Verificando librerías instaladas...")
required_modules = [
    ('telegram', 'python-telegram-bot'),
    ('requests', 'requests'),
    ('httpx', 'httpx'),
    ('phonenumbers', 'phonenumbers'),
    ('PIL', 'Pillow'),
    ('dotenv', 'python-dotenv')
]

missing = []
for mod_name, pip_name in required_modules:
    try:
        importlib.import_module(mod_name)
        print(f"   ✅ {pip_name} instalado.")
    except ImportError:
        print(f"   ❌ Faltante: {pip_name}")
        missing.append(pip_name)

if missing:
    print(f"\n❌ Faltan dependencias. Ejecuta:\n   pip install {' '.join(missing)}")
    sys.exit(1)

# 4. Verificar Token y Conexión
print("\n🌐 Probando conexión con Telegram...")
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("GEKOSINT_TOKEN")

if not TOKEN or "tu_token" in TOKEN:
    print("❌ Error: Token inválido o no configurado en .env")
    sys.exit(1)

import httpx

async def check_connection():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                bot_user = data['result']['username']
                print(f"✅ Conexión exitosa! Bot detectado: @{bot_user}")
                print("\n🎉 Todo parece correcto. Intenta ejecutar: python bot.py")
            elif resp.status_code == 401:
                print("❌ Error: Token rechazado por Telegram (401 Unauthorized).")
                print("   -> Verifica que copiaste bien el token de BotFather.")
            else:
                print(f"⚠️ Alerta: Respuesta inesperada de Telegram ({resp.status_code})")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

try:
    asyncio.run(check_connection())
except Exception as e:
    print(f"❌ Error ejecutando test async: {e}")

input("\nPresiona ENTER para salir...")
