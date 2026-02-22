
def render_header(title):
    return f"🛡️ <b>GEKOSINT | {title}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

def format_ip_result(data):
    if not data: return "⚠️ Error analizando IP."
    if isinstance(data, dict) and "error" in data: return f"⚠️ {data['error']}"
    
    # Sección principal
    txt = (
        f"{render_header('IP INTEL')}"
        f"🎯 <b>Target:</b> <code>{data['ip']}</code>\n\n"
        f"🌍 <b>Ubicación:</b> {data['city']}, {data['country']}\n"
        f"📮 <b>Código Postal:</b> {data.get('zip', 'N/A')}\n"
        f"🕐 <b>Zona Horaria:</b> {data.get('timezone', 'N/A')}\n\n"
    )
    
    # Red e ISP
    txt += (
        f"🏢 <b>ISP:</b> {data['isp']}\n"
        f"🏛️ <b>Organización:</b> {data.get('org', 'N/A')}\n"
        f"🔢 <b>ASN:</b> <code>{data.get('asn', 'N/A')}</code>\n"
        f"🌐 <b>Hostname:</b> {data.get('hostname', 'N/A')}\n"
        f"📡 <b>Reverse DNS:</b> {data.get('rdns', 'N/A')}\n\n"
    )
    
    # WHOIS
    txt += (
        f"📋 <b>WHOIS:</b>\n"
        f"  • Red: {data.get('net_name', 'N/A')}\n"
        f"  • Rango: <code>{data.get('net_range', 'N/A')}</code>\n"
        f"  • Abuso: {data.get('abuse_contact', 'N/A')}\n\n"
    )
    
    # Clasificación y riesgo
    txt += (
        f"💻 <b>Tipo:</b> {data['type']}\n"
        f"🔌 <b>Proxy/VPN:</b> {data['proxy']}\n"
        f"🛡️ <b>Riesgo:</b> {data['risk']} ({data.get('risk_score', 0)}/100)\n"
    )
    
    # Factores de riesgo
    risk_factors = data.get('risk_factors', [])
    if risk_factors:
        txt += f"⚠️ <b>Factores:</b> {', '.join(risk_factors)}\n"
    
    # Blacklist
    if data.get('blacklisted'):
        txt += f"🚫 <b>Blacklisted:</b> SÍ — {data.get('threat_type', 'Desconocido')} ({data.get('abuse_reports', 0)} reportes)\n"
    else:
        txt += f"✅ <b>Blacklisted:</b> No\n"
    
    # Puertos abiertos
    open_ports = data.get('open_ports', [])
    if open_ports and open_ports != ["Ninguno detectado"]:
        txt += f"\n🔓 <b>PUERTOS ABIERTOS:</b>\n"
        for port in open_ports[:8]:
            txt += f"  • <code>{port}</code>\n"
    
    # Mapa
    txt += (
        f"\n📍 <b>Coords:</b> <code>{data['coords']}</code>\n"
        f"🗺️ <a href='{data['map_url']}'>Ver en Google Maps</a>\n"
    )
    
    # Links OSINT
    osint = data.get('osint_links', {})
    if osint:
        txt += f"\n🔍 <b>OSINT LINKS:</b>\n"
        for name, url in osint.items():
            txt += f"  • <a href='{url}'>{name}</a>\n"
    
    return txt

