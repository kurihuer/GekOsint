"""
Phone Intelligence — módulo mejorado.
Añade: riesgo HLR estimado, análisis de portabilidad, enriquecimiento
de datos de carrier, detección VOIP/virtual, y más fuentes de lookup.
"""

import phonenumbers
from phonenumbers import geocoder, carrier, timezone, number_type, NumberParseException
import requests
import re
from config import logger, RAPIDAPI_KEY, NUMVERIFY_KEY
from modules.geolocation import get_ip_geolocation

# ── Constantes ────────────────────────────────────────────────────────────────
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_HEADERS = {"User-Agent": _UA}

# IPs representativas por carrier (para geo aproximada del operador)
_CARRIER_IPS = {
    "telcel": "148.244.0.0",      "movistar": "177.228.0.0",
    "at&t":   "107.223.0.0",      "claro":    "189.216.0.0",
    "tigo":   "181.62.0.0",       "entel":    "186.10.0.0",
    "orange": "212.194.0.0",      "vodafone": "85.56.0.0",
    "wom":    "186.8.0.0",        "bitel":    "191.102.0.0",
    "megacable": "189.254.0.0",   "izzi":     "189.248.0.0",
    "totalplay": "187.254.0.0",   "virgin":   "66.54.0.0",
}

# Carriers conocidos por VOIP / números virtuales
_VOIP_KEYWORDS = {"twilio", "voip", "google voice", "skype", "magicjack",
                  "bandwidth", "vonage", "textplus", "grasshopper", "ringcentral",
                  "virtual", "openphone", "talkatone", "textfree", "textnow"}

# ── Helpers internos ──────────────────────────────────────────────────────────

def _carrier_ip(carrier_name: str) -> str | None:
    if not carrier_name:
        return None
    low = carrier_name.lower()
    for key, ip in _CARRIER_IPS.items():
        if key in low:
            return ip
    return None


def _is_voip_carrier(carrier_name: str) -> bool:
    if not carrier_name:
        return False
    low = carrier_name.lower()
    return any(k in low for k in _VOIP_KEYWORDS)


def _country_info(country_code: str) -> dict:
    """Datos básicos del país vía restcountries."""
    try:
        r = requests.get(
            f"https://restcountries.com/v3.1/alpha/{country_code}",
            timeout=8
        )
        if r.status_code == 200:
            d = r.json()[0]
            coords = d.get("latlng", [])
            capital = (d.get("capital") or [""])[0]
            flag = d.get("flag", "")
            currencies = list((d.get("currencies") or {}).keys())
            languages = list((d.get("languages") or {}).values())
            region = d.get("subregion", d.get("region", ""))
            pop = d.get("population", 0)
            if len(coords) == 2:
                return {
                    "lat": coords[0], "lon": coords[1],
                    "capital": capital, "flag": flag,
                    "region": region, "population": pop,
                    "currencies": currencies[:2],
                    "languages": languages[:3],
                    "map_url": f"https://www.google.com/maps?q={coords[0]},{coords[1]}",
                }
    except Exception as e:
        logger.debug(f"[phone] country info error: {e}")
    return {}


def _numverify(e164: str) -> dict:
    if not NUMVERIFY_KEY:
        return {}
    try:
        r = requests.get(
            "http://apilayer.net/api/validate",
            params={"access_key": NUMVERIFY_KEY, "number": e164, "format": 1},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"[phone] numverify error: {e}")
    return {}


def _scrape_truecaller_web(clean_number: str, country_alpha: str) -> dict:
    """
    Intenta obtener el nombre de caller desde Truecaller web scraping.
    Fallback cuando no hay API key de RapidAPI.
    """
    result = {"name": None, "spam_score": 0, "reported": False}
    try:
        r = requests.get(
            f"https://www.truecaller.com/search/{country_alpha.lower()}/{clean_number}",
            headers={**_HEADERS, "Accept-Language": "es-MX,es;q=0.9"},
            timeout=10,
            allow_redirects=True,
        )
        if r.status_code == 200:
            # Buscar name en JSON-LD o meta
            m = re.search(r'"name"\s*:\s*"([^"]{2,80})"', r.text)
            if m:
                name = m.group(1).strip()
                if name and not any(w in name.lower() for w in ["truecaller", "unknown", "caller"]):
                    result["name"] = name
            low = (r.text or "").lower()
            m_score = re.search(r'(?:spam\s*score|spamScore)[^0-9]{0,20}(\d{1,3})', low)
            if m_score:
                try:
                    result["spam_score"] = max(0, min(100, int(m_score.group(1))))
                except Exception:
                    pass
            if re.search(r'reported\s+as\s+spam|marked\s+as\s+spam|es\s+spam', low):
                result["reported"] = True
                if result["spam_score"] <= 0:
                    result["spam_score"] = 30
    except Exception as e:
        logger.debug(f"[phone] truecaller web scrape error: {e}")
    return result


