
import phonenumbers
from phonenumbers import geocoder, carrier, timezone, number_type
import requests
import re
from config import logger, RAPIDAPI_KEY

def get_location_from_country(country_code):
    try:
        r = requests.get(f"https://restcountries.com/v3.1/alpha/{country_code}", timeout=10)
        if r.status_code == 200:
            data = r.json()[0]
            coords = data.get("latlng", [])
            capital = data.get("capital", [""])[0] if data.get("capital") else ""
            flag = data.get("flag", "")
            if len(coords) == 2:
                return {
                    "lat": coords[0], "lon": coords[1],
                    "capital": capital, "flag": flag,
                    "map_url": f"https://www.google.com/maps?q={coords[0]},{coords[1]}"
                }
    except Exception as e:
        logger.warning(f"Error ubicación país: {e}")
    return None

def get_phone_validation_details(number, country_code, carrier_name=""):
    details = {"possible_fraud": False, "is_ported": False, "line_status": "Activa (Estimado)"}
    try:
        if not carrier_name or carrier_name.strip() == "":
            details["is_ported"] = True
        first_digit = str(number).replace("+", "").replace(" ", "")[2:3] if len(str(number)) > 3 else ""
        if first_digit in ["0", "1"]:
            details["possible_fraud"] = True
            details["line_status"] = "Posible Fraude"
    except Exception as e:
        logger.warning(f"Error validación: {e}")
    return details

