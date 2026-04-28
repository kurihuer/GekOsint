# -*- coding: utf-8 -*-
"""
Formateadores de resultados para Telegram (HTML parse_mode).
Cada función recibe un dict y retorna un string HTML listo para enviar.
"""

import urllib.parse


# ── Helpers de presentación ───────────────────────────────────────────────────

def render_header(title: str) -> str:
    return (
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"  🛡️ <b>{title}</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
    )

def render_section(title: str) -> str:
    return f"\n🔹 <b>{title}</b>\n"

def _risk_bar(score: int) -> str:
    filled = min(score, 100) // 10
    return "[" + "█" * filled + "░" * (10 - filled) + "]"

def _risk_level_icon(level: str) -> str:
    return {"ALTO": "🔴", "MEDIO": "🟡", "BAJO": "🟢"}.get(level.upper(), "⚪")

def render_missing_keys(data: dict) -> str:
    keys = [k for k in (data.get("missing_keys") or []) if k]
    if not keys:
        return ""
    txt  = render_section("APIs OPCIONALES NO CONFIGURADAS")
    txt += "⚙️ " + ", ".join(f"<code>{k}</code>" for k in keys) + "\n"
    txt += "<i>Añádelas a .env para resultados más completos.</i>\n"
    return txt


# ── IP Intelligence ───────────────────────────────────────────────────────────

def format_ip_result(data: dict) -> str:
    if not data:
        return "❌ Error analizando IP."
    if "error" in data:
        return f"❌ {data['error']}"

    risk_score = data.get("risk_score", 0)
    txt  = render_header("IP INTELLIGENCE")
    txt += f"<b>Target:</b> <code>{data['ip']}</code>\n"
    txt += render_missing_keys(data)

    txt += render_section("UBICACIÓN GEOGRÁFICA")
    txt += f"🏙️ <b>Ciudad:</b> {data['city']}, {data['country']}\n"
    txt += f"📮 <b>Código Postal:</b> {data.get('zip', 'N/A')}\n"
    txt += f"🕐 <b>Zona Horaria:</b> {data.get('timezone', 'N/A')}\n"
    txt += f"📍 <b>Coordenadas:</b> <code>{data['coords']}</code>\n"

    txt += render_section("RED / ISP")
    txt += f"🏢 <b>ISP:</b> {data['isp']}\n"
    txt += f"🏗️ <b>Organización:</b> {data.get('org', 'N/A')}\n"
    txt += f"🔢 <b>ASN:</b> <code>{data.get('asn', 'N/A')}</code>\n"
    txt += f"🔗 <b>Hostname:</b> {data.get('hostname', 'N/A')}\n"
    txt += f"🔄 <b>Reverse DNS:</b> {data.get('rdns', 'N/A')}\n"

    txt += render_section("WHOIS / REGISTRO")
    txt += f"🌐 <b>Red:</b> {data.get('net_name', 'N/A')}\n"
    txt += f"📊 <b>Rango:</b> <code>{data.get('net_range', 'N/A')}</code>\n"
    txt += f"📩 <b>Abuso:</b> {data.get('abuse_contact', 'N/A')}\n"

    txt += render_section("SEGURIDAD & REPUTACIÓN")
    txt += f"📡 <b>Tipo:</b> {data['type']}\n"
    txt += f"🔒 <b>Proxy/VPN:</b> {data['proxy']}\n"
    txt += f"⚠️ <b>Riesgo:</b> {_risk_bar(risk_score)} {data['risk']} ({risk_score}/100)\n"
    if data.get("risk_factors"):
        txt += f"🚩 <b>Factores:</b> {', '.join(data['risk_factors'])}\n"
    if data.get("blacklisted"):
        txt += f"🚫 <b>Blacklist:</b> SÍ — {data.get('threat_type', '?')} ({data.get('abuse_reports', 0)} reportes)\n"
    else:
        txt += "✅ <b>Blacklist:</b> No encontrada\n"

    ports = data.get("open_ports", [])
    if ports and ports != ["Ninguno detectado"]:
        txt += render_section("PUERTOS ABIERTOS (Shodan)")
        txt += " | ".join(f"<code>{p}</code>" for p in ports[:10]) + "\n"

    txt += render_section("MAPA Y OSINT")
    txt += f"🗺️ <a href='{data['map_url']}'>Abrir en Google Maps</a>\n"
    osint = data.get("osint_links", {})
    if osint:
        txt += " | ".join(f"<a href='{url}'>{name}</a>" for name, url in osint.items()) + "\n"

    return txt


