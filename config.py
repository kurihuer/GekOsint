
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración del Bot
BOT_TOKEN = os.getenv("GEKOSINT_TOKEN", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(BASE_DIR, "pages")
os.makedirs(PAGES_DIR, exist_ok=True)

# APIs Externas (Opcionales)
IPSTACK_KEY = os.getenv("IPSTACK_KEY", "")
NUMVERIFY_KEY = os.getenv("NUMVERIFY_KEY", "")
HUNTER_KEY = os.getenv("HUNTER_KEY", "")
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
VERCEL_TOKEN  = os.getenv("VERCEL_TOKEN", "")
RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")

# ============================================
# CONTROL DE ACCESO — HARDCODEADO
# ============================================
# Solo estos 6 usuarios pueden usar el bot.
# Obtén tu ID enviando /start a @userinfobot en Telegram.
ALLOWED_USERS = {
    7891650726,  # Admin principal
    0,           # Usuario 2 — REEMPLAZAR
    0,           # Usuario 3 — REEMPLAZAR
    0,           # Usuario 4 — REEMPLAZAR
    0,           # Usuario 5 — REEMPLAZAR
    0,           # Usuario 6 — REEMPLAZAR
}

# El acceso SIEMPRE está restringido (hardcodeado)
# Filtrar IDs válidos (ignorar 0)
ALLOWED_USERS = {uid for uid in ALLOWED_USERS if uid > 0}
ACCESS_RESTRICTED = len(ALLOWED_USERS) > 0

# ID del administrador principal (primer usuario) — recibe logs especiales
ADMIN_ID = list(ALLOWED_USERS)[0]

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL)
)
logger = logging.getLogger("GekOsint")
