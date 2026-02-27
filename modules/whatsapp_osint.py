
import requests
import re
import phonenumbers
from phonenumbers import geocoder, carrier as ph_carrier
from config import logger, RAPIDAPI_KEY

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def check_wa_registered(clean):
    """Verifica registro en WhatsApp via wa.me"""
    try:
        r = requests.get(
            f"https://wa.me/{clean}",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"},
            timeout=10, allow_redirects=True
        )
        if r.status_code == 200:
            if "api.whatsapp.com/send" in r.url or "api.whatsapp.com/send" in r.text:
                return True
            if "phone_number_invalid" in r.text:
                return False
    except Exception as e:
        logger.debug(f"wa.me: {e}")
    return None

def check_spam_reports(clean):
    """Busca reportes de spam en multiples fuentes"""
    results = {"total_reports": 0, "sources": [], "labels": []}

    try:
        r = requests.get(
            f"https://spamcalls.net/en/number/{clean}",
            headers=HEADERS, timeout=8
        )
        if r.status_code == 200:
            count_match = re.search(r'(\d+)\s*(?:report|reporte)', r.text, re.IGNORECASE)
            label_matches = re.findall(r'class="label[^"]*">([^<]{3,30})</span>', r.text)
            if count_match:
                n = int(count_match.group(1))
                results["total_reports"] += n
                if n > 0:
                    results["sources"].append(f"SpamCalls ({n})")
            if label_matches:
                results["labels"] += [l.strip() for l in label_matches[:4]]
    except Exception as e:
        logger.debug(f"spamcalls: {e}")

    try:
        r2 = requests.get(
            f"https://whocalledme.com/PhoneNumber/{clean}",
            headers=HEADERS, timeout=8
        )
        if r2.status_code == 200:
            count_match = re.search(r'(\d+)\s*(?:comment|reporte|report)', r2.text, re.IGNORECASE)
            if count_match:
                n = int(count_match.group(1))
                results["total_reports"] += n
                if n > 0:
                    results["sources"].append(f"WhoCalledMe ({n})")
    except Exception as e:
        logger.debug(f"whocalledme: {e}")

    try:
        r3 = requests.get(
            f"https://www.tellows.com/num/{clean}",
            headers=HEADERS, timeout=8
        )
        if r3.status_code == 200:
            score_match = re.search(r'score["\s:]+(\d)', r3.text, re.IGNORECASE)
            if score_match:
                score = int(score_match.group(1))
                if score >= 7:
                    results["total_reports"] += 1
                    results["sources"].append(f"Tellows (score {score}/9)")
                    results["labels"].append("Spam probable")
    except Exception:
        pass

    return results

def get_wa_profile_photo(clean):
    """Intenta obtener foto de perfil publica"""
    endpoints = [
        f"https://wa.me/p/{clean}",
        f"https://api.whatsapp.com/send?phone={clean}"
    ]
    for url in endpoints:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "WhatsApp/2.23.20.0 A"},
                timeout=8, allow_redirects=True
            )
            if r.status_code == 200 and "image/jpeg" in r.headers.get("Content-Type", ""):
                return url
        except Exception:
            pass
    return None

def check_wa_business(clean):
    """Verifica si es una cuenta de WhatsApp Business"""
    try:
        r = requests.get(
            f"https://wa.me/{clean}",
            headers={"User-Agent": "WhatsApp/2.23.20.0 B"},
            timeout=8, allow_redirects=True
        )
        if r.status_code == 200:
            text = r.text.lower()
            if "business" in text or "catalog" in text:
                return True
    except Exception:
        pass
    return False

def get_social_presence(clean, e164):
    """Busca presencia del numero en redes sociales"""
    presence = {}

    try:
        r = requests.get(
            f"https://t.me/+{clean}",
            headers=HEADERS, timeout=5, allow_redirects=True
        )
        if r.status_code == 200 and "tgme_page" in r.text:
            presence["telegram"] = True
    except Exception:
        pass

    return presence

