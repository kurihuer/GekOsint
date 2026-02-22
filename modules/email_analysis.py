
import requests
import re
import socket
import hashlib
from config import logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Lista expandida de dominios desechables
DISPOSABLE_DOMAINS = {
    "tempmail.com", "guerrillamail.com", "yopmail.com", "10minutemail.com",
    "mailinator.com", "throwaway.email", "fakeinbox.com", "sharklasers.com",
    "spam4.me", "grr.la", "maildrop.cc", "getnada.com", "mintemail.com",
    "temp-mail.org", "guerrillamailblock.com", "dispostable.com",
    "trashmail.com", "trashmail.me", "trashmail.net", "mailnesia.com",
    "tempail.com", "tempr.email", "discard.email", "discardmail.com",
    "mailcatch.com", "mytemp.email", "mohmal.com", "emailondeck.com",
    "crazymailing.com", "tempinbox.com", "harakirimail.com", "jetable.org",
    "mailexpire.com", "mailforspam.com", "mailmoat.com", "mailnull.com",
    "mailshell.com", "mailzilla.com", "nomail.xl.cx", "nowmymail.com",
    "spamfree24.org", "spamgourmet.com", "tempomail.fr", "thankyou2010.com",
    "trashemail.de", "trashymail.com", "trashymail.net", "wegwerfmail.de",
    "wegwerfmail.net", "wh4f.org", "yopmail.fr", "yopmail.net",
    "guerrillamail.info", "guerrillamail.net", "guerrillamail.org",
    "guerrillamail.de", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "guerrillamail.biz", "tempmail.ninja", "tempmailo.com",
}

def analyze_email(email):
    """Análisis profundo de correo electrónico con múltiples fuentes"""
    email = email.strip().lower()
    
    # Validación
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, email):
        return {"error": "Formato inválido"}
    
    domain = email.split('@')[1]
    local_part = email.split('@')[0]
    
    # 1. Verificar dominio
    domain_exists = verify_domain(domain)
    
    # 2. DNS MX Check
    mx_records = get_mx_records(domain)
    
    # 3. Reputación
    rep_data = get_email_reputation(email)
    
    # 4. Disposable Check
    is_disposable = check_disposable_email(domain)
    
    # 5. Proveedor
    provider = detect_email_provider(mx_records, domain)
    
    # 6. Breach check (HaveIBeenPwned via hash)
    breaches = check_breaches(email)
    
    # 7. Gravatar check
    gravatar = check_gravatar(email)
    
    # 8. Análisis del local part
    local_analysis = analyze_local_part(local_part)
    
    # 9. DNS adicional (SPF, DMARC, DKIM)
    dns_security = check_dns_security(domain)
    
    # 10. Edad estimada del dominio
    domain_age = get_domain_age(domain)
    
    return {
        "email": email,
        "domain": domain,
        "local_part": local_part,
        "domain_exists": domain_exists,
        "reputation": rep_data.get("reputation", "UNKNOWN").upper() if rep_data else "UNKNOWN",
        "suspicious": rep_data.get("suspicious", False) if rep_data else False,
        "leaked": rep_data.get("details", {}).get("credentials_leaked", False) if rep_data else False,
        "malicious": rep_data.get("details", {}).get("malicious_activity", False) if rep_data else False,
        "mx_records": mx_records[:5] if mx_records else [],
        "disposable": is_disposable,
        "provider": provider,
        "breaches": breaches,
        "gravatar": gravatar,
        "local_analysis": local_analysis,
        "dns_security": dns_security,
        "domain_age": domain_age,
        "links": {
            "haveibeenpwned": f"https://haveibeenpwned.com/account/{email}",
            "intelx": f"https://intelx.io/?s={email}",
            "dehashed": f"https://dehashed.com/search?query={email}",
            "psbdmp": f"https://psbdmp.ws/api/search/{email}",
            "emailrep": f"https://emailrep.io/{email}",
            "hunter": f"https://hunter.io/email-verifier/{email}",
            "google_dork": f"https://www.google.com/search?q=%22{email}%22",
            "holehe": f"https://github.com/megadose/holehe",
        }
    }

def verify_domain(domain):
    """Verifica si el dominio tiene registros DNS"""
    try:
        socket.gethostbyname(domain)
        return True
    except (socket.gaierror, OSError):
        return False

