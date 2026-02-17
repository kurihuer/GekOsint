
import logging
import zipfile
import io
import random
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

# Headers globales
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

async def deploy_html(html_content, filename="index.html"):
    """
    Sube HTML a servicios de hosting temporal de forma asíncrona.
    Retorna la URL del primer servicio exitoso.
    """
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        
        # 1. File.io (Rápido y efímero)
        try:
            files = {'file': (filename, html_content.encode('utf-8'), 'text/html')}
            data = {'expires': '14d'} # 2 semanas de validez
            
            r = await client.post("https://file.io", files=files, data=data, headers=HEADERS)
            
            if r.status_code == 200:
                resp = r.json()
                if resp.get("success"):
                    return resp.get("link")
        except Exception as e:
            logger.warning(f"File.io deploy failed: {e}")

        # 2. Netlify (Más robusto, fallback)
        try:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("index.html", html_content)
            zip_buffer.seek(0)
            
            headers = {"Content-Type": "application/zip", **HEADERS}
            
            r = await client.post(
                "https://api.netlify.com/api/v1/sites",
                headers=headers,
                content=zip_buffer.read()
            )
            
            if r.status_code in [200, 201]:
                data = r.json()
                url = data.get("ssl_url") or data.get("url")
                if url: return url
        except Exception as e:
            logger.warning(f"Netlify deploy failed: {e}")

    return None

async def shorten_url(url):
    """Acorta URLs de forma asíncrona usando múltiples servicios"""
    if not url: return url
    
    encoded_url = urllib.parse.quote(url)
    services = [
        f"https://is.gd/create.php?format=simple&url={encoded_url}",
        f"https://tinyurl.com/api-create.php?url={encoded_url}",
        f"https://v.gd/create.php?format=simple&url={encoded_url}",
        f"https://clck.ru/--?url={encoded_url}"
    ]
    
    random.shuffle(services)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for service in services:
            try:
                r = await client.get(service, headers=HEADERS)
                if r.status_code == 200:
                    text = r.text.strip()
                    if text.startswith("http"):
                        return text
            except Exception:
                continue
            
    return url
