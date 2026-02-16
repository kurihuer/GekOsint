
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
        await app.updater.start_polling()
        
        # Mantener la ejecución activa
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await app.stop()
            await app.shutdown()

if __name__ == '__main__':
    try:
        # Usar asyncio.run para asegurar que se cree y gestione un event loop limpio
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario.")
    except Exception as e:
        print(f"❌ Error crítico durante la ejecución: {e}")
