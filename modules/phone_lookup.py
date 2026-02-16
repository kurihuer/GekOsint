
import phonenumbers
from phonenumbers import geocoder, carrier, timezone, number_type
import requests
from config import logger

def analyze_phone(number):
    """Analiza número telefónico con soporte mejorado para LATAM"""
    try:
        parsed = phonenumbers.parse(number, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"error": "Número inválido"}

        # Datos básicos
        country_name = geocoder.description_for_number(parsed, "es")
        carrier_name = carrier.name_for_number(parsed, "es")
        time_zones = timezone.time_zones_for_number(parsed)
        
        # Tipo de número
        ntype = number_type(parsed)
        types = {
            1: "Móvil", 2: "Fijo", 3: "Número Gratuito", 
            4: "Tarifa Premium", 5: "VoIP", 6: "Pager", 27: "Móvil"
        }
        line_type = types.get(ntype, "Desconocido")

        # Formatos
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        
        # Datos enriquecidos
        result = {
            "number": e164,
            "national": national,
            "country": f"{country_name} (+{parsed.country_code})",
            "carrier": carrier_name or "Operador desconocido/portado",
            "type": line_type,
            "timezone": ", ".join(time_zones),
            "whatsapp": f"https://wa.me/{parsed.country_code}{parsed.national_number}",
            "telegram": f"https://t.me/+{parsed.country_code}{parsed.national_number}"
        }

        # Lógica específica LATAM y Áreas
        region_detail = get_specific_region(parsed.country_code, str(parsed.national_number))
        if region_detail:
            result["region_detail"] = region_detail

        return result

    except Exception as e:
        logger.error(f"Phone Error: {e}")
        return {"error": str(e)}

def get_specific_region(cc, national):
    """Detecta ciudades específicas por lada"""
    if cc == 52: # México
        prefixes = {
            "33": "Jalisco (Guadalajara)", "55": "CDMX (Ciudad de México)", 
            "81": "Nuevo León (Monterrey)", "222": "Puebla", "442": "Querétaro",
            "998": "Quintana Roo (Cancún)", "664": "Baja California (Tijuana)",
            "667": "Sinaloa (Culiacán)", "614": "Chihuahua"
        }
        for p, region in prefixes.items():
            if national.startswith(p): return region
            
    elif cc == 57: # Colombia
        prefixes = {
            "601": "Bogotá", "604": "Antioquia (Medellín)", "602": "Valle (Cali)",
            "605": "Costa Caribe", "3": "Móvil Nacional"
        }
        for p, region in prefixes.items():
            if national.startswith(p): return region

    return None