def _scrape_numbway(clean_number):
    """Scrape Numbway para obtener info del numero"""
    result = {"name": None, "type": None}
    try:
        r = requests.get(
            f"https://numbway.com/phone/{clean_number}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=10
        )
        if r.status_code == 200:
            name_match = re.search(r'<h2[^>]*>([^<]{2,60})</h2>', r.text)
            type_match = re.search(r'(?:type|tipo)[^:]*:\s*([^<]{2,40})', r.text, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                if name and not any(w in name.lower() for w in ["unknown", "numbway", "phone", "number"]):
                    result["name"] = name
            if type_match:
                result["type"] = type_match.group(1).strip()
    except Exception as e:
        logger.debug(f"Numbway scrape error: {e}")
    return result

def _scrape_spamcalls_name(clean_number):
    """Scrape SpamCalls para nombre y reportes"""
    result = {"name": None, "reports": 0}
    try:
        r = requests.get(
            f"https://spamcalls.net/en/number/{clean_number}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=8
        )
        if r.status_code == 200:
            name_match = re.search(r'caller["\s]*(?:name|id)[^:]*:\s*"?([^"<]{2,50})"?', r.text, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                if name and not any(w in name.lower() for w in ["unknown", "spam"]):
                    result["name"] = name
            count_match = re.search(r'(\d+)\s*(?:report|reporte)', r.text, re.IGNORECASE)
            if count_match:
                result["reports"] = int(count_match.group(1))
    except Exception as e:
        logger.debug(f"SpamCalls scrape error: {e}")
    return result

def get_truecaller_data(national_number, country_code_alpha, clean_number=""):
    """
    Lookup via Truecaller API (RapidAPI) + scraping gratuito de multiples fuentes.
    """
    result = {
        "name":       None,
        "name_type":  None,
        "spam_score": 0,
        "spam_type":  None,
        "reported":   False,
        "carrier_tc": None,
        "line_type":  None,
        "sources":    [],
        "quota_exceeded": False,
        "scraped_data": {},
        "social_links": [
            {"name": "Truecaller",  "url": f"https://www.truecaller.com/search/{country_code_alpha.lower()}/{national_number}"},
            {"name": "GetContact",  "url": f"https://getcontact.com/en/number/{clean_number or national_number}"},
            {"name": "SpamCalls",   "url": f"https://spamcalls.net/en/number/{clean_number or national_number}"},
            {"name": "Sync.me",    "url": f"https://www.sync.me/search/?number=%2B{clean_number or national_number}"},
        ]
    }

    # 1. Scraping gratuito de fuentes publicas (siempre)
    if clean_number:
        numbway = _scrape_numbway(clean_number)
        if numbway.get("name"):
            result["scraped_data"]["numbway_name"] = numbway["name"]
            if not result["name"]:
                result["name"] = numbway["name"]
                result["sources"].append("Numbway")
        if numbway.get("type"):
            result["scraped_data"]["numbway_type"] = numbway["type"]

        spamcalls = _scrape_spamcalls_name(clean_number)
        if spamcalls.get("name") and not result["name"]:
            result["name"] = spamcalls["name"]
            result["sources"].append("SpamCalls")
        if spamcalls.get("reports", 0) > 0:
            result["spam_score"] = max(result["spam_score"], spamcalls["reports"])
            result["reported"] = True
            result["spam_type"] = result.get("spam_type") or "Spam"
            if "SpamDB" not in result["sources"]:
                result["sources"].append("SpamDB")

    # 2. Truecaller API (si hay key)
    if RAPIDAPI_KEY:
        try:
            r = requests.post(
                "https://truecaller-api3.p.rapidapi.com/v2.php",
                headers={
                    "Content-Type":    "application/x-www-form-urlencoded",
                    "x-rapidapi-host": "truecaller-api3.p.rapidapi.com",
                    "x-rapidapi-key":  RAPIDAPI_KEY
                },
                data={
                    "phone":       national_number,
                    "countryCode": country_code_alpha
                },
                timeout=12
            )

            if r.status_code == 429:
                result["quota_exceeded"] = True
                logger.warning("Truecaller API: cuota agotada")
                return result

            if r.status_code == 200:
                data = r.json()
                tc = data.get("truecaller_lookup") or data

                name = tc.get("name") or tc.get("caller_name") or tc.get("callerName")
                if name and name.lower() not in ["unknown", "desconocido", ""]:
                    result["name"] = name
                    if "Truecaller" not in result["sources"]:
                        result["sources"].insert(0, "Truecaller")

                result["name_type"] = tc.get("name_type") or tc.get("nameType")
                result["carrier_tc"] = tc.get("carrier") or tc.get("carrier_name")
                result["line_type"] = tc.get("line_type") or tc.get("lineType")

                spam_score = tc.get("spam_score") or tc.get("spamScore") or 0
                try:
                    spam_score = int(float(str(spam_score)))
                except Exception:
                    spam_score = 0

                if spam_score > 0:
                    result["spam_score"] = max(result["spam_score"], spam_score)
                    result["reported"] = True
                    result["spam_type"] = tc.get("spam_type") or tc.get("spamType") or "Spam"

                logger.info(f"Truecaller OK: name={result['name']}, spam={spam_score}")
        except Exception as e:
            logger.error(f"Truecaller API error: {e}")

    return result


def analyze_phone(number):
    """Analiza número telefónico con información extensa y lookup Truecaller real"""
    try:
        parsed = phonenumbers.parse(number, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"error": "Número inválido"}

        country_name = geocoder.description_for_number(parsed, "es")
        carrier_name = carrier.name_for_number(parsed, "es")
        time_zones   = timezone.time_zones_for_number(parsed)

        ntype = number_type(parsed)
        types = {1: "Móvil", 2: "Fijo", 3: "Número Gratuito", 4: "Tarifa Premium", 5: "VoIP", 6: "Pager", 27: "Móvil"}
        line_type = types.get(ntype, "Desconocido")

        e164               = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        national           = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        intl               = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        country_code_alpha = phonenumbers.region_code_for_number(parsed)

        # Número local sin código de país (formato que necesita la API)
        national_digits = re.sub(r'\D', '', national)

        location_data = get_location_from_country(country_code_alpha)
        validation    = get_phone_validation_details(e164, country_code_alpha, carrier_name or "")
        clean_number  = e164.replace("+", "")
        truecaller    = get_truecaller_data(national_digits, country_code_alpha, clean_number)

        result = {
            "number": e164,
            "national": national,
            "international": intl,
            "country": f"{country_name} (+{parsed.country_code})",
            "country_code": country_code_alpha,
            "carrier": carrier_name or "Operador desconocido/portado",
            "type": line_type,
            "timezone": ", ".join(time_zones) if time_zones else "No disponible",
            "is_valid": phonenumbers.is_valid_number(parsed),
            "is_possible": phonenumbers.is_possible_number(parsed),
            "whatsapp": f"https://wa.me/{parsed.country_code}{parsed.national_number}",
            "telegram": f"https://t.me/+{parsed.country_code}{parsed.national_number}",
            "validation": validation,
            "truecaller": truecaller
        }

        if location_data:
            result["location"] = location_data
        
        region_detail = get_specific_region(parsed.country_code, str(parsed.national_number))
        if region_detail:
            result["region_detail"] = region_detail
            result["region_coords"] = get_region_coordinates(parsed.country_code, region_detail)

        return result

    except Exception as e:
        logger.error(f"Phone Error: {e}")
        return {"error": str(e)}

def get_specific_region(cc, national):
    """Detecta ciudades específicas por lada"""
    if cc == 52:
        prefixes = {
            "33": "Jalisco (Guadalajara)", "55": "CDMX (Ciudad de México)", 
            "81": "Nuevo León (Monterrey)", "222": "Puebla", "442": "Querétaro",
            "998": "Quintana Roo (Cancún)", "664": "Baja California (Tijuana)",
            "667": "Sinaloa (Culiacán)", "614": "Chihuahua", "618": "Durango",
            "662": "Sonora (Hermosillo)", "656": "Juárez", "229": "Veracruz",
            "844": "Coahuila (Saltillo)", "477": "Guanajuato (León)"
        }
        for p, region in prefixes.items():
            if national.startswith(p): return region
            
    elif cc == 57:
        prefixes = {
            "601": "Bogotá", "604": "Antioquia (Medellín)", "602": "Valle (Cali)",
            "605": "Costa Caribe", "607": "Santander", "3": "Móvil Nacional"
        }
        for p, region in prefixes.items():
            if national.startswith(p): return region
    
    elif cc == 54:
        prefixes = {
            "11": "Buenos Aires", "351": "Córdoba", "341": "Rosario", "261": "Mendoza"
        }
        for p, region in prefixes.items():
            if national.startswith(p): return region
    
    elif cc == 51:
        prefixes = {
            "1": "Lima", "44": "Arequipa", "54": "Cusco", "74": "Piura"
        }
        for p, region in prefixes.items():
            if national.startswith(p): return region

    return None

def get_region_coordinates(cc, region_name):
    """Retorna coordenadas aproximadas de regiones conocidas"""
    coords_map = {
        "52": {
            "Jalisco (Guadalajara)": {"lat": 20.6597, "lon": -103.3496},
            "CDMX (Ciudad de México)": {"lat": 19.4326, "lon": -99.1332},
            "Nuevo León (Monterrey)": {"lat": 25.6866, "lon": -100.3161},
            "Puebla": {"lat": 19.0414, "lon": -98.2063},
            "Querétaro": {"lat": 20.5888, "lon": -100.3899},
            "Quintana Roo (Cancún)": {"lat": 21.1619, "lon": -86.8515},
            "Baja California (Tijuana)": {"lat": 32.5149, "lon": -117.0382},
            "Sinaloa (Culiacán)": {"lat": 24.8091, "lon": -107.3940},
            "Chihuahua": {"lat": 28.6353, "lon": -106.0889}
        },
        "57": {
            "Bogotá": {"lat": 4.7110, "lon": -74.0721},
            "Antioquia (Medellín)": {"lat": 6.2442, "lon": -75.5812},
            "Valle (Cali)": {"lat": 3.4516, "lon": -76.5320}
        }
    }
    
    country_map = coords_map.get(str(cc), {})
    coords = country_map.get(region_name)
    
    if coords:
        coords["map_url"] = f"https://www.google.com/maps?q={coords['lat']},{coords['lon']}"
        return coords
    
    return None