def get_mx_records(domain):
    """Obtiene registros MX del dominio"""
    mx_records = []
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        
        answers = resolver.resolve(domain, 'MX')
        mx_records = [str(rdata).rstrip('.') for rdata in answers]
        mx_records.sort()
    except ImportError:
        # Fallback sin dnspython
        try:
            r = requests.get(
                f"https://dns.google/resolve?name={domain}&type=MX",
                timeout=5, headers=HEADERS
            )
            if r.status_code == 200:
                answers = r.json().get("Answer", [])
                mx_records = [a.get("data", "").rstrip('.') for a in answers]
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Error obteniendo MX: {e}")
    
    return mx_records

def get_email_reputation(email):
    """Consulta reputación en emailrep.io"""
    try:
        headers = {"User-Agent": "GekOsint/5.0", "Accept": "application/json"}
        r = requests.get(f"https://emailrep.io/{email}", headers=headers, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning(f"EmailRep no disponible: {e}")
    return {}

def check_disposable_email(domain):
    """Verifica si es un dominio de email temporal"""
    if domain.lower() in DISPOSABLE_DOMAINS:
        return True
    
    # Verificar con API externa como fallback
    try:
        r = requests.get(
            f"https://open.kickbox.com/v1/disposable/{domain}",
            timeout=5, headers=HEADERS
        )
        if r.status_code == 200:
            return r.json().get("disposable", False)
    except Exception:
        pass
    
    return False

def detect_email_provider(mx_records, domain):
    """Detecta el proveedor de email por registros MX y dominio"""
    if not mx_records:
        # Verificar por dominio conocido
        known = {
            "gmail.com": "Google / Gmail",
            "googlemail.com": "Google / Gmail",
            "outlook.com": "Microsoft / Outlook",
            "hotmail.com": "Microsoft / Hotmail",
            "live.com": "Microsoft / Live",
            "yahoo.com": "Yahoo Mail",
            "yahoo.com.mx": "Yahoo Mail MX",
            "protonmail.com": "ProtonMail (Privado)",
            "proton.me": "ProtonMail (Privado)",
            "icloud.com": "Apple / iCloud",
            "me.com": "Apple / iCloud",
            "aol.com": "AOL Mail",
            "zoho.com": "Zoho Mail",
            "tutanota.com": "Tutanota (Privado)",
            "tuta.io": "Tutanota (Privado)",
            "mail.ru": "Mail.ru",
            "yandex.com": "Yandex Mail",
        }
        return known.get(domain.lower(), "Desconocido/Privado")
    
    mx_str = ' '.join(mx_records).lower()
    
    providers = [
        (["google", "googlemail", "gmail"], "Google Workspace / Gmail"),
        (["outlook", "protection.outlook", "microsoft"], "Microsoft 365 / Outlook"),
        (["protonmail", "proton.ch", "protonmail.ch"], "ProtonMail (Privado)"),
        (["zoho"], "Zoho Mail"),
        (["yahoo"], "Yahoo Mail"),
        (["icloud", "apple"], "Apple / iCloud"),
        (["yandex"], "Yandex Mail"),
        (["mail.ru"], "Mail.ru"),
        (["tutanota", "tuta.io"], "Tutanota (Privado)"),
        (["mxhichina", "alibaba"], "Alibaba Cloud"),
        (["ovh.net"], "OVH"),
        (["ionos", "1and1"], "IONOS / 1&1"),
        (["godaddy", "secureserver"], "GoDaddy"),
        (["namecheap", "privateemail"], "Namecheap"),
        (["dondominio"], "DonDominio"),
    ]
    
    for keywords, name in providers:
        if any(kw in mx_str for kw in keywords):
            return name
    
    return "Servidor Propio / Desconocido"

def check_breaches(email):
    """Verifica brechas de datos usando APIs públicas"""
    breaches = []
    
    # Método 1: XposedOrNot (API pública gratuita)
    try:
        r = requests.get(
            f"https://api.xposedornot.com/v1/check-email/{email}",
            timeout=8, headers=HEADERS
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("breaches"):
                for b in data["breaches"]:
                    if isinstance(b, str):
                        breaches.append(b)
                    elif isinstance(b, dict):
                        breaches.append(b.get("name", b.get("domain", "Desconocido")))
    except Exception as e:
        logger.debug(f"XposedOrNot error: {e}")
    
    # Método 2: BreachDirectory (API pública)
    try:
        r = requests.get(
            f"https://breachdirectory.p.rapidapi.com/?func=auto&term={email}",
            timeout=8,
            headers={
                "User-Agent": "GekOsint/5.0",
                "Accept": "application/json"
            }
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("result"):
                for entry in data["result"][:5]:
                    source = entry.get("sources", ["Desconocido"])
                    if isinstance(source, list):
                        breaches.extend(source)
                    else:
                        breaches.append(str(source))
    except Exception:
        pass
    
    # Eliminar duplicados
    return list(set(breaches))[:15]

def check_gravatar(email):
    """Verifica si el email tiene un perfil de Gravatar"""
    try:
        email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
        r = requests.get(
            f"https://www.gravatar.com/avatar/{email_hash}?d=404",
            timeout=5, headers=HEADERS
        )
        if r.status_code == 200:
            return {
                "exists": True,
                "url": f"https://www.gravatar.com/avatar/{email_hash}",
                "profile": f"https://en.gravatar.com/{email_hash}"
            }
    except Exception:
        pass
    return {"exists": False}

def analyze_local_part(local_part):
    """Analiza el nombre de usuario del email para extraer información"""
    analysis = {
        "has_numbers": bool(re.search(r'\d', local_part)),
        "has_dots": '.' in local_part,
        "has_plus": '+' in local_part,
        "length": len(local_part),
        "possible_name": None,
        "possible_year": None,
    }
    
    # Intentar extraer nombre
    name_match = re.match(r'^([a-zA-Z]+)[._]?([a-zA-Z]+)?', local_part)
    if name_match:
        parts = [p for p in name_match.groups() if p]
        if parts:
            analysis["possible_name"] = ' '.join(p.capitalize() for p in parts)
    
    # Intentar extraer año
    year_match = re.search(r'(19[5-9]\d|20[0-2]\d)', local_part)
    if year_match:
        analysis["possible_year"] = int(year_match.group(1))
    
    # Alias con +
    if '+' in local_part:
        analysis["base_email"] = local_part.split('+')[0]
        analysis["alias_tag"] = local_part.split('+')[1] if len(local_part.split('+')) > 1 else None
    
    return analysis

def check_dns_security(domain):
    """Verifica registros de seguridad DNS (SPF, DMARC)"""
    security = {"spf": False, "dmarc": False, "spf_record": None, "dmarc_record": None}
    
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        
        # SPF
        try:
            answers = resolver.resolve(domain, 'TXT')
            for rdata in answers:
                txt = str(rdata).strip('"')
                if 'v=spf1' in txt:
                    security["spf"] = True
                    security["spf_record"] = txt[:100]
                    break
        except Exception:
            pass
        
        # DMARC
        try:
            answers = resolver.resolve(f"_dmarc.{domain}", 'TXT')
            for rdata in answers:
                txt = str(rdata).strip('"')
                if 'v=DMARC1' in txt:
                    security["dmarc"] = True
                    security["dmarc_record"] = txt[:100]
                    break
        except Exception:
            pass
    except ImportError:
        # Fallback con Google DNS API
        try:
            r = requests.get(f"https://dns.google/resolve?name={domain}&type=TXT", timeout=5)
            if r.status_code == 200:
                for a in r.json().get("Answer", []):
                    if 'v=spf1' in a.get("data", ""):
                        security["spf"] = True
                        security["spf_record"] = a["data"][:100]
            
            r2 = requests.get(f"https://dns.google/resolve?name=_dmarc.{domain}&type=TXT", timeout=5)
            if r2.status_code == 200:
                for a in r2.json().get("Answer", []):
                    if 'v=DMARC1' in a.get("data", ""):
                        security["dmarc"] = True
                        security["dmarc_record"] = a["data"][:100]
        except Exception:
            pass
    
    return security

def get_domain_age(domain):
    """Intenta obtener la edad del dominio"""
    try:
        r = requests.get(
            f"https://rdap.org/domain/{domain}",
            timeout=8, headers=HEADERS
        )
        if r.status_code == 200:
            data = r.json()
            events = data.get("events", [])
            for event in events:
                if event.get("eventAction") == "registration":
                    return event.get("eventDate", "Desconocido")[:10]
    except Exception:
        pass
    return None