# ── Phone Intelligence ────────────────────────────────────────────────────────

def format_phone_result(data: dict) -> str:
    if "error" in data:
        return f"❌ {data['error']}"

    risk_level = data.get("risk_level", "BAJO")
    risk_icon  = _risk_level_icon(risk_level)

    txt  = render_header("PHONE INTELLIGENCE")
    txt += f"📞 <b>Número:</b> <code>{data['number']}</code>\n"
    txt += render_missing_keys(data)

    # ── Identificación básica ─────────────────────────────────────────────
    txt += render_section("IDENTIFICACIÓN")
    txt += f"🌍 <b>País:</b> {data['country']}\n"
    txt += f"📡 <b>Operadora:</b> {data['carrier']}\n"
    if data.get("carrier_type") == "VOIP":
        txt += "  ⚠️ <i>VOIP / Número Virtual detectado</i>\n"
    txt += f"📱 <b>Tipo de línea:</b> {data['type']}\n"
    txt += f"🕐 <b>Zona Horaria:</b> {data.get('timezone', 'N/A')}\n"
    if data.get("region"):
        txt += f"📍 <b>Área/Lada:</b> {data['region']}\n"

    # ── Caller ID ─────────────────────────────────────────────────────────
    txt += render_section("CALLER ID")
    if data.get("caller_name"):
        txt += f"👤 <b>Nombre:</b> {data['caller_name']}"
        if data.get("caller_source"):
            txt += f" <i>({data['caller_source']})</i>"
        txt += "\n"
        if data.get("caller_type"):
            txt += f"🏷️ <b>Tipo caller:</b> {data['caller_type']}\n"
    else:
        txt += "👤 <b>Nombre:</b> No encontrado en bases de datos\n"

    # ── Spam / Reputación ─────────────────────────────────────────────────
    spam = data.get("spam", {})
    txt += render_section("SPAM & REPUTACIÓN")
    if spam.get("reported"):
        txt += f"🚨 <b>Estado:</b> REPORTADO COMO SPAM\n"
        total = spam.get("total_reports", 0)
        if total:
            txt += f"📊 <b>Total reportes:</b> {total}\n"
        if spam.get("type"):
            txt += f"🏷️ <b>Categoría:</b> {spam['type']}\n"
        if spam.get("labels"):
            txt += f"🔖 <b>Etiquetas:</b> {', '.join(spam['labels'][:4])}\n"
        if spam.get("tellows_score"):
            ts = spam["tellows_score"]
            bar = "🔴" if ts >= 7 else "🟡" if ts >= 4 else "🟢"
            txt += f"📉 <b>Tellows Score:</b> {bar} {ts}/9\n"
        if spam.get("caller_type_tellows"):
            txt += f"📋 <b>Tipo (Tellows):</b> {spam['caller_type_tellows']}\n"
    else:
        txt += "✅ Sin reportes de spam en bases consultadas\n"

    pres = data.get("presence", {}) or {}
    if pres:
        txt += render_section("PRESENCIA (HEURÍSTICA)")
        wa = pres.get("whatsapp_registered")
        if wa is True:
            txt += "💚 <b>WhatsApp:</b> Probable registrado\n"
        elif wa is False:
            txt += "💚 <b>WhatsApp:</b> No registrado\n"
        else:
            txt += "💚 <b>WhatsApp:</b> No se pudo determinar\n"

    # ── Riesgo consolidado ────────────────────────────────────────────────
    flags = data.get("risk_flags", [])
    txt += render_section("EVALUACIÓN DE RIESGO")
    txt += f"{risk_icon} <b>Nivel:</b> {risk_level}\n"
    if flags:
        for f in flags:
            txt += f"  ⚠️ {f}\n"
    else:
        txt += "  ✅ Sin indicadores de riesgo\n"

    # ── Formatos ──────────────────────────────────────────────────────────
    txt += render_section("FORMATOS")
    txt += f"E.164:         <code>{data['number']}</code>\n"
    txt += f"Nacional:      <code>{data.get('national', 'N/A')}</code>\n"
    txt += f"Internacional: <code>{data.get('international', 'N/A')}</code>\n"
    txt += f"Válido: {'✅' if data.get('is_valid') else '❌'} | "
    txt += f"Posible: {'✅' if data.get('is_possible') else '❌'}\n"

    # ── Datos del país ────────────────────────────────────────────────────
    cd = data.get("country_data", {})
    if cd:
        txt += render_section("DATOS DEL PAÍS")
        if cd.get("flag") and cd.get("capital"):
            txt += f"🏴 <b>Capital:</b> {cd['flag']} {cd['capital']}\n"
        if cd.get("region"):
            txt += f"🌎 <b>Subregión:</b> {cd['region']}\n"
        if cd.get("population"):
            txt += f"👥 <b>Población:</b> {cd['population']:,}\n"
        if cd.get("languages"):
            txt += f"🗣️ <b>Idiomas:</b> {', '.join(cd['languages'][:2])}\n"
        if cd.get("currencies"):
            txt += f"💱 <b>Moneda:</b> {', '.join(cd['currencies'])}\n"
        if cd.get("map_url"):
            txt += f"📍 <a href='{cd['map_url']}'>Ver país en Maps</a>\n"
        if data.get("region_coords"):
            rc = data["region_coords"]
            txt += f"🏙️ <a href='{rc['map_url']}'>Ver área/ciudad en Maps</a>\n"

    # ── Geo del carrier (aproximada) ──────────────────────────────────────
    cgeo = data.get("carrier_geo")
    if cgeo:
        txt += render_section("GEO CARRIER (Referencia Operadora)")
        txt += f"🏢 <b>ISP registrado:</b> <code>{cgeo.get('ip', data.get('carrier_ip', 'N/A'))}</code>\n"
        txt += f"🏳️ <b>País del servidor:</b> {cgeo.get('country', 'N/A')}\n"
        txt += f"🏙️ <b>Ciudad del servidor:</b> {cgeo.get('city', 'N/A')}\n"
        txt += f"🔗 <b>ISP:</b> {cgeo.get('isp', 'N/A')}\n"
        if cgeo.get("map_url"):
            txt += f"<a href='{cgeo['map_url']}'>Ver en Maps</a>\n"
        txt += "<i>⚠️ Esta NO es la ubicación del usuario — es la del servidor del operador.</i>\n"

    # ── Contacto directo ──────────────────────────────────────────────────
    txt += render_section("CONTACTO DIRECTO")
    txt += f"<a href='{data.get('whatsapp', '#')}'>💬 WhatsApp</a>\n"
    if data.get("telegram_search"):
        txt += f"<a href='{data['telegram_search']}'>✈️ Telegram (búsqueda)</a>\n"
        txt += "<i>Nota: Telegram no permite abrir chat por número con un link público si el usuario no tiene username o lo tiene privado.</i>\n"

    # ── Links OSINT ───────────────────────────────────────────────────────
    links = data.get("osint_links", [])
    if links:
        txt += render_section("VERIFICAR EN")
        txt += " | ".join(f"<a href='{l['url']}'>{l['name']}</a>" for l in links) + "\n"

    socials = data.get("social_search_links", [])
    if socials:
        txt += render_section("BÚSQUEDA EN REDES (DORKS)")
        txt += " | ".join(f"<a href='{l['url']}'>{l['name']}</a>" for l in socials) + "\n"

    return txt


