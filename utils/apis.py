
import logging
import asyncio
import urllib.parse
import httpx
import os
import base64
from config import PAGES_DIR

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def deploy_html(html_content, filename="index.html"):
    """
    Sube HTML usando múltiples servicios con fallback automático.
    Orden: Vercel -> Catbox -> 0x0.st -> Netlify Drop
    """
    # Guardar localmente siempre
    filepath = os.path.join(PAGES_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"✅ Archivo guardado: {filepath}")
    
    # Intentar cada servicio en orden
    deployers = [
        ("Vercel", _deploy_vercel),
        ("Catbox", _deploy_catbox),
        ("0x0.st", _deploy_0x0),
        ("Telegra.ph", _deploy_telegraph),
    ]
    
    for name, deployer in deployers:
        try:
            url = await deployer(html_content, filename)
            if url:
                logger.info(f"✅ Deploy exitoso via {name}: {url}")
                return url
        except Exception as e:
            logger.warning(f"⚠️ {name} falló: {e}")
            continue
    
    logger.error("❌ Todos los servicios de deploy fallaron")
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

async def _deploy_telegraph(html_content, filename):
    """Deploy a Telegra.ph (requiere crear página)"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Crear cuenta temporal
        r = await client.post(
            "https://api.telegra.ph/createAccount",
            json={"short_name": "GekOsint", "author_name": "GekOsint"}
        )
        if r.status_code != 200:
            return None
        
        token = r.json().get("result", {}).get("access_token")
        if not token:
            return None
        
        # Crear página con iframe del HTML
        # Telegraph no soporta HTML raw, así que usamos un enfoque diferente
        # Subimos a otro servicio y enlazamos
        return None  # Telegraph no es ideal para HTML raw

async def shorten_url(url):
    """Acorta URLs usando servicios gratuitos sin advertencias"""
    if not url:
        return url
    
    if len(url) < 50:
        return url
    
    encoded_url = urllib.parse.quote(url, safe='')
    
    shorteners = [
        ("is.gd", f"https://is.gd/create.php?format=simple&url={encoded_url}"),
        ("tinyurl", f"https://tinyurl.com/api-create.php?url={encoded_url}"),
        ("v.gd", f"https://v.gd/create.php?format=simple&url={encoded_url}"),
    ]
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for name, api_url in shorteners:
            try:
                r = await client.get(api_url)
                if r.status_code == 200 and r.text.strip().startswith("http"):
                    short = r.text.strip()
                    logger.info(f"✅ URL acortada con {name}: {short}")
                    return short
            except Exception as e:
                logger.debug(f"⚠️ {name} falló: {e}")
                continue
    
    logger.info("⚠️ No se pudo acortar, usando URL original")
    return url
