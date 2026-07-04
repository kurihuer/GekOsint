# -*- coding: utf-8 -*-
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io
import hashlib
import urllib.parse
from config import logger


# -- Deteccion de rostro (heuristica de tono de piel) -------------------------

def detect_face_heuristic(image_bytes: bytes) -> bool:
    """
    Deteccion basica de presencia de piel humana/rostro usando la
    regla de Kovac simplificada sobre el espacio RGB.
    No requiere OpenCV ni dlib. Falsos positivos posibles, pero suficiente
    para trigger de busqueda inversa.
    Retorna True si >10% de los pixeles muestreados caen en rango de piel.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize((150, 150), Image.LANCZOS)
        pixels = list(img.getdata())
        skin = 0
        for r, g, b in pixels:
            if (r > 95 and g > 40 and b > 20 and
                    (max(r, g, b) - min(r, g, b)) > 15 and
                    abs(int(r) - int(g)) > 15 and
                    r > g and r > b):
                skin += 1
        return (skin / len(pixels)) > 0.10
    except Exception:
        return False


def generate_reverse_search_links(image_url: str, has_face: bool = False) -> dict:
    """Genera URLs listas para busqueda inversa en los principales motores."""
    enc = urllib.parse.quote(image_url, safe="")
    links = {
        "Google Lens":   f"https://lens.google.com/uploadbyurl?url={enc}",
        "Yandex Images": f"https://yandex.com/images/search?url={enc}&rpt=imageview",
        "TinEye":        f"https://tineye.com/search?url={enc}",
        "Bing Visual":   f"https://www.bing.com/images/search?q=imgurl:{enc}&view=detailv2&iss=sbi",
    }
    if has_face:
        links["FaceCheck.ID"] = "https://facecheck.id"
        links["PimEyes"]      = "https://pimeyes.com"
        links["Search4Faces"] = "https://search4faces.com"
    return links


# -- EXIF extraction ----------------------------------------------------------

def get_exif(image_bytes):
    """Extrae metadatos EXIF completos, GPS, y hash de la imagen."""
    try:
        img = Image.open(io.BytesIO(image_bytes))

        data = {
            "basic": {},
            "gps": {},
            "device": {},
            "all_tags": {},
            "hash": {},
        }

        data["basic"] = {
            "Format":     img.format or "Desconocido",
            "Mode":       img.mode,
            "Size":       f"{img.size[0]}x{img.size[1]}",
            "Width":      img.size[0],
            "Height":     img.size[1],
            "Megapixels": round((img.size[0] * img.size[1]) / 1_000_000, 2),
            "FileSize":   f"{len(image_bytes) / 1024:.1f} KB",
        }

        data["hash"] = {
            "MD5":    hashlib.md5(image_bytes).hexdigest(),
            "SHA256": hashlib.sha256(image_bytes).hexdigest()[:32] + "...",
        }

        exif = img._getexif()
        if not exif:
            return data

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

            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8", errors="ignore")
                except (UnicodeDecodeError, AttributeError):
                    continue

            if tag == "GPSInfo":
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    data["gps"][sub_tag] = value[t]

            if tag in device_tags:
                if tag == "FocalLength" and hasattr(value, "numerator"):
                    data["device"][tag] = f"{float(value):.1f}"
                elif tag == "FNumber" and hasattr(value, "numerator"):
                    data["device"][tag] = f"{float(value):.1f}"
                elif tag == "ExposureTime" and hasattr(value, "numerator"):
                    if value.numerator and value.denominator:
                        data["device"][tag] = (
                            f"1/{int(value.denominator/value.numerator)}"
                            if value.numerator < value.denominator
                            else str(float(value))
                        )
                    else:
                        data["device"][tag] = str(value)
                elif tag == "Flash":
                    flash_modes = {
                        0: "No disparo", 1: "Disparo", 5: "Disparo (sin retorno)",
                        7: "Disparo (con retorno)", 8: "No disparo (auto)",
                        9: "Disparo (auto)", 16: "No disparo (forzado off)",
                        24: "No disparo (auto)", 25: "Disparo (auto)",
                    }
                    data["device"][tag] = flash_modes.get(value, f"Modo {value}")
                elif tag == "Orientation":
                    orientations = {
                        1: "Normal", 2: "Espejo horizontal", 3: "Rotado 180",
                        4: "Espejo vertical", 5: "Espejo + Rotado 270",
                        6: "Rotado 90", 7: "Espejo + Rotado 90", 8: "Rotado 270"
                    }
                    data["device"][tag] = orientations.get(value, f"Valor {value}")
                elif tag == "MeteringMode":
                    modes = {
                        0: "Desconocido", 1: "Promedio", 2: "Ponderado central",
                        3: "Puntual", 4: "Multi-punto", 5: "Patron", 6: "Parcial"
                    }
                    data["device"][tag] = modes.get(value, f"Modo {value}")
                elif tag == "ExposureProgram":
                    programs = {
                        0: "No definido", 1: "Manual", 2: "Programa normal",
                        3: "Prioridad apertura", 4: "Prioridad velocidad",
                        5: "Creativo", 6: "Accion", 7: "Retrato", 8: "Paisaje"
                    }
                    data["device"][tag] = programs.get(value, f"Programa {value}")
                else:
                    data["device"][tag] = str(value)

            try:
                str_val = str(value)
                if len(str_val) < 200:
                    data["all_tags"][tag] = str_val
            except Exception:
                pass

        if data["gps"]:
            lat = convert_to_degrees(data["gps"].get("GPSLatitude"),  data["gps"].get("GPSLatitudeRef"))
            lon = convert_to_degrees(data["gps"].get("GPSLongitude"), data["gps"].get("GPSLongitudeRef"))
            if lat and lon:
                data["coords"] = f"{lat:.6f}, {lon:.6f}"
                data["map"]    = f"https://www.google.com/maps?q={lat},{lon}"

                alt = data["gps"].get("GPSAltitude")
                if alt:
                    try:
                        data["altitude"] = f"{float(alt):.1f}m"
                    except Exception:
                        pass

                speed = data["gps"].get("GPSSpeed")
                if speed:
                    try:
                        data["gps_speed"] = f"{float(speed):.1f} km/h"
                    except Exception:
                        pass

                direction = data["gps"].get("GPSImgDirection")
                if direction:
                    try:
                        data["gps_direction"] = f"{float(direction):.1f} deg"
                    except Exception:
                        pass

        return data

    except Exception as e:
        logger.error(f"Error EXIF: {e}")
        return {"error": str(e)}


def convert_to_degrees(value, ref):
    """Convierte coordenadas GPS EXIF a grados decimales."""
    if not value or not ref:
        return None
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        res = d + (m / 60.0) + (s / 3600.0)
        if ref in ["S", "W"]:
            res = -res
        return res
    except Exception:
        return None
