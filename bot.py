import logging
import os
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN, PAGES_DIR, PUBLIC_URL
from handlers.commands import start, help_command, button_handler, message_handler, document_handler, person_command

logger = logging.getLogger(__name__)

IS_CLOUD = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or os.getenv("FLY_APP_NAME") or os.getenv("HEROKU_APP_NAME") or os.getenv("PORT")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", 8443))
FILE_SERVER_PORT = int(os.getenv("FILE_SERVER_PORT", 8000))
KEEP_ALIVE_URL = PUBLIC_URL or os.getenv("KOYEB_PUBLIC_DOMAIN", "")

class HealthAndPagesHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PAGES_DIR, **kwargs)
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return
        super().do_GET()
    def log_message(self, format, *args):
        pass

def start_file_server(port):
    try:
        server = HTTPServer(('0.0.0.0', port), HealthAndPagesHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"[OK] Servidor HTTP activo en :{port} (health + pages)")
        return server
    except Exception as e:
        print(f"[WARN] Servidor HTTP no disponible: {e}")
        return None

def start_keep_alive():
    if not KEEP_ALIVE_URL:
        return
    ping_url = KEEP_ALIVE_URL.rstrip("/") + "/health"
    def ping_loop():
        import urllib.request
        while True:
            time.sleep(240)
            try:
                urllib.request.urlopen(ping_url, timeout=10)
            except Exception:
                pass
    threading.Thread(target=ping_loop, daemon=True).start()

def main():
    print("\n[*] Iniciando GekOsint v5.0")
    if IS_CLOUD:
        if WEBHOOK_URL:
            start_file_server(FILE_SERVER_PORT)
        else:
            start_file_server(PORT)
        start_keep_alive()
    else:
        start_file_server(FILE_SERVER_PORT)
    if not BOT_TOKEN or "tu_token" in BOT_TOKEN or len(BOT_TOKEN) < 20:
        print("[X] GEKOSINT_TOKEN no configurado")
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("person", person_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.IMAGE | filters.PHOTO, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("[OK] Conectado a Telegram")
    if IS_CLOUD and WEBHOOK_URL:
        print(f"[*] Modo: Webhook en puerto {PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=f"{WEBHOOK_URL.rstrip('/')}/webhook",
            drop_pending_updates=True
        )
    else:
        print("[*] Modo: Long Polling")
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

if __name__ == "__main__":
    main()