# ── IP extra en consulta de teléfono ──────────────────────────────────────────

def _format_ip_intel_block(data: dict, ip_intel: dict, ip_target: str | None) -> str:
    """Bloque extra cuando el usuario adjuntó IP/dominio a la búsqueda de teléfono."""
    if not ip_intel or "error" in ip_intel:
        return ""
    txt  = render_section("IP ADJUNTA — ANÁLISIS")
    if ip_target:
        txt += f"🎯 <b>Entrada:</b> <code>{ip_target}</code>\n"
    txt += f"🌐 <b>IP resuelta:</b> <code>{ip_intel.get('ip', 'N/A')}</code>\n"
    txt += f"📍 <b>Ubicación:</b> {ip_intel.get('city', 'N/A')}, {ip_intel.get('country', 'N/A')}\n"
    txt += f"🏢 <b>ISP:</b> {ip_intel.get('isp', 'N/A')}\n"
    rs = ip_intel.get("risk_score", 0)
    txt += f"⚠️ <b>Riesgo:</b> {_risk_bar(rs)} {ip_intel.get('risk', 'N/A')} ({rs}/100)\n"
    if ip_intel.get("proxy"):
        txt += f"🔒 <b>Proxy/VPN:</b> {ip_intel['proxy']}\n"
    if ip_intel.get("map_url"):
        txt += f"<a href='{ip_intel['map_url']}'>Abrir en Maps</a>\n"
    return txt