def format_phone_result(data):
    if "error" in data: return f"⚠️ {data['error']}"
    
    region = f"\n🏙️ <b>Zona Regional:</b> {data['region_detail']}" if "region_detail" in data else ""
    
    # Sección TrueCaller
    tc_section = ""
    tc = data.get("truecaller", {})
    if tc:
        tc_section = "\n\n👁️ <b>CALLER ID (Truecaller):</b>\n"
        if tc.get("quota_exceeded"):
            tc_section += "⚠️ <i>Cuota mensual agotada — renueva el plan en RapidAPI</i>\n"
        elif tc.get("name"):
            tc_section += f"👤 <b>Nombre:</b> {tc['name']}"
            if tc.get("name_type"):
                tc_section += f" <i>({tc['name_type']})</i>"
            tc_section += "\n"
            if tc.get("carrier_tc"):
                tc_section += f"📡 <b>Operadora (TC):</b> {tc['carrier_tc']}\n"
            if tc.get("reported"):
                tc_section += f"🚨 <b>Spam:</b> score {tc['spam_score']} — {tc.get('spam_type','Spam')}\n"
            else:
                tc_section += "✅ <b>Spam:</b> Sin reportes\n"
        else:
            tc_section += "❔ <b>Nombre:</b> No encontrado en base de datos\n"
            if tc.get("reported"):
                tc_section += f"🚨 <b>Spam:</b> score {tc['spam_score']} — {tc.get('spam_type','Spam')}\n"
            else:
                tc_section += "✅ <b>Spam:</b> Sin reportes\n"
        tc_section += "🔍 <b>Buscar en:</b>\n"
        for link in tc.get("social_links", []):
            tc_section += f"  • <a href='{link['url']}'>{link['name']}</a>\n"

    location_section = ""
    if "location" in data and data['location']:
        loc = data['location']
        location_section = f"\n\n📍 <b>UBICACIÓN DEL PAÍS:</b>\n"
        location_section += f"🏛️ <b>Capital:</b> {loc.get('flag','')} {loc.get('capital','N/A')}\n"
        location_section += f"📌 <b>Coords:</b> <code>{loc['lat']}, {loc['lon']}</code>\n"
        location_section += f"🗺️ <a href='{loc['map_url']}'>Ver País en Mapa</a>"
    
    region_map_section = ""
    if "region_coords" in data and data['region_coords']:
        rc = data['region_coords']
        region_map_section = f"\n\n🎯 <b>UBICACIÓN REGIONAL:</b>\n"
        region_map_section += f"📍 <b>Coords:</b> <code>{rc['lat']}, {rc['lon']}</code>\n"
        region_map_section += f"🗺️ <a href='{rc['map_url']}'>Ver Región en Mapa</a>"
    
    validation_section = ""
    if "validation" in data:
        val = data['validation']
        status_emoji = "✅" if not val.get('possible_fraud') else "⚠️"
        ported_text = "Sí ⚠️" if val.get('is_ported') else "No"
        validation_section = f"\n\n🔍 <b>VALIDACIÓN:</b>\n"
        validation_section += f"📊 <b>Estado:</b> {status_emoji} {val.get('line_status','Desconocido')}\n"
        validation_section += f"🔄 <b>Portado:</b> {ported_text}\n"
        validation_section += f"✔️ <b>Válido:</b> {'Sí' if data.get('is_valid') else 'No'}\n"
        validation_section += f"🎯 <b>Posible:</b> {'Sí' if data.get('is_possible') else 'No'}"
    
    formats_section = f"\n\n📋 <b>FORMATOS:</b>\n"
    formats_section += f"• E164: <code>{data['number']}</code>\n"
    formats_section += f"• Nacional: <code>{data.get('national','N/A')}</code>\n"
    formats_section += f"• Internacional: <code>{data.get('international','N/A')}</code>"
    
    return (
        f"{render_header('GSM INTEL')}"
        f"📱 <b>NÚMERO:</b> <code>{data['number']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌍 <b>País:</b> {data['country']}\n"
        f"📡 <b>Operadora:</b> {data['carrier']}\n"
        f"💾 <b>Tipo:</b> {data['type']}{region}\n"
        f"🕐 <b>Zona Horaria:</b> {data.get('timezone','N/A')}\n"
        f"{tc_section}"
        f"{location_section}"
        f"{region_map_section}"
        f"{validation_section}"
        f"{formats_section}\n\n"
        f"🔗 <b>CONTACTO DIRECTO:</b>\n"
        f"• <a href='{data.get('whatsapp','#')}'>WhatsApp</a>  "
        f"• <a href='{data.get('telegram','#')}'>Telegram</a>"
    )

