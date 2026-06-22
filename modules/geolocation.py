# -*- coding: utf-8 -*-
"""
MODULO PARCIALMENTE DEPRECADO - GekOsint v6.1
get_ip_geolocation() se mantiene porque phone_lookup.py la necesita.
El resto (scan_wifi, menu_geoloc) fue eliminado.
"""
import time
import logging
import requests

logger = logging.getLogger("GekOsint.Geo")

CACHE     = {}
CACHE_TTL = 300  # 5 min


def get_ip_geolocation(ip_address: str) -> dict:
    """Geolocaliza una IP usando ip-api.com (sin API key)."""
    if not ip_address:
        return {"error": "IP vacia"}

    cache_key = ("geo", ip_address)
    now = int(time.time())
    if cache_key in CACHE and now - CACHE[cache_key][0] <= CACHE_TTL:
        return CACHE[cache_key][1]

    try:
        r = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=8)
        data = r.json()
        if data.get("status") == "success":
            result = {
                "ip":           ip_address,
                "country":      data.get("country"),
                "country_code": data.get("countryCode"),
                "region":       data.get("regionName"),
                "city":         data.get("city"),
                "zip":          data.get("zip"),
                "lat":          data.get("lat"),
                "lon":          data.get("lon"),
                "timezone":     data.get("timezone"),
                "isp":          data.get("isp"),
                "org":          data.get("org"),
                "as":           data.get("as"),
                "proxy":        data.get("proxy", False),
                "hosting":      data.get("hosting", False),
                "mobile":       data.get("mobile", False),
                "map_url": (
                    f"https://www.google.com/maps?q={data.get('lat')},{data.get('lon')}"
                )
            }
            CACHE[cache_key] = (now, result)
            return result
    except Exception as e:
        logger.error(f"get_ip_geolocation error: {e}")

    return {"error": "No se pudo geolocalizar la IP"}