def format_phone_result_with_ip(data: dict) -> str:
    """Extiende format_phone_result añadiendo el bloque de IP si está presente."""
    base = format_phone_result(data)
    ipi  = data.get("ip_intel")
    if isinstance(ipi, dict) and ipi:
        base += _format_ip_intel_block(data, ipi, data.get("ip_intel_target"))
    return base


# ── Username Search ───────────────────────────────────────────────────────────

def format_username_result(username: str, found: list, telegram_data: dict = None) -> str:
    txt  = render_header("USERNAME SEARCH")
    txt += f"🔎 <b>Target:</b> <code>{username}</code>\n"

    if telegram_data:
        tg = telegram_data
        txt += render_section("TELEGRAM")
        if tg.get("exists"):
            txt += "✅ <b>Estado:</b> Encontrado\n"
            if tg.get("name"):
                txt += f"👤 <b>Nombre:</b> {tg['name']}\n"
            txt += f"🏷️ <b>Tipo:</b> {tg.get('type', 'Desconocido')}\n"
            if tg.get("id"):
                txt += f"🆔 <b>ID:</b> <code>{tg['id']}</code>\n"
            if tg.get("members"):
                m = f"{tg['members']:,}" if isinstance(tg["members"], int) else str(tg["members"])
                txt += f"👥 <b>Miembros:</b> {m}\n"
            if tg.get("bio"):
                bio = tg["bio"][:150] + "…" if len(tg["bio"]) > 150 else tg["bio"]
                txt += f"📝 <b>Bio:</b> {bio}\n"
            flags = []
            if tg.get("is_verified"): flags.append("✅ Verificado")
            if tg.get("is_bot"):      flags.append("🤖 Bot")
            if tg.get("is_scam"):     flags.append("🚨 SCAM")
            if tg.get("is_fake"):     flags.append("⚠️ FAKE")
            if flags:
                txt += f"🚩 <b>Flags:</b> {' | '.join(flags)}\n"
            url  = tg.get("url") or f"https://t.me/{tg.get('username','').lstrip('@')}"
            deep = f"tg://resolve?domain={tg.get('username','').lstrip('@')}"
            txt += f"<a href='{url}'>Abrir (Web)</a> | <a href='{deep}'>Abrir (App)</a>\n"
        else:
            txt += "❌ <b>Estado:</b> No encontrado / Privado\n"

    if found:
        txt += render_section(f"REDES SOCIALES — {len(found)} encontradas")
        for site, url in found:
            txt += f"  ✅ <a href='{url}'>{site}</a>\n"
    else:
        txt += render_section("REDES SOCIALES")
        txt += "Sin perfiles encontrados en esta búsqueda.\n"

    txt += render_section("BÚSQUEDA AVANZADA")
    q = username
    txt += f"<a href='https://www.google.com/search?q=%22{q}%22'>Google</a>"
    txt += f" | <a href='https://web.archive.org/web/*/https://*/{q}'>Wayback</a>"
    txt += f" | <a href='https://whatsmyname.app/?q={q}'>WhatsMyName</a>"
    txt += f" | <a href='https://namechk.com/'>Namechk</a>\n"

    return txt


# ── Email Intelligence ────────────────────────────────────────────────────────

