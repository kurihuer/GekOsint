
def render_header(title):
    return f"🛡️ <b>GEKOSINT | {title}</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"

def format_ip_result(data):
    if not data: return "⚠️ Error analizando IP."
    return (
        f"{render_header('IP INTEL')}"
        f"📡 <b>Target:</b> <code>{data['ip']}</code>\n"
        f"🌍 <b>Ubicación:</b> {data['city']}, {data['country']}\n"
        f"🏢 <b>ISP/Org:</b> {data['isp']}\n"
        f"🛡️ <b>Riesgo:</b> {data['risk']}\n"
        f"🕵️ <b>Tipo:</b> {data['type']}\n"
        f"🔌 <b>Proxy/VPN:</b> {data['proxy']}\n\n"
        f"📍 <b>Coords:</b> <code>{data['coords']}</code>\n"
        f"🔗 <a href='{data['map_url']}'>Ver en Mapa</a>"
    )

def format_phone_result(data):
    if "error" in data: return f"⚠️ {data['error']}"
    region = f"\n🏙️ <b>Zona:</b> {data['region_detail']}" if "region_detail" in data else ""
    
    return (
        f"{render_header('GSM INTEL')}"
        f"📱 <b>Número:</b> <code>{data['number']}</code>\n"
        f"🌍 <b>País:</b> {data['country']}\n"
        f"📡 <b>Operadora:</b> {data['carrier']}\n"
        f"💾 <b>Tipo:</b> {data['type']}{region}\n\n"
        f"🔗 <b>Enlaces Directos:</b>\n"
        f"• <a href='{data['whatsapp']}'>WhatsApp</a>\n"
        f"• <a href='{data['telegram']}'>Telegram</a>"
    )

def format_username_result(username, found):
    if not found: return f"❌ No se encontraron perfiles para <b>{username}</b>."
    
    txt = f"{render_header('SOCIAL SEARCH')}"
    txt += f"👤 <b>Username:</b> <code>{username}</code>\n"
    txt += f"✅ <b>Encontrado en {len(found)} sitios:</b>\n\n"
    
    for site, url in found:
        txt += f"• <a href='{url}'>{site}</a>\n"
        
    return txt

def format_exif_result(data):
    if not data or "error" in data:
        return "❌ No se encontraron metadatos EXIF o el archivo es inválido."
    
    txt = render_header("EXIF DATA")
    txt += f"📷 <b>Dispositivo:</b> {data['device'].get('Model', 'N/A')}\n"
    txt += f"📅 <b>Fecha:</b> {data['device'].get('DateTimeOriginal', 'N/A')}\n"
    txt += f"🖼 <b>Resolución:</b> {data['basic'].get('Size', 'N/A')}\n"
    
    if "coords" in data:
        txt += f"\n📍 <b>GPS Detectado!</b>\n"
        txt += f"🔗 <a href='{data['map']}'>Ver Ubicación en Google Maps</a>\n"
    else:
        txt += "\n⚠️ Sin datos GPS.\n"
        
    return txt

def format_email_result(data):
    if "error" in data: return "❌ Email inválido o formato incorrecto."
    
    mx_str = "\n  └ " + "\n  └ ".join(data['mx_records']) if data['mx_records'] else "Sin registros MX"
    
    return (
        f"{render_header('EMAIL INTEL')}"
        f"📧 <b>Target:</b> <code>{data['email']}</code>\n"
        f"🏢 <b>Proveedor:</b> {data.get('provider', 'N/A')}\n"
        f"⚖️ <b>Reputación:</b> {data['reputation']}\n"
        f"🗑️ <b>Desechable:</b> {'SI ⚠️' if data['disposable'] else 'NO'}\n"
        f"🚨 <b>Sospechoso:</b> {'SI 🔴' if data['suspicious'] else 'NO 🟢'}\n"
        f"🔓 <b>Filtrado:</b> {'SI ⚠️' if data['leaked'] else 'NO'}\n\n"
        f"⚙️ <b>Infraestructura DNS:</b>\n"
        f"• Dominio: {data['domain']}\n"
        f"• MX Records: {mx_str}\n\n"
        f"🔗 <b>Fuentes de Brechas:</b>\n"
        f"• <a href='{data['links']['haveibeenpwned']}'>HaveIBeenPwned</a>\n"
        f"• <a href='{data['links']['intelx']}'>IntelligenceX</a>\n"
        f"• <a href='{data['links']['dehashed']}'>DeHashed</a>"
    )
