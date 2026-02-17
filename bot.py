
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

def main():
    """
    Punto de entrada principal del bot.
    Usa run_polling() para un manejo robusto del ciclo de vida y reconexiones.
    """
    print("\n🛡️  Iniciando GekOsint v4.0...")
    
    # Validación básica del token
    if not BOT_TOKEN or "tu_token" in BOT_TOKEN or len(BOT_TOKEN) < 20:
        print("\n❌ ERROR CRÍTICO: Token no configurado.")
        print("   1. Crea un archivo llamado '.env' (sin comillas) en esta carpeta.")
        print("   2. Escribe dentro: GEKOSINT_TOKEN=tu_token_de_botfather")
        print("   3. Guarda y vuelve a ejecutar.\n")
        return

    try:
        # Construir la aplicación
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Registrar Handlers (Manejadores de eventos)
        # Comandos básicos
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        
        # Interacciones con botones
        app.add_handler(CallbackQueryHandler(button_handler))
        
        # Manejo de archivos (para metadatos, etc.)
        app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
        
        # Manejo de mensajes de texto (para búsqueda de IP, Username, etc.)
        # Importante: ~filters.COMMAND evita que procese /start como texto
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print("✅ Conexión establecida con Telegram.")
        print("🚀 El bot está ejecutándose. Ve a Telegram y usa /start")
        print("   (Presiona Ctrl+C en esta ventana para detenerlo)\n")
        
        # Ejecutar polling (bloqueante, maneja reconexiones y señales automáticamente)
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error fatal al iniciar el bot: {e}")
        print(f"\n❌ Error fatal: {e}")

if __name__ == '__main__':
    # Fix crítico para Windows: Establecer política Y asegurar que run_polling pueda crear/usar el loop
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        # run_polling() maneja su propio loop, pero en algunos entornos de Windows
        # necesita que no haya conflicto con un loop existente.
        main()
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido correctamente.")
    except RuntimeError as e:
        if "There is no current event loop" in str(e):
            # Fallback para entornos donde get_event_loop falla
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            main()
        else:
            raise e
