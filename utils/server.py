
import threading
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
import time
import urllib.request
import os

logger = logging.getLogger("GekOsint.Server")

# ── Estado global del file server ─────────────────────────────────────────────
# Se lee desde utils/apis.py (_deploy_local) para no devolver URLs muertas.
_FILE_SERVER_RUNNING = False
_FILE_SERVER_PORT: int | None = None


def is_file_server_running() -> bool:
    """True si el servidor HTTP local está activo y sirviendo /pages."""
    return _FILE_SERVER_RUNNING


def get_file_server_port() -> int | None:
    """Puerto en el que está escuchando el file server (o None)."""
    return _FILE_SERVER_PORT


class HealthAndPagesHandler(SimpleHTTPRequestHandler):
    # Forzar text/html para *.html (algunos clientes/proxies caen en octet-stream)
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".htm":  "text/html; charset=utf-8",
    }

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def _safe_path(self) -> str:
        """Bloquea path traversal antes de delegar al handler base."""
        # self.path llega URL-decoded por el handler base, así que normalizamos aquí.
        from urllib.parse import urlparse, unquote
        raw = unquote(urlparse(self.path).path)
        # Cualquier intento de subir niveles → rechazamos
        if ".." in raw.split("/"):
            return ""
        return raw

    def do_HEAD(self):
        if self.path in ("/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            return
        if not self._safe_path():
            self.send_response(403)
            self.end_headers()
            return
        super().do_HEAD()

    def do_GET(self):
        if self.path in ("/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return
        if not self._safe_path():
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass

def start_file_server(port, pages_dir):
    global _FILE_SERVER_RUNNING, _FILE_SERVER_PORT
    try:
        # Intentar abrir el socket sincrónicamente para detectar conflictos
        # (puerto ya en uso por el webhook, etc.) en vez de fallar en silencio.
        server = HTTPServer(
            ('0.0.0.0', port),
            lambda *args, **kwargs: HealthAndPagesHandler(*args, directory=pages_dir, **kwargs),
        )

        def run_server():
            try:
                server.serve_forever()
            except Exception as exc:
                global _FILE_SERVER_RUNNING
                _FILE_SERVER_RUNNING = False
                logger.warning(f"File server caído: {exc}")

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        _FILE_SERVER_RUNNING = True
        _FILE_SERVER_PORT = int(port)
        logger.info(f"[OK] Servidor HTTP activo en :{port}")
        return True
    except OSError as e:
        # Típicamente: puerto ya en uso (webhook ya lo tomó)
        _FILE_SERVER_RUNNING = False
        logger.warning(f"Servidor HTTP no pudo bindear en :{port} ({e}). "
                       f"Tracking caerá a Gist/Catbox/0x0.st.")
        return False
    except Exception as e:
        _FILE_SERVER_RUNNING = False
        logger.warning(f"Servidor HTTP no disponible: {e}")
        return False

def start_keep_alive(url):
    if not url:
        return

    ping_url = url.rstrip("/") + "/health"

    def ping_loop():
        while True:
            time.sleep(240)
            try:
                urllib.request.urlopen(ping_url, timeout=10)
                logger.debug(f"Keep-alive ping OK: {ping_url}")
            except Exception as e:
                logger.debug(f"Keep-alive ping fail: {e}")

    threading.Thread(target=ping_loop, daemon=True).start()
    logger.info(f"[OK] Keep-alive activo a {ping_url}")