def format_email_result(data: dict) -> str:
    if "error" in data:
        return f"❌ {data['error']}"

    rep = data.get("reputation", "").upper()
    rep_icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(rep, "⚪")

    txt  = render_header("EMAIL INTELLIGENCE")
    txt += f"📧 <b>Target:</b> <code>{data['email']}</code>\n"
    txt += render_missing_keys(data)

    txt += render_section("REPUTACIÓN & VALIDACIÓN")
    txt += f"{rep_icon} <b>Reputación:</b> {rep}\n"
    txt += f"🗑️ <b>Desechable:</b> {'🔴 SÍ' if data['disposable'] else '✅ No'}\n"
    txt += f"⚠️ <b>Sospechoso:</b> {'🔴 SÍ' if data.get('suspicious') else '✅ No'}\n"
    txt += f"💧 <b>Filtrado en breaches:</b> {'🚨 SÍ' if data.get('leaked') else '✅ No'}\n"

    local = data.get("local_analysis", {})
    if local and (local.get("possible_name") or local.get("possible_year")):
        txt += render_section("ANÁLISIS DEL ALIAS")
        txt += f"🏷️ <b>Proveedor:</b> {data.get('provider', 'N/A')}\n"
        if local.get("possible_name"):
            txt += f"👤 <b>Posible nombre:</b> {local['possible_name']}\n"
        if local.get("possible_year"):
            txt += f"📅 <b>Posible año:</b> {local['possible_year']}\n"
        if local.get("has_plus"):
            txt += f"🔖 <b>Alias (+tag):</b> base = <code>{local.get('base_email', 'N/A')}</code>\n"

    gravatar = data.get("gravatar", {})
    if gravatar.get("exists"):
        txt += f"\n🖼️ <b>Gravatar:</b> <a href='{gravatar['profile']}'>Perfil encontrado</a>\n"

    txt += render_section("INFRAESTRUCTURA DNS")
    txt += f"🌐 <b>Dominio:</b> {data['domain']}\n"
    if data.get("domain_age"):
        txt += f"📅 <b>Registrado:</b> {data['domain_age']}\n"
    mx = data.get("mx_records", [])
    if mx:
        txt += f"📬 <b>MX servers:</b> {' | '.join(mx[:3])}\n"
    sec = data.get("dns_security", {})
    if sec:
        txt += f"🛡️ <b>SPF:</b> {'✅' if sec.get('spf') else '❌'} | "
        txt += f"<b>DMARC:</b> {'✅' if sec.get('dmarc') else '❌'}\n"

    breaches = data.get("breaches", [])
    txt += render_section("BRECHAS DE DATOS")
    if breaches:
        txt += f"🚨 Encontrado en <b>{len(breaches)}</b> brechas conocidas:\n"
        for b in breaches[:10]:
            txt += f"  💀 {b}\n"
        if len(breaches) > 10:
            txt += f"  <i>…y {len(breaches) - 10} más</i>\n"
    else:
        txt += "✅ No encontrado en brechas conocidas\n"

    links = data.get("links", {})
    txt += render_section("VERIFICAR EN")
    _link_labels = {
        "haveibeenpwned": "HIBP", "intelx": "IntelX",
        "dehashed": "DeHashed", "emailrep": "EmailRep",
        "hunter": "Hunter", "google_dork": "Google",
    }
    parts = [f"<a href='{links[k]}'>{v}</a>" for k, v in _link_labels.items() if links.get(k)]
    txt += " | ".join(parts) + "\n"

    return txt


# ── EXIF Metadata ─────────────────────────────────────────────────────────────

def format_exif_result(data: dict) -> str:
    if not data or "error" in data:
        return "⚠️ No se encontraron metadatos EXIF o el archivo es inválido."

    txt = render_header("EXIF METADATA")

    device = data.get("device", {})
    make   = device.get("Make", "")
    model  = device.get("Model", "N/A")
    txt += f"📱 <b>Dispositivo:</b> {make} {model}\n"
    txt += f"📅 <b>Fecha captura:</b> {device.get('DateTimeOriginal', 'N/A')}\n"
    txt += f"🖼️ <b>Resolución:</b> {data.get('basic', {}).get('Size', 'N/A')}\n"
    if device.get("Software"):
        txt += f"💾 <b>Software:</b> {device['Software']}\n"

    cam_fields = ["FocalLength", "FNumber", "ExposureTime", "ISOSpeedRatings", "Flash"]
    if any(device.get(f) for f in cam_fields):
        txt += render_section("CONFIGURACIÓN DE CÁMARA")
        if device.get("FocalLength"):
            txt += f"🔭 Focal: {device['FocalLength']} mm\n"
        if device.get("FNumber"):
            txt += f"🎯 Apertura: f/{device['FNumber']}\n"
        if device.get("ExposureTime"):
            txt += f"⏱️ Exposición: {device['ExposureTime']} s\n"
        if device.get("ISOSpeedRatings"):
            txt += f"📊 ISO: {device['ISOSpeedRatings']}\n"
        if device.get("Flash"):
            txt += f"⚡ Flash: {device['Flash']}\n"

    if data.get("coords"):
        txt += render_section("🚨 GPS DETECTADO")
        txt += f"📍 <b>Coordenadas:</b> <code>{data['coords']}</code>\n"
        txt += f"🗺️ <a href='{data.get('map', '#')}'>Ver ubicación exacta en Maps</a>\n"
        txt += "<b>⚠️ Esta imagen contiene la ubicación geográfica del momento de captura.</b>\n"
    else:
        txt += "\n📡 Sin datos GPS en esta imagen.\n"

    h = data.get("hash", {})
    if h:
        txt += render_section("HUELLAS (HASH)")
        if h.get("MD5"):
            txt += f"MD5: <code>{h['MD5']}</code>\n"
        if h.get("SHA256"):
            txt += f"SHA256: <code>{h['SHA256']}</code>\n"

    image_url = data.get("image_url")
    if image_url:
        enc = urllib.parse.quote(image_url, safe="")
        txt += render_section("BÚSQUEDA POR IMAGEN")
        txt += f"<a href='https://lens.google.com/uploadbyurl?url={enc}'>Google Lens</a>"
        txt += f" | <a href='https://yandex.com/images/search?rpt=imageview&url={enc}'>Yandex Images</a>"
        txt += f" | <a href='https://tineye.com/search?url={enc}'>TinEye</a>"
        txt += f" | <a href='https://www.bing.com/images/search?q=imgurl:{enc}&view=detailv2&iss=sbi'>Bing Visual Search</a>\n"

    all_tags = data.get("all_tags", {})
    if all_tags and len(all_tags) > 5:
        txt += render_section(f"TODOS LOS METADATOS ({len(all_tags)} tags)")
        count = 0
        for key, val in all_tags.items():
            if count >= 15:
                txt += f"<i>… y {len(all_tags) - 15} tags más</i>\n"
                break
            txt += f"{key}: <code>{str(val)[:60]}</code>\n"
            count += 1

    return txt