def _get_caller_name(clean, country_code_alpha, national_number):
    """Intenta obtener el nombre del propietario via multiples fuentes gratuitas"""
    name = None
    source = None

    # 1. Numbway scraping
    try:
        r = requests.get(
            f"https://numbway.com/phone/{clean}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=10
        )
        if r.status_code == 200:
            name_match = re.search(r'<h2[^>]*>([^<]{2,60})</h2>', r.text)
            if name_match:
                found = name_match.group(1).strip()
                if found and not any(w in found.lower() for w in ["unknown", "numbway", "phone", "number", "lookup"]):
                    name = found
                    source = "Numbway"
    except Exception as e:
        logger.debug(f"Numbway WA: {e}")

    # 2. Truecaller API (si hay key)
    if not name and RAPIDAPI_KEY:
        try:
            r = requests.post(
                "https://truecaller-api3.p.rapidapi.com/v2.php",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "x-rapidapi-host": "truecaller-api3.p.rapidapi.com",
                    "x-rapidapi-key": RAPIDAPI_KEY
                },
                data={
                    "phone": national_number,
                    "countryCode": country_code_alpha
                },
                timeout=12
            )
            if r.status_code == 200:
                data = r.json()
                tc = data.get("truecaller_lookup") or data
                tc_name = tc.get("name") or tc.get("caller_name") or tc.get("callerName")
                if tc_name and tc_name.lower() not in ["unknown", "desconocido", ""]:
                    name = tc_name
                    source = "Truecaller"
        except Exception as e:
            logger.debug(f"Truecaller WA: {e}")

    # 3. SpamCalls scraping
    if not name:
        try:
            r = requests.get(
                f"https://spamcalls.net/en/number/{clean}",
                headers=HEADERS, timeout=8
            )
            if r.status_code == 200:
                name_match = re.search(r'caller["\s]*(?:name|id)[^:]*:\s*"?([^"<]{2,50})"?', r.text, re.IGNORECASE)
                if name_match:
                    found = name_match.group(1).strip()
                    if found and not any(w in found.lower() for w in ["unknown", "spam"]):
                        name = found
                        source = "SpamCalls"
        except Exception:
            pass

    return name, source

def analyze_whatsapp(number):
    """Analisis completo OSINT de WhatsApp para un numero"""
    try:
        parsed = phonenumbers.parse(number, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"error": "Numero invalido. Usa formato: +521234567890"}

        e164     = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        intl     = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        clean    = e164.replace("+", "")

        country  = geocoder.description_for_number(parsed, "es")
        operador = ph_carrier.name_for_number(parsed, "es") or "Desconocido/portado"

        country_code = parsed.country_code
        region_code = phonenumbers.region_code_for_number(parsed)
        national_digits = re.sub(r'\D', '', national)

        registered = check_wa_registered(clean)
        spam       = check_spam_reports(clean)
        photo      = get_wa_profile_photo(clean)
        is_business = check_wa_business(clean)
        social     = get_social_presence(clean, e164)

        caller_name, caller_source = _get_caller_name(clean, region_code, national_digits)

        return {
            "number":       e164,
            "national":     national,
            "international": intl,
            "clean":        clean,
            "country":      country,
            "country_code": country_code,
            "region_code":  region_code,
            "carrier":      operador,
            "registered":   registered,
            "is_business":  is_business,
            "photo":        photo,
            "caller_name":  caller_name,
            "caller_source": caller_source,
            "about":        None,
            "spam":         spam,
            "social":       social,
            "wa_link":      f"https://wa.me/{clean}",
            "wa_msg":       f"https://api.whatsapp.com/send?phone={clean}",
            "links": {
                "truecaller":  f"https://www.truecaller.com/search/{region_code.lower()}/{clean}",
                "getcontact":  f"https://getcontact.com/en/number/{clean}",
                "syncme":      f"https://www.sync.me/search/?number={e164}",
                "spamcalls":   f"https://spamcalls.net/en/number/{clean}",
                "whocalledme": f"https://whocalledme.com/PhoneNumber/{clean}",
                "tellows":     f"https://www.tellows.com/num/{clean}",
                "numbway":     f"https://numbway.com/phone/{clean}",
                "google_dork": f"https://www.google.com/search?q=%22{e164}%22+OR+%22{clean}%22",
            }
        }

    except phonenumbers.phonenumberutil.NumberParseException:
        return {"error": "Formato invalido. Usa: +521234567890"}
    except Exception as e:
        logger.error(f"WA OSINT error: {e}")
        return {"error": str(e)}
