# -*- coding: utf-8 -*-
import logging
import sys
import os
import asyncio
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, AIORateLimiter
from config import BOT_TOKEN, PAGES_DIR, PUBLIC_URL
from handlers.commands import start, help_command, button_handler, message_handler, document_handler, admin_command
from utils.server import start_file_server, start_keep_alive
from telegram.error import Conflict, NetworkError

if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

logger = logging.getLogger(__name__)

IS_CLOUD = (
    os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or
    os.getenv("FLY_APP_NAME") or os.getenv("HEROKU_APP_NAME") or os.getenv("PORT")
)
WEBHOOK_URL      = os.getenv("WEBHOOK_URL", "")
PORT             = int(os.getenv("PORT", 8443))
FILE_SERVER_PORT = int(os.getenv("FILE_SERVER_PORT", 8000))
KEEP_ALIVE_URL   = PUBLIC_URL or os.getenv("KOYEB_PUBLIC_DOMAIN", "")

def build_app():
    async def error_handler(update, context):
        err = context.error
        if isinstance(err, Conflict):
            logger.warning("409 Conflict: otra instancia activa (Koyeb/Cloud). Ignorando.")
            return
        if isinstance(err, NetworkError):
            logger.warning(f"NetworkError transitorio: {err}")
            return
        if isinstance(err, TimeoutError):
            logger.warning("TimeoutError: la solicitud tardó demasiado.")
            return
        logger.error(f"Error no manejado: {err}", exc_info=err)

    builder = ApplicationBuilder().token(BOT_TOKEN)
    try:
        builder = builder.rate_limiter(AIORateLimiter())
    except Exception:
        pass
    app = builder.build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.IMAGE | filters.PHOTO, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app

def main():
    print("\n[*] Iniciando GekOsint v5.0 (Cloud-Ready Mode)...")
    logger.info("Iniciando GekOsint v5.0...")

    if not BOT_TOKEN or "tu_token" in BOT_TOKEN or len(BOT_TOKEN) < 20:
        print("\n[X] ERROR: Token no configurado.")
        print("   Configura GEKOSINT_TOKEN en .env o variables de entorno")
        logger.error("BOT_TOKEN no configurado. Abortando.")
        sys.exit(1)

    if IS_CLOUD:
        start_file_server(PORT, PAGES_DIR)
        start_keep_alive(KEEP_ALIVE_URL)
    else:
        start_file_server(FILE_SERVER_PORT, PAGES_DIR)

    app = build_app()

    env_name = 'Cloud' if IS_CLOUD else ('Windows' if sys.platform == 'win32' else 'Linux')
    print(f"[OK] Conexion establecida con Telegram.")
    print(f"[*] El bot esta ejecutandose. Ve a Telegram y usa /start")
    print(f"    Entorno: {env_name}")
    print("    (Presiona Ctrl+C para detenerlo)\n")

    try:
        # Python 3.14+ requiere event loop explícito
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if IS_CLOUD and WEBHOOK_URL:
            print(f"[*] Modo: Webhook en puerto {PORT}")
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path="webhook",
                webhook_url=f"{WEBHOOK_URL}/webhook",
                drop_pending_updates=True,
            )
        else:
            print("[*] Modo: Long Polling")
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
    except KeyboardInterrupt:
        pass
    finally:
        try:
            loop.close()
        except Exception:
            pass

    print("[OK] Bot detenido correctamente.")

if __name__ == '__main__':
    main()
