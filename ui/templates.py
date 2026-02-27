
def render_header(title):
    return (
        f"<b>{'=' * 28}</b>\n"
        f"  <b>{title}</b>\n"
        f"<b>{'=' * 28}</b>\n\n"
    )

def render_section(title):
    return f"\n<b>--- {title} ---</b>\n"

def format_ip_result(data):
    if not data: return "Error analizando IP."
    if isinstance(data, dict) and "error" in data: return f"{data['error']}"

    risk_bar = _risk_bar(data.get('risk_score', 0))

    txt = render_header("IP INTELLIGENCE")
    txt += f"<b>Target:</b> <code>{data['ip']}</code>\n\n"

    txt += f"<b>Ubicacion:</b> {data['city']}, {data['country']}\n"
    txt += f"<b>Codigo Postal:</b> {data.get('zip', 'N/A')}\n"
    txt += f"<b>Zona Horaria:</b> {data.get('timezone', 'N/A')}\n"
    txt += f"<b>Coordenadas:</b> <code>{data['coords']}</code>\n"

    txt += render_section("RED / ISP")
    txt += f"<b>ISP:</b> {data['isp']}\n"
    txt += f"<b>Organizacion:</b> {data.get('org', 'N/A')}\n"
    txt += f"<b>ASN:</b> <code>{data.get('asn', 'N/A')}</code>\n"
    txt += f"<b>Hostname:</b> {data.get('hostname', 'N/A')}\n"
    txt += f"<b>Reverse DNS:</b> {data.get('rdns', 'N/A')}\n"

    txt += render_section("WHOIS")
    txt += f"<b>Red:</b> {data.get('net_name', 'N/A')}\n"
    txt += f"<b>Rango:</b> <code>{data.get('net_range', 'N/A')}</code>\n"
    txt += f"<b>Abuso:</b> {data.get('abuse_contact', 'N/A')}\n"

    txt += render_section("SEGURIDAD")
    txt += f"<b>Tipo:</b> {data['type']}\n"
    txt += f"<b>Proxy/VPN:</b> {data['proxy']}\n"
    txt += f"<b>Riesgo:</b> {risk_bar} {data['risk']} ({data.get('risk_score', 0)}/100)\n"

    risk_factors = data.get('risk_factors', [])
    if risk_factors:
        txt += f"<b>Factores:</b> {', '.join(risk_factors)}\n"

    if data.get('blacklisted'):
        txt += f"<b>Blacklist:</b> SI - {data.get('threat_type', '?')} ({data.get('abuse_reports', 0)} reportes)\n"
    else:
        txt += f"<b>Blacklist:</b> No\n"

    open_ports = data.get('open_ports', [])
    if open_ports and open_ports != ["Ninguno detectado"]:
        txt += render_section("PUERTOS ABIERTOS")
        txt += " | ".join(f"<code>{p}</code>" for p in open_ports[:8]) + "\n"

    txt += render_section("MAPA")
    txt += f"<a href='{data['map_url']}'>Abrir en Google Maps</a>\n"

    osint = data.get('osint_links', {})
    if osint:
        txt += render_section("OSINT LINKS")
        txt += " | ".join(f"<a href='{url}'>{name}</a>" for name, url in osint.items()) + "\n"

    return txt

