
import logging
import sys
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from handlers.commands import start, help_command, button_handler, message_handler, document_handler

# Configurar logging para ver errores en consola
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_bot():
    """
    Función principal asíncrona.
    Maneja el ciclo de vida del bot manualmente para evitar conflictos de Event Loop en Windows.
    """
    print("\n🛡️  Iniciando GekOsint v4.0 (Async Mode)...")
    
    # Validación básica del token
    if not BOT_TOKEN or "tu_token" in BOT_TOKEN or len(BOT_TOKEN) < 20:
        print("\n❌ ERROR CRÍTICO: Token no configurado.")
        print("   1. Crea un archivo llamado '.env' (sin comillas) en esta carpeta.")
        print("   2. Escribe dentro: GEKOSINT_TOKEN=tu_token_de_botfather")
        print("   3. Guarda y vuelve a ejecutar.\n")
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
    
    print("✅ Conexión establecida con Telegram.")
    print("🚀 El bot está ejecutándose. Ve a Telegram y usa /start")
    print("   (Presiona Ctrl+C en esta ventana para detenerlo)\n")

    # Ciclo de vida manual: Init -> Start -> Start Polling -> Wait -> Stop
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Mantener el proceso vivo hasta que se reciba una señal de parada
        stop_signal = asyncio.Event()
        try:
            # Esperar indefinidamente (o hasta Ctrl+C que lanza CancelledError)
            await stop_signal.wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            print("\n🛑 Deteniendo servicios...")
            if app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()
                await app.shutdown()
            print("✅ Bot detenido correctamente.")

def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        print(f"\n❌ Error fatal: {e}")

if __name__ == '__main__':
    main()