def format_username_result(username, found, telegram_data=None):
    txt = f"{render_header('SOCIAL SEARCH')}"
    txt += f"👤 <b>Username:</b> <code>{username}</code>\n"

    # Bloque Telegram (siempre primero)
    if telegram_data:
        tg = telegram_data
        txt += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        txt += "✈️ <b>TELEGRAM:</b>\n"
        if tg.get("exists"):
            status_icon = "🟢"
            txt += f"{status_icon} <b>Estado:</b> Encontrado\n"
            if tg.get("name"):
                txt += f"📛 <b>Nombre:</b> {tg['name']}\n"
            txt += f"🏷️ <b>Tipo:</b> {tg.get('type','Desconocido')}\n"
            if tg.get("id"):
                txt += f"🆔 <b>ID:</b> <code>{tg['id']}</code>\n"
            if tg.get("members"):
                txt += f"👥 <b>Miembros:</b> {tg['members']:,}\n" if isinstance(tg['members'], int) else f"👥 <b>Miembros:</b> {tg['members']}\n"
            if tg.get("bio"):
                bio_short = tg['bio'][:120] + "..." if len(tg['bio']) > 120 else tg['bio']
                txt += f"📝 <b>Bio:</b> {bio_short}\n"
            flags = []
            if tg.get("is_verified"): flags.append("✅ Verificado")
            if tg.get("is_bot"):      flags.append("🤖 Bot")
            if tg.get("is_scam"):     flags.append("🚨 SCAM")
            if tg.get("is_fake"):     flags.append("⚠️ FAKE")
            if flags:
                txt += f"🏅 <b>Flags:</b> {' | '.join(flags)}\n"
            txt += f"🔗 <a href='{tg['url']}'>Abrir en Telegram</a>\n"
        else:
            txt += "🔴 <b>Estado:</b> No encontrado / Privado\n"
            txt += f"🔗 <a href='https://t.me/{username}'>Verificar en Telegram</a>\n"

    # Bloque redes sociales
    txt += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    if found:
        txt += f"🌐 <b>REDES SOCIALES ({len(found)} encontradas):</b>\n\n"
        for site, url in found:
            txt += f"• <a href='{url}'>{site}</a>\n"
    else:
        txt += "❌ <b>No se encontraron perfiles en redes sociales.</b>\n"

    # Links OSINT adicionales
    txt += f"\n🔍 <b>BÚSQUEDA AVANZADA:</b>\n"
    txt += f"• <a href='https://www.google.com/search?q=%22{username}%22'>Google Dork</a>\n"
    txt += f"• <a href='https://web.archive.org/web/*/https://*/{username}'>Wayback Machine</a>\n"
    txt += f"• <a href='https://whatsmyname.app/?q={username}'>WhatsMyName</a>\n"
    txt += f"• <a href='https://namechk.com/'>NameChk</a>\n"

    return txt