def format_phone_result(data):
    if "error" in data: return f"{data['error']}"

    txt = render_header("PHONE INTELLIGENCE")
    txt += f"<b>Numero:</b> <code>{data['number']}</code>\n\n"

    txt += f"<b>Pais:</b> {data['country']}\n"
    txt += f"<b>Operadora:</b> {data['carrier']}\n"
    txt += f"<b>Tipo:</b> {data['type']}\n"
    txt += f"<b>Zona Horaria:</b> {data.get('timezone', 'N/A')}\n"
    if "region_detail" in data:
        txt += f"<b>Region:</b> {data['region_detail']}\n"

    # Truecaller / CallerID
    tc = data.get("truecaller", {})
    if tc:
        txt += render_section("CALLER ID")
        if tc.get("quota_exceeded"):
            txt += "<i>Cuota agotada en servicio de Caller ID</i>\n"
        elif tc.get("name"):
            txt += f"<b>Nombre:</b> {tc['name']}"
            if tc.get("name_type"):
                txt += f" ({tc['name_type']})"
            txt += "\n"
            if tc.get("carrier_tc"):
                txt += f"<b>Operadora (TC):</b> {tc['carrier_tc']}\n"
        else:
            txt += "<b>Nombre:</b> No encontrado en base de datos\n"

        if tc.get("reported"):
            txt += f"<b>Spam:</b> Score {tc['spam_score']} - {tc.get('spam_type', 'Spam')}\n"
        else:
            txt += "<b>Spam:</b> Sin reportes\n"

        # Datos scrapeados de fuentes externas
        scraped = tc.get("scraped_data", {})
        if scraped:
            if scraped.get("numbway_name"):
                txt += f"<b>Nombre (Numbway):</b> {scraped['numbway_name']}\n"
            if scraped.get("numbway_type"):
                txt += f"<b>Info:</b> {scraped['numbway_type']}\n"

    # Validacion
    if "validation" in data:
        val = data['validation']
        txt += render_section("VALIDACION")
        status_icon = "[OK]" if not val.get('possible_fraud') else "[!]"
        ported_text = "Si" if val.get('is_ported') else "No"
        txt += f"<b>Estado:</b> {status_icon} {val.get('line_status', 'Desconocido')}\n"
        txt += f"<b>Portado:</b> {ported_text}\n"
        txt += f"<b>Valido:</b> {'Si' if data.get('is_valid') else 'No'}\n"

    # Formatos
    txt += render_section("FORMATOS")
    txt += f"E164: <code>{data['number']}</code>\n"
    txt += f"Nacional: <code>{data.get('national', 'N/A')}</code>\n"
    txt += f"Internacional: <code>{data.get('international', 'N/A')}</code>\n"

    # Ubicacion
    if "location" in data and data['location']:
        loc = data['location']
        txt += render_section("UBICACION")
        txt += f"<b>Capital:</b> {loc.get('flag', '')} {loc.get('capital', 'N/A')}\n"
        txt += f"<b>Coords:</b> <code>{loc['lat']}, {loc['lon']}</code>\n"
        txt += f"<a href='{loc['map_url']}'>Ver en Mapa</a>"
        if "region_coords" in data and data['region_coords']:
            rc = data['region_coords']
            txt += f" | <a href='{rc['map_url']}'>Ver Region</a>"
        txt += "\n"

    # Contacto
    txt += render_section("CONTACTO DIRECTO")
    txt += f"<a href='{data.get('whatsapp', '#')}'>WhatsApp</a> | "
    txt += f"<a href='{data.get('telegram', '#')}'>Telegram</a>\n"

    # Links de busqueda
    if tc and tc.get("social_links"):
        txt += render_section("BUSCAR EN")
        txt += " | ".join(f"<a href='{l['url']}'>{l['name']}</a>" for l in tc['social_links']) + "\n"

    return txt

def format_username_result(username, found, telegram_data=None):
    txt = render_header("USERNAME SEARCH")
    txt += f"<b>Target:</b> <code>{username}</code>\n"

    if telegram_data:
        tg = telegram_data
        txt += render_section("TELEGRAM")
        if tg.get("exists"):
            txt += f"<b>Estado:</b> Encontrado\n"
            if tg.get("name"):
                txt += f"<b>Nombre:</b> {tg['name']}\n"
            txt += f"<b>Tipo:</b> {tg.get('type', 'Desconocido')}\n"
            if tg.get("id"):
                txt += f"<b>ID:</b> <code>{tg['id']}</code>\n"
            if tg.get("members"):
                members = f"{tg['members']:,}" if isinstance(tg['members'], int) else str(tg['members'])
                txt += f"<b>Miembros:</b> {members}\n"
            if tg.get("bio"):
                bio = tg['bio'][:120] + "..." if len(tg['bio']) > 120 else tg['bio']
                txt += f"<b>Bio:</b> {bio}\n"
            flags = []
            if tg.get("is_verified"): flags.append("Verificado")
            if tg.get("is_bot"):      flags.append("Bot")
            if tg.get("is_scam"):     flags.append("SCAM")
            if tg.get("is_fake"):     flags.append("FAKE")
            if flags:
                txt += f"<b>Flags:</b> {' | '.join(flags)}\n"
            txt += f"<a href='{tg['url']}'>Abrir en Telegram</a>\n"
        else:
            txt += "<b>Estado:</b> No encontrado / Privado\n"

    if found:
        txt += render_section(f"REDES SOCIALES ({len(found)})")
        for site, url in found:
            txt += f"  <a href='{url}'>{site}</a>\n"
    else:
        txt += render_section("REDES SOCIALES")
        txt += "No se encontraron perfiles.\n"

    txt += render_section("BUSQUEDA AVANZADA")
    txt += f"<a href='https://www.google.com/search?q=%22{username}%22'>Google</a>"
    txt += f" | <a href='https://web.archive.org/web/*/https://*/{username}'>Wayback</a>"
    txt += f" | <a href='https://whatsmyname.app/?q={username}'>WhatsMyName</a>\n"

    return txt

