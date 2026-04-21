
import threading
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
import time
import urllib.request
import os

logger = logging.getLogger("GekOsint.Server")

class HealthAndPagesHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self):
        if self.path in ("/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return
        super().do_GET()

    def log_message(self, format, *args):
        pass

def start_file_server(port, pages_dir):
    try:
        def run_server():
            server = HTTPServer(('0.0.0.0', port), lambda *args, **kwargs: HealthAndPagesHandler(*args, directory=pages_dir, **kwargs))
            server.serve_forever()
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        logger.info(f"[OK] Servidor HTTP activo en :{port}")
        return True
    except Exception as e:
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
