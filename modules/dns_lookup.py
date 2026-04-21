
import requests
import socket
import logging
from config import logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_dns_info(domain):
    """Obtiene información completa de DNS y WHOIS para un dominio"""
    domain = domain.strip().lower()
    if domain.startswith("http"):
        domain = domain.split("//")[-1].split("/")[0]
    
    result = {
        "domain": domain,
        "a_records": [],
        "mx_records": [],
        "txt_records": [],
        "ns_records": [],
        "cname_records": [],
        "whois": {},
        "security": {"spf": False, "dmarc": False, "dnssec": False},
        "ip_info": None
    }

    # 1. Registros DNS (A, MX, TXT, NS, CNAME)
    record_types = ["A", "MX", "TXT", "NS", "CNAME"]
    for rtype in record_types:
        try:
            r = requests.get(f"https://dns.google/resolve?name={domain}&type={rtype}", timeout=8)
            if r.status_code == 200:
                answers = r.json().get("Answer", [])
                for ans in answers:
                    val = ans.get("data", "").rstrip('.')
                    if rtype == "A": result["a_records"].append(val)
                    elif rtype == "MX": result["mx_records"].append(val)
                    elif rtype == "TXT": result["txt_records"].append(val)
                    elif rtype == "NS": result["ns_records"].append(val)
                    elif rtype == "CNAME": result["cname_records"].append(val)
        except Exception as e:
            logger.debug(f"Error DNS {rtype}: {e}")

    # 2. Seguridad DNS
    for txt in result["txt_records"]:
        if "v=spf1" in txt.lower(): result["security"]["spf"] = True
    
    try:
        r = requests.get(f"https://dns.google/resolve?name=_dmarc.{domain}&type=TXT", timeout=5)
        if r.status_code == 200 and r.json().get("Answer"):
            result["security"]["dmarc"] = True
    except Exception: pass

    # 3. WHOIS Básico (RDAP)
    try:
        r = requests.get(f"https://rdap.org/domain/{domain}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            result["whois"] = {
                "registrar": data.get("port43", "N/A"),
                "status": ", ".join(data.get("status", [])),
                "events": {e.get("eventAction"): e.get("eventDate")[:10] for e in data.get("events", []) if "eventDate" in e}
            }
    except Exception: pass

    # 4. Info de la IP principal (si existe registro A)
    if result["a_records"]:
        from modules.ip_lookup import get_ip_info
        result["ip_info"] = get_ip_info(result["a_records"][0])

    return result
