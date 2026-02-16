
import requests
import zipfile
import io
import logging
import urllib.parse

logger = logging.getLogger(__name__)

def deploy_html(html_content, filename="index.html"):
    """Sube HTML a servicios de hosting temporal y retorna la URL"""
    
    # 1. Netlify (Anónimo)
    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", html_content)
        zip_buffer.seek(0)

        r = requests.post(
            "https://api.netlify.com/api/v1/sites",
            headers={"Content-Type": "application/zip"},
            data=zip_buffer.read(),
            timeout=20
        )
        if r.status_code in [200, 201]:
            data = r.json()
            return data.get("ssl_url") or data.get("url")
    except Exception as e:
        logger.error(f"Netlify error: {e}")

    # 2. File.io
    try:
        r = requests.post(
            "https://file.io",
            files={"file": (filename, html_content.encode('utf-8'), "text/html")},
            data={"expires": "14d"},
            timeout=15
        )
        if r.status_code == 200 and r.json().get("success"):
            return r.json().get("link")
    except Exception as e:
        logger.error(f"File.io error: {e}")

    return None

def shorten_url(url):
    """Acorta URLs usando servicios sin API key"""
    if not url: return url
    
    services = [
        f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(url)}",
        f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url)}",
        f"https://v.gd/create.php?format=simple&url={urllib.parse.quote(url)}"
    ]

    for service in services:
        try:
            r = requests.get(service, timeout=8)
            if r.status_code == 200 and r.text.startswith("http"):
                return r.text.strip()
        except:
            continue
            
    return url
