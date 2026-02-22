
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io
import hashlib
from config import logger

def get_exif(image_bytes):
    """Extrae metadatos EXIF completos, GPS, y hash de la imagen"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        data = {
            "basic": {},
            "gps": {},
            "device": {},
            "all_tags": {},
            "hash": {},
        }
        
        # Información básica (siempre disponible)
        data["basic"] = {
            "Format": img.format or "Desconocido",
            "Mode": img.mode,
            "Size": f"{img.size[0]}x{img.size[1]}",
            "Width": img.size[0],
            "Height": img.size[1],
            "Megapixels": round((img.size[0] * img.size[1]) / 1_000_000, 2),
            "FileSize": f"{len(image_bytes) / 1024:.1f} KB",
        }
        
        # Hash de la imagen (para búsqueda inversa)
        data["hash"] = {
            "MD5": hashlib.md5(image_bytes).hexdigest(),
            "SHA256": hashlib.sha256(image_bytes).hexdigest()[:32] + "...",
        }
        
        # Intentar obtener EXIF
        exif = img._getexif()
        
        if not exif:
            # Sin EXIF pero con datos básicos
            return data

        # Tags de dispositivo expandidos
        device_tags = [
            "Make", "Model", "Software", "DateTimeOriginal", "DateTime",
            "DateTimeDigitized", "LensModel", "LensMake", "FocalLength",
            "FocalLengthIn35mmFilm", "FNumber", "ExposureTime", "ISOSpeedRatings",
            "ExposureBiasValue", "MeteringMode", "Flash", "WhiteBalance",
            "ExposureProgram", "SceneCaptureType", "Orientation",
            "ImageDescription", "Artist", "Copyright", "BodySerialNumber",
            "LensSerialNumber", "CameraOwnerName"
        ]

        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, str(tag_id))
            
            # Decodificar bytes
            if isinstance(value, bytes):
                try:
                    value = value.decode('utf-8', errors='ignore')
                except (UnicodeDecodeError, AttributeError):
                    continue

            # GPS Info
            if tag == "GPSInfo":
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    data["gps"][sub_tag] = value[t]
            
            # Tags de dispositivo
            if tag in device_tags:
                # Formatear valores especiales
                if tag == "FocalLength" and hasattr(value, 'numerator'):
                    data["device"][tag] = f"{float(value):.1f}"
                elif tag == "FNumber" and hasattr(value, 'numerator'):
                    data["device"][tag] = f"{float(value):.1f}"
                elif tag == "ExposureTime" and hasattr(value, 'numerator'):
                    if value.numerator and value.denominator:
                        data["device"][tag] = f"1/{int(value.denominator/value.numerator)}" if value.numerator < value.denominator else str(float(value))
                    else:
                        data["device"][tag] = str(value)
                elif tag == "Flash":
                    flash_modes = {
                        0: "No disparó", 1: "Disparó", 5: "Disparó (sin retorno)",
                        7: "Disparó (con retorno)", 8: "No disparó (modo auto)",
                        9: "Disparó (modo auto)", 16: "No disparó (forzado off)",
                        24: "No disparó (auto)", 25: "Disparó (auto)",
                    }
                    data["device"][tag] = flash_modes.get(value, f"Modo {value}")
                elif tag == "Orientation":
                    orientations = {
                        1: "Normal", 2: "Espejo horizontal", 3: "Rotado 180°",
                        4: "Espejo vertical", 5: "Espejo + Rotado 270°",
                        6: "Rotado 90°", 7: "Espejo + Rotado 90°", 8: "Rotado 270°"
                    }
                    data["device"][tag] = orientations.get(value, f"Valor {value}")
                elif tag == "MeteringMode":
                    modes = {
                        0: "Desconocido", 1: "Promedio", 2: "Ponderado central",
                        3: "Puntual", 4: "Multi-punto", 5: "Patrón", 6: "Parcial"
                    }
                    data["device"][tag] = modes.get(value, f"Modo {value}")
                elif tag == "ExposureProgram":
                    programs = {
                        0: "No definido", 1: "Manual", 2: "Programa normal",
                        3: "Prioridad apertura", 4: "Prioridad velocidad",
                        5: "Creativo", 6: "Acción", 7: "Retrato", 8: "Paisaje"
                    }
                    data["device"][tag] = programs.get(value, f"Programa {value}")
                else:
                    data["device"][tag] = str(value)
            
            # Guardar todos los tags (para raw dump)
            try:
                str_val = str(value)
                if len(str_val) < 200:
                    data["all_tags"][tag] = str_val
            except Exception:
                pass

        # Procesar coordenadas GPS
        if data["gps"]:
            lat = convert_to_degrees(data["gps"].get("GPSLatitude"), data["gps"].get("GPSLatitudeRef"))
            lon = convert_to_degrees(data["gps"].get("GPSLongitude"), data["gps"].get("GPSLongitudeRef"))
            if lat and lon:
                data["coords"] = f"{lat:.6f}, {lon:.6f}"
                data["map"] = f"https://www.google.com/maps?q={lat},{lon}"
                
                # Altitud
                alt = data["gps"].get("GPSAltitude")
                if alt:
                    try:
                        data["altitude"] = f"{float(alt):.1f}m"
                    except Exception:
                        pass
                
                # Velocidad GPS
                speed = data["gps"].get("GPSSpeed")
                if speed:
                    try:
                        data["gps_speed"] = f"{float(speed):.1f} km/h"
                    except Exception:
                        pass
                
                # Dirección GPS
                direction = data["gps"].get("GPSImgDirection")
                if direction:
                    try:
                        data["gps_direction"] = f"{float(direction):.1f}°"
                    except Exception:
                        pass

        return data
    except Exception as e:
        logger.error(f"Error EXIF: {e}")
        return {"error": str(e)}

def convert_to_degrees(value, ref):
    """Convierte coordenadas GPS EXIF a grados decimales"""
    if not value or not ref:
        return None
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        res = d + (m / 60.0) + (s / 3600.0)
        if ref in ['S', 'W']:
            res = -res
        return res
    except Exception:
        return None
