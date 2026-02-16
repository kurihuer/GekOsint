
import requests
import re
import socket
from config import logger

def analyze_email(email):
    """Analiza reputación, formato y configuración técnica del email"""
    # Regex más robusto (RFC 5322)
    email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if not re.match(email_regex, email):
        return {"error": "Formato inválido"}
    
    domain = email.split('@')[1]
    
    # 1. EmailRep.io (Reputación - Pública)
    rep_data = {}
    try:
        headers = {"User-Agent": "GekOsint/4.0"}
        r = requests.get(f"https://emailrep.io/{email}", headers=headers, timeout=5)
        if r.status_code == 200:
            rep_data = r.json()
    except:
        pass

    # 2. DNS MX Check (Técnico - Google DNS)
    mx_records = []
    try:
        r = requests.get(f"https://dns.google/resolve?name={domain}&type=MX", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if 'Answer' in data:
                # Ordenar por prioridad si es posible, aquí tomamos el target
                mx_records = [a['data'].split()[-1].rstrip('.') for a in data['Answer']]
    except Exception as e:
        logger.error(f"DNS Error: {e}")

    # 3. Disposable Check (Lista local básica + API externa opcional)
    is_disposable = rep_data.get("details", {}).get("disposable", False)
    if not is_disposable:
        # Fallback check simple
        disposable_domains = ["tempmail.com", "guerrillamail.com", "yopmail.com", "10minutemail.com"]
        if domain in disposable_domains:
            is_disposable = True

    # 4. Detección de proveedor
    provider = "Desconocido/Privado"
    if "google.com" in str(mx_records) or "googlemail" in str(mx_records): provider = "Google Workspace / Gmail"
    elif "outlook.com" in str(mx_records) or "protection.outlook.com" in str(mx_records): provider = "Microsoft 365 / Outlook"
    elif "protonmail" in str(mx_records): provider = "ProtonMail (Privado)"

    return {
        "email": email,
        "domain": domain,
        "reputation": rep_data.get("reputation", "Desconocida").upper(),
        "suspicious": rep_data.get("suspicious", False),
        "leaked": rep_data.get("details", {}).get("credentials_leaked", False),
        "malicious": rep_data.get("details", {}).get("malicious_activity", False),
        "mx_records": mx_records[:3], # Top 3 registros MX
        "disposable": is_disposable,
        "provider": provider,
        "links": {
            "haveibeenpwned": f"https://haveibeenpwned.com/account/{email}",
            "intelx": f"https://intelx.io/?s={email}",
            "dehashed": f"https://dehashed.com/search?query={email}",
            "psbdmp": f"https://psbdmp.ws/api/search/{email}"
        }
    }
