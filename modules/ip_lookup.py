
import requests
from config import logger

def get_ip_info(ip_address):
    """Análisis profundo de dirección IP usando múltiples fuentes"""
    try:
        # Fuente principal: IP-API
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy,hosting,query,mobile"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') != 'success':
            return "❌ IP no encontrada o privada/bogon."

        # Análisis de riesgo simulado (o real si agregamos AbuseIPDB)
        is_proxy = data.get('proxy', False)
        is_hosting = data.get('hosting', False)
        is_mobile = data.get('mobile', False)
        
        risk_score = 0
        if is_proxy: risk_score += 40
        if is_hosting: risk_score += 30
        
        risk_emoji = "🟢 Baja"
        if risk_score > 30: risk_emoji = "🟡 Media"
        if risk_score > 60: risk_emoji = "🔴 Alta"

        # Reverse DNS
        rdns = "No disponible"
        try:
            rdns_req = requests.get(f"https://dns.google/resolve?name={'.'.join(reversed(ip_address.split('.')))}.in-addr.arpa&type=PTR", timeout=5)
            if rdns_req.status_code == 200:
                answers = rdns_req.json().get("Answer", [])
                if answers:
                    rdns = answers[0].get('data', 'N/A').rstrip('.')
        except:
            pass

        return {
            "ip": data['query'],
            "country": f"{data['country']} {data['countryCode']}",
            "city": f"{data['city']}, {data['regionName']}",
            "zip": data.get('zip', 'N/A'),
            "coords": f"{data['lat']}, {data['lon']}",
            "timezone": data['timezone'],
            "isp": data['isp'],
            "org": data['org'],
            "asn": data.get('as', 'N/A'),
            "rdns": rdns,
            "type": "📱 Móvil" if is_mobile else ("🏢 Datacenter" if is_hosting else "🏠 Residencial"),
            "proxy": "⚠️ VPN/Proxy Detectado" if is_proxy else "✅ Limpia",
            "risk": risk_emoji,
            "map_url": f"https://www.google.com/maps?q={data['lat']},{data['lon']}"
        }

    except Exception as e:
        logger.error(f"Error IP: {e}")
        return None