def format_whatsapp_result(data):
    if "error" in data:
        return f"{data['error']}"

    txt = render_header("WHATSAPP OSINT")
    txt += f"<b>Numero:</b> <code>{data['number']}</code>\n"
    txt += f"<b>Pais:</b> {data.get('country', 'N/A')}  |  <b>Operadora:</b> {data.get('carrier', 'N/A')}\n\n"

    # Estado
    reg = data.get("registered")
    if reg is True:
        txt += "<b>WhatsApp:</b> REGISTRADO\n"
    elif reg is False:
        txt += "<b>WhatsApp:</b> No registrado\n"
    else:
        txt += "<b>WhatsApp:</b> Indeterminado\n"

    if data.get("is_business"):
        txt += "<b>Tipo:</b> WhatsApp Business\n"

    # Nombre obtenido
    caller_name = data.get("caller_name")
    if caller_name:
        txt += render_section("IDENTIDAD")
        txt += f"<b>Nombre:</b> {caller_name}\n"
        if data.get("caller_source"):
            txt += f"<b>Fuente:</b> {data['caller_source']}\n"

    # Foto
    photo = data.get("photo")
    if photo:
        txt += f"<b>Foto Perfil:</b> <a href='{photo}'>Ver foto</a>\n"
    else:
        txt += "<b>Foto Perfil:</b> Privada o no disponible\n"

    # About / Estado
    about = data.get("about")
    if about:
        txt += f"<b>Estado/About:</b> {about}\n"

    # Presencia social
    social = data.get("social", {})
    if social:
        txt += render_section("PRESENCIA SOCIAL")
        if social.get("telegram"):
            txt += "Telegram: Encontrado\n"

    # Spam
    spam = data.get("spam", {})
    total = spam.get("total_reports", 0)
    txt += render_section("REPORTE SPAM")
    if total > 0:
        txt += f"<b>Total reportes:</b> {total}\n"
        if spam.get("sources"):
            txt += f"<b>Fuentes:</b> {', '.join(spam['sources'])}\n"
        if spam.get("labels"):
            txt += f"<b>Etiquetas:</b> {', '.join(spam['labels'])}\n"
    else:
        txt += "Sin reportes de spam\n"

    # Contacto
    txt += render_section("CONTACTO DIRECTO")
    txt += f"<a href='{data['wa_link']}'>Abrir perfil</a> | "
    txt += f"<a href='{data['wa_msg']}'>Enviar mensaje</a>\n"

    # Links OSINT
    txt += render_section("VERIFICAR EN")
    links = data.get("links", {})
    link_labels = {
        "truecaller": "Truecaller", "getcontact": "GetContact",
        "syncme": "Sync.me", "numbway": "Numbway",
        "tellows": "Tellows", "google_dork": "Google",
    }
    link_parts = []
    for key, label in link_labels.items():
        if links.get(key):
            link_parts.append(f"<a href='{links[key]}'>{label}</a>")
    txt += " | ".join(link_parts) + "\n"

    return txt

def format_exif_result(data):
    if not data or "error" in data:
        return "No se encontraron metadatos EXIF o el archivo es invalido."

    txt = render_header("EXIF METADATA")

    device = data.get('device', {})
    txt += f"<b>Dispositivo:</b> {device.get('Make', '')} {device.get('Model', 'N/A')}\n"
    txt += f"<b>Fecha:</b> {device.get('DateTimeOriginal', 'N/A')}\n"
    txt += f"<b>Resolucion:</b> {data.get('basic', {}).get('Size', 'N/A')}\n"

    if device.get('Software'):
        txt += f"<b>Software:</b> {device['Software']}\n"

    if device.get('FocalLength') or device.get('ExposureTime') or device.get('FNumber'):
        txt += render_section("CONFIGURACION CAMARA")
        if device.get('FocalLength'):
            txt += f"Focal: {device['FocalLength']}mm\n"
        if device.get('FNumber'):
            txt += f"Apertura: f/{device['FNumber']}\n"
        if device.get('ExposureTime'):
            txt += f"Exposicion: {device['ExposureTime']}s\n"
        if device.get('ISOSpeedRatings'):
            txt += f"ISO: {device['ISOSpeedRatings']}\n"
        if device.get('Flash'):
            txt += f"Flash: {device['Flash']}\n"

    if "coords" in data and data['coords']:
        txt += render_section("GPS DETECTADO")
        txt += f"<b>Coordenadas:</b> <code>{data['coords']}</code>\n"
        txt += f"<a href='{data.get('map', '#')}'>Ver en Google Maps</a>\n"
        txt += "<i>Esta imagen contiene ubicacion exacta</i>\n"
    else:
        txt += "\nSin datos GPS.\n"

    all_tags = data.get('all_tags', {})
    if all_tags and len(all_tags) > 5:
        txt += render_section(f"METADATOS RAW ({len(all_tags)} tags)")
        count = 0
        for key, val in all_tags.items():
            if count >= 12:
                txt += f"<i>... y {len(all_tags) - 12} mas</i>\n"
                break
            val_str = str(val)[:50]
            txt += f"{key}: <code>{val_str}</code>\n"
            count += 1

    return txt

