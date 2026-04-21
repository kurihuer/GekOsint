
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
IPSTACK_KEY      = os.getenv("IPSTACK_KEY", "")
NUMVERIFY_KEY    = os.getenv("NUMVERIFY_KEY", "")
HUNTER_KEY       = os.getenv("HUNTER_KEY", "")
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")
VERCEL_TOKEN     = os.getenv("VERCEL_TOKEN", "")
RAPIDAPI_KEY     = os.getenv("RAPIDAPI_KEY", "")
PUBLIC_URL       = os.getenv("PUBLIC_URL", "").rstrip("/")
VT_API_KEY       = os.getenv("VT_API_KEY", "")
ABUSEIPDB_KEY    = os.getenv("ABUSEIPDB_KEY", "")
SHODAN_API_KEY   = os.getenv("SHODAN_API_KEY", "")
GREYNOISE_API_KEY = os.getenv("GREYNOISE_API_KEY", "")

# ============================================
# CONTROL DE ACCESO — DINÁMICO
# ============================================
# Se pueden cargar desde .env (GEKOSINT_ALLOWED=ID1,ID2,...)
env_allowed = os.getenv("GEKOSINT_ALLOWED", "")
ALLOWED_USERS = set()
if env_allowed:
    for uid in env_allowed.split(","):
        try:
            ALLOWED_USERS.add(int(uid.strip()))
        except ValueError:
            continue

# Fallback a lista hardcodeada si no hay env
if not ALLOWED_USERS:
    ALLOWED_USERS = {
        7891650726,  # Admin principal
    }

# Filtrar IDs válidos (ignorar 0)
ALLOWED_USERS = {uid for uid in ALLOWED_USERS if uid > 0}
ACCESS_RESTRICTED = len(ALLOWED_USERS) > 0

ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
if ADMIN_ID > 0:
    ALLOWED_USERS.add(ADMIN_ID)

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL)
)
logger = logging.getLogger("GekOsint")
