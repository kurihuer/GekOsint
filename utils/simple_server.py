
"""
Servidor HTTP simple para servir archivos HTML de tracking
"""
import http.server
import socketserver
import threading
import os
from config import PAGES_DIR

PORT = 8000

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PAGES_DIR, **kwargs)
    
    def log_message(self, format, *args):
        # Silenciar logs del servidor
        pass

def start_server():
    """Inicia el servidor HTTP en un thread separado"""
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print(f"[*] Servidor HTTP iniciado en puerto {PORT}")
        httpd.serve_forever()

def run_server_background():
    """Ejecuta el servidor en background"""
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
    return PORT
