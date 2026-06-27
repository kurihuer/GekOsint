# -*- coding: utf-8 -*-
"""
Formateadores de resultados para Telegram (HTML parse_mode).
Cada función recibe un dict y retorna un string HTML listo para enviar.
"""

import urllib.parse
from config import STRICT_LINKS


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
    osint = data.get("osint_links", {}) or {}
    if osint and not STRICT_LINKS:
        txt += " | ".join(f"<a href='{url}'>{name}</a>" for name, url in osint.items()) + "\n"
    elif osint and STRICT_LINKS:
        links = []
        if data.get("open_ports") and data.get("open_ports") != ["Ninguno detectado"]:
            if osint.get("Shodan"):
                links.append(("Shodan", osint["Shodan"]))
            if osint.get("Censys"):
                links.append(("Censys", osint["Censys"]))
        if data.get("blacklisted") or (data.get("abuse_reports", 0) or 0) > 0:
            for k in ("VirusTotal", "AbuseIPDB", "IPVoid"):
                if osint.get(k):
                    links.append((k, osint[k]))
        if any("GreyNoise" in str(x) for x in (data.get("risk_factors") or [])):
            if osint.get("GreyNoise"):
                links.append(("GreyNoise", osint["GreyNoise"]))
        if links:
            txt += " | ".join(f"<a href='{u}'>{n}</a>" for n, u in links) + "\n"

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
    pres = data.get("presence", {}) or {}
    if pres.get("whatsapp_registered") is True and data.get("whatsapp"):
        txt += f"<a href='{data['whatsapp']}'>💬 WhatsApp</a>\n"
    else:
        txt += "<i>💬 WhatsApp: no disponible (no registrado o no verificable).</i>\n"
    if data.get("telegram_search"):
        txt += f"<a href='{data['telegram_search']}'>✈️ Telegram (búsqueda)</a>\n"
        txt += "<i>Nota: Telegram no permite abrir chat por número con un link público si el usuario no tiene username o lo tiene privado.</i>\n"

    # ── Links OSINT ───────────────────────────────────────────────────────
    links = data.get("osint_links", []) or []
    spam = data.get("spam", {}) or {}
    caller_src = (data.get("caller_source") or "").lower()
    verified_links = []
    search_links = []
    for l in links:
        name = (l.get("name") or "").lower()
        if name == "truecaller":
            if "truecaller" in caller_src:
                verified_links.append(l)
        elif name == "spamcalls":
            if (spam.get("total_reports", 0) or 0) > 0 or (spam.get("labels") or []):
                verified_links.append(l)
        elif name == "tellows":
            if spam.get("tellows_score") is not None or spam.get("caller_type_tellows") or spam.get("reported"):
                verified_links.append(l)
        elif name == "google":
            search_links.append(l)

    if verified_links:
        txt += render_section("FUENTES CON EVIDENCIA")
        txt += " | ".join(f"<a href='{l['url']}'>{l['name']}</a>" for l in verified_links) + "\n"
    else:
        txt += render_section("FUENTES CON EVIDENCIA")
        txt += "<i>No hay fuentes con datos confirmados en esta consulta.</i>\n"

    if not STRICT_LINKS:
        socials = data.get("social_search_links", [])
        if socials:
            txt += render_section("BÚSQUEDA EN REDES (DORKS)")
            txt += " | ".join(f"<a href='{l['url']}'>{l['name']}</a>" for l in socials) + "\n"
        elif search_links:
            txt += render_section("BÚSQUEDA")
            txt += " | ".join(f"<a href='{l['url']}'>{l['name']}</a>" for l in search_links) + "\n"

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

    if not STRICT_LINKS:
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
    show = []
    if breaches or data.get("leaked"):
        for k, v in (("haveibeenpwned", "HIBP"), ("intelx", "IntelX"), ("dehashed", "DeHashed"), ("psbdmp", "PSBDMP")):
            if links.get(k):
                show.append((v, links[k]))
    if data.get("suspicious") or data.get("disposable") or rep in ("LOW", "MEDIUM"):
        if links.get("emailrep"):
            show.append(("EmailRep", links["emailrep"]))
    if not STRICT_LINKS:
        if links.get("hunter"):
            show.append(("Hunter", links["hunter"]))
        if links.get("google_dork"):
            show.append(("Google", links["google_dork"]))
    if show:
        txt += render_section("FUENTES CON EVIDENCIA")
        txt += " | ".join(f"<a href='{u}'>{n}</a>" for n, u in show) + "\n"

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
        enc       = urllib.parse.quote(image_url, safe="")
        has_face  = data.get("has_face", False)

        txt += render_section("🔍 BÚSQUEDA INVERSA POR IMAGEN")
        txt += (
            f"<a href='https://lens.google.com/uploadbyurl?url={enc}'>🔎 Google Lens</a>"
            f" | <a href='https://yandex.com/images/search?rpt=imageview&url={enc}'>🟡 Yandex</a>"
            f" | <a href='https://tineye.com/search?url={enc}'>👁️ TinEye</a>"
            f" | <a href='https://www.bing.com/images/search?q=imgurl:{enc}&view=detailv2&iss=sbi'>🔷 Bing</a>\n"
        )

        if has_face:
            txt += render_section("🧠 BÚSQUEDA FACIAL DETECTADA")
            txt += "⚠️ <b>Posible rostro humano detectado.</b>\n"
            txt += "Motores especializados en reconocimiento facial:\n\n"
            txt += (
                f"<a href='https://facecheck.id'>🕵️ FaceCheck.ID</a>"
                f" | <a href='https://pimeyes.com'>👤 PimEyes</a>"
                f" | <a href='https://search4faces.com'>🔬 Search4Faces</a>\n\n"
            )
            txt += (
                "<i>💡 Instrucciones: entrá al sitio, subí la imagen "
                "manualmente para la búsqueda facial.</i>\n"
            )
        else:
            txt += "<i>🧬 Sin indicios claros de rostro (skin tone check negativo).</i>\n"

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
    if reg is True:
        txt += f"<a href='{data['wa_link']}'>Abrir perfil</a> | "
        txt += f"<a href='{data['wa_msg']}'>Enviar mensaje</a>\n"
    else:
        txt += "<i>Link directo no disponible (no registrado o no verificable).</i>\n"
    if data.get("tg_search") and not STRICT_LINKS:
        txt += f"<a href='{data['tg_search']}'>Telegram (búsqueda)</a>\n"

    links = data.get("links", {})
    src = (data.get("caller_source") or "").lower()
    spam_sources = (spam.get("sources") or [])

    txt += render_section("FUENTES CON EVIDENCIA")
    parts = []
    if "truecaller" in src and links.get("truecaller"):
        parts.append(f"<a href='{links['truecaller']}'>Truecaller</a>")
    if "numbway" in src and links.get("numbway"):
        parts.append(f"<a href='{links['numbway']}'>Numbway</a>")
    if (total or 0) > 0 and links.get("spamcalls"):
        parts.append(f"<a href='{links['spamcalls']}'>SpamCalls</a>")
    if any("whocalledme" in s.lower() for s in spam_sources) and links.get("whocalledme"):
        parts.append(f"<a href='{links['whocalledme']}'>WhoCalledMe</a>")
    if any("tellows" in s.lower() for s in spam_sources) and links.get("tellows"):
        parts.append(f"<a href='{links['tellows']}'>Tellows</a>")
    if parts:
        txt += " | ".join(parts) + "\n"
    else:
        txt += "<i>No hay fuentes con datos confirmados en esta consulta.</i>\n"

    if links.get("google_dork") and not STRICT_LINKS:
        txt += render_section("BÚSQUEDA")
        txt += f"<a href='{links['google_dork']}'>Google</a>\n"

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

    if not STRICT_LINKS:
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
        if not STRICT_LINKS:
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

    if not STRICT_LINKS:
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


