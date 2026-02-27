# -*- coding: utf-8 -*-
import logging
import sys
import asyncio
import os
import signal
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN, PAGES_DIR, PUBLIC_URL
from handlers.commands import start, help_command, button_handler, message_handler, document_handler

if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

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
        logger.info(f"[OK] Servidor HTTP en puerto {port}")
        print(f"[OK] Servidor HTTP activo en :{port} (health + pages)")
        return server
    except Exception as e:
        logger.warning(f"Servidor HTTP no disponible: {e}")
        return None

def start_keep_alive():
    if not KEEP_ALIVE_URL:
        logger.info("Sin PUBLIC_URL, keep-alive desactivado")
        return

    ping_url = KEEP_ALIVE_URL.rstrip("/") + "/health"

    def ping_loop():
        import urllib.request
        while True:
            time.sleep(240)
            try:
                urllib.request.urlopen(ping_url, timeout=10)
                logger.debug(f"Keep-alive ping OK: {ping_url}")
            except Exception as e:
                logger.debug(f"Keep-alive ping fail: {e}")

    t = threading.Thread(target=ping_loop, daemon=True)
    t.start()
    logger.info(f"[OK] Keep-alive activo (ping cada 4 min a {ping_url})")
    print(f"[OK] Keep-alive activo (cada 4 min)")

async def run_bot():
    logger.info("Iniciando GekOsint v5.0...")
    print("\n[*] Iniciando GekOsint v5.0 (Cloud-Ready Mode)...")

    if IS_CLOUD:
        start_file_server(PORT)
    else:
        start_file_server(FILE_SERVER_PORT)

    if IS_CLOUD:
        start_keep_alive()

    if not BOT_TOKEN or "tu_token" in BOT_TOKEN or len(BOT_TOKEN) < 20:
        print("\n[X] ERROR: Token no configurado.")
        print("   Configura GEKOSINT_TOKEN en .env o en variables de entorno")
        logger.error("BOT_TOKEN no configurado. Abortando.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.IMAGE | filters.PHOTO, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    env_name = 'Cloud' if IS_CLOUD else ('Windows' if sys.platform == 'win32' else 'Linux')
    print(f"[OK] Conexion establecida con Telegram.")
    print(f"[*] El bot esta ejecutandose. Ve a Telegram y usa /start")
    print(f"    Entorno: {env_name}")
    print("    (Presiona Ctrl+C para detenerlo)\n")

    if IS_CLOUD and WEBHOOK_URL:
        logger.info(f"Usando webhook: {WEBHOOK_URL}")
        print(f"[*] Modo: Webhook en puerto {PORT}")

        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=f"{WEBHOOK_URL}/webhook",
            drop_pending_updates=True
        )
    else:
        print("[*] Modo: Long Polling")

        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            stop_signal = asyncio.Event()

            if sys.platform != 'win32':
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, stop_signal.set)

            try:
                await stop_signal.wait()
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            finally:
                logger.info("Deteniendo servicios...")
                print("\n[*] Deteniendo servicios...")
                if app.updater.running:
                    await app.updater.stop()
                if app.running:
                    await app.stop()
                    await app.shutdown()
                print("[OK] Bot detenido correctamente.")

def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        print(f"\n[ERROR] Error fatal: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
