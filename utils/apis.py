
import logging
import asyncio
import urllib.parse
import httpx
import os
from config import PAGES_DIR

import datetime

logger = logging.getLogger(__name__)

def generate_text_report(title, data_str):
    """Genera un reporte en texto plano formateado"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = (
        f"{'='*50}\n"
        f" GEKOSINT OSINT REPORT - {title}\n"
        f"{'='*50}\n"
        f"Fecha: {now}\n"
        f"{'='*50}\n\n"
        f"{data_str}\n\n"
        f"{'='*50}\n"
        f" Fin del reporte. Uso ético únicamente.\n"
        f"{'='*50}\n"
    )
    # Limpiar tags HTML para el reporte de texto
    import re
    report = re.sub(r'<[^>]+>', '', report)
    return report

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def _verify_url_serves_html(url: str, expect_html: bool = True) -> bool:
    """
    Verifica con HEAD (con fallback a GET) que la URL devuelva 200.
    También chequea Content-Type, pero de forma conservadora:
      - Rechaza tipos claramente NO-HTML (image/*, video/*, audio/*).
      - Acepta text/html, application/xhtml+xml, text/plain, octet-stream
        y respuestas SIN Content-Type (Catbox, 0x0.st a veces).
    Esto evita devolver URLs muertas (404) sin descartar deployers que
    sí sirven HTML aunque con un Content-Type imperfecto.
    """
    if not url:
        return False
    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, headers=HEADERS
        ) as client:
            r = await client.head(url)
            # Algunos hosts (Catbox, 0x0) no soportan HEAD bien → reintentar con GET
            if r.status_code in (405, 501) or r.status_code >= 400:
                r = await client.get(url)
            if r.status_code != 200:
                logger.warning(f"verify_url: {url} → HTTP {r.status_code}")
                return False
            if expect_html:
                ctype = (r.headers.get("content-type") or "").lower().strip()
                bad_prefixes = ("image/", "video/", "audio/", "application/pdf",
                                "application/zip", "application/json")
                if any(ctype.startswith(p) for p in bad_prefixes):
                    logger.warning(f"verify_url: {url} → content-type rechazado {ctype!r}")
                    return False
            return True
    except Exception as e:
        logger.warning(f"verify_url: {url} → {e}")
        return False


async def deploy_html(html_content, filename="index.html"):
    """
    Sube HTML usando múltiples servicios con fallback automático.
    Orden: Servidor Local -> GitHub Gist -> Vercel -> Catbox -> 0x0.st

    Cada deployer es validado con HEAD/GET antes de devolverse al usuario,
    así nunca se envía un enlace que dé 404.
    """
    # Guardar localmente siempre
    filepath = os.path.join(PAGES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"📁 Archivo guardado: {filepath}")

    # Intentar cada servicio en orden
    deployers = [
        ("Servidor Local", _deploy_local),
        ("GitHub Gist",    _deploy_gist),
        ("Vercel",         _deploy_vercel),
        ("Catbox",         _deploy_catbox),
        ("0x0.st",         _deploy_0x0),
    ]

    last_unverified = None  # último candidato que devolvió URL pero no verificó

    for name, deployer in deployers:
        try:
            url = await deployer(html_content, filename)
            if not url:
                continue

            if await _verify_url_serves_html(url):
                logger.info(f"✅ Deploy verificado via {name}: {url}")
                return url

            logger.warning(f"⚠️ {name} devolvió {url} pero no sirve HTML — probando siguiente")
            last_unverified = (name, url)
        except Exception as e:
            logger.warning(f"⚠️ {name} falló: {e}")
            continue

    if last_unverified:
        logger.error(
            f"❌ Ningún deploy verificó. Último intento sin validar: "
            f"{last_unverified[0]} → {last_unverified[1]}"
        )
    else:
        logger.error("❌ Todos los servicios de deploy fallaron")
    return None


async def _deploy_local(html_content, filename):
    """
    Sirve el archivo desde el propio servidor del bot.
    Requisitos:
      - PUBLIC_URL configurado.
      - File server local activo (utils/server.is_file_server_running()).
        Esto evita devolver URLs muertas cuando el bot está en modo webhook
        sin un file server detrás.
    """
    try:
        from config import PUBLIC_URL
        if not PUBLIC_URL:
            return None
        # Importación tardía para evitar ciclos al importar utils/apis.py
        try:
            from utils.server import is_file_server_running
            if not is_file_server_running():
                logger.debug("_deploy_local: file server no activo → skip")
                return None
        except Exception:
            # Si no podemos consultar el estado, mejor no arriesgar
            return None
        return f"{PUBLIC_URL.rstrip('/')}/{filename}"
    except Exception:
        return None

async def _deploy_gist(html_content, filename):
    """Deploy via GitHub Gist + GitHack CDN (sirve HTML con Content-Type correcto)"""
    try:
        from config import GITHUB_TOKEN
        if not GITHUB_TOKEN:
            return None
    except (ImportError, AttributeError):
        return None

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GekOsint-Bot"
            },
            json={
                "description": "GekOsint tracking page",
                "public": True,
                "files": {filename: {"content": html_content}}
            }
        )
        if r.status_code == 201:
            gist = r.json()
            gist_id = gist.get("id", "")
            owner = gist.get("owner", {}).get("login", "")
            if owner and gist_id:
                # GitHack sirve el Gist con text/html correcto
                return f"https://gist.githack.com/{owner}/{gist_id}/raw/{filename}"
    return None

async def _deploy_vercel(html_content, filename):
    """Deploy a Vercel (requiere VERCEL_TOKEN)"""
    try:
        from config import VERCEL_TOKEN
        if not VERCEL_TOKEN:
            return None
    except (ImportError, AttributeError):
        return None
    
    project_prefix = filename.split('_')[0] if '_' in filename else "gekosint"
    project_name = f"gekosint-{project_prefix}"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {VERCEL_TOKEN}",
            "Content-Type": "application/json"
        }
        
        deployment_data = {
            "name": project_name,
            "files": [{"file": "index.html", "data": html_content}],
            "projectSettings": {"framework": None},
            "target": "production"
        }
        
        r = await client.post(
            "https://api.vercel.com/v13/deployments",
            json=deployment_data, headers=headers
        )
        
        if r.status_code in [200, 201]:
            resp = r.json()
            deploy_id = resp.get("id")
            project_id = resp.get("projectId")
            
            aliases = resp.get("alias", [])
            stable_alias = None
            for a in aliases:
                if a and a.count('-') <= 4:
                    stable_alias = a
                    break
            
            raw_url = stable_alias or resp.get("url", "")
            if not raw_url:
                return None
            
            if not raw_url.startswith("http"):
                raw_url = f"https://{raw_url}"
            
            # Deshabilitar SSO
            if project_id:
                try:
                    await client.patch(
                        f"https://api.vercel.com/v9/projects/{project_id}",
                        json={"ssoProtection": None}, headers=headers
                    )
                except Exception:
                    pass
            
            # Esperar READY
            if deploy_id:
                for _ in range(9):
                    await asyncio.sleep(5)
                    try:
                        sr = await client.get(
                            f"https://api.vercel.com/v13/deployments/{deploy_id}",
                            headers=headers
                        )
                        if sr.status_code == 200:
                            state = sr.json().get("readyState", "")
                            if state == "READY":
                                break
                            elif state in ["ERROR", "CANCELED"]:
                                return None
                    except Exception:
                        pass
            
            return raw_url
    return None

async def _deploy_catbox(html_content, filename):
    """Deploy a Catbox.moe (sin cuenta, archivos temporales)"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {"fileToUpload": (filename, html_content.encode(), "text/html")}
        data = {"reqtype": "fileupload"}
        
        r = await client.post(
            "https://catbox.moe/user/api.php",
            data=data, files=files
        )
        
        if r.status_code == 200 and r.text.strip().startswith("http"):
            return r.text.strip()
    return None

async def _deploy_0x0(html_content, filename):
    """Deploy a 0x0.st (archivos temporales)"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {"file": (filename, html_content.encode(), "text/html")}
        
        r = await client.post("https://0x0.st", files=files)
        
        if r.status_code == 200 and r.text.strip().startswith("http"):
            return r.text.strip()
    return None

async def shorten_url(url):
    """Acorta URLs usando servicios gratuitos sin advertencias"""
    if not url:
        return url

    encoded_url = urllib.parse.quote(url, safe='')

    shorteners = [
        ("tinyurl", f"https://tinyurl.com/api-create.php?url={encoded_url}"),
        ("is.gd", f"https://is.gd/create.php?format=simple&url={encoded_url}"),
        ("v.gd", f"https://v.gd/create.php?format=simple&url={encoded_url}"),
        ("clck.ru", f"https://clck.ru/--?url={encoded_url}"),
    ]

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for name, api_url in shorteners:
            try:
                r = await client.get(api_url)
                if r.status_code == 200 and r.text.strip().startswith("http"):
                    short = r.text.strip()
                    logger.info(f"URL acortada con {name}: {short}")
                    return short
            except Exception as e:
                logger.debug(f"{name} fallo: {e}")
                continue

    logger.info("No se pudo acortar, usando URL original")
    return url


async def upload_bytes(file_bytes: bytes, filename: str, content_type: str = "application/octet-stream") -> str | None:
    if not file_bytes:
        return None
    if not filename:
        filename = "file.bin"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            files = {"fileToUpload": (filename, file_bytes, content_type)}
            data = {"reqtype": "fileupload"}
            r = await client.post("https://catbox.moe/user/api.php", data=data, files=files)
            if r.status_code == 200 and r.text.strip().startswith("http"):
                return r.text.strip()
        except Exception as e:
            logger.debug(f"upload catbox fallo: {e}")

        try:
            files = {"file": (filename, file_bytes, content_type)}
            r = await client.post("https://0x0.st", files=files)
            if r.status_code == 200 and r.text.strip().startswith("http"):
                return r.text.strip()
        except Exception as e:
            logger.debug(f"upload 0x0 fallo: {e}")

    return None
