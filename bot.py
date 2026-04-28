# -*- coding: utf-8 -*-
"""
GekOsint v6.0 — Punto de entrada principal.
"""
import logging
import sys
import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, AIORateLimiter
)
from telegram.error import Conflict, NetworkError
from config import BOT_TOKEN, PAGES_DIR, PUBLIC_URL
from handlers.commands import (
    start, help_command, button_handler,
    message_handler, document_handler, admin_command
)
from utils.server import start_file_server, start_keep_alive

# ── UTF-8 en Windows ──────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        os.system("chcp 65001 >nul 2>&1")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("GekOsint.bot")

# ── Detección de entorno ──────────────────────────────────────────────────────
IS_CLOUD = bool(
    os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or
    os.getenv("FLY_APP_NAME") or os.getenv("HEROKU_APP_NAME") or os.getenv("PORT")
)
_RAW_WEBHOOK_URL = (os.getenv("WEBHOOK_URL", "") or "").strip()
if not _RAW_WEBHOOK_URL:
    _RAW_WEBHOOK_URL = (PUBLIC_URL or os.getenv("KOYEB_PUBLIC_DOMAIN", "") or "").strip()
if _RAW_WEBHOOK_URL and not _RAW_WEBHOOK_URL.startswith(("http://", "https://")):
    _RAW_WEBHOOK_URL = "https://" + _RAW_WEBHOOK_URL.lstrip("/")
WEBHOOK_URL      = _RAW_WEBHOOK_URL.rstrip("/")
PORT             = int(os.getenv("PORT", 8443))
FILE_SERVER_PORT = int(os.getenv("FILE_SERVER_PORT", 8000))
KEEP_ALIVE_URL   = PUBLIC_URL or os.getenv("KOYEB_PUBLIC_DOMAIN", "")


def build_app():
    async def error_handler(update, context):
        err = context.error
        if isinstance(err, Conflict):
            logger.warning("409 Conflict — otra instancia activa. Ignorando.")
            return
        if isinstance(err, NetworkError):
            logger.warning(f"NetworkError transitorio: {err}")
            return
        if isinstance(err, TimeoutError):
            logger.warning("TimeoutError en solicitud.")
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
    app.add_handler(CommandHandler("help",  help_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.IMAGE | filters.PHOTO, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app


def main():
    logger.info("Iniciando GekOsint v6.0…")
    print("\n[*] GekOsint v6.0 — Iniciando…")

    if not BOT_TOKEN or "tu_token" in BOT_TOKEN or len(BOT_TOKEN) < 20:
        print("\n[X] ERROR: Token no configurado.")
        print("    Configura GEKOSINT_TOKEN en .env o variables de entorno.")
        sys.exit(1)

    env_name = "Cloud" if IS_CLOUD else ("Windows" if sys.platform == "win32" else "Linux/Mac")
    use_webhook = bool(IS_CLOUD and WEBHOOK_URL)

    if IS_CLOUD:
        if not use_webhook:
            start_file_server(PORT, PAGES_DIR)
        keep_url = (KEEP_ALIVE_URL or "").strip()
        if keep_url and not keep_url.startswith(("http://", "https://")):
            keep_url = "https://" + keep_url.lstrip("/")
        if keep_url:
            start_keep_alive(keep_url)
    else:
        start_file_server(FILE_SERVER_PORT, PAGES_DIR)

    app = build_app()
    print(f"[OK] Conectado con Telegram.")
    print(f"[*]  Entorno: {env_name}")
    print(f"[*]  Bot listo — usa /start en Telegram")
    print("     (Ctrl+C para detener)\n")

    if use_webhook:
        logger.info(f"Modo Webhook en puerto {PORT}")
        print(f"[*] Modo: Webhook — {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=f"{WEBHOOK_URL}/webhook",
            drop_pending_updates=True,
        )
    else:
        logger.info("Modo Long Polling")
        print("[*] Modo: Long Polling")
        try:
            asyncio.run(app.bot.delete_webhook(drop_pending_updates=True))
        except Exception:
            pass
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

    print("\n[OK] Bot detenido correctamente.")


if __name__ == "__main__":
    main()
