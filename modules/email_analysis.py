
import requests
import re
from config import logger

def analyze_email(email):
    """Analiza reputación, formato y configuración técnica del email"""
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return {"error": "Formato inválido"}
    
    domain = email.split('@')[1]
    
    # 1. EmailRep.io (Reputación)
    rep_data = {}
    try:
        r = requests.get(f"https://emailrep.io/{email}", timeout=5)
        if r.status_code == 200:
            rep_data = r.json()
    except:
        pass

    # 2. DNS MX Check (Técnico)
    mx_records = []
    try:
        r = requests.get(f"https://dns.google/resolve?name={domain}&type=MX", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if 'Answer' in data:
                mx_records = [a['data'].split()[-1].rstrip('.') for a in data['Answer']]
    except:
        pass

    return {
        "email": email,
        "domain": domain,
        "reputation": rep_data.get("reputation", "Desconocida").upper(),
        "suspicious": rep_data.get("suspicious", False),
        "leaked": rep_data.get("details", {}).get("credentials_leaked", False),
        "malicious": rep_data.get("details", {}).get("malicious_activity", False),
        "mx_records": mx_records[:2], # Solo los primeros 2
        "disposable": rep_data.get("details", {}).get("disposable", False),
        "links": {
            "haveibeenpwned": f"https://haveibeenpwned.com/account/{email}",
            "intelx": f"https://intelx.io/?s={email}",
            "dehashed": f"https://dehashed.com/search?query={email}"
        }
    }