def format_email_result(data):
    if "error" in data: return "Email invalido o formato incorrecto."

    rep_label = data['reputation']
    if rep_label in ['HIGH', 'high']: rep_indicator = "[BUENA]"
    elif rep_label in ['MEDIUM', 'medium']: rep_indicator = "[MEDIA]"
    else: rep_indicator = "[BAJA]"

    txt = render_header("EMAIL INTELLIGENCE")
    txt += f"<b>Target:</b> <code>{data['email']}</code>\n\n"

    txt += f"<b>Proveedor:</b> {data.get('provider', 'N/A')}\n"
    txt += f"<b>Reputacion:</b> {rep_indicator} {rep_label}\n"
    txt += f"<b>Desechable:</b> {'SI' if data['disposable'] else 'NO'}\n"
    txt += f"<b>Sospechoso:</b> {'SI' if data['suspicious'] else 'NO'}\n"
    txt += f"<b>Filtrado:</b> {'SI' if data['leaked'] else 'NO'}\n"

    local = data.get('local_analysis', {})
    if local and (local.get('possible_name') or local.get('possible_year')):
        txt += render_section("ANALISIS USUARIO")
        if local.get('possible_name'):
            txt += f"<b>Posible nombre:</b> {local['possible_name']}\n"
        if local.get('possible_year'):
            txt += f"<b>Posible anio:</b> {local['possible_year']}\n"
        if local.get('has_plus'):
            txt += f"<b>Alias (+tag):</b> base = {local.get('base_email', 'N/A')}\n"

    gravatar = data.get('gravatar', {})
    if gravatar.get('exists'):
        txt += f"\n<b>Gravatar:</b> <a href='{gravatar['profile']}'>Perfil encontrado</a>\n"

    txt += render_section("DNS / INFRAESTRUCTURA")
    txt += f"<b>Dominio:</b> {data['domain']}\n"
    if data.get('domain_age'):
        txt += f"<b>Registrado:</b> {data['domain_age']}\n"
    mx = data.get('mx_records', [])
    if mx:
        txt += f"<b>MX:</b> {' | '.join(mx[:3])}\n"

    dns_sec = data.get('dns_security', {})
    if dns_sec:
        txt += f"<b>SPF:</b> {'Configurado' if dns_sec.get('spf') else 'No'} | "
        txt += f"<b>DMARC:</b> {'Configurado' if dns_sec.get('dmarc') else 'No'}\n"

    breaches = data.get('breaches', [])
    txt += render_section("BRECHAS DE DATOS")
    if breaches:
        txt += f"Encontrado en <b>{len(breaches)} brechas:</b>\n"
        for b in breaches[:10]:
            txt += f"  {b}\n"
    else:
        txt += "No encontrado en brechas conocidas\n"

    links = data.get('links', {})
    txt += render_section("VERIFICAR EN")
    link_labels = {
        'haveibeenpwned': 'HIBP', 'intelx': 'IntelX',
        'dehashed': 'DeHashed', 'emailrep': 'EmailRep',
        'hunter': 'Hunter', 'google_dork': 'Google',
    }
    link_parts = []
    for key, label in link_labels.items():
        if links.get(key):
            link_parts.append(f"<a href='{links[key]}'>{label}</a>")
    txt += " | ".join(link_parts) + "\n"

    return txt

def _risk_bar(score):
    filled = score // 10
    empty = 10 - filled
    return "[" + "|" * filled + "." * empty + "]"
