# -*- coding: utf-8 -*-
"""
Domain / DNS Lookup — registros DNS, seguridad y WHOIS (RDAP).

Mejoras v6.2:
  - WHOIS arreglado: el registrar ya NO se toma de `port43` (que es el host
    del servidor WHOIS, no el registrar). Ahora se extrae de las entities RDAP
    con rol "registrar" (vcard "fn"), más el IANA ID si está.
  - DNSSEC real: se lee `secureDNS.delegationSigned` del RDAP.
  - AAAA (IPv6) añadido a los tipos de registro.
"""

import requests
from config import logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _extract_registrar(rdap_data):
    """Extrae el nombre del registrar desde las entities RDAP."""
    registrar = None
    iana_id = None
    for ent in rdap_data.get("entities", []):
        roles = ent.get("roles", [])
        if "registrar" in roles:
            # vcardArray: ["vcard", [ [...], ["fn", {}, "text", "NOMBRE"], ... ]]
            try:
                for item in ent.get("vcardArray", [None, []])[1]:
                    if item[0] == "fn":
                        registrar = item[3]
                        break
            except Exception:
                pass
            # IANA ID del registrar
            for pid in ent.get("publicIds", []):
                if pid.get("type", "").lower().startswith("iana"):
                    iana_id = pid.get("identifier")
            if registrar:
                break
    return registrar, iana_id


def get_dns_info(domain):
    """Obtiene información completa de DNS y WHOIS para un dominio."""
    domain = domain.strip().lower()
    if domain.startswith("http"):
        domain = domain.split("//")[-1].split("/")[0]
    domain = domain.split("/")[0].strip()

    result = {
        "domain": domain,
        "a_records": [],
        "aaaa_records": [],
        "mx_records": [],
        "txt_records": [],
        "ns_records": [],
        "cname_records": [],
        "whois": {},
        "security": {"spf": False, "dmarc": False, "dnssec": False},
        "ip_info": None
    }

    # 1. Registros DNS (A, AAAA, MX, TXT, NS, CNAME)
    record_types = ["A", "AAAA", "MX", "TXT", "NS", "CNAME"]
    for rtype in record_types:
        try:
            r = requests.get(
                f"https://dns.google/resolve?name={domain}&type={rtype}",
                timeout=8, headers=HEADERS
            )
            if r.status_code == 200:
                answers = r.json().get("Answer", [])
                for ans in answers:
                    val = ans.get("data", "").rstrip('.')
                    if rtype == "A":       result["a_records"].append(val)
                    elif rtype == "AAAA":  result["aaaa_records"].append(val)
                    elif rtype == "MX":    result["mx_records"].append(val)
                    elif rtype == "TXT":   result["txt_records"].append(val)
                    elif rtype == "NS":    result["ns_records"].append(val)
                    elif rtype == "CNAME": result["cname_records"].append(val)
        except Exception as e:
            logger.debug(f"Error DNS {rtype}: {e}")

    # 2. Seguridad DNS (SPF / DMARC)
    for txt in result["txt_records"]:
        if "v=spf1" in txt.lower():
            result["security"]["spf"] = True
    try:
        r = requests.get(f"https://dns.google/resolve?name=_dmarc.{domain}&type=TXT",
                         timeout=5, headers=HEADERS)
        if r.status_code == 200 and r.json().get("Answer"):
            for a in r.json()["Answer"]:
                if "v=dmarc1" in a.get("data", "").lower():
                    result["security"]["dmarc"] = True
                    break
    except Exception:
        pass

    # 3. WHOIS (RDAP) — registrar real, fechas y DNSSEC
    try:
        r = requests.get(f"https://rdap.org/domain/{domain}", timeout=10, headers=HEADERS)
        if r.status_code == 200:
            data = r.json()
            registrar, iana_id = _extract_registrar(data)
            events = {}
            for e in data.get("events", []):
                if "eventDate" in e and e.get("eventAction"):
                    events[e["eventAction"]] = e["eventDate"][:10]
            result["whois"] = {
                "registrar": registrar or "N/A",
                "registrar_iana_id": iana_id,
                "status": ", ".join(data.get("status", [])) or "N/A",
                "events": events,
                "created": events.get("registration"),
                "expires": events.get("expiration"),
                "updated": events.get("last changed") or events.get("last update of rdap database"),
            }
            # DNSSEC
            secure = data.get("secureDNS", {})
            if secure.get("delegationSigned"):
                result["security"]["dnssec"] = True
    except Exception as e:
        logger.debug(f"RDAP error: {e}")

    # 4. Info de la IP principal (si existe registro A)
    if result["a_records"]:
        try:
            from modules.ip_lookup import get_ip_info
            result["ip_info"] = get_ip_info(result["a_records"][0])
        except Exception as e:
            logger.debug(f"ip_info en DNS: {e}")

    return result
