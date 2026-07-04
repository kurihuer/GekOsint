# -*- coding: utf-8 -*-
"""
IP Lookup — geolocalización, ASN/WHOIS, reputación y puertos.

Mejoras v6.2:
  - Se elimina el escaneo de puertos por socket (`socket.connect_ex`): desde
    una IP de datacenter (Koyeb) es lento, poco fiable y a menudo lo bloquea
    el firewall del objetivo. Los puertos ahora vienen de Shodan (si hay key);
    si no, se indica claramente que requiere SHODAN_API_KEY en vez de devolver
    "Ninguno detectado" (que era engañoso).
  - Geolocalización con doble fuente (ip-api.com + ipinfo.io) y caché.
  - Reputación en paralelo (Shodan, AbuseIPDB, GreyNoise, VirusTotal, DNSBL).
  - Manejo de errores y timeouts endurecido.
"""

import requests
import socket
import re
import httpx
import concurrent.futures
import time
from config import logger, VT_API_KEY, ABUSEIPDB_KEY, SHODAN_API_KEY, GREYNOISE_API_KEY

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_CACHE = {}
_TTL = 600


def _is_valid_ip(ip):
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
        parts = ip.split('.')
        return all(0 <= int(p) <= 255 for p in parts)
    if ':' in ip:
        return True
    return False


def _is_private_ip(ip):
    private_ranges = [
        r'^10\.', r'^172\.(1[6-9]|2[0-9]|3[01])\.', r'^192\.168\.',
        r'^127\.', r'^0\.', r'^169\.254\.', r'^224\.', r'^240\.'
    ]
    return any(re.match(p, ip) for p in private_ranges)


def _get_vt(ip):
    if not VT_API_KEY:
        return {}
    try:
        r = httpx.get(
            f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
            headers={"x-apikey": VT_API_KEY}, timeout=12
        )
        if r.status_code == 200:
            return r.json().get("data", {}).get("attributes", {})
    except Exception:
        pass
    return {}


def _get_abuseipdb(ip):
    if not ABUSEIPDB_KEY:
        return {}
    try:
        r = httpx.get(
            "https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": ip, "maxAgeInDays": "90"},
            headers={"Key": ABUSEIPDB_KEY, "Accept": "application/json"},
            timeout=12
        )
        if r.status_code == 200:
            return r.json().get("data", {})
    except Exception:
        pass
    return {}


