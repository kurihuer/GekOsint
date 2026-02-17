
import logging
import random
import urllib.parse
import httpx
import io

logger = logging.getLogger(__name__)

# Headers globales para evitar bloqueos
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def deploy_html(html_content, filename="index.html"):
    """
    Sube HTML a múltiples servicios de hosting temporal de forma asíncrona.
    Retorna la URL del primer servicio exitoso con múltiples fallbacks.
    """
    html_bytes = html_content.encode('utf-8')
    
    # Intentamos con múltiples clientes y configuraciones para maximizar éxito
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        
        # 1. File.io (Primario - Muy rápido si se usa correctamente)
        try:
            # File.io a veces prefiere multipart sin headers explícitos por campo
            files = {'file': (filename, html_bytes)}
            r = await client.post("https://file.io", files=files, data={"expires": "1d"})
            if r.status_code == 200:
                resp = r.json()
                if resp.get("success"):
                    url = resp.get("link")
                    logger.info(f"File.io success: {url}")
                    return url
        except Exception as e:
            logger.warning(f"File.io failed: {e}")

        # 2. Catbox.moe (Excelente estabilidad)
        try:
            # Catbox requiere campos específicos
            data = {"reqtype": "fileupload"}
            files = {"fileToUpload": (filename, html_bytes)}
            r = await client.post("https://catbox.moe/user/api.php", data=data, files=files)
            if r.status_code == 200 and r.text.strip().startswith("http"):
                url = r.text.strip()
                logger.info(f"Catbox success: {url}")
                return url
        except Exception as e:
            logger.warning(f"Catbox failed: {e}")

        # 3. 0x0.st (Sencillo y robusto)
        try:
            files = {"file": (filename, html_bytes)}
            # 0x0.st es estricto con el User-Agent a veces
            r = await client.post("https://0x0.st", files=files, headers=HEADERS)
            if r.status_code == 200 and r.text.strip().startswith("http"):
                url = r.text.strip()
                logger.info(f"0x0.st success: {url}")
                return url
        except Exception as e:
            logger.warning(f"0x0.st failed: {e}")

        # 4. Bashupload.com (Fallback de último recurso)
        try:
            # Bashupload permite subir vía POST simple a una URL con el nombre
            r = await client.post(f"https://bashupload.com/{filename}", content=html_bytes)
            if r.status_code in [200, 201]:
                # Retorna un texto que contiene el enlace
                for line in r.text.splitlines():
                    if "https://bashupload.com/" in line:
                        url = line.strip().split()[-1]
                        logger.info(f"Bashupload success: {url}")
                        return url
        except Exception as e:
            logger.warning(f"Bashupload failed: {e}")

    logger.error("All deployment services failed.")
    return None

async def shorten_url(url):
    """Acorta URLs de forma asíncrona usando múltiples servicios"""
    if not url: return url
    
    encoded_url = urllib.parse.quote(url)
    services = [
        f"https://is.gd/create.php?format=simple&url={encoded_url}",
        f"https://tinyurl.com/api-create.php?url={encoded_url}",
        f"https://v.gd/create.php?format=simple&url={encoded_url}"
    ]
    
    random.shuffle(services)
    
    async with httpx.AsyncClient(timeout=8.0) as client:
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