def _check_whatsapp_registered(clean_number: str) -> bool | None:
    try:
        r = requests.get(
            f"https://wa.me/{clean_number}",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"},
            timeout=8,
            allow_redirects=True,
        )
        if r.status_code == 200:
            if "api.whatsapp.com/send" in (r.url or "") or "api.whatsapp.com/send" in (r.text or ""):
                return True
            if "phone_number_invalid" in (r.text or ""):
                return False
    except Exception:
        pass
    return None


def _scrape_spamcalls(clean_number: str) -> dict:
    result = {"name": None, "reports": 0, "labels": []}
    try:
        r = requests.get(
            f"https://spamcalls.net/en/number/{clean_number}",
            headers=_HEADERS, timeout=8,
        )
        if r.status_code == 200:
            m_name = re.search(r'caller["\s]*(?:name|id)[^:]*:\s*"?([^"<]{2,50})"?', r.text, re.IGNORECASE)
            if m_name:
                n = m_name.group(1).strip()
                if n and "unknown" not in n.lower():
                    result["name"] = n
            m_count = re.search(r'(\d+)\s*(?:report|reporte)', r.text, re.IGNORECASE)
            if m_count:
                result["reports"] = int(m_count.group(1))
            # Etiquetas
            labels = re.findall(r'(?:label|type|tag)["\s]*:\s*"([^"]{2,40})"', r.text, re.IGNORECASE)
            result["labels"] = list({l.strip() for l in labels if l.strip()})[:5]
    except Exception as e:
        logger.debug(f"[phone] spamcalls error: {e}")
    return result


def _scrape_tellows(clean_number: str) -> dict:
    result = {"score": None, "reports": 0, "caller_type": None}
    try:
        r = requests.get(
            f"https://www.tellows.com/num/{clean_number}",
            headers=_HEADERS, timeout=8,
        )
        if r.status_code == 200:
            m_score = re.search(r'"tellowsScore"\s*:\s*(\d+)', r.text)
            if m_score:
                result["score"] = int(m_score.group(1))
            m_reports = re.search(r'(\d+)\s*(?:calls|anrufe|llamadas)', r.text, re.IGNORECASE)
            if m_reports:
                result["reports"] = int(m_reports.group(1))
            m_type = re.search(r'"callerType"\s*:\s*"([^"]{2,50})"', r.text)
            if m_type:
                result["caller_type"] = m_type.group(1)
    except Exception as e:
        logger.debug(f"[phone] tellows error: {e}")
    return result


def _rapidapi_truecaller(national: str, country_alpha: str) -> dict:
    if not RAPIDAPI_KEY:
        return {}
    try:
        r = requests.post(
            "https://truecaller-api3.p.rapidapi.com/v2.php",
            headers={
                "Content-Type":    "application/x-www-form-urlencoded",
                "x-rapidapi-host": "truecaller-api3.p.rapidapi.com",
                "x-rapidapi-key":  RAPIDAPI_KEY,
            },
            data={"phone": national, "countryCode": country_alpha},
            timeout=12,
        )
        if r.status_code == 429:
            return {"quota_exceeded": True}
        if r.status_code == 200:
            data = r.json()
            tc = data.get("truecaller_lookup") or data
            name = tc.get("name") or tc.get("caller_name") or tc.get("callerName")
            spam_score = 0
            try:
                spam_score = int(float(str(tc.get("spam_score") or tc.get("spamScore") or 0)))
            except Exception:
                pass
            return {
                "name":       name if name and name.lower() not in ["unknown", "desconocido"] else None,
                "name_type":  tc.get("name_type") or tc.get("nameType"),
                "carrier_tc": tc.get("carrier") or tc.get("carrier_name"),
                "line_type":  tc.get("line_type") or tc.get("lineType"),
                "spam_score": spam_score,
                "spam_type":  tc.get("spam_type") or tc.get("spamType"),
                "reported":   spam_score > 0,
            }
    except Exception as e:
        logger.error(f"[phone] RapidAPI Truecaller error: {e}")
    return {}