def format_whatsapp_result(data):
    if "error" in data:
        return f"⚠️ {data['error']}"

    txt = f"{render_header('WHATSAPP OSINT')}"
    txt += f"📞 <b>Número:</b> <code>{data['number']}</code>\n"
    txt += f"🌍 <b>País:</b> {data.get('country','N/A')}  |  📡 <b>Operadora:</b> {data.get('carrier','N/A')}\n"
    if data.get('international'):
        txt += f"📋 <b>Internacional:</b> {data['international']}\n"
    txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Estado WhatsApp
    reg = data.get("registered")
    if reg is True:
        txt += "🟢 <b>WhatsApp:</b> REGISTRADO ✅\n"
    elif reg is False:
        txt += "🔴 <b>WhatsApp:</b> No registrado\n"
    else:
        txt += "🟡 <b>WhatsApp:</b> Indeterminado (número privado)\n"

    # Tipo de cuenta
    if data.get("is_business"):
        txt += "💼 <b>Tipo:</b> WhatsApp Business\n"

    # Foto de perfil
    photo = data.get("photo")
    if photo:
        txt += f"🖼️ <b>Foto de Perfil:</b> <a href='{photo}'>Ver foto pública</a>\n"
    else:
        txt += "🖼️ <b>Foto de Perfil:</b> Privada o no disponible\n"

    # Presencia en otras plataformas
    social = data.get("social", {})
    if social:
        txt += "\n📱 <b>PRESENCIA SOCIAL:</b>\n"
        if social.get("telegram"):
            txt += "  • ✈️ Telegram: Encontrado\n"

    # Spam
    spam = data.get("spam", {})
    total = spam.get("total_reports", 0)
    txt += "\n🚨 <b>REPORTE DE SPAM:</b>\n"
    if total > 0:
        txt += f"⚠️ <b>Total reportes:</b> {total}\n"
        if spam.get("sources"):
            txt += f"📂 <b>Fuentes:</b> {', '.join(spam['sources'])}\n"
        if spam.get("labels"):
            txt += f"🏷️ <b>Etiquetas:</b> {', '.join(spam['labels'])}\n"
    else:
        txt += "✅ Sin reportes de spam encontrados\n"

    # Contacto directo
    txt += f"\n💬 <b>CONTACTO DIRECTO:</b>\n"
    txt += f"• <a href='{data['wa_link']}'>Abrir perfil en WhatsApp</a>\n"
    txt += f"• <a href='{data['wa_msg']}'>Enviar mensaje</a>\n"

    # Links OSINT externos
    txt += "\n🔍 <b>VER NOMBRE Y FOTO EN:</b>\n"
    txt += "<i>(Truecaller y GetContact muestran el nombre público si existe)</i>\n"
    links = data.get("links", {})
    icons = {
        "truecaller":  "📞 Truecaller",
        "getcontact":  "📇 GetContact",
        "syncme":      "🔄 Sync.me",
        "spamcalls":   "🚨 SpamCalls",
        "whocalledme": "📋 WhoCalledMe",
        "tellows":     "📊 Tellows",
        "numbway":     "🔢 Numbway",
        "google_dork": "🔍 Google Dork",
    }
    for key, label in icons.items():
        if links.get(key):
            txt += f"• <a href='{links[key]}'>{label}</a>\n"

    return txt

def format_exif_result(data):
    if not data or "error" in data:
        return "❌ No se encontraron metadatos EXIF o el archivo es inválido."
    
    txt = render_header("EXIF DATA")
    
    # Información del dispositivo
    device = data.get('device', {})
    txt += f"📷 <b>Dispositivo:</b> {device.get('Make', '')} {device.get('Model', 'N/A')}\n"
    txt += f"📅 <b>Fecha:</b> {device.get('DateTimeOriginal', 'N/A')}\n"
    txt += f"🖼 <b>Resolución:</b> {data.get('basic', {}).get('Size', 'N/A')}\n"
    
    # Software
    if device.get('Software'):
        txt += f"💿 <b>Software:</b> {device['Software']}\n"
    
    # Configuración de cámara
    if device.get('FocalLength') or device.get('ExposureTime') or device.get('FNumber'):
        txt += f"\n📸 <b>CONFIGURACIÓN:</b>\n"
        if device.get('FocalLength'):
            txt += f"  • Focal: {device['FocalLength']}mm\n"
        if device.get('FNumber'):
            txt += f"  • Apertura: f/{device['FNumber']}\n"
        if device.get('ExposureTime'):
            txt += f"  • Exposición: {device['ExposureTime']}s\n"
        if device.get('ISOSpeedRatings'):
            txt += f"  • ISO: {device['ISOSpeedRatings']}\n"
        if device.get('Flash'):
            txt += f"  • Flash: {device['Flash']}\n"
    
    # GPS
    if "coords" in data and data['coords']:
        txt += f"\n📍 <b>⚠️ GPS DETECTADO!</b>\n"
        txt += f"🌐 <b>Coordenadas:</b> <code>{data['coords']}</code>\n"
        txt += f"🗺️ <a href='{data.get('map', '#')}'>Ver Ubicación en Google Maps</a>\n"
        txt += f"⚠️ <i>Esta imagen contiene datos de ubicación exacta</i>\n"
    else:
        txt += "\n✅ Sin datos GPS detectados.\n"
    
    # Todos los metadatos raw
    all_tags = data.get('all_tags', {})
    if all_tags and len(all_tags) > 5:
        txt += f"\n📋 <b>METADATOS RAW ({len(all_tags)} tags):</b>\n"
        count = 0
        for key, val in all_tags.items():
            if count >= 15:
                txt += f"  <i>... y {len(all_tags) - 15} más</i>\n"
                break
            val_str = str(val)[:60]
            txt += f"  • {key}: <code>{val_str}</code>\n"
            count += 1
        
    return txt

