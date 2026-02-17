
import asyncio
import logging
import sys
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from handlers.commands import start, help_command, button_handler, message_handler, document_handler
from config import BOT_TOKEN

async def run_bot():
    """Inicializa y ejecuta el bot de forma asíncrona para compatibilidad con Python 3.14+"""
    print("🛡️ Iniciando GekOsint v4.0...")
    
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        print("❌ Error: BOT_TOKEN no configurado o inválido en .env")
        return

    # Configurar la aplicación
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Registro de Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    
    print("✅ Bot Online y esperando mensajes...")
    
    # En Python 3.14+, el manejo explícito del loop y el contexto asíncrono es más seguro
    async with app:
        await app.initialize()
        await app.start()
        
        # Iniciar polling con manejo robusto de errores
        try:
            await app.updater.start_polling(allowed_updates=["message", "callback_query", "inline_query"])
            
            # Bucle infinito eficiente para mantener vivo el proceso
            stop_signal = asyncio.Event()
            await stop_signal.wait()
            
        except (asyncio.CancelledError, KeyboardInterrupt):
            print("\n🛑 Deteniendo servicios...")
        finally:
            # Asegurar cierre limpio
            if app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()
                await app.shutdown()

if __name__ == '__main__':
    # Fix específico para Windows y asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        # Usar asyncio.run para asegurar que se cree y gestione un event loop limpio
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario.")
    except Exception as e:
        print(f"❌ Error crítico durante la ejecución: {e}")
