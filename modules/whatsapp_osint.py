# -*- coding: utf-8 -*-
"""
WhatsApp OSINT — estado de registro, foto, spam reports, caller-ID y Business.

Mejoras v6.2:
  - Todos los scrapers (wa.me, SpamCalls, Tellows, WhoCalledMe, Numbway,
    Truecaller-web) ahora se enrutan por PROXY_URL si está configurado, para
    no ser bloqueados desde la IP de datacenter de Koyeb.
  - Caller-ID por RapidAPI (Truecaller) se mantiene como fuente principal.
  - Manejo de errores y timeouts endurecido.
"""

import requests
import re
import urllib.parse
import phonenumbers
from phonenumbers import geocoder, carrier as ph_carrier
from config import logger, RAPIDAPI_KEY
import time

try:
    from config import PROXY_URL
except Exception:
    PROXY_URL = ""

# Proxy para scrapers que bloquean IPs de datacenter (sitios web, NO APIs)
_PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_CACHE = {}
_TTL = 600

_SOCIAL_HOSTS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "x.com": "X",
    "twitter.com": "X",
    "linkedin.com": "LinkedIn",
    "github.com": "GitHub",
    "t.me": "Telegram",
}


def check_wa_registered(clean):
    try:
        r = requests.get(
            f"https://wa.me/{clean}",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"},
            timeout=10, allow_redirects=True, proxies=_PROXIES,
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
            headers=HEADERS, timeout=8, proxies=_PROXIES,
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
            headers=HEADERS, timeout=8, proxies=_PROXIES,
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
            headers=HEADERS, timeout=8, proxies=_PROXIES,
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
            timeout=10, allow_redirects=True, proxies=_PROXIES,
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
            timeout=8, allow_redirects=True, proxies=_PROXIES,
        )
        if r.status_code == 200:
            text = r.text.lower()
            if "business" in text or "catalog" in text:
                return True
    except Exception:
        pass
    return False


def get_social_presence(clean, e164):
    direct_tg = f"https://t.me/+{clean}"
    return {
        "telegram": {
            "phone_link": direct_tg,
            "note": (
                "Telegram puede abrir chat por número solo si la cuenta permite ser "
                "encontrada con su teléfono."
            ),
        }
    }


def _append_unique(items, value):
    value = (value or "").strip()
    if value and value not in items:
        items.append(value)


def _collect_truecaller_hints(data, clean):
    emails = []
    phones = []
    social_profiles = []
    photos = []
    seen_social = set()

    def walk(node, key_hint=""):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, str(key).lower())
            return
        if isinstance(node, list):
            for value in node:
                walk(value, key_hint)
            return
        if not isinstance(node, str):
            return

        text = node.strip()
        if not text:
            return

        for email in re.findall(
            r"\b[A-Za-z0-9._%+\-]{1,64}(?:\*+[A-Za-z0-9._%+\-]{0,32})?@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            text,
        ):
            _append_unique(emails, email)

        for phone in re.findall(
            r"(?:\+?\d[\d\-\s()]{0,6}\*{2,}[\d\-\s()*]{0,12}\d{1,4}|\b\d{2,4}\*{2,}\d{1,4}\b)",
            text,
        ):
            normalized = phone.strip()
            if normalized and normalized != clean:
                _append_unique(phones, normalized)

        for url in re.findall(r"https?://[^\s<>'\"]+", text):
            clean_url = url.rstrip(").,]}")
            low = clean_url.lower()
            matched = None
            for host, site in _SOCIAL_HOSTS.items():
                if host in low:
                    matched = site
                    break
            if matched:
                pair = (matched, clean_url)
                if pair not in seen_social:
                    seen_social.add(pair)
                    social_profiles.append({"site": matched, "url": clean_url})
            if any(k in key_hint for k in ("photo", "image", "avatar", "picture")):
                _append_unique(photos, clean_url)

        if any(k in key_hint for k in ("photo", "image", "avatar", "picture")) and text.startswith("http"):
            _append_unique(photos, text)

    walk(data)

    telegram = None
    for profile in social_profiles:
        if profile["site"] == "Telegram":
            username = profile["url"].rstrip("/").split("/")[-1].lstrip("@+")
            telegram = {
                "username": username if username and username != clean else None,
                "url": profile["url"],
                "deep_link": f"tg://resolve?domain={username}" if username and username != clean else None,
            }
            break

    return {
        "emails": emails[:5],
        "phones": phones[:5],
        "social_profiles": social_profiles[:8],
        "photo": photos[0] if photos else None,
        "telegram": telegram,
    }