# ── WhatsApp OSINT ────────────────────────────────────────────────────────────

def format_whatsapp_result(data: dict) -> str:
    if not data or "error" in data:
        return f"❌ {data.get('error', 'Error desconocido')}"

    txt = render_header("WHATSAPP OSINT")
    txt += f"💚 <b>Número:</b> <code>{data.get('number', 'N/A')}</code>\n"
    txt += render_missing_keys(data)
    txt += "\n"

    reg = data.get("registered")
    if reg is True:
        txt += "✅ <b>Registrado en WhatsApp</b>\n"
    elif reg is False:
        txt += "❌ <b>No registrado en WhatsApp</b>\n"
    else:
        txt += "⚠️ <b>Estado desconocido</b>\n"

    if data.get("business") or data.get("is_business"):
        txt += "🏢 <b>Cuenta Business detectada</b>\n"

    name = data.get("name") or data.get("caller_name")
    if name:
        txt += f"👤 <b>Nombre:</b> {name}\n"
        src = data.get("caller_source")
        if src:
            txt += f"ℹ️ <i>Fuente:</i> {src}\n"

    if data.get("country") or data.get("carrier"):
        txt += render_section("TELÉFONO (OFFLINE)")
        if data.get("country"):
            txt += f"🌍 <b>Región/País:</b> {data.get('country')}\n"
        if data.get("carrier"):
            txt += f"📡 <b>Operadora:</b> {data.get('carrier')}\n"

    photo = data.get("profile_picture") or data.get("photo")
    if photo:
        txt += render_section("FOTO DE PERFIL")
        txt += f"🖼️ <a href='{photo}'>Ver foto de perfil</a>\n"
    else:
        txt += "\n🖼️ <b>Foto de perfil:</b> Privada o no disponible\n"

    if data.get("about"):
        txt += f"📝 <b>Estado/About:</b> {data['about']}\n"

    spam = data.get("spam", {})
    txt += render_section("REPORTE SPAM")
    total = spam.get("total_reports", 0)
    if total > 0:
        txt += f"🚨 <b>Reportes totales:</b> {total}\n"
        if spam.get("sources"):
            txt += f"📊 <b>Fuentes:</b> {', '.join(spam['sources'])}\n"
        if spam.get("labels"):
            txt += f"🏷️ <b>Etiquetas:</b> {', '.join(spam['labels'])}\n"
    else:
        txt += "✅ Sin reportes de spam\n"

    txt += render_section("CONTACTO DIRECTO")
    txt += f"<a href='{data['wa_link']}'>Abrir perfil</a> | "
    txt += f"<a href='{data['wa_msg']}'>Enviar mensaje</a>\n"
    if data.get("tg_search"):
        txt += f"<a href='{data['tg_search']}'>Telegram (búsqueda)</a>\n"

    links = data.get("links", {})
    _lmap = {
        "truecaller": "Truecaller", "getcontact": "GetContact",
        "syncme": "Sync.me", "numbway": "Numbway",
        "tellows": "Tellows", "google_dork": "Google",
    }
    txt += render_section("VERIFICAR EN")
    parts = [f"<a href='{links[k]}'>{v}</a>" for k, v in _lmap.items() if links.get(k)]
    txt += " | ".join(parts) + "\n"

    return txt


# ── DNS / Domain ──────────────────────────────────────────────────────────────

