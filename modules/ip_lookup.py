
import requests
import socket
import re
from config import logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def _is_valid_ip(ip):
    """Valida formato IPv4 o IPv6"""
    # IPv4
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
        parts = ip.split('.')
        return all(0 <= int(p) <= 255 for p in parts)
    # IPv6 básico
    if ':' in ip:
        return True
    return False

def _is_private_ip(ip):
    """Detecta IPs privadas/reservadas"""
    private_ranges = [
        r'^10\.', r'^172\.(1[6-9]|2[0-9]|3[01])\.', r'^192\.168\.',
        r'^127\.', r'^0\.', r'^169\.254\.', r'^224\.', r'^240\.'
    ]
    return any(re.match(p, ip) for p in private_ranges)

def _get_abuse_info(ip):
    """Obtiene información de abuso/reputación de la IP"""
    result = {"blacklisted": False, "reports": 0, "threat_type": "Ninguna"}
    try:
        # VirusTotal community (sin API key, limitado)
        r = requests.get(
            f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
            headers={"x-apikey": ""},  # Sin key = limitado pero funcional para check básico
            timeout=5
        )
        if r.status_code == 200:
            data = r.json().get("data", {}).get("attributes", {})
            malicious = data.get("last_analysis_stats", {}).get("malicious", 0)
            if malicious > 0:
                result["blacklisted"] = True
                result["reports"] = malicious
                result["threat_type"] = "Malicioso"
    except Exception:
        pass
    
    # Verificar en listas de spam conocidas
    try:
        dnsbl_hosts = [
            "zen.spamhaus.org",
            "bl.spamcop.net",
            "dnsbl.sorbs.net"
        ]
        reversed_ip = '.'.join(reversed(ip.split('.')))
        for dnsbl in dnsbl_hosts:
            try:
                socket.gethostbyname(f"{reversed_ip}.{dnsbl}")
                result["blacklisted"] = True
                result["reports"] += 1
                result["threat_type"] = "Spam/Abuso"
                break
            except socket.gaierror:
                continue
    except Exception:
        pass
    
    return result

def _get_whois_basic(ip):
    """Obtiene datos WHOIS básicos"""
    result = {"net_name": "N/A", "net_range": "N/A", "abuse_contact": "N/A"}
    try:
        r = requests.get(f"https://rdap.arin.net/registry/ip/{ip}", timeout=8, headers=HEADERS)
        if r.status_code == 200:
            data = r.json()
            result["net_name"] = data.get("name", "N/A")
            
            # Rango de red
            start = data.get("startAddress", "")
            end = data.get("endAddress", "")
            if start and end:
                result["net_range"] = f"{start} - {end}"
            
            # Contacto de abuso
            entities = data.get("entities", [])
            for entity in entities:
                roles = entity.get("roles", [])
                if "abuse" in roles:
                    vcards = entity.get("vcardArray", [None, []])[1]
                    for vcard in vcards:
                        if vcard[0] == "email":
                            result["abuse_contact"] = vcard[3]
                            break
    except Exception:
        pass
    return result

def _get_open_ports(ip):
    """Escaneo rápido de puertos comunes (solo los más relevantes)"""
    common_ports = {
        21: "FTP", 22: "SSH", 25: "SMTP", 53: "DNS",
        80: "HTTP", 443: "HTTPS", 3306: "MySQL", 3389: "RDP",
        5432: "PostgreSQL", 8080: "HTTP-Alt", 8443: "HTTPS-Alt"
    }
    open_ports = []
    for port, service in common_ports.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(f"{port}/{service}")
            sock.close()
        except Exception:
            pass
    return open_ports if open_ports else ["Ninguno detectado"]