# ── Detección regional por lada ───────────────────────────────────────────────

_REGIONS: dict[int, dict[str, str]] = {
    52: {   # México
        "55": "Ciudad de México", "33": "Guadalajara, Jalisco",
        "81": "Monterrey, Nuevo León", "222": "Puebla",
        "442": "Querétaro", "998": "Cancún, Quintana Roo",
        "664": "Tijuana, Baja California", "667": "Culiacán, Sinaloa",
        "614": "Chihuahua", "656": "Ciudad Juárez",
        "662": "Hermosillo, Sonora", "229": "Veracruz",
        "844": "Saltillo, Coahuila", "477": "León, Guanajuato",
        "618": "Durango", "871": "Torreón, Coahuila",
        "999": "Mérida, Yucatán", "312": "Colima",
        "722": "Toluca, Estado de México", "735": "Cuautla, Morelos",
    },
    57: {   # Colombia
        "601": "Bogotá", "604": "Medellín, Antioquia",
        "602": "Cali, Valle", "605": "Costa Caribe",
        "607": "Bucaramanga, Santander",
    },
    54: {   # Argentina
        "11": "Buenos Aires", "351": "Córdoba",
        "341": "Rosario", "261": "Mendoza",
    },
    51: {   # Perú
        "1": "Lima", "44": "Arequipa", "54": "Cusco", "74": "Piura",
    },
    56: {   # Chile
        "2": "Santiago", "32": "Valparaíso", "41": "Concepción",
    },
    58: {   # Venezuela
        "212": "Caracas", "261": "Maracaibo", "241": "Valencia",
    },
    34: {   # España
        "91": "Madrid", "93": "Barcelona", "96": "Valencia",
        "95": "Sevilla", "94": "Bilbao",
    },
}

_REGION_COORDS: dict[str, dict] = {
    # México
    "Ciudad de México":           {"lat": 19.4326,  "lon": -99.1332},
    "Guadalajara, Jalisco":       {"lat": 20.6597,  "lon": -103.3496},
    "Monterrey, Nuevo León":      {"lat": 25.6866,  "lon": -100.3161},
    "Puebla":                     {"lat": 19.0414,  "lon": -98.2063},
    "Querétaro":                  {"lat": 20.5888,  "lon": -100.3899},
    "Cancún, Quintana Roo":       {"lat": 21.1619,  "lon": -86.8515},
    "Tijuana, Baja California":   {"lat": 32.5149,  "lon": -117.0382},
    "Culiacán, Sinaloa":          {"lat": 24.8091,  "lon": -107.394},
    "Chihuahua":                  {"lat": 28.6353,  "lon": -106.0889},
    "Ciudad Juárez":              {"lat": 31.7385,  "lon": -106.4870},
    "Hermosillo, Sonora":         {"lat": 29.0729,  "lon": -110.9559},
    "Veracruz":                   {"lat": 19.1738,  "lon": -96.1342},
    "Saltillo, Coahuila":         {"lat": 25.4232,  "lon": -100.9737},
    "León, Guanajuato":           {"lat": 21.1221,  "lon": -101.6824},
    "Mérida, Yucatán":            {"lat": 20.9674,  "lon": -89.5926},
    "Torreón, Coahuila":          {"lat": 25.5428,  "lon": -103.4068},
    # Colombia
    "Bogotá":                     {"lat": 4.7110,   "lon": -74.0721},
    "Medellín, Antioquia":        {"lat": 6.2442,   "lon": -75.5812},
    "Cali, Valle":                {"lat": 3.4516,   "lon": -76.532},
    # Argentina
    "Buenos Aires":               {"lat": -34.6037, "lon": -58.3816},
    "Córdoba":                    {"lat": -31.4201, "lon": -64.1888},
    "Rosario":                    {"lat": -32.9468, "lon": -60.6393},
    # Perú
    "Lima":                       {"lat": -12.0464, "lon": -77.0428},
    "Arequipa":                   {"lat": -16.4090, "lon": -71.5375},
    # Chile
    "Santiago":                   {"lat": -33.4489, "lon": -70.6693},
    "Valparaíso":                 {"lat": -33.0472, "lon": -71.6127},
    # España
    "Madrid":                     {"lat": 40.4168,  "lon": -3.7038},
    "Barcelona":                  {"lat": 41.3851,  "lon": 2.1734},
    "Valencia":                   {"lat": 39.4699,  "lon": -0.3763},
}


