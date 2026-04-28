
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

    El "Servidor Local" tiene verificación ESTRICTA: si la URL no responde 200
    con HTML, se descarta (era la causa del 404 del v6.0). Para los servicios
    externos (Gist/Vercel/Catbox/0x0) la verificación es BEST-EFFORT: si pasa,
    perfecto; si falla (timeouts, 403 anti-abuse desde la IP del host), igual
    se mantiene como fallback — peor un link sin validar que ningún link.
    """
    # Guardar localmente siempre
    filepath = os.path.join(PAGES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"📁 Archivo guardado: {filepath}")

    # (nombre, función, strict_verify)
    # strict_verify=True  → si HEAD/GET falla, se descarta la URL
    # strict_verify=False → si HEAD/GET falla, se guarda como fallback
    deployers = [
        ("Servidor Local", _deploy_local,  True),
        ("GitHub Gist",    _deploy_gist,   False),
        ("Vercel",         _deploy_vercel, False),
        ("Catbox",         _deploy_catbox, False),
        ("0x0.st",         _deploy_0x0,    False),
    ]

    fallback = None  # primer URL "best-effort" que vemos

    for name, deployer, strict in deployers:
        try:
            url = await deployer(html_content, filename)
        except Exception as e:
            logger.warning(f"⚠️ {name} falló al deployar: {e}")
            continue

        if not url:
            logger.debug(f"➖ {name}: sin credenciales o no aplicable")
            continue

        verified = await _verify_url_serves_html(url)
        if verified:
            logger.info(f"✅ Deploy verificado via {name}: {url}")
            return url

        if strict:
            logger.warning(f"⚠️ {name} no verificó — descartado (strict): {url}")
            continue

        logger.warning(f"⚠️ {name} no verificó — guardado como fallback: {url}")
        if fallback is None:
            fallback = (name, url)

    if fallback:
        logger.info(
            f"↩️ Usando fallback no verificado: {fallback[0]} → {fallback[1]}"
        )
        return fallback[1]

    logger.error(
        "❌ Todos los servicios de deploy fallaron. "
        "Configurá GITHUB_TOKEN (scope=gist) o VERCEL_TOKEN para producción."
    )
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
    except (ImportError, AttributeError):
        logger.warning("_deploy_gist: no se pudo importar GITHUB_TOKEN del config")
        return None

    if not GITHUB_TOKEN:
        logger.info("_deploy_gist: GITHUB_TOKEN no configurado → skip")
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
            # Sacar el commit SHA del gist — necesario para el CDN de producción
            history = gist.get("history") or []
            sha = history[0].get("version", "") if history else ""
            if owner and gist_id and sha:
                # gistcdn.githack.com = CDN de producción → sirve directo,
                # SIN página "One more step". Requiere SHA del commit.
                return f"https://gistcdn.githack.com/{owner}/{gist_id}/raw/{sha}/{filename}"
            if owner and gist_id:
                # Fallback: dev URL (puede mostrar preview, pero al menos sirve)
                logger.warning("_deploy_gist: gist sin SHA — usando URL dev")
                return f"https://gist.githack.com/{owner}/{gist_id}/raw/{filename}"
            logger.warning(f"_deploy_gist: respuesta 201 sin owner/id ({gist!r})")
            return None
        # Diagnóstico: por qué falló
        try:
            body = r.json()
            msg = body.get("message", "")
        except Exception:
            msg = (r.text or "")[:200]
        logger.warning(
            f"_deploy_gist: GitHub respondió {r.status_code} — {msg}. "
            f"Si es 401 → token inválido. 403 → scope incorrecto (necesita 'gist'). "
            f"422 → contenido rechazado."
        )
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

        try:
            r = await client.post(
                "https://catbox.moe/user/api.php",
                data=data, files=files
            )
        except httpx.HTTPError as e:
            logger.warning(f"_deploy_catbox: red/conexión falló ({type(e).__name__}: {e}) "
                           f"— probable IP del host bloqueada por anti-abuse")
            return None

        if r.status_code == 200 and r.text.strip().startswith("http"):
            return r.text.strip()
        logger.warning(
            f"_deploy_catbox: HTTP {r.status_code} — {(r.text or '')[:150]!r}"
        )
    return None

async def _deploy_0x0(html_content, filename):
    """Deploy a 0x0.st (archivos temporales)"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {"file": (filename, html_content.encode(), "text/html")}

        try:
            r = await client.post("https://0x0.st", files=files)
        except httpx.HTTPError as e:
            logger.warning(f"_deploy_0x0: red/conexión falló ({type(e).__name__}: {e}) "
                           f"— probable IP del host bloqueada por anti-abuse")
            return None

        if r.status_code == 200 and r.text.strip().startswith("http"):
            return r.text.strip()
        logger.warning(
            f"_deploy_0x0: HTTP {r.status_code} — {(r.text or '')[:150]!r}"
        )
    return None


async def shorten_url(url):
    """Acorta URLs usando servicios gratuitos sin advertencias"""
    if not url:
        return url

    encoded_url = urllib.parse.quote(url, safe='')

    # is.gd y v.gd: gratis, redirección directa sin preview ni warnings
    # (tinyurl/clck.ru muestran página de revisión para enlaces de tracking)
    shorteners = [
        ("is.gd", f"https://is.gd/create.php?format=simple&url={encoded_url}"),
        ("v.gd",  f"https://v.gd/create.php?format=simple&url={encoded_url}"),
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
