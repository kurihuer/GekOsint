
import requests
import zipfile
import io
import logging
import urllib.parse
import random

logger = logging.getLogger(__name__)

# Headers globales para evitar bloqueos por UA por defecto
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def deploy_html(html_content, filename="index.html"):
    """Sube HTML a servicios de hosting temporal y retorna la URL"""
    
    # 1. Netlify (Anónimo via API de sitios)
    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", html_content)
        zip_buffer.seek(0)

        r = requests.post(
            "https://api.netlify.com/api/v1/sites",
            headers={"Content-Type": "application/zip", **HEADERS},
            data=zip_buffer.read(),
            timeout=25
        )
        if r.status_code in [200, 201]:
            data = r.json()
            url = data.get("ssl_url") or data.get("url")
            if url: return url
    except Exception as e:
        logger.warning(f"Netlify deploy failed: {e}")

    # 2. File.io (Válido para un solo uso/descarga)
    try:
        r = requests.post(
            "https://file.io",
            files={"file": (filename, html_content.encode('utf-8'), "text/html")},
            data={"expires": "14d"},
            headers=HEADERS,
            timeout=15
        )
        if r.status_code == 200 and r.json().get("success"):
            return r.json().get("link")
    except Exception as e:
        logger.warning(f"File.io deploy failed: {e}")

    # 3. Uguu.se (Temporal, 24h)
    try:
        r = requests.post(
            "https://uguu.se/upload.php",
            files={"files[]": (filename, html_content.encode('utf-8'), "text/html")},
            headers=HEADERS,
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                return data["files"][0]["url"]
    except Exception as e:
        logger.error(f"Uguu.se deploy failed: {e}")

    return None

def shorten_url(url):
    """Acorta URLs usando múltiples servicios con reintentos"""
    if not url: return url
    
    encoded_url = urllib.parse.quote(url)
    services = [
        f"https://is.gd/create.php?format=simple&url={encoded_url}",
        f"https://tinyurl.com/api-create.php?url={encoded_url}",
        f"https://v.gd/create.php?format=simple&url={encoded_url}",
        f"https://clck.ru/--?url={encoded_url}"
    ]

    # Mezclar para no saturar siempre el mismo
    random.shuffle(services)

    for service in services:
        try:
            r = requests.get(service, headers=HEADERS, timeout=10)
            if r.status_code == 200 and r.text.strip().startswith("http"):
                return r.text.strip()
        except Exception:
            continue
            
    return url
