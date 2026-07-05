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
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_API_KEY     = os.getenv("TWILIO_API_KEY", "")
TWILIO_API_SECRET  = os.getenv("TWILIO_API_SECRET", "")
ZENROWS_API_KEY    = os.getenv("ZENROWS_API_KEY", "")
SERPAPI_KEY        = os.getenv("SERPAPI_KEY", "")

# ── Instagram OSINT (cookies de sesión, NO password) ─────────────────────────
# Cómo obtenerlas: logueate en instagram.com con cuenta dedicada,
# DevTools → Application → Cookies → instagram.com → copiar valores.
IG_USERNAME   = os.getenv("IG_USERNAME", "")
IG_SESSIONID  = os.getenv("IG_SESSIONID", "")
IG_DS_USER_ID = os.getenv("IG_DS_USER_ID", "")
IG_CSRFTOKEN  = os.getenv("IG_CSRFTOKEN", "")

# ── Gmail/Google OSINT (cookies de sesión, opcionales) ───────────────────────
# Sin cookies → modo "anónimo" con recovery hints + Gravatar (limitado).
# Con cookies → People API (foto, nombre completo, gaia ID, servicios).
GOOGLE_SAPISID      = os.getenv("GOOGLE_SAPISID", "")
GOOGLE_HSID         = os.getenv("GOOGLE_HSID", "")
GOOGLE_SSID         = os.getenv("GOOGLE_SSID", "")
GOOGLE_APISID       = os.getenv("GOOGLE_APISID", "")
GOOGLE_SECURE_1PSID = os.getenv("GOOGLE_SECURE_1PSID", "")
GOOGLE_SECURE_3PSID = os.getenv("GOOGLE_SECURE_3PSID", "")
GOOGLE_NID          = os.getenv("GOOGLE_NID", "")

# ── Facebook OSINT (cookies de sesión, opcionales) ───────────────────────────
# Sin cookies → recovery hints + findmyfbid + foto de perfil (limitado).
# Con cookies → más metadata de Pages.
FB_C_USER = os.getenv("FB_C_USER", "")
FB_XS     = os.getenv("FB_XS", "")
FB_DATR   = os.getenv("FB_DATR", "")
FB_FR     = os.getenv("FB_FR", "")

# ── Proxy residencial (opcional, para FB y Gmail OSINT) ──────────────────────
# Desde IPs de cloud (Koyeb/Railway) Meta y Google bloquean los endpoints
# de recovery hints. Un proxy residencial evita el bloqueo.
# Formato Webshare: http://usuario:password@proxy.webshare.io:80
PROXY_URL = os.getenv("PROXY_URL", "")

# ============================================
# CONTROL DE ACCESO
# Todos los IDs se gestionan via ADMIN_ID / GEKOSINT_ALLOWED
# o en tiempo de ejecucion con /admin.
# NUNCA hardcodear IDs en este archivo.
# ============================================
# ADMIN_ID puede ser un solo ID o varios separados por coma: "123,456"
_admin_raw = os.getenv("ADMIN_ID", "0") or "0"
ADMIN_IDS: set = set()
for _a in _admin_raw.split(","):
    try:
        _ai = int(_a.strip())
        if _ai > 0:
            ADMIN_IDS.add(_ai)
    except ValueError:
        continue
ADMIN_ID = next(iter(ADMIN_IDS), 0)  # compatibilidad con codigo existente

_env_allowed = os.getenv("GEKOSINT_ALLOWED", "")
ALLOWED_USERS: set = set()
for _uid in _env_allowed.split(","):
    try:
        _parsed = int(_uid.strip())
        if _parsed > 0:
            ALLOWED_USERS.add(_parsed)
    except ValueError:
        continue

ALLOWED_USERS.update(ADMIN_IDS)

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