def format_dns_result(data: dict) -> str:
    if not data or "error" in data:
        return "❌ Error analizando el dominio."

    txt  = render_header("DOMAIN INTELLIGENCE")
    txt += f"🌐 <b>Dominio:</b> <code>{data['domain']}</code>\n"

    if data.get("a_records"):
        txt += render_section("REGISTROS A (IPs asignadas)")
        for ip in data["a_records"][:6]:
            txt += f"📍 <code>{ip}</code>\n"

    if data.get("mx_records"):
        txt += render_section("REGISTROS MX (Correo)")
        for mx in data["mx_records"][:4]:
            txt += f"📬 <code>{mx}</code>\n"

    if data.get("ns_records"):
        txt += render_section("NAMESERVERS")
        for ns in data["ns_records"][:4]:
            txt += f"🔗 <code>{ns}</code>\n"

    sec = data.get("security", {})
    txt += render_section("SEGURIDAD DNS")
    txt += f"📧 <b>SPF:</b>   {'✅ Configurado' if sec.get('spf')   else '❌ No encontrado'}\n"
    txt += f"📛 <b>DMARC:</b> {'✅ Configurado' if sec.get('dmarc') else '❌ No encontrado'}\n"
    txt += f"🔑 <b>DNSSEC:</b>{'✅ Activo'      if sec.get('dnssec')else '❌ No activo'}\n"

    whois = data.get("whois", {})
    if whois:
        txt += render_section("WHOIS / REGISTRO")
        events = whois.get("events", {})
        if events.get("registration"):
            txt += f"📅 <b>Creado:</b> {events['registration']}\n"
        if events.get("expiration"):
            txt += f"⌛ <b>Expira:</b> {events['expiration']}\n"
        if whois.get("registrar"):
            txt += f"🏢 <b>Registrar:</b> {whois['registrar']}\n"
        if whois.get("status"):
            txt += f"🛡️ <b>Estado:</b> {str(whois['status'])[:60]}\n"

    d = data["domain"]
    txt += render_section("OSINT LINKS")
    txt += (
        f"<a href='https://who.is/whois/{d}'>WHOIS</a> | "
        f"<a href='https://securitytrails.com/domain/{d}'>SecurityTrails</a> | "
        f"<a href='https://censys.io/ipv4?q={d}'>Censys</a> | "
        f"<a href='https://viewdns.info/iphistory/?domain={d}'>IP History</a> | "
        f"<a href='https://www.shodan.io/search?query={d}'>Shodan</a>\n"
    )

    return txt


# ── People Search ─────────────────────────────────────────────────────────────

def format_people_result(data: dict) -> str:
    if not data:
        return "❌ Error en la búsqueda."
    if "error" in data:
        return f"❌ {data['error']}"

    txt  = render_header("PEOPLE SEARCH")
    txt += f"🧑 <b>Objetivo:</b> <code>{data['full_name']}</code>\n\n"
    if data.get("context"):
        txt += f"📌 <b>Contexto:</b> <code>{data['context']}</code>\n\n"

    variants = data.get("variants_checked", [])
    if variants:
        txt += f"🔄 <b>Variantes analizadas:</b> {len(variants)}\n"
        txt += f"<code>{', '.join(variants[:8])}</code>\n"

    profiles = data.get("social_profiles", [])
    if profiles:
        txt += render_section(f"PERFILES ENCONTRADOS ({len(profiles)})")
        by_site: dict = {}
        for p in profiles:
            by_site.setdefault(p["site"], []).append(p)
        for site, entries in list(by_site.items())[:12]:
            best = entries[0]
            txt += f"✅ <b>{site}</b> — @{best['username']}\n"
            txt += f"   <a href='{best['url']}'>{best['url']}</a>\n"
    else:
        txt += render_section("PERFILES SOCIALES")
        txt += "Sin perfiles encontrados con las variantes generadas.\n"
        cands = data.get("candidate_profiles", [])
        if cands:
            txt += render_section("POSIBLES USERNAMES (NO VERIFICADOS)")
            for p in cands[:10]:
                txt += f"🔗 <b>{p['site']}</b> — @{p['username']}\n"
                txt += f"   <a href='{p['url']}'>{p['url']}</a>\n"

    li = data.get("linkedin", {})
    if li.get("found"):
        txt += render_section("LINKEDIN")
        for url in li.get("profiles", [])[:3]:
            txt += f"🔗 <a href='{url}'>{url}</a>\n"

    dorks = data.get("dorks", {})
    if dorks:
        txt += render_section("BÚSQUEDAS RECOMENDADAS")
        for label, url in list(dorks.items())[:10]:
            txt += f"🔎 <a href='{url}'>{label}</a>\n"

    osint = data.get("osint_links", {})
    if osint:
        txt += render_section("BASES DE DATOS OSINT")
        for site, url in list(osint.items())[:10]:
            txt += f"📋 <a href='{url}'>{site}</a>\n"

    txt += "\n<i>⚠️ Uso exclusivamente para investigación ética y legal.</i>"
    return txt