def _rapidapi_truecaller_enrich(national_number, country_code_alpha, clean):
    if not RAPIDAPI_KEY:
        return {}
    try:
        r = requests.post(
            "https://truecaller-api3.p.rapidapi.com/v2.php",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "x-rapidapi-host": "truecaller-api3.p.rapidapi.com",
                "x-rapidapi-key": RAPIDAPI_KEY,
            },
            data={"phone": national_number, "countryCode": country_code_alpha},
            timeout=14,
        )
        if r.status_code != 200:
            return {"http_status": r.status_code}
        data = r.json()
        tc = data.get("truecaller_lookup") or data
        hints = _collect_truecaller_hints(tc, clean)
        return {
            "name": tc.get("name") or tc.get("caller_name") or tc.get("callerName"),
            "name_type": tc.get("name_type") or tc.get("nameType"),
            "carrier": tc.get("carrier") or tc.get("carrier_name"),
            "line_type": tc.get("line_type") or tc.get("lineType"),
            "spam_type": tc.get("spam_type") or tc.get("spamType"),
            "photo": hints.get("photo"),
            "emails": hints.get("emails", []),
            "phones": hints.get("phones", []),
            "social_profiles": hints.get("social_profiles", []),
            "telegram": hints.get("telegram"),
        }
    except Exception as e:
        logger.debug(f"RapidAPI WA enrich: {e}")
        return {}


