import requests
import re
import phonenumbers
from phonenumbers import geocoder, carrier as ph_carrier
from config import logger, RAPIDAPI_KEY
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_CACHE = {}
_TTL = 600

def check_wa_registered(clean):
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
    try:
        r = requests.get(
            f"https://wa.me/{clean}",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"},
            timeout=10,
            allow_redirects=True
        )
        if r.status_code != 200:
            return None
        html = r.text or ""
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html, re.IGNORECASE)
        if not m:
            return None
        img = m.group(1).strip()
        if not img:
            return None
        low = img.lower()
        if "whatsapp" in low and ("logo" in low or "icon" in low or "static" in low):
            return None
        return img
    except Exception:
        return None

def check_wa_business(clean):
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
    return {}

def _get_caller_name(clean, country_code_alpha, national_number):
    name = None
    source = None

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
    try:
        missing_keys = []
        if not RAPIDAPI_KEY:
            missing_keys.append("RAPIDAPI_KEY")

        raw = (number or "").strip()
        if raw and not raw.startswith("+") and raw[0].isdigit():
            raw = "+" + raw
        parsed = phonenumbers.parse(raw, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"error": "Numero invalido. Usa formato: +521234567890", "missing_keys": missing_keys}

        e164     = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        intl     = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        clean    = e164.replace("+", "")

        country  = geocoder.description_for_number(parsed, "es")
        operador = ph_carrier.name_for_number(parsed, "es") or "Desconocido/portado"

        country_code = parsed.country_code
        region_code = phonenumbers.region_code_for_number(parsed) or phonenumbers.region_code_for_country_code(country_code)
        national_digits = re.sub(r'\D', '', national)

        ck = ("wa", clean)
        now = int(time.time())
        cached = _CACHE.get(ck)
        if cached and now - cached[0] <= _TTL:
            return cached[1]

        registered = check_wa_registered(clean)
        spam = check_spam_reports(clean)
        photo = get_wa_profile_photo(clean)
        is_business = check_wa_business(clean)
        social = get_social_presence(clean, e164)

        caller_name, caller_source = _get_caller_name(clean, region_code or "", national_digits)

        if registered is None:
            if caller_name or spam.get("total_reports", 0) > 0:
                registered = True

        result = {
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
            "tg_link":      f"https://t.me/+{clean}",
            "links": {
                "truecaller":  f"https://www.truecaller.com/search/{(region_code or 'global').lower()}/{clean}",
                "getcontact":  f"https://getcontact.com/en/number/{clean}",
                "syncme":      f"https://www.sync.me/search/?number={e164}",
                "spamcalls":   f"https://spamcalls.net/en/number/{clean}",
                "whocalledme": f"https://whocalledme.com/PhoneNumber/{clean}",
                "tellows":     f"https://www.tellows.com/num/{clean}",
                "numbway":     f"https://numbway.com/phone/{clean}",
                "google_dork": f"https://www.google.com/search?q=%22{e164}%22+OR+%22{clean}%22",
            }
        }
        result["business"] = is_business
        result["name"] = caller_name
        result["profile_picture"] = photo
        result["missing_keys"] = missing_keys
        _CACHE[ck] = (now, result)
        return result

    except phonenumbers.phonenumberutil.NumberParseException:
        missing_keys = []
        if not RAPIDAPI_KEY:
            missing_keys.append("RAPIDAPI_KEY")
        return {"error": "Formato invalido. Usa: +521234567890", "missing_keys": missing_keys}
    except Exception as e:
        logger.error(f"WA OSINT error: {e}")
        missing_keys = []
        if not RAPIDAPI_KEY:
            missing_keys.append("RAPIDAPI_KEY")
        return {"error": str(e), "missing_keys": missing_keys}