def _detect_region(country_code: int, national_number: str) -> str | None:
    prefixes = _REGIONS.get(country_code, {})
    # Probar de más largo a más corto
    for length in (5, 4, 3, 2, 1):
        prefix = national_number[:length]
        if prefix in prefixes:
            return prefixes[prefix]
    return None


def _region_coords(region: str) -> dict | None:
    c = _REGION_COORDS.get(region)
    if c:
        return {**c, "map_url": f"https://www.google.com/maps?q={c['lat']},{c['lon']}"}
    return None


# ── Función principal ─────────────────────────────────────────────────────────

def analyze_phone(number: str) -> dict:
    """
    Análisis completo de un número telefónico.
    Retorna un dict rico en datos para ser formateado por ui/templates.py.
    """
    missing_keys = []
    if not RAPIDAPI_KEY:  missing_keys.append("RAPIDAPI_KEY")
    if not NUMVERIFY_KEY: missing_keys.append("NUMVERIFY_KEY")

    try:
        parsed = phonenumbers.parse(number, None)
    except NumberParseException as e:
        return {"error": f"No se pudo parsear el número: {e}", "missing_keys": missing_keys}

    if not phonenumbers.is_valid_number(parsed):
        return {"error": "Número inválido o no asignable", "missing_keys": missing_keys}

    cc          = parsed.country_code
    nat_num_str = str(parsed.national_number)
    e164        = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    national    = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    intl        = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    alpha       = phonenumbers.region_code_for_number(parsed)
    clean       = e164.replace("+", "")

    # Metadatos básicos (librería phonenumbers — offline, muy fiable)
    country_name  = geocoder.description_for_number(parsed, "es") or "Desconocido"
    carrier_name  = carrier.name_for_number(parsed, "es") or ""
    time_zones    = timezone.time_zones_for_number(parsed)
    ntype         = number_type(parsed)

    _LINE_TYPES = {
        0: "Fijo", 1: "Móvil", 2: "Fijo",
        3: "Número Gratuito", 4: "Tarifa Premium",
        5: "VoIP / Virtual", 6: "Pager", 27: "Móvil",
    }
    line_type_str = _LINE_TYPES.get(ntype, "Desconocido")

    # Enriquecimiento
    nv_data      = _numverify(e164)
    national_digits = re.sub(r'\D', '', national)
    tc_api       = _rapidapi_truecaller(re.sub(r'\D', '', national), alpha)
    tc_web       = _scrape_truecaller_web(clean, alpha) if not tc_api.get("name") else {}
    spam_data    = _scrape_spamcalls(clean)
    tellows_data = _scrape_tellows(clean)
    country_data = _country_info(alpha)
    region       = _detect_region(cc, nat_num_str)
    region_c     = _region_coords(region) if region else None
    carrier_ip   = _carrier_ip(carrier_name)
    carrier_geo  = get_ip_geolocation(carrier_ip) if carrier_ip else None

    # Consolidar nombre de caller
    caller_name   = tc_api.get("name") or tc_web.get("name") or spam_data.get("name")
    caller_source = "Truecaller API" if tc_api.get("name") else \
                    "Truecaller Web"  if tc_web.get("name") else \
                    "SpamCalls DB"    if spam_data.get("name") else None

    # Spam score consolidado
    spam_score_final = max(
        tc_api.get("spam_score", 0),
        spam_data.get("reports", 0),
        (tellows_data.get("score") or 0) * 3,   # tellows 1-9 → escalar a ~30 max
    )
    is_reported = (
        tc_api.get("reported", False) or
        tc_web.get("reported", False) or
        spam_data.get("reports", 0) > 0 or
        (tellows_data.get("score") or 0) >= 5
    )

    # Análisis de riesgo local
    risk_flags = []
    if _is_voip_carrier(carrier_name):
        risk_flags.append("VOIP / Número Virtual")
    if not carrier_name:
        risk_flags.append("Operador desconocido (posible portación)")
    if is_reported:
        risk_flags.append(f"Reportado como spam ({spam_score_final} reportes)")
    if line_type_str in ("Número Gratuito", "Tarifa Premium"):
        risk_flags.append(f"Tipo de línea inusual: {line_type_str}")

    spam_type = None
    if is_reported:
        spam_type = tc_api.get("spam_type")
        if not spam_type:
            labels = spam_data.get("labels") or []
            spam_type = labels[0] if labels else "Spam"

    whatsapp_registered = _check_whatsapp_registered(clean)
    e164_q = requests.utils.quote(e164)
    clean_q = requests.utils.quote(clean)

    return {
        # Identificación
        "number":        e164,
        "national":      national,
        "international": intl,
        "country":       f"{country_name} (+{cc})",
        "country_code":  alpha,
        "missing_keys":  missing_keys,

        # Operadora y tipo
        "carrier":       carrier_name or nv_data.get("carrier") or "Desconocido / Portado",
        "carrier_type":  "VOIP" if _is_voip_carrier(carrier_name) else "Convencional",
        "type":          nv_data.get("line_type") or line_type_str,
        "timezone":      ", ".join(time_zones) if time_zones else "No disponible",

        # Validación
        "is_valid":    bool(nv_data.get("valid")) if nv_data else phonenumbers.is_valid_number(parsed),
        "is_possible": phonenumbers.is_possible_number(parsed),

        # CallerID
        "caller_name":   caller_name,
        "caller_source": caller_source,
        "caller_type":   tc_api.get("name_type") or tc_api.get("line_type"),

        # Spam / Reputación
        "spam": {
            "reported":     is_reported,
            "score":        spam_score_final,
            "type":         spam_type,
            "labels":       spam_data.get("labels") or [],
            "tellows_score": tellows_data.get("score"),
            "caller_type_tellows": tellows_data.get("caller_type"),
            "total_reports": max(spam_data.get("reports", 0), tellows_data.get("reports", 0)),
        },

        # Riesgo
        "risk_flags": risk_flags,
        "risk_level": "ALTO" if len(risk_flags) >= 2 else "MEDIO" if risk_flags else "BAJO",

        # Geografía
        "country_data": country_data,
        "region":       region,
        "region_coords": region_c,

        # Carrier geo (aproximada)
        "carrier_ip":  carrier_ip,
        "carrier_geo": carrier_geo if carrier_geo and "error" not in (carrier_geo or {}) else None,

        # Links directos
        "whatsapp": f"https://wa.me/{cc}{parsed.national_number}",
        "telegram_search": f"https://www.google.com/search?q=site%3At.me+%22{clean_q}%22+OR+%22{e164_q}%22",
        "presence": {
            "whatsapp_registered": whatsapp_registered,
        },
        "social_search_links": [
            {"name": "Google", "url": f"https://www.google.com/search?q=%22{clean_q}%22+OR+%22{e164_q}%22"},
            {"name": "Facebook", "url": f"https://www.google.com/search?q=site%3Afacebook.com+%22{clean_q}%22+OR+%22{e164_q}%22"},
            {"name": "Instagram", "url": f"https://www.google.com/search?q=site%3Ainstagram.com+%22{clean_q}%22+OR+%22{e164_q}%22"},
            {"name": "TikTok", "url": f"https://www.google.com/search?q=site%3Atiktok.com+%22{clean_q}%22+OR+%22{e164_q}%22"},
            {"name": "X", "url": f"https://www.google.com/search?q=site%3Ax.com+%22{clean_q}%22+OR+%22{e164_q}%22"},
        ],

        # Links OSINT externos
        "osint_links": [
            {"name": "Truecaller",  "url": f"https://www.truecaller.com/search/{alpha.lower()}/{national_digits}"},
            {"name": "GetContact",  "url": f"https://getcontact.com/en/number/{clean}"},
            {"name": "SpamCalls",   "url": f"https://spamcalls.net/en/number/{clean}"},
            {"name": "Tellows",     "url": f"https://www.tellows.com/num/{clean}"},
            {"name": "Sync.me",     "url": f"https://www.sync.me/search/?number=%2B{clean}"},
            {"name": "Whocallsme",  "url": f"https://whocallsme.com/Phone-Number.aspx/{clean}"},
            {"name": "Google",      "url": f"https://www.google.com/search?q=%22{clean}%22"},
        ],
    }
