
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import io

def get_exif(image_bytes):
    """Extrae metadatos y coordenadas GPS"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img._getexif()
        
        if not exif:
            return None

        data = {"basic": {}, "gps": {}, "device": {}}
        
        data["basic"] = {
            "Format": img.format,
            "Mode": img.mode,
            "Size": f"{img.size[0]}x{img.size[1]}"
        }

        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            
            # Decodificar bytes
            if isinstance(value, bytes):
                try: value = value.decode()
                except: continue

            if tag == "GPSInfo":
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    data["gps"][sub_tag] = value[t]
            
            if tag in ["Make", "Model", "Software", "DateTimeOriginal", "LensModel"]:
                data["device"][tag] = str(value)

        # Procesar coordenadas
        if data["gps"]:
            lat = convert_to_degrees(data["gps"].get("GPSLatitude"), data["gps"].get("GPSLatitudeRef"))
            lon = convert_to_degrees(data["gps"].get("GPSLongitude"), data["gps"].get("GPSLongitudeRef"))
            if lat and lon:
                data["coords"] = (lat, lon)
                data["map"] = f"https://www.google.com/maps?q={lat},{lon}"

        return data
    except Exception as e:
        return {"error": str(e)}

def convert_to_degrees(value, ref):
    if not value or not ref: return None
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    res = d + (m / 60.0) + (s / 3600.0)
    if ref in ['S', 'W']: res = -res
    return res
