import os
import logging
from dotenv import load_dotenv

load_dotenv()

# ============================================
# BOT
# ============================================
BOT_TOKEN = os.getenv("GEKOSINT_TOKEN", "")
LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")

# ============================================
# DIRECTORIOS
# ============================================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(BASE_DIR, "pages")
os.makedirs(PAGES_DIR, exist_ok=True)

# ============================================
# APIs EXTERNAS (todas opcionales)
# ============================================
IPSTACK_KEY       = os.getenv("IPSTACK_KEY", "")
NUMVERIFY_KEY     = os.getenv("NUMVERIFY_KEY", "")
HUNTER_KEY        = os.getenv("HUNTER_KEY", "")
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN", "")
VERCEL_TOKEN      = os.getenv("VERCEL_TOKEN", "")
RAPIDAPI_KEY      = os.getenv("RAPIDAPI_KEY", "")
PUBLIC_URL        = os.getenv("PUBLIC_URL", "").rstrip("/")
VT_API_KEY        = os.getenv("VT_API_KEY", "")
ABUSEIPDB_KEY     = os.getenv("ABUSEIPDB_KEY", "")
SHODAN_API_KEY    = os.getenv("SHODAN_API_KEY", "")
GREYNOISE_API_KEY = os.getenv("GREYNOISE_API_KEY", "")

# ============================================
# CONTROL DE ACCESO
# Todos los IDs se gestionan via ADMIN_ID / GEKOSINT_ALLOWED
# o en tiempo de ejecucion con /admin.
# NUNCA hardcodear IDs en este archivo.
# ============================================
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

_env_allowed = os.getenv("GEKOSINT_ALLOWED", "")
ALLOWED_USERS: set = set()
for _uid in _env_allowed.split(","):
    try:
        _parsed = int(_uid.strip())
        if _parsed > 0:
            ALLOWED_USERS.add(_parsed)
    except ValueError:
        continue

if ADMIN_ID > 0:
    ALLOWED_USERS.add(ADMIN_ID)

ACCESS_RESTRICTED = len(ALLOWED_USERS) > 0

# ============================================
# RATE LIMITING (cooldown por usuario)
# ============================================
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "5"))
RATE_LIMIT_BURST   = int(os.getenv("RATE_LIMIT_BURST", "3"))

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger("GekOsint")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