def _get_shodan(ip):
    if not SHODAN_API_KEY:
        return {}
    try:
        r = httpx.get(
            f"https://api.shodan.io/shodan/host/{ip}",
            params={"key": SHODAN_API_KEY}, timeout=12
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _get_greynoise(ip):
    if not GREYNOISE_API_KEY:
        return {}
    try:
        r = httpx.get(
            f"https://api.greynoise.io/v3/community/ip/{ip}",
            headers={"key": GREYNOISE_API_KEY}, timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _get_abuse_info(ip):
    result = {"blacklisted": False, "reports": 0, "threat_type": "Ninguna"}
    vt = _get_vt(ip)
    if vt:
        malicious = vt.get("last_analysis_stats", {}).get("malicious", 0)
        if malicious > 0:
            result["blacklisted"] = True
            result["reports"] = malicious
            result["threat_type"] = "Malicioso (VT)"
    try:
        # DNSBL: consultas DNS rápidas (no son escaneo de puertos)
        dnsbl_hosts = ["zen.spamhaus.org", "bl.spamcop.net", "dnsbl.sorbs.net"]
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
    result = {"net_name": "N/A", "net_range": "N/A", "abuse_contact": "N/A"}
    try:
        r = requests.get(f"https://rdap.arin.net/registry/ip/{ip}", timeout=8, headers=HEADERS)
        if r.status_code == 200:
            data = r.json()
            result["net_name"] = data.get("name", "N/A")
            start = data.get("startAddress", "")
            end   = data.get("endAddress", "")
            if start and end:
                result["net_range"] = f"{start} - {end}"
            for entity in data.get("entities", []):
                if "abuse" in entity.get("roles", []):
                    for vcard in entity.get("vcardArray", [None, []])[1]:
                        if vcard[0] == "email":
                            result["abuse_contact"] = vcard[3]
                            break
    except Exception:
        pass
    return result


def _ports_from_shodan(shodan_data):
    """Construye la lista de puertos a partir de los datos de Shodan."""
    ports = shodan_data.get("ports") or []
    if not ports:
        return None
    labeled = []
    for p in sorted(set(ports)):
        try:
            svc = socket.getservbyport(int(p))
            labeled.append(f"{p}/{svc.upper()}")
        except Exception:
            labeled.append(f"{p}/TCP")
    return labeled


def _get_additional_intel(ip_address):
    """Obtiene información adicional: ASN detallado, reverse DNS extendido."""
    intel = {"asn_info": None, "rdns_extended": None}
    try:
        r = httpx.get(
            f"https://api.bgpview.io/ip/{ip_address}",
            timeout=10, headers=HEADERS
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("data", {}).get("asn"):
                asn = data["data"]["asn"]
                intel["asn_info"] = {
                    "asn": asn.get("asn", {}).get("asn"),
                    "name": asn.get("asn", {}).get("name"),
                    "country": asn.get("asn", {}).get("country_code"),
                    "type": asn.get("asn", {}).get("type"),
                }
    except Exception:
        pass
    try:
        r = httpx.get(
            f"https://api.hackertarget.com/reversedns/?q={ip_address}",
            timeout=8
        )
        if r.status_code == 200 and r.text:
            lines = [l.strip() for l in r.text.split('\n') if l.strip() and 'error' not in l.lower()]
            intel["rdns_extended"] = lines[:5] if lines else None
    except Exception:
        pass
    return intel


def get_ip_info(ip_address):
    ip_address = ip_address.strip()
    missing_keys = []
    if not SHODAN_API_KEY:
        missing_keys.append("SHODAN_API_KEY")
    if not ABUSEIPDB_KEY:
        missing_keys.append("ABUSEIPDB_KEY")
    if not VT_API_KEY:
        missing_keys.append("VT_API_KEY")
    if not GREYNOISE_API_KEY:
        missing_keys.append("GREYNOISE_API_KEY")

    if not _is_valid_ip(ip_address):
        try:
            ip_address = socket.gethostbyname(ip_address)
        except Exception:
            return {"error": f"'{ip_address}' no es una IP válida ni un hostname resoluble.",
                    "missing_keys": missing_keys}
    if _is_private_ip(ip_address):
        return {"error": f"'{ip_address}' es una IP privada/reservada.", "missing_keys": missing_keys}

    ck = ("ip", ip_address)
    now = int(time.time())
    entry = _CACHE.get(ck)
    if entry and now - entry[0] <= _TTL:
        return entry[1]

    try:
        url = (
            f"http://ip-api.com/json/{ip_address}"
            "?fields=status,message,country,countryCode,region,regionName,"
            "city,zip,lat,lon,timezone,isp,org,as,proxy,hosting,query,mobile"
        )
        data = requests.get(url, timeout=10, headers=HEADERS).json()
        if data.get('status') != 'success':
            return {"error": "IP no encontrada o privada/bogon.", "missing_keys": missing_keys}

        extra = {}
        try:
            r2 = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=8, headers=HEADERS)
            if r2.status_code == 200:
                extra = r2.json()
        except Exception:
            pass

        shodan_data, abuse_data, gn_data = {}, {}, {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            fut_s = ex.submit(_get_shodan, ip_address)
            fut_a = ex.submit(_get_abuseipdb, ip_address)
            fut_g = ex.submit(_get_greynoise, ip_address)
            try: shodan_data = fut_s.result(timeout=12)
            except Exception: pass
            try: abuse_data = fut_a.result(timeout=12)
            except Exception: pass
            try: gn_data = fut_g.result(timeout=12)
            except Exception: pass

        is_proxy   = data.get('proxy', False)
        is_hosting = data.get('hosting', False)
        is_mobile  = data.get('mobile', False)

        risk_score, risk_factors = 0, []
        if is_proxy:    risk_score += 40; risk_factors.append("VPN/Proxy")
        if is_hosting:  risk_score += 30; risk_factors.append("Datacenter")

        shodan_ports = shodan_data.get("ports", [])
        if shodan_ports:
            risk_score += 10
            risk_factors.append(f"Servicios expuestos ({len(shodan_ports)})")

        abuse_score = abuse_data.get("abuseConfidenceScore", 0)
        if abuse_score > 0:
            risk_score += min(40, int(abuse_score / 2))
            risk_factors.append(f"Abuso ({abuse_score}%)")

        if gn_data.get("classification") and str(gn_data["classification"]).lower() != "benign":
            risk_score += 15; risk_factors.append(f"GreyNoise {gn_data['classification']}")

        abuse = _get_abuse_info(ip_address)
        if abuse.get("blacklisted"):
            risk_score += 30; risk_factors.append(f"Blacklist ({abuse.get('reports', 0)})")

        risk_score = min(100, risk_score)

        if   risk_score > 80: risk_label = "⛔ Crítica"
        elif risk_score > 50: risk_label = "🔴 Alta"
        elif risk_score > 20: risk_label = "🟡 Media"
        else:                 risk_label = "🟢 Baja"

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

        whois = _get_whois_basic(ip_address)
        additional = _get_additional_intel(ip_address)

        # Puertos: SOLO desde Shodan (sin escaneo por socket)
        ports_from_shodan = _ports_from_shodan(shodan_data)
        if ports_from_shodan:
            open_ports = ports_from_shodan
        elif SHODAN_API_KEY:
            open_ports = ["Ninguno expuesto (según Shodan)"]
        else:
            open_ports = ["Requiere SHODAN_API_KEY"]

        if is_mobile:        conn_type = "📱 Móvil"
        elif is_hosting:     conn_type = "🏢 Datacenter/Hosting"
        else:                conn_type = "🏠 Residencial"

        result = {
            "ip":            data['query'],
            "country":       f"{data['country']} {data['countryCode']}",
            "country_code":  data['countryCode'],
            "city":          f"{data['city']}, {data['regionName']}",
            "region":        data.get('regionName', 'N/A'),
            "zip":           data.get('zip', 'N/A'),
            "coords":        f"{data['lat']}, {data['lon']}",
            "lat":           data['lat'],
            "lon":           data['lon'],
            "timezone":      data['timezone'],
            "isp":           data['isp'],
            "org":           data['org'],
            "asn":           data.get('as', 'N/A'),
            "rdns":          rdns,
            "type":          conn_type,
            "proxy":         "⚠️ VPN/Proxy Detectado" if is_proxy else "✅ Limpia",
            "risk":          risk_label,
            "risk_score":    risk_score,
            "risk_factors":  risk_factors,
            "map_url":       f"https://www.google.com/maps?q={data['lat']},{data['lon']}",
            "hostname":      extra.get("hostname", rdns),
            "net_name":      whois["net_name"],
            "net_range":     whois["net_range"],
            "abuse_contact": whois["abuse_contact"],
            "open_ports":    open_ports,
            "blacklisted":   abuse.get("blacklisted", False) or abuse_data.get("abuseConfidenceScore", 0) > 0,
            "threat_type":   abuse.get("threat_type", "Ninguna"),
            "abuse_reports": abuse.get("reports", 0) or abuse_data.get("totalReports", 0),
            "osint_links": {
                "Shodan":    f"https://www.shodan.io/host/{ip_address}",
                "Censys":    f"https://search.censys.io/hosts/{ip_address}",
                "VirusTotal":f"https://www.virustotal.com/gui/ip-address/{ip_address}",
                "AbuseIPDB": f"https://www.abuseipdb.com/check/{ip_address}",
                "GreyNoise": f"https://viz.greynoise.io/ip/{ip_address}",
                "IPVoid":    f"https://www.ipvoid.com/ip-blacklist-check/?ip={ip_address}",
            },
            "asn_info": additional.get("asn_info"),
            "rdns_extended": additional.get("rdns_extended"),
        }
        result["missing_keys"] = missing_keys
        _CACHE[ck] = (now, result)
        return result

    except Exception as e:
        logger.error(f"Error IP: {e}")
        return {"error": f"Error analizando IP: {str(e)}", "missing_keys": missing_keys}