def format_email_result(data):
    if "error" in data: return "❌ Email inválido o formato incorrecto."
    
    mx_str = "\n  └ " + "\n  └ ".join(data['mx_records']) if data['mx_records'] else "Sin registros MX"
    
    # Emoji según reputación
    rep_emoji = "🟢"
    if data['reputation'] in ['MEDIUM', 'medium']: rep_emoji = "🟡"
    elif data['reputation'] in ['LOW', 'low', 'RISK', 'poor']: rep_emoji = "🔴"
    
    txt = (
        f"{render_header('EMAIL INTEL')}"
        f"📧 <b>Target:</b> <code>{data['email']}</code>\n\n"
        f"🏢 <b>Proveedor:</b> {data.get('provider', 'N/A')}\n"
        f"⚖️ <b>Reputación:</b> {rep_emoji} {data['reputation']}\n"
        f"🗑️ <b>Desechable:</b> {'SI ⚠️' if data['disposable'] else 'NO ✅'}\n"
        f"🚨 <b>Sospechoso:</b> {'SI 🔴' if data['suspicious'] else 'NO 🟢'}\n"
        f"🔓 <b>Filtrado:</b> {'SI ⚠️' if data['leaked'] else 'NO ✅'}\n"
    )
    
    # Análisis del nombre de usuario
    local = data.get('local_analysis', {})
    if local:
        txt += f"\n👤 <b>ANÁLISIS DEL USUARIO:</b>\n"
        if local.get('possible_name'):
            txt += f"  • Posible nombre: {local['possible_name']}\n"
        if local.get('possible_year'):
            txt += f"  • Posible año: {local['possible_year']}\n"
        if local.get('has_plus'):
            txt += f"  • ⚠️ Usa alias (+tag): base = {local.get('base_email', 'N/A')}\n"
    
    # Gravatar
    gravatar = data.get('gravatar', {})
    if gravatar.get('exists'):
        txt += f"\n🖼️ <b>GRAVATAR:</b> <a href='{gravatar['profile']}'>Perfil encontrado</a>\n"
    
    # Dominio
    txt += (
        f"\n⚙️ <b>INFRAESTRUCTURA DNS:</b>\n"
        f"  • Dominio: {data['domain']}\n"
    )
    if data.get('domain_age'):
        txt += f"  • Registrado: {data['domain_age']}\n"
    txt += f"  • MX Records: {mx_str}\n"
    
    # Seguridad DNS
    dns_sec = data.get('dns_security', {})
    if dns_sec:
        txt += f"\n🔒 <b>SEGURIDAD DNS:</b>\n"
        txt += f"  • SPF: {'✅ Configurado' if dns_sec.get('spf') else '❌ No configurado'}\n"
        txt += f"  • DMARC: {'✅ Configurado' if dns_sec.get('dmarc') else '❌ No configurado'}\n"
    
    # Brechas de datos
    txt += f"\n🔓 <b>BRECHAS DE DATOS:</b>\n"
    breaches = data.get('breaches', [])
    if breaches:
        txt += f"⚠️ <b>Encontrado en {len(breaches)} brechas:</b>\n"
        for b in breaches[:10]:
            txt += f"  • {b}\n"
    else:
        txt += "✅ No encontrado en brechas conocidas\n"
    
    # Links OSINT
    txt += f"\n🔗 <b>VERIFICAR EN:</b>\n"
    links = data.get('links', {})
    link_labels = {
        'haveibeenpwned': 'HaveIBeenPwned',
        'intelx': 'IntelligenceX',
        'dehashed': 'DeHashed',
        'emailrep': 'EmailRep',
        'hunter': 'Hunter.io',
        'google_dork': 'Google Dork',
    }
    for key, label in link_labels.items():
        if links.get(key):
            txt += f"• <a href='{links[key]}'>{label}</a>\n"
    
    return txt
