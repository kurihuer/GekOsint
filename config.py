
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración del Bot
BOT_TOKEN = os.getenv("GEKOSINT_TOKEN", "8575617284:AAEnhzskJXyLFC5VV4Qi2-TEz8UNAK4idYQ")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(BASE_DIR, "pages")
os.makedirs(PAGES_DIR, exist_ok=True)

# APIs Externas (Opcionales)
IPSTACK_KEY = os.getenv("IPSTACK_KEY", "")
NUMVERIFY_KEY = os.getenv("NUMVERIFY_KEY", "")
HUNTER_KEY = os.getenv("HUNTER_KEY", "")

# Configuración de Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL)
)
logger = logging.getLogger("GekOsint")