def get_ip_info(ip_address):
    """Análisis profundo de dirección IP usando múltiples fuentes"""
    ip_address = ip_address.strip()
    
    # Validación
    if not _is_valid_ip(ip_address):
        # Intentar resolver hostname
        try:
            resolved = socket.gethostbyname(ip_address)
            ip_address = resolved
        except Exception:
            return {"error": f"'{ip_address}' no es una IP válida ni un hostname resoluble."}
    
    if _is_private_ip(ip_address):
        return {"error": f"'{ip_address}' es una IP privada/reservada. Solo se analizan IPs públicas."}
    
    try:
        # === FUENTE 1: IP-API (datos principales) ===
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,proxy,hosting,query,mobile"
        response = requests.get(url, timeout=10, headers=HEADERS)
        data = response.json()
        
        if data.get('status') != 'success':
            return {"error": "IP no encontrada o privada/bogon."}

        # === FUENTE 2: ipinfo.io (datos adicionales) ===
        extra = {}
        try:
            r2 = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=8, headers=HEADERS)
            if r2.status_code == 200:
                extra = r2.json()
        except Exception:
            pass

        # Análisis de riesgo
        is_proxy = data.get('proxy', False)
        is_hosting = data.get('hosting', False)
        is_mobile = data.get('mobile', False)
        
        risk_score = 0
        risk_factors = []
        if is_proxy:
            risk_score += 40
            risk_factors.append("VPN/Proxy")
        if is_hosting:
            risk_score += 30
            risk_factors.append("Datacenter")
        
        # Verificar reputación
        abuse = _get_abuse_info(ip_address)
        if abuse["blacklisted"]:
            risk_score += 30
            risk_factors.append(f"Blacklisted ({abuse['reports']} reportes)")
        
        risk_emoji = "🟢 Baja"
        if risk_score > 20: risk_emoji = "🟡 Media"
        if risk_score > 50: risk_emoji = "🔴 Alta"
        if risk_score > 70: risk_emoji = "⛔ Crítica"

        # Reverse DNS
        rdns = "No disponible"
        try:
            rdns_req = requests.get(
                f"https://dns.google/resolve?name={'.'.join(reversed(ip_address.split('.')))}.in-addr.arpa&type=PTR",
                timeout=5, headers=HEADERS
            )
            if rdns_req.status_code == 200:
                answers = rdns_req.json().get("Answer", [])
                if answers:
                    rdns = answers[0].get('data', 'N/A').rstrip('.')
        except Exception:
            pass

        # WHOIS básico
        whois = _get_whois_basic(ip_address)
        
        # Puertos abiertos (escaneo rápido)
        open_ports = _get_open_ports(ip_address)

        # Tipo de conexión
        if is_mobile:
            conn_type = "📱 Móvil"
        elif is_hosting:
            conn_type = "🏢 Datacenter/Hosting"
        else:
            conn_type = "🏠 Residencial"

        return {
            "ip": data['query'],
            "country": f"{data['country']} {data['countryCode']}",
            "country_code": data['countryCode'],
            "city": f"{data['city']}, {data['regionName']}",
            "region": data.get('regionName', 'N/A'),
            "zip": data.get('zip', 'N/A'),
            "coords": f"{data['lat']}, {data['lon']}",
            "lat": data['lat'],
            "lon": data['lon'],
            "timezone": data['timezone'],
            "isp": data['isp'],
            "org": data['org'],
            "asn": data.get('as', 'N/A'),
            "rdns": rdns,
            "type": conn_type,
            "proxy": "⚠️ VPN/Proxy Detectado" if is_proxy else "✅ Limpia",
            "risk": risk_emoji,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "map_url": f"https://www.google.com/maps?q={data['lat']},{data['lon']}",
            # Datos extra
            "hostname": extra.get("hostname", rdns),
            "net_name": whois["net_name"],
            "net_range": whois["net_range"],
            "abuse_contact": whois["abuse_contact"],
            "open_ports": open_ports,
            "blacklisted": abuse["blacklisted"],
            "threat_type": abuse["threat_type"],
            "abuse_reports": abuse["reports"],
            # Links OSINT
            "osint_links": {
                "Shodan": f"https://www.shodan.io/host/{ip_address}",
                "Censys": f"https://search.censys.io/hosts/{ip_address}",
                "VirusTotal": f"https://www.virustotal.com/gui/ip-address/{ip_address}",
                "AbuseIPDB": f"https://www.abuseipdb.com/check/{ip_address}",
                "GreyNoise": f"https://viz.greynoise.io/ip/{ip_address}",
                "IPVoid": f"https://www.ipvoid.com/ip-blacklist-check/?ip={ip_address}",
            }
        }

    except Exception as e:
        logger.error(f"Error IP: {e}")
        return {"error": f"Error analizando IP: {str(e)}"}
