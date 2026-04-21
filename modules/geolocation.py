import os
import re
import json
import time
import io
import sqlite3
import logging
import subprocess
import requests
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

logger = logging.getLogger(__name__)

CACHE = {}
CACHE_TTL = 600

def _convert_gps_to_decimal(value):
    """Convertir coordenadas GPS a formato decimal"""
    if not value or len(value) != 3:
        return None
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except:
        return None

def get_exif_data(image_bytes):
    """Extraer datos EXIF completos de una imagen"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img._getexif()
        
        if not exif:
            return {"error": "Sin metadatos EXIF"}
        
        result = {"raw": {}, "gps": None, "camera": {}, "software": None, "datetime": None}
        
        for tag_id, value in exif.items():
            tag_name = TAGS.get(tag_id, tag_id)
            
            if tag_name == "GPSInfo":
                gps_data = {}
                for gps_tag in value:
                    gps_tag_name = GPSTAGS.get(gps_tag, gps_tag)
                    gps_data[gps_tag_name] = value[gps_tag]
                
                lat = _convert_gps_to_decimal(gps_data.get("GPSLatitude"))
                lon = _convert_gps_to_decimal(gps_data.get("GPSLongitude"))
                
                if lat and lon:
                    if gps_data.get("GPSLatitudeRef") == "S":
                        lat = -lat
                    if gps_data.get("GPSLongitudeRef") == "W":
                        lon = -lon
                    
                    result["gps"] = {
                        "lat": lat,
                        "lon": lon,
                        "alt": gps_data.get("GPSAltitude"),
                        "map_url": f"https://www.google.com/maps?q={lat},{lon}"
                    }
                
                result["raw"]["GPSInfo"] = gps_data
            elif tag_name in ["Make", "Model", "Software", "DateTime", "Orientation"]:
                result["raw"][tag_name] = str(value)
                if tag_name == "Make":
                    result["camera"]["make"] = str(value)
                elif tag_name == "Model":
                    result["camera"]["model"] = str(value)
                elif tag_name == "Software":
                    result["software"] = str(value)
                elif tag_name == "DateTime":
                    result["datetime"] = str(value)
        
        return result
    except Exception as e:
        logger.error(f"Error extrayendo EXIF: {e}")
        return {"error": str(e)}

def get_ip_geolocation(ip_address):
    """Geolocalizar IP sin API key (gratis)"""
    cache_key = ("geo", ip_address)
    now = int(time.time())
    
    if cache_key in CACHE and now - CACHE[cache_key][0] <= CACHE_TTL:
        return CACHE[cache_key][1]
    
    try:
        r = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=8)
        data = r.json()
        
        if data.get("status") == "success":
            result = {
                "ip": ip_address,
                "country": data.get("country"),
                "country_code": data.get("countryCode"),
                "region": data.get("regionName"),
                "city": data.get("city"),
                "zip": data.get("zip"),
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "timezone": data.get("timezone"),
                "isp": data.get("isp"),
                "org": data.get("org"),
                "as": data.get("as"),
                "proxy": data.get("proxy", False),
                "hosting": data.get("hosting", False),
                "mobile": data.get("mobile", False),
                "map_url": f"https://www.google.com/maps?q={data.get('lat')},{data.get('lon')}"
            }
            CACHE[cache_key] = (now, result)
            return result
    except Exception as e:
        logger.error(f"Error geo IP: {e}")
    
    return {"error": "No se pudo geolocalizar la IP"}

def get_cell_location(mcc, mnc, lac, cid, api_key=None):
    """Obtener ubicación de torre celular usando OpenCellID"""
    if not api_key:
        return {"error": "Se requiere API key de OpenCellID"}
    
    try:
        url = f"https://opencellid.org/cell/get?key={api_key}&mcc={mcc}&mnc={mnc}&lac={lac}&cellid={cid}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        if "lat" in data and "lon" in data:
            return {
                "mcc": mcc,
                "mnc": mnc,
                "lac": lac,
                "cell_id": cid,
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "range": data.get("range", 0),
                "map_url": f"https://www.google.com/maps?q={data.get('lat')},{data.get('lon')}"
            }
    except Exception as e:
        logger.error(f"Error celda: {e}")
    
    return {"error": "No se pudo obtener ubicación de celda"}

def scan_wifi_networks():
    """Escanear redes Wi-Fi disponibles (requiere permisos root en Linux)"""
    try:
        if os.name == "nt":
            return {"error": "Windows no soporta escaneo WiFi nativo. Usa herramientas como aircrack-ng."}

        if os.getenv("KOYEB_PUBLIC_DOMAIN") or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or os.getenv("FLY_APP_NAME") or os.getenv("HEROKU_APP_NAME"):
            return {"error": "WiFi Scanner no está disponible en servidores cloud (sin interfaz Wi‑Fi).", "source": "cloud"}

        nmcli = subprocess.run(["sh", "-lc", "command -v nmcli >/dev/null 2>&1"], capture_output=True, text=True)
        if nmcli.returncode == 0:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,BSSID", "device", "wifi", "list"],
                capture_output=True, text=True, timeout=10
            )
            networks = []
            for line in (result.stdout or "").strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                if len(parts) >= 3:
                    networks.append({
                        "ssid": parts[0] or "Oculta",
                        "signal": parts[1],
                        "bssid": parts[2]
                    })
            if networks:
                return {"networks": networks, "source": "nmcli"}
            if result.stderr:
                return {"error": result.stderr.strip()[:200], "source": "nmcli"}
            return {"error": "No se detectaron redes Wi-Fi (sin adaptador o sin permisos).", "source": "nmcli"}

        iwlist = subprocess.run(["sh", "-lc", "command -v iwlist >/dev/null 2>&1"], capture_output=True, text=True)
        if iwlist.returncode == 0:
            result = subprocess.run(
                ["iwlist", "scan"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return {"error": (result.stderr or "iwlist falló").strip()[:200], "source": "iwlist"}

            output = result.stdout
            networks = []
            cells = re.split(r"Cell [0-9A-Fa-f]+ - ", output)

            for cell in cells[1:]:
                ssid_match = re.search(r'ESSID:"([^"]*)"', cell)
                bssid_match = re.search(r'Address: ([0-9A-F:]+)', cell)
                signal_match = re.search(r'Signal level[=:](-?\d+)', cell)

                if ssid_match:
                    networks.append({
                        "ssid": ssid_match.group(1) or "Oculta",
                        "bssid": bssid_match.group(1) if bssid_match else "N/A",
                        "signal_dbm": int(signal_match.group(1)) if signal_match else None
                    })

            return {"networks": networks, "source": "iwlist"}

        return {"error": "No hay herramientas WiFi disponibles (nmcli/iwlist).", "source": "system"}
    except Exception as e:
        logger.error(f"Error escaneo WiFi: {e}")
        return {"error": str(e)}

def check_webrtc_leak(url):
    """Verificar posible fuga de WebRTC en un sitio"""
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        html = r.text
        
        patterns = [
            r'RTCPeerConnection',
            r'createOffer',
            r'setLocalDescription',
            r'webkitRTCPeerConnection',
            r'mozRTCPeerConnection'
        ]
        
        leaks = []
        for pattern in patterns:
            if re.search(pattern, html):
                leaks.append(pattern)
        
        if leaks:
            return {
                "leak_detected": True,
                "patterns": leaks,
                "risk": "Medio - Posible filtración de IP real"
            }
        
        return {"leak_detected": False}
    except Exception as e:
        logger.error(f"Error WebRTC: {e}")
        return {"error": str(e)}

def extract_google_maps_location(text):
    """Extraer coordenadas de texto de Google Maps"""
    patterns = [
        r'@(-?\d+\.\d+),(-?\d+\.\d+)',
        r'q=(-?\d+\.\d+)%2C(-?\d+\.\d+)',
        r'(-?\d+\.\d+),(-?\d+\.\d+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return {
                "lat": float(match.group(1)),
                "lon": float(match.group(2)),
                "map_url": f"https://www.google.com/maps?q={match.group(1)},{match.group(2)}"
            }
    
    return None

def analyze_screenshot_ocr(image_bytes):
    """Analizar captura de pantalla para detectar información de ubicación (simulado)"""
    return {
        "note": "OCR no disponible - Instala pytesseract para análisis de texto en imágenes",
        "suggestion": "Revisa manualmente la imagen buscando coordenadas, direcciones, o logos de apps de mapas"
    }

def comprehensive_geo_analysis(ip_address=None, image_bytes=None, mcc=None, mnc=None, lac=None, cid=None, cell_api_key=None):
    """Análisis completo de geolocalización"""
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "methods": []
    }
    
    if ip_address:
        geo = get_ip_geolocation(ip_address)
        if "error" not in geo:
            results["ip_location"] = geo
            results["methods"].append("IP Geolocation")
    
    if image_bytes:
        exif = get_exif_data(image_bytes)
        if exif.get("gps"):
            results["image_gps"] = exif["gps"]
            results["methods"].append("EXIF GPS")
        if exif.get("camera"):
            results["image_camera"] = exif["camera"]
            results["methods"].append("EXIF Camera")
    
    if mcc and mnc and lac and cid:
        cell = get_cell_location(mcc, mnc, lac, cid, cell_api_key)
        if "error" not in cell:
            results["cell_location"] = cell
            results["methods"].append("Cell Tower")
    
    return results
