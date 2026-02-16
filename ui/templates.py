
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

def format_email_result(data):
    if "error" in data: return "❌ Email inválido."
    
    mx_str = ", ".join(data['mx_records']) if data['mx_records'] else "Sin registros"
    
    return (
        f"{render_header('EMAIL INTEL')}"
        f"📧 <b>Email:</b> <code>{data['email']}</code>\n"
        f"⚖️ <b>Reputación:</b> {data['reputation']}\n"
        f"🚨 <b>Sospechoso:</b> {'SI' if data['suspicious'] else 'NO'}\n"
        f"🔓 <b>Filtrado:</b> {'SI ⚠️' if data['leaked'] else 'NO'}\n\n"
        f"⚙️ <b>Datos Técnicos:</b>\n"
        f"• Dominio: {data['domain']}\n"
        f"• MX: {mx_str}\n"
        f"• Desechable: {'SI' if data['disposable'] else 'NO'}\n\n"
        f"🔍 <a href='{data['links']['haveibeenpwned']}'>Verificar Brechas</a>"
    )