def _get_caller_name(clean, country_code_alpha, national_number):
    name = None
    source = None

    try:
        r = requests.get(
            f"https://numbway.com/phone/{clean}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=10, proxies=_PROXIES,
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

    # Truecaller via RapidAPI — es API, NO necesita proxy
    if not name and RAPIDAPI_KEY:
        try:
            r = requests.post(
                "https://truecaller-api3.p.rapidapi.com/v2.php",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "x-rapidapi-host": "truecaller-api3.p.rapidapi.com",
                    "x-rapidapi-key": RAPIDAPI_KEY
                },
                data={"phone": national_number, "countryCode": country_code_alpha},
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
                headers=HEADERS, timeout=8, proxies=_PROXIES,
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

        phone_intel = {}
        search_bundle = {}
        try:
            from modules.phone_lookup import analyze_phone, build_phone_search_bundle
            phone_intel = analyze_phone(e164) or {}
            search_bundle = build_phone_search_bundle(e164, clean, national_digits)
        except Exception as e:
            logger.debug(f"WA fallback phone_intel: {e}")
            search_bundle = {}

        registered = (
            ((phone_intel.get("presence") or {}).get("whatsapp_registered"))
            if isinstance(phone_intel, dict) else None
        )
        if registered is None:
            registered = check_wa_registered(clean)

        spam = (
            (phone_intel.get("spam") if isinstance(phone_intel, dict) else None)
            or check_spam_reports(clean)
        )
        photo = get_wa_profile_photo(clean)
        is_business = check_wa_business(clean)
        social = get_social_presence(clean, e164)
        tc_enrich = _rapidapi_truecaller_enrich(national_digits, region_code or "", clean)

        caller_name = (
            tc_enrich.get("name")
            or (phone_intel.get("caller_name") if isinstance(phone_intel, dict) else None)
        )
        caller_source = (
            "Truecaller API"
            if tc_enrich.get("name")
            else (phone_intel.get("caller_source") if isinstance(phone_intel, dict) else None)
        )
        if not caller_name:
            caller_name, caller_source = _get_caller_name(clean, region_code or "", national_digits)

        if registered is None:
            if caller_name or spam.get("total_reports", 0) > 0:
                registered = True

        spam_sources = []
        if isinstance(spam, dict):
            existing_sources = spam.get("sources") or []
            if isinstance(existing_sources, list):
                spam_sources.extend(existing_sources)
            if spam.get("tellows_score"):
                _append_unique(spam_sources, f"Tellows ({spam['tellows_score']}/9)")
            if tc_enrich.get("spam_type"):
                _append_unique(spam_sources, f"Truecaller ({tc_enrich['spam_type']})")
            spam["sources"] = spam_sources[:5]

        telegram = (social.get("telegram") or {}).copy() if isinstance(social, dict) else {}
        if tc_enrich.get("telegram"):
            telegram.update({k: v for k, v in tc_enrich["telegram"].items() if v})
        telegram.setdefault("phone_link", f"https://t.me/+{clean}")
        telegram.setdefault(
            "search_link",
            f"https://www.google.com/search?q=site%3At.me+%22{urllib.parse.quote(clean)}%22+OR+%22{urllib.parse.quote(e164)}%22",
        )
        social["telegram"] = telegram

        social_profiles = tc_enrich.get("social_profiles", [])
        social_profiles = [p for p in social_profiles if p.get("site") != "Telegram"]
        if not search_bundle:
            try:
                from modules.phone_lookup import build_phone_search_bundle
                search_bundle = build_phone_search_bundle(e164, clean, national_digits)
            except Exception:
                search_bundle = {}
        social_links = search_bundle.get("social_search_links") or []
        direct_links = search_bundle.get("direct_platform_links") or []

        def _link_at(items, index):
            if 0 <= index < len(items):
                return (items[index] or {}).get("url")
            return None

        result = {
            "number":       e164,
            "national":     national,
            "international": intl,
            "clean":        clean,
            "country":      phone_intel.get("country") if isinstance(phone_intel, dict) and phone_intel.get("country") else country,
            "country_code": country_code,
            "region_code":  region_code,
            "carrier":      phone_intel.get("carrier") if isinstance(phone_intel, dict) and phone_intel.get("carrier") else operador,
            "registered":   registered,
            "is_business":  is_business,
            "photo":        photo or tc_enrich.get("photo"),
            "caller_name":  caller_name,
            "caller_source": caller_source,
            "about":        None,
            "spam":         spam,
            "social":       social,
            "risk_level":   phone_intel.get("risk_level") if isinstance(phone_intel, dict) else None,
            "risk_flags":   phone_intel.get("risk_flags") if isinstance(phone_intel, dict) else [],
            "type":         phone_intel.get("type") if isinstance(phone_intel, dict) else None,
            "timezone":     phone_intel.get("timezone") if isinstance(phone_intel, dict) else None,
            "region":       phone_intel.get("region") if isinstance(phone_intel, dict) else None,
            "country_data": phone_intel.get("country_data") if isinstance(phone_intel, dict) else None,
            "emails_hints": tc_enrich.get("emails", []),
            "phones_hints": tc_enrich.get("phones", []),
            "social_profiles": social_profiles,
            "platform_searches": search_bundle.get("platform_searches", []),
            "wa_link":      f"https://wa.me/{clean}",
            "wa_msg":       f"https://api.whatsapp.com/send?phone={clean}",
            "tg_search":    telegram.get("search_link"),
            "tg_direct":    telegram.get("phone_link"),
            "links": {
                "truecaller":  f"https://www.truecaller.com/search/{(region_code or 'global').lower()}/{national_digits}",
                "syncme":      f"https://www.sync.me/search/?number=%2B{clean}",
                "spamcalls":   f"https://spamcalls.net/en/number/{clean}",
                "whocalledme": f"https://whocalledme.com/Phone-Number.aspx/{clean}",
                "tellows":     f"https://www.tellows.com/num/{clean}",
                "google_dork": f"https://www.google.com/search?q=%22{e164}%22+OR+%22{clean}%22",
                "facebook_dork": _link_at(social_links, 1),
                "instagram_dork": _link_at(social_links, 2),
                "tiktok_dork": _link_at(social_links, 3),
                "x_dork": _link_at(social_links, 4),
                "facebook_search": _link_at(direct_links, 0),
                "instagram_search": _link_at(direct_links, 1),
                "tiktok_search": _link_at(direct_links, 2),
                "x_search": _link_at(direct_links, 3),
            }
        }
        result["business"] = is_business
        result["name"] = caller_name
        result["profile_picture"] = result["photo"]
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