def format_github_recon(data: dict) -> str:
    """Formatea el resultado de modules.github_recon.github_recon()."""
    if not data.get("found"):
        errs = "\n".join(f"❌ {e}" for e in data.get("errors", []))
        return (
            "💻 <b>GitHub Recon</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{errs or '❌ No se encontró información.'}"
        )

    p = data["profile"]
    s = data["stats"]
    out: list[str] = []

    # ── Header ───────────────────────────────────────────────────────────────
    out.append(f"💻 <b>GitHub Recon — @{p.get('login', '?')}</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    if data.get("input_type") == "email":
        out.append(
            f"📧 <i>Email investigado:</i> <code>{data['input']}</code> "
            f"→ resuelto a <b>@{data.get('resolved_username')}</b>"
        )
    out.append("")

    # ── Perfil ───────────────────────────────────────────────────────────────
    out.append("👤 <b>Perfil</b>")
    if p.get("name"):
        out.append(f"   ▪️ Nombre: <b>{p['name']}</b>")
    if p.get("bio"):
        bio = p["bio"][:200].replace("<", "&lt;").replace(">", "&gt;")
        out.append(f"   ▪️ Bio: <i>{bio}</i>")
    if p.get("company"):
        out.append(f"   ▪️ Empresa: {p['company']}")
    if p.get("location"):
        out.append(f"   ▪️ Ubicación: 📍 {p['location']}")
    if p.get("email"):
        out.append(f"   ▪️ Email público: <code>{p['email']}</code>")
    if p.get("blog"):
        blog = p["blog"]
        if not blog.startswith("http"):
            blog = "https://" + blog
        out.append(f"   ▪️ Blog: {blog}")
    if p.get("twitter_username"):
        out.append(f"   ▪️ Twitter: @{p['twitter_username']}")
    if p.get("hireable"):
        out.append("   ▪️ ✅ Disponible para contratación")
    if p.get("created_at"):
        out.append(f"   ▪️ Cuenta creada: {p['created_at'][:10]}")
    if p.get("updated_at"):
        out.append(f"   ▪️ Última actividad: {p['updated_at'][:10]}")
    out.append("")

    # ── Estadísticas ─────────────────────────────────────────────────────────
    out.append("📊 <b>Estadísticas</b>")
    out.append(f"   ⭐ {s['total_stars']} stars · 🍴 {s['total_forks']} forks")
    out.append(f"   📦 {s['total_repos']} repos · 📝 {s['total_gists']} gists")
    out.append(f"   👥 {s['followers']} seguidores · sigue a {s['following']}")
    out.append("")

    # ── Emails leakeados (la joya) ───────────────────────────────────────────
    if data["leaked_emails"]:
        out.append(
            f"📨 <b>Emails leakeados en commits</b> "
            f"({s['unique_leaked_emails']} únicos)"
        )
        for email, info in list(data["leaked_emails"].items())[:8]:
            names = ", ".join(info["names"][:3])
            out.append(f"   ▪️ <code>{email}</code> ({info['count']}x)")
            if names:
                out.append(f"     └ Como: <i>{names}</i>")
        out.append(
            f"   <i>(De {s['events_analyzed']} eventos públicos analizados)</i>"
        )
        out.append("")
    else:
        out.append(
            "📨 <b>Emails en commits:</b> ninguno detectado "
            "(solo noreply o sin push events recientes)\n"
        )

    # ── Organizaciones ───────────────────────────────────────────────────────
    if data["orgs"]:
        out.append(f"🏢 <b>Organizaciones</b> ({len(data['orgs'])})")
        for o in data["orgs"][:8]:
            login = o.get("login", "?")
            out.append(f"   ▪️ <a href='https://github.com/{login}'>{login}</a>")
        out.append("")

    # ── Top repos ────────────────────────────────────────────────────────────
    if data["repos"]:
        out.append("🔥 <b>Top repos por stars</b>")
        for r in data["repos"][:5]:
            stars = r.get("stargazers_count", 0)
            forks = r.get("forks_count", 0)
            lang = r.get("language") or "—"
            name = r.get("name", "?")
            url = r.get("html_url", "")
            desc = (r.get("description") or "").strip()
            desc = desc.replace("<", "&lt;").replace(">", "&gt;")[:90]
            fork_tag = " 🍴" if r.get("fork") else ""
            out.append(
                f"   <a href='{url}'><b>{name}</b></a>{fork_tag} "
                f"— ⭐ {stars} · 🍴 {forks} · {lang}"
            )
            if desc:
                out.append(f"     <i>{desc}</i>")
        out.append("")

    # ── Lenguajes ────────────────────────────────────────────────────────────
    if data["languages"]:
        items = list(data["languages"].items())[:6]
        langs_str = " · ".join(f"{l} ({c})" for l, c in items)
        out.append(f"💻 <b>Lenguajes:</b> {langs_str}\n")

    # ── Keys ─────────────────────────────────────────────────────────────────
    keys_line = []
    if s["ssh_keys_count"]:
        keys_line.append(f"🔑 SSH: {s['ssh_keys_count']}")
    if s["gpg_keys_count"]:
        keys_line.append(f"🔐 GPG: {s['gpg_keys_count']}")
    if keys_line:
        out.append(f"<b>Llaves públicas:</b> {' · '.join(keys_line)}\n")

    # ── Gists recientes ──────────────────────────────────────────────────────
    if data["gists"]:
        out.append(f"📝 <b>Gists públicos</b> ({len(data['gists'])} recientes)")
        for g in data["gists"][:3]:
            desc = (g.get("description") or "(sin descripción)").strip()
            desc = desc.replace("<", "&lt;").replace(">", "&gt;")[:60]
            url = g.get("html_url", "")
            out.append(f"   ▪️ <a href='{url}'>{desc}</a>")
        out.append("")

    # ── Footer ───────────────────────────────────────────────────────────────
    if data.get("errors"):
        for err in data["errors"]:
            out.append(f"<i>{err}</i>")

    out.append(f"🔗 <a href='{p.get('html_url', '')}'>Ver perfil completo en GitHub</a>")
    return "\n".join(out)


def format_ig_osint(data: dict) -> str:
    """Formatea el resultado de modules.ig_osint.ig_lookup()."""
    out: list[str] = []
    out.append(f"📷 <b>IG OSINT — @{data.get('input', '?')}</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━")

    if data.get("session"):
        out.append(f"🔐 <i>Sesión: {data['session']}</i>")
    out.append("")

    if not data.get("found"):
        for err in data.get("errors", []):
            out.append(f"❌ {err}")
        if data.get("recovery", {}).get("error"):
            out.append(f"❌ Recovery: {data['recovery']['error']}")
        return "\n".join(out)

    p = data.get("profile") or {}
    rec = data.get("recovery") or {}

    # ── Perfil base ──────────────────────────────────────────────────────────
    if p:
        out.append("👤 <b>Perfil</b>")
        if p.get("full_name"):
            name = p["full_name"].replace("<", "&lt;").replace(">", "&gt;")
            out.append(f"   ▪️ Nombre: <b>{name}</b>")
        if p.get("user_id"):
            out.append(f"   ▪️ User ID: <code>{p['user_id']}</code>")

        flags = []
        if p.get("is_verified"):    flags.append("✅ verificada")
        if p.get("is_private"):     flags.append("🔒 privada")
        if p.get("is_business"):    flags.append("🏢 business")
        if p.get("has_highlights"): flags.append("⭐ highlights")
        if flags:
            out.append(f"   ▪️ Estado: {' · '.join(flags)}")

        if p.get("business_category"):
            out.append(f"   ▪️ Categoría: {p['business_category']}")
        if p.get("biography"):
            bio = p["biography"][:240].replace("<", "&lt;").replace(">", "&gt;")
            out.append(f"   ▪️ Bio: <i>{bio}</i>")
        if p.get("external_url"):
            out.append(f"   ▪️ Link: {p['external_url']}")
        out.append("")

        # ── Stats ────────────────────────────────────────────────────────────
        out.append("📊 <b>Estadísticas</b>")
        out.append(
            f"   👥 {p.get('followers', 0):,} seguidores · "
            f"sigue a {p.get('followees', 0):,}"
        )
        out.append(
            f"   📷 {p.get('posts_count', 0):,} posts · "
            f"📺 {p.get('igtv_count', 0)} IGTV"
        )
        out.append("")

    # ── Recovery hints (la joya) ─────────────────────────────────────────────
    if rec.get("found"):
        out.append("🎯 <b>Recovery hints</b> (técnica Toutatis)")
        if rec.get("obfuscated_email"):
            out.append(f"   📧 Email: <code>{rec['obfuscated_email']}</code>")
        if rec.get("obfuscated_phone"):
            out.append(f"   📱 Phone: <code>{rec['obfuscated_phone']}</code>")
        out.append(
            "   <i>(Hints parciales del email/teléfono asociados al recovery)</i>"
        )
        out.append("")
    elif rec.get("error"):
        out.append(f"🎯 <b>Recovery hints:</b> <i>{rec['error']}</i>\n")

    # ── Posts recientes ──────────────────────────────────────────────────────
    posts = (p or {}).get("recent_posts") or []
    if posts:
        out.append(f"📸 <b>Últimos posts</b> ({len(posts)})")
        for i, post in enumerate(posts, 1):
            tipo = "🎥" if post.get("is_video") else "🖼️"
            date = (post.get("date") or "")[:10]
            likes = post.get("likes", 0)
            comments = post.get("comments", 0)
            out.append(
                f"   {i}. {tipo} <a href='{post['url']}'>{post['shortcode']}</a> "
                f"· {date} · ❤️ {likes:,} · 💬 {comments:,}"
            )
            if post.get("location"):
                loc = post["location"].replace("<", "&lt;").replace(">", "&gt;")
                out.append(f"      📍 <b>{loc}</b>")
            if post.get("caption"):
                cap = post["caption"][:80].replace("<", "&lt;").replace(">", "&gt;")
                out.append(f"      <i>{cap}</i>")
        out.append("")
    elif p and p.get("is_private"):
        out.append("🔒 <i>Perfil privado — no se pueden ver posts.</i>\n")

    # ── Errores no fatales ───────────────────────────────────────────────────
    for err in data.get("errors", []):
        out.append(f"⚠️ <i>{err}</i>")

    # ── Footer ───────────────────────────────────────────────────────────────
    if p:
        out.append(
            f"🔗 <a href='https://www.instagram.com/{p.get('username','')}/'>"
            f"Ver perfil en Instagram</a>"
        )
    return "\n".join(out)


def format_gmail_osint(data: dict) -> str:
    """Formatea el resultado de modules.gmail_osint.gmail_lookup()."""
    out: list[str] = []
    out.append(f"📧 <b>Gmail / Google OSINT — {data.get('input', '?')}</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    out.append(f"🔐 <i>Sesión: {data.get('session', 'anonymous')}</i>\n")

    if data.get("errors") and not data.get("found"):
        for e in data["errors"]:
            out.append(f"⚠️ {e}")

    if not data.get("found"):
        if data.get("recovery", {}).get("error"):
            out.append("❌ No se pudo verificar la cuenta.")
        else:
            out.append("❌ Cuenta no encontrada o sin datos públicos.")
        return "\n".join(out)

    rec = data.get("recovery") or {}
    prof = data.get("profile") or {}
    pics = data.get("pictures") or {}
    yt = data.get("youtube") or {}

    # ── Status ───────────────────────────────────────────────────────────────
    out.append("✅ <b>Cuenta encontrada</b>")
    flags = []
    if data.get("is_gmail"):  flags.append("Gmail")
    elif data.get("is_google"): flags.append("Google Workspace")
    if flags:
        out.append(f"   ▪️ Tipo: {' · '.join(flags)}")
    out.append("")

    # ── Recovery hints (la joya) ─────────────────────────────────────────────
    if rec.get("obfuscated_phone") or rec.get("obfuscated_email"):
        out.append("🎯 <b>Recovery hints</b>")
        if rec.get("obfuscated_phone"):
            out.append(f"   📱 Phone: <code>{rec['obfuscated_phone']}</code>")
        if rec.get("obfuscated_email"):
            out.append(f"   📧 Email recovery: <code>{rec['obfuscated_email']}</code>")
        out.append("   <i>(Hints parciales del recovery de Google)</i>\n")

    # ── Profile (con cookies) ────────────────────────────────────────────────
    if prof.get("found"):
        out.append("👤 <b>Perfil Google</b> (vía People API)")
        if prof.get("gaia_id"):
            out.append(f"   ▪️ Google ID: <code>{prof['gaia_id']}</code>")
        if prof.get("names"):
            for nm in prof["names"][:3]:
                nm_safe = nm.replace("<", "&lt;").replace(">", "&gt;")
                out.append(f"   ▪️ Nombre: <b>{nm_safe}</b>")
        if prof.get("photo_url"):
            out.append(f"   ▪️ <a href='{prof['photo_url']}'>Foto de perfil (HD)</a>")
        out.append("")

    # ── YouTube ──────────────────────────────────────────────────────────────
    if yt.get("found"):
        out.append(f"📺 <b>Posibles canales YouTube</b> ({len(yt['channels'])})")
        for ch in yt["channels"][:3]:
            out.append(f"   ▪️ <a href='{ch['url']}'>{ch['channel_id']}</a>")
        out.append("   <i>(Búsqueda heurística por handle del email)</i>\n")

    # ── Pictures (Gravatar) ──────────────────────────────────────────────────
    if pics.get("has_gravatar"):
        out.append(f"🖼️ <a href='{pics['gravatar']}'>Gravatar disponible</a>\n")

    # ── Análisis del dominio (útil para Workspace) ───────────────────────────
    dom = data.get("domain") or {}
    if dom.get("mail_provider"):
        out.append("🌐 <b>Dominio del email</b>")
        out.append(f"   ▪️ Dominio: <code>{dom.get('domain', '?')}</code>")
        out.append(f"   ▪️ Proveedor: <b>{dom['mail_provider']}</b>")
        if dom.get("is_workspace"):
            out.append("   ▪️ ✅ <i>Google Workspace confirmado</i>")
        if dom.get("mx_records"):
            out.append(f"   ▪️ MX: <code>{', '.join(dom['mx_records'][:2])}</code>")
        spf = dom.get("has_spf")
        dmarc = dom.get("has_dmarc")
        sec = []
        if spf:   sec.append("✅ SPF")
        elif spf is False: sec.append("❌ sin SPF")
        if dmarc: sec.append("✅ DMARC")
        elif dmarc is False: sec.append("❌ sin DMARC")
        if sec:
            out.append(f"   ▪️ Seguridad: {' · '.join(sec)}")
        out.append("")

    # Avisos no fatales
    for e in data.get("errors", []):
        out.append(f"<i>⚠️ {e}</i>")

    return "\n".join(out)


def format_fb_osint(data: dict) -> str:
    """Formatea el resultado de modules.fb_osint.fb_lookup()."""
    out: list[str] = []
    inp = data.get("input", "?")
    inp_type = data.get("input_type", "?")
    out.append(f"📘 <b>Facebook OSINT — {inp}</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    out.append(f"🔍 <i>Tipo de input: {inp_type}</i>")
    out.append(f"🔐 <i>Sesión: {data.get('session', 'anonymous')}</i>\n")

    if not data.get("found"):
        for e in data.get("errors", []):
            out.append(f"⚠️ {e}")
        if not data.get("errors"):
            out.append("❌ Cuenta no encontrada o sin datos públicos.")
        return "\n".join(out)

    rec = data.get("recovery") or {}

    # ── Status básico ────────────────────────────────────────────────────────
    out.append("✅ <b>Cuenta encontrada</b>")
    if data.get("display_name"):
        nm = data["display_name"].replace("<", "&lt;").replace(">", "&gt;")
        out.append(f"   ▪️ Nombre: <b>{nm}</b>")
    if data.get("user_id"):
        out.append(f"   ▪️ FB User ID: <code>{data['user_id']}</code>")
        out.append(
            f"   ▪️ Perfil: "
            f"<a href='https://www.facebook.com/{data['user_id']}'>"
            f"facebook.com/{data['user_id']}</a>"
        )
    out.append("")

    # ── Recovery hints ───────────────────────────────────────────────────────
    if rec.get("obfuscated_email") or rec.get("obfuscated_phone"):
        out.append("🎯 <b>Recovery hints</b>")
        if rec.get("obfuscated_email"):
            out.append(f"   📧 Email: <code>{rec['obfuscated_email']}</code>")
        if rec.get("obfuscated_phone"):
            out.append(f"   📱 Phone: <code>{rec['obfuscated_phone']}</code>")
        out.append("   <i>(Hints parciales del recovery de Facebook)</i>\n")
    else:
        # Meta migró el flujo de recovery a Bloks/CAA con payload encriptado
        # (cliente: com.bloks.www.caa.ar.search). Los hints ya no están en
        # el HTML — vienen por XHR async con `caa_core_data_encrypted`.
        # No replicable sin browser real (Playwright/Selenium).
        out.append("🎯 <b>Recovery hints:</b> ❌ no disponibles")
        out.append(
            "   <i>Meta migró el recovery a <b>Bloks/CAA</b> con payload "
            "encriptado en 2024. Los hints ya no están en el HTML inicial — "
            "se cargan por XHR async con cifrado de cliente que no se puede "
            "replicar desde un bot.</i>"
        )
        out.append(
            "   💡 <b>Alternativa:</b> probá <code>📷 IG OSINT</code> con el "
            "username — IG aún devuelve hints vía Toutatis. Muchas cuentas "
            "FB/IG están enlazadas y comparten el mismo email/teléfono.\n"
        )

    # ── Foto de perfil ───────────────────────────────────────────────────────
    # Prioridad: URL real del CDN (scontent.fbcdn.net) que sale del recovery,
    # porque graph.facebook.com/{id}/picture devuelve placeholder en blanco
    # para perfiles nuevos (IDs 615... post-2024).
    pic_urls = data.get("profile_pic_urls") or []
    real_pic = (rec or {}).get("profile_pic_url")
    if real_pic or (data.get("user_id") and pic_urls):
        out.append("🖼️ <b>Foto de perfil</b>")
        if real_pic:
            out.append(f"   ▪️ <a href='{real_pic}'>HD (CDN real)</a>")
        if pic_urls:
            label = "HD (graph fallback)" if real_pic else "HD (large)"
            out.append(f"   ▪️ <a href='{pic_urls[0]}'>{label}</a>")
        if len(pic_urls) > 1:
            out.append(f"   ▪️ <a href='{pic_urls[1]}'>Normal</a>")
        out.append("")

    # Errores no fatales
    for e in data.get("errors", []):
        if e:
            out.append(f"<i>⚠️ {e}</i>")

    return "\n".join(out)


def format_email_recon(data: dict) -> str:
    """Formatea el resultado de modules.email_recon.email_recon()."""
    out: list[str] = []
    out.append(f"📨 <b>Email Multi-Platform Recon — {data.get('input', '?')}</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━")

    if not data.get("valid"):
        for e in data.get("errors", []):
            out.append(f"❌ {e}")
        return "\n".join(out)

    found = data.get("found_in") or []
    checked = data.get("checked") or []

    out.append(f"🔍 Chequeado contra <b>{len(checked)} servicios</b>")
    out.append(f"✅ Encontrado en: <b>{len(found)}</b>\n")

    if found:
        out.append("📍 <b>Servicios donde el email está registrado</b>")
        for entry in found:
            line = f"   ▪️ <b>{entry['service']}</b>"
            if entry.get("hint"):
                line += f" — <code>{entry['hint']}</code>"
            out.append(line)
        out.append("")

    if data.get("hints"):
        out.append("🎯 <b>Hints adicionales</b>")
        for h in data["hints"]:
            out.append(f"   ▪️ {h}")
        out.append("")

    if not found:
        out.append("ℹ️ <i>Email no detectado en los servicios chequeados.</i>")
        out.append("   <i>Puede ser cuenta nueva o servicios no cubiertos.</i>")

    not_found = [s for s in checked if not any(f["service"] == s for f in found)]
    if not_found:
        out.append("\n<i>No registrado en: " + ", ".join(not_found) + "</i>")

    return "\n".join(out)


# TikTok OSINT template

def format_tiktok_osint(data: dict) -> str:
    if data.get("error"):
        username = data.get("username", "")
        url = f"https://www.tiktok.com/@{username}"
        blocked = data.get("_blocked", False)
        if blocked:
            base = (
                f"{render_header('TIKTOK OSINT')}"
                f"<b>@{username}</b>\n\n"
                f"TikTok bloquea IPs de servidor. No se pueden obtener datos automaticamente.\n\n"
                f"<b>Ver perfil completo:</b>\n"
                f"<a href='{url}'>{url}</a>\n\n"
                f"<i>Abre el link — el perfil carga completo en tu navegador.</i>"
            )
            if not STRICT_LINKS:
                google = f"https://www.google.com/search?q=tiktok+{username}"
                base += (
                    f"\n\n<b>Buscar en Google:</b>\n"
                    f"<a href='{google}'>tiktok {username}</a>"
                )
            return base
        return (
            "<b>TikTok OSINT</b>\n\n"
            + str(data["error"])
            + "\n\n"
            + f"<a href='{url}'>Ver perfil en TikTok</a>"
        )

    out = []
    out.append(render_header("TIKTOK OSINT"))

    username = data.get("username", "?")
    nickname = data.get("nickname", username)
    uid      = data.get("user_id", "")

    verified_badge = " (Verificado)" if data.get("verified") else ""
    private_badge  = " [Privada]"    if data.get("private")  else " [Publica]"
    out.append(f"<b>@{username}</b>{verified_badge}{private_badge}")
    out.append(f"<b>Nombre:</b> {nickname}")
    if uid:
        out.append(f"<b>User ID:</b> <code>{uid}</code>")
    out.append(f"Perfil: https://www.tiktok.com/@{username}")
    if data.get("avatar_url"):
        out.append(f"🖼️ <a href='{data['avatar_url']}'>Avatar (HD)</a>")
    out.append("")

    bio = (data.get("bio") or "").strip()
    if bio:
        out.append(render_section("BIO"))
        out.append(f"<i>{bio[:300]}</i>")
    if data.get("bio_link"):
        out.append(f"<b>Link en bio:</b> <code>{data['bio_link']}</code>")
    out.append("")

    exposure = data.get("exposure") or {}
    if any(exposure.get(k) for k in ("emails", "phones", "urls", "handles")):
        out.append(render_section("SEÑALES DE EXPOSICIÓN"))
        if exposure.get("emails"):
            out.append("📧 <b>Emails:</b> " + " | ".join(f"<code>{e}</code>" for e in exposure["emails"]))
        if exposure.get("phones"):
            out.append("📱 <b>Teléfonos:</b> " + " | ".join(f"<code>{p}</code>" for p in exposure["phones"]))
        if exposure.get("handles"):
            out.append("🏷️ <b>Handles:</b> " + " | ".join(f"@{h}" for h in exposure["handles"]))
        if exposure.get("urls"):
            out.append("🔗 <b>URLs:</b> " + " | ".join(f"<a href='{u}'>link</a>" for u in exposure["urls"][:4]))
        out.append("<i>Esto suele usarse para ingeniería social (phishing dirigido y suplantación).</i>")
        out.append("")

    out.append(render_section("ESTADISTICAS"))
    if data.get("followers") is None and data.get("following") is None:
        out.append("<i>No disponible (bloqueo por IP o perfil privado).</i>")
    else:
        out.append(f"<b>Seguidores:</b>    {data.get('followers','?')}")
        out.append(f"<b>Siguiendo:</b>     {data.get('following','?')}")
        out.append(f"<b>Likes totales:</b> {data.get('total_likes','?')}")
        out.append(f"<b>Videos:</b>        {data.get('video_count','?')}")

    eng = data.get("engagement_est")
    if eng:
        try:
            v = float(eng.strip("%"))
            em = "fuerte" if v >= 5 else ("normal" if v >= 2 else "bajo")
        except Exception:
            em = ""
        out.append(f"<b>Engagement est.:</b> {eng} ({em})")

    try:
        fr = int(data.get("_followers_raw", 0) or 0)
        if   fr >= 1_000_000: tier = "Mega-influencer (1M+)"
        elif fr >= 100_000:   tier = "Macro-influencer (100K+)"
        elif fr >= 10_000:    tier = "Micro-influencer (10K+)"
        elif fr >= 1_000:     tier = "Nano-influencer (1K+)"
        else:                  tier = "Cuenta pequena (<1K)"
        out.append(f"<b>Tier:</b> {tier}")
    except Exception:
        pass

    out.append(render_section("CUENTA"))
    out.append(f"<b>Verificado:</b> {'Si' if data.get('verified') else 'No'}")
    out.append(f"<b>Privada:</b>    {'Si' if data.get('private') else 'No'}")
    if data.get("region"):
        out.append(f"<b>Region:</b>     {data['region']}")
    if data.get("create_time"):
        out.append(f"<b>Creado:</b>     {data['create_time']}")

    if data.get("commerce"):
        c = data["commerce"]
        out.append(render_section("CUENTA COMERCIAL"))
        out.append(f"  Ads:   {'Si' if c.get('ad_authorized') else 'No'}")
        out.append(f"  Lives: {'Si' if c.get('live_authorized') else 'No'}")

    note = data.get("note","")
    src  = data.get("_source","")
    if note:
        out.append(f"<i>{note}</i>")
    if src:
        if src in ("html_regex", "og_meta"):
            out.append("<i>Datos parciales - TikTok limitó la extracción desde esta IP.</i>")
        elif src.startswith("tikwm:"):
            out.append("<i>Datos obtenidos vía RapidAPI (TikWM).</i>")
        elif src == "tiktok_internal_api":
            out.append("<i>Datos obtenidos vía API interna web.</i>")
        elif src in ("universal_json", "sigi_state"):
            out.append("<i>Datos obtenidos del JSON embebido en la web.</i>")

    return "\n".join(out)