# ── Geolocation ───────────────────────────────────────────────────────────────

def format_geoloc_coords(data: dict) -> str:
    txt  = render_header("GEOLOCALIZACIÓN")
    txt += f"📍 <b>Latitud:</b>  <code>{data['lat']}</code>\n"
    txt += f"📍 <b>Longitud:</b> <code>{data['lon']}</code>\n"
    txt += f"🗺️ <a href='{data['map_url']}'>Ver en Google Maps</a>\n"
    txt += f"\n<i>Tipo: {data.get('type', 'coordenadas')}</i>"
    return txt

def format_geoloc_ip(data: dict) -> str:
    if "error" in data:
        return f"❌ {data['error']}"
    txt  = render_header("GEOLOCALIZACIÓN IP")
    txt += f"🌐 <b>IP:</b> <code>{data['ip']}</code>\n"
    txt += render_section("UBICACIÓN")
    txt += f"🏳️ <b>País:</b>       {data.get('country', 'N/A')} ({data.get('country_code', 'N/A')})\n"
    txt += f"🗺️ <b>Región:</b>     {data.get('region', 'N/A')}\n"
    txt += f"🏙️ <b>Ciudad:</b>     {data.get('city', 'N/A')}\n"
    txt += f"📮 <b>C.P.:</b>       {data.get('zip', 'N/A')}\n"
    txt += f"🕐 <b>Zona Horaria:</b> {data.get('timezone', 'N/A')}\n"
    txt += render_section("PROVEEDOR")
    txt += f"🏢 <b>ISP:</b> {data.get('isp', 'N/A')}\n"
    txt += f"🏗️ <b>Org:</b> {data.get('org', 'N/A')}\n"
    txt += f"🔢 <b>AS:</b>  {data.get('as', 'N/A')}\n"
    txt += render_section("CARACTERÍSTICAS")
    txt += f"📱 <b>Móvil:</b>    {'✅' if data.get('mobile')  else '❌'}\n"
    txt += f"🖥️ <b>Hosting:</b>  {'✅' if data.get('hosting') else '❌'}\n"
    txt += f"🔒 <b>Proxy/VPN:</b>{'✅' if data.get('proxy')   else '❌'}\n"
    txt += f"\n🗺️ <a href='{data.get('map_url', '')}'>Ver en Maps</a>\n"
    return txt

def format_geoloc_webrtc(data: dict) -> str:
    result = data.get("result", {})
    txt  = render_header("ANÁLISIS WebRTC")
    txt += f"🔗 <b>URL:</b> <code>{data.get('url', '')}</code>\n\n"
    if result.get("leak_detected"):
        txt += "⚠️ <b>FUGA DETECTADA</b>\n"
        txt += f"📊 <b>Riesgo:</b> {result.get('risk', 'Medio')}\n"
        for p in result.get("patterns", []):
            txt += f"  — {p}\n"
    else:
        txt += "✅ <b>Sin fugas detectadas</b>\n"
    return txt

def format_wifi_scan(data: dict) -> str:
    if "error" in data:
        return f"❌ Error: {data['error']}"
    networks = data.get("networks", [])
    if not networks:
        return "📶 No se detectaron redes Wi-Fi."
    txt  = render_header("ESCÁNER Wi-Fi")
    txt += f"📡 <b>Redes encontradas:</b> {len(networks)}\n"
    txt += render_section("REDES CERCANAS")
    for i, net in enumerate(networks[:12], 1):
        ssid   = net.get("ssid", "Oculta")
        signal = net.get("signal", net.get("signal_dbm", "N/A"))
        bssid  = net.get("bssid", "N/A")
        enc    = net.get("encryption", "")
        txt += f"{i}. 🔹 <b>{ssid}</b>"
        if enc:
            txt += f" ({enc})"
        txt += f"\n   📶 Señal: {signal}  |  MAC: <code>{bssid}</code>\n"
    txt += f"\n<i>Fuente: {data.get('source', 'desconocida')}</i>"
    return txt
