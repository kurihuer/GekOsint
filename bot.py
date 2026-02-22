# -*- coding: utf-8 -*-
import logging
import sys
import asyncio
import os
import signal
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from handlers.commands import start, help_command, button_handler, message_handler, document_handler

# Configurar encoding UTF-8 para Windows (ignorado en Linux/Cloud)
if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Logger (basicConfig ya configurado en config.py)
logger = logging.getLogger(__name__)

# Detectar entorno cloud
IS_CLOUD = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or os.getenv("FLY_APP_NAME") or os.getenv("HEROKU_APP_NAME") or os.getenv("PORT")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", 8443))

async def run_bot():
    """
    Función principal asíncrona.
    Compatible con Windows local y Linux cloud (Railway/Render/Fly.io).
    """
    logger.info("Iniciando GekOsint v5.0...")
    print("\n[*] Iniciando GekOsint v5.0 (Cloud-Ready Mode)...")
    
    # Validación básica del token
    if not BOT_TOKEN or "tu_token" in BOT_TOKEN or len(BOT_TOKEN) < 20:
        print("\n❌ ERROR CRÍTICO: Token no configurado.")
        print("   Configura la variable de entorno GEKOSINT_TOKEN")
        print("   Local: crea archivo .env con GEKOSINT_TOKEN=tu_token")
        print("   Cloud: configura la variable en el panel del servicio\n")
        logger.error("BOT_TOKEN no configurado. Abortando.")
        return

    # Construir la aplicación
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Registrar Handlers (Manejadores de eventos)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    # Manejar tanto documentos como fotos para EXIF
    app.add_handler(MessageHandler(filters.Document.IMAGE | filters.PHOTO, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    env_name = 'Cloud' if IS_CLOUD else ('Windows' if sys.platform == 'win32' else 'Linux')
    print(f"[OK] Conexion establecida con Telegram.")
    print(f"[*] El bot esta ejecutandose. Ve a Telegram y usa /start")
    print(f"    Entorno: {env_name}")
    print("    (Presiona Ctrl+C para detenerlo)\n")

    if IS_CLOUD and WEBHOOK_URL:
        # === MODO WEBHOOK (Cloud) ===
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
        # === MODO POLLING (Local / Cloud sin webhook) ===
        print("[*] Modo: Long Polling")
        
        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            # Mantener el proceso vivo hasta señal de parada
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
