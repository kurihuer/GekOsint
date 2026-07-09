
import logging
import asyncio
import urllib.parse
import httpx
import os
from config import PAGES_DIR
from datetime import datetime
from io import BytesIO

logger = logging.getLogger(__name__)

def generate_text_report(title, data_str):
    """Genera un reporte en texto plano formateado"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    # Netlify va PRIMERO (después de Local) porque sirve URLs directas
    # *.netlify.app sin páginas intermedias — ideal para tracking pages.
    deployers = [
        ("Servidor Local", _deploy_local,   True),
        ("Netlify",        _deploy_netlify, False),
        ("GitHub Gist",    _deploy_gist,    False),
        ("Vercel",         _deploy_vercel,  False),
        ("Catbox",         _deploy_catbox,  False),
        ("0x0.st",         _deploy_0x0,     False),
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
            if owner and gist_id:
                # cdn.statically.io → CDN serio que sirve gists con
                # Content-Type: text/html y SIN página intermedia tipo
                # "One more step" (problema crónico de gist.githack.com).
                return f"https://cdn.statically.io/gist/{owner}/{gist_id}/raw/{filename}"
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

async def _deploy_netlify(html_content, filename):
    """
    Deploy a Netlify (requiere NETLIFY_TOKEN).

    Crea un site nuevo + sube el HTML como un .zip (deploy "drop").
    Devuelve URL tipo https://<random-name>.netlify.app/<filename> que
    sirve el HTML directamente con Content-Type correcto, SIN página
    intermedia ni warning. Es el deployer ideal para tracking pages.
    """
    try:
        from config import NETLIFY_TOKEN
    except (ImportError, AttributeError):
        # config.py no expone NETLIFY_TOKEN: lo leemos directo del entorno
        NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN", "")

    if not NETLIFY_TOKEN:
        logger.info("_deploy_netlify: NETLIFY_TOKEN no configurado → skip")
        return None

    # Construimos un .zip en memoria con el HTML como index.html (para que
    # Netlify lo sirva en la raíz) Y con el nombre real (para mantener el
    # path original tipo /geo_xxxx.html).
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", html_content)
        if filename and filename != "index.html":
            zf.writestr(filename, html_content)
    zip_bytes = buf.getvalue()

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(
                "https://api.netlify.com/api/v1/sites",
                headers={
                    "Authorization": f"Bearer {NETLIFY_TOKEN}",
                    "Content-Type": "application/zip",
                },
                content=zip_bytes,
            )
        except httpx.HTTPError as e:
            logger.warning(f"_deploy_netlify: red/conexión falló ({type(e).__name__}: {e})")
            return None

        if r.status_code not in (200, 201):
            try:
                body = r.json()
                msg = body.get("message", "")
            except Exception:
                msg = (r.text or "")[:200]
            logger.warning(
                f"_deploy_netlify: HTTP {r.status_code} — {msg}. "
                f"Si es 401 → token inválido. 403 → permisos insuficientes."
            )
            return None

        try:
            site = r.json()
        except Exception as e:
            logger.warning(f"_deploy_netlify: respuesta no-JSON: {e}")
            return None

        # Netlify devuelve 'url' (https://<sub>.netlify.app) o 'ssl_url'
        site_url = site.get("ssl_url") or site.get("url")
        if not site_url:
            subdomain = site.get("subdomain") or site.get("name")
            if subdomain:
                site_url = f"https://{subdomain}.netlify.app"

        if not site_url:
            logger.warning(f"_deploy_netlify: sin URL en respuesta ({site!r})")
            return None

        # El path final servido es /<filename> (o /index.html en raíz)
        return f"{site_url.rstrip('/')}/{filename}"


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
    """
    Acorta URLs usando servicios que redirigen DIRECTO al destino
    (HTTP 301/302 sin páginas intermedias ni warnings).

    Servicios usados (todos sin auth, sin interstitials, sin captcha):
      - tinyurl.com  → 301 directo
      - is.gd        → 301 directo
      - v.gd         → 301 directo
      - da.gd        → 301 directo, ultra minimal
      - chilp.it     → 301 directo

    Si todos fallan, retorna la URL original (mejor URL larga directa
    que un shortener con interstitial tipo clck.ru).
    """
    if not url:
        return url

    encoded_url = urllib.parse.quote(url, safe='')

    shorteners = [
        ("tinyurl", f"https://tinyurl.com/api-create.php?url={encoded_url}"),
        ("is.gd",   f"https://is.gd/create.php?format=simple&url={encoded_url}"),
        ("v.gd",    f"https://v.gd/create.php?format=simple&url={encoded_url}"),
        ("da.gd",   f"https://da.gd/s?url={encoded_url}"),
        ("chilp.it", f"https://chilp.it/api.php?url={encoded_url}"),
    ]

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for name, api_url in shorteners:
            try:
                r = await client.get(api_url, headers=HEADERS)
                if r.status_code != 200:
                    logger.debug(f"{name}: HTTP {r.status_code}")
                    continue
                short = r.text.strip()
                if not short.startswith("http"):
                    logger.debug(f"{name}: respuesta sin URL ({short[:80]!r})")
                    continue
                # Verificación: que redirija DIRECTO (un solo salto)
                try:
                    h = await client.head(short, headers=HEADERS)
                    if h.status_code in (301, 302, 303, 307, 308):
                        location = h.headers.get("location", "")
                        if location and url.split("?")[0] in location:
                            logger.info(f"URL acortada con {name} (verificada directa): {short}")
                            return short
                        logger.info(f"URL acortada con {name}: {short}")
                        return short
                    logger.info(f"URL acortada con {name}: {short}")
                    return short
                except Exception:
                    logger.info(f"URL acortada con {name}: {short}")
                    return short
            except Exception as e:
                logger.debug(f"{name} falló: {e}")
                continue

    logger.info("No se pudo acortar, usando URL original (preferible a shortener con interstitial)")
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


def generate_pdf_report(title: str, data: dict, input_text: str = "") -> bytes:
    """Genera un reporte PDF profesional con todos los resultados del OSINT."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.colors import Color, black, darkblue, crimson
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        def normalize_report_payload(report_data: dict) -> tuple[dict, str]:
            if not isinstance(report_data, dict):
                return {}, input_text or ""

            if any(k in report_data for k in (
                "ip_lookup", "phone_intel", "email_analysis", "email_recon",
                "gmail_osint", "fb_osint", "username_search", "github_recon",
                "people_search", "dns_lookup", "tiktok_osint", "whatsapp_osint",
            )):
                return report_data, input_text or report_data.get("input", "")

            target = input_text or report_data.get("input", "")
            mode = report_data.get("mode", "")

            if mode == "menu_universal":
                payload = report_data.get("universal_results") or report_data.get("data") or {}
                return payload, target

            raw = report_data.get("data")
            if not isinstance(raw, dict):
                return {}, target

            mode_map = {
                "menu_ip": "ip_lookup",
                "menu_phone": "phone_intel",
                "menu_email": "email_analysis",
                "menu_emailrecon": "email_recon",
                "menu_gmail": "gmail_osint",
                "menu_fb": "fb_osint",
                "menu_user": "username_search",
                "menu_github": "github_recon",
                "menu_people": "people_search",
                "menu_dns": "dns_lookup",
                "menu_tiktok": "tiktok_osint",
                "menu_wa": "whatsapp_osint",
            }
            key = mode_map.get(mode)
            return ({key: raw} if key else raw), target

        payload, resolved_input = normalize_report_payload(data)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              rightMargin=50, leftMargin=50,
                              topMargin=50, bottomMargin=50)
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=22,
            textColor=darkblue,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=darkblue,
            spaceBefore=15,
            spaceAfter=10
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=6
        )
        
        danger_style = ParagraphStyle(
            'Danger',
            parent=styles['Normal'],
            fontSize=10,
            textColor=crimson,
            leading=14,
            spaceAfter=6
        )
        
        story = []
        
        story.append(Paragraph("🔒 GEKOSINT OSINT REPORT", title_style))
        story.append(Spacer(1, 10))
        
        meta_data = [
            ['Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ['Target:', resolved_input or 'N/A'],
            ['Purpose:', 'Educational - Ethical Hacking Demonstration'],
        ]
        meta_table = Table(meta_data, colWidths=[100, 400])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), Color(0.95, 0.95, 0.95)),
            ('TEXTCOLOR', (0, 0), (-1, -1), black),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, black),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 20))
        
        def add_section(title_text: str, content_dict: dict):
            if "error" in content_dict:
                return
            
            story.append(Paragraph(title_text, header_style))
            
            items = []
            for key, value in list(content_dict.items())[:15]:
                if key in ["error", "missing_keys", "osint_links", "links", "social_search_links"]:
                    continue
                if value is None:
                    continue
                if isinstance(value, dict):
                    for k2, v2 in list(value.items())[:5]:
                        if v2 is not None and not isinstance(v2, dict):
                            items.append([f"{key}.{k2}", str(v2)[:100]])
                elif not isinstance(value, (list, dict)):
                    items.append([key.replace('_', ' ').title(), str(value)[:150]])
            
            if items:
                t = Table(items, colWidths=[150, 350])
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 10))
        
        if "ip_lookup" in payload:
            add_section("🌐 IP INTELLIGENCE", payload["ip_lookup"])
        
        if "phone_intel" in payload:
            add_section("📱 PHONE INTELLIGENCE", payload["phone_intel"])
        
        if "email_analysis" in payload:
            add_section("📧 EMAIL ANALYSIS", payload["email_analysis"])
        
        if "gmail_osint" in payload:
            gmail = payload["gmail_osint"] or {}
            story.append(Paragraph("📧 GMAIL / GOOGLE OSINT", header_style))
            gmail_items = []
            if gmail.get("input"):
                gmail_items.append(["Email", str(gmail.get("input"))[:120]])
            if gmail.get("session"):
                gmail_items.append(["Sesion", str(gmail.get("session"))[:60]])
            if gmail.get("account_type"):
                gmail_items.append(["Tipo", str(gmail.get("account_type"))[:60]])
            if gmail.get("confidence"):
                gmail_items.append(["Confianza", str(gmail.get("confidence"))[:20]])
            evidence = gmail.get("evidence_signals") or []
            if evidence:
                gmail_items.append(["Evidencia", " | ".join(evidence[:4])])
            if gmail_items:
                t = Table(gmail_items, colWidths=[120, 380])
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))

            rec = gmail.get("recovery") or {}
            rec_items = []
            if rec.get("obfuscated_phone"):
                rec_items.append(["Telefono hint", rec.get("obfuscated_phone")])
            if rec.get("obfuscated_email"):
                rec_items.append(["Email hint", rec.get("obfuscated_email")])
            if rec_items:
                story.append(Paragraph("Recovery hints", section_style))
                t = Table(rec_items, colWidths=[120, 380])
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))

            prof = gmail.get("profile") or {}
            prof_items = []
            if prof.get("gaia_id"):
                prof_items.append(["Google ID", str(prof.get("gaia_id"))[:80]])
            if prof.get("names"):
                prof_items.append(["Nombres", " | ".join([str(x)[:40] for x in prof.get("names", [])[:3]])])
            if prof.get("photo_url"):
                prof_items.append(["Foto", str(prof.get("photo_url"))[:140]])
            if prof.get("organizations"):
                orgs = []
                for org in prof.get("organizations", [])[:2]:
                    bits = [org.get("name"), org.get("title")]
                    orgs.append(" | ".join([str(x)[:30] for x in bits if x]))
                if orgs:
                    prof_items.append(["Organizacion", " ; ".join(orgs)])
            if prof.get("locations"):
                prof_items.append(["Ubicacion", " | ".join([str(x)[:40] for x in prof.get("locations", [])[:2]])])
            if prof_items:
                story.append(Paragraph("Perfil Google", section_style))
                t = Table(prof_items, colWidths=[120, 380])
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))

            dom = gmail.get("domain") or {}
            dom_items = []
            if dom.get("domain"):
                dom_items.append(["Dominio", str(dom.get("domain"))[:80]])
            if dom.get("mail_provider"):
                dom_items.append(["Proveedor", str(dom.get("mail_provider"))[:80]])
            if dom.get("mx_records"):
                dom_items.append(["MX", ", ".join([str(x)[:40] for x in dom.get("mx_records", [])[:2]])])
            sec_bits = []
            if dom.get("has_spf") is True:
                sec_bits.append("SPF")
            elif dom.get("has_spf") is False:
                sec_bits.append("sin SPF")
            if dom.get("has_dmarc") is True:
                sec_bits.append("DMARC")
            elif dom.get("has_dmarc") is False:
                sec_bits.append("sin DMARC")
            if sec_bits:
                dom_items.append(["Seguridad", " | ".join(sec_bits)])
            if dom_items:
                story.append(Paragraph("Dominio", section_style))
                t = Table(dom_items, colWidths=[120, 380])
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))

            pivots = gmail.get("manual_pivots") or []
            if pivots:
                story.append(Paragraph("Pivotes recomendados", section_style))
                for pivot in pivots[:3]:
                    label = pivot.get("label", "Pivote")
                    url = pivot.get("url", "")
                    desc = pivot.get("description", "")
                    line = f"• {label}: {url}"
                    if desc:
                        line += f" ({desc})"
                    story.append(Paragraph(line, body_style))
                story.append(Spacer(1, 10))

        if "fb_osint" in payload:
            fb = payload["fb_osint"] or {}
            story.append(Paragraph("📘 FACEBOOK OSINT", header_style))
            fb_items = []
            if fb.get("input"):
                fb_items.append(["Input", str(fb.get("input"))[:120]])
            if fb.get("input_type"):
                fb_items.append(["Tipo", str(fb.get("input_type"))[:40]])
            if fb.get("session"):
                fb_items.append(["Sesion", str(fb.get("session"))[:40]])
            if fb.get("confidence"):
                fb_items.append(["Confianza", str(fb.get("confidence"))[:20]])
            if fb.get("display_name"):
                fb_items.append(["Nombre", str(fb.get("display_name"))[:80]])
            if fb.get("user_id"):
                fb_items.append(["FB User ID", str(fb.get("user_id"))[:40]])
            if fb.get("profile_url"):
                fb_items.append(["Perfil", str(fb.get("profile_url"))[:150]])
            signals = fb.get("evidence_signals") or []
            if signals:
                fb_items.append(["Evidencia", " | ".join(str(s) for s in signals[:4])[:150]])
            if fb.get("profile_pic_cdn"):
                fb_items.append(["Foto publica", str(fb.get("profile_pic_cdn"))[:150]])
            if fb_items:
                t = Table(fb_items, colWidths=[120, 380])
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 10))

        if "email_recon" in payload:
            recon = payload["email_recon"]
            story.append(Paragraph("📨 EMAIL RECON (Multi-Platform)", header_style))
            summary = recon.get("summary") or {}
            meta_bits = [
                f"Chequeados: {summary.get('checked_total', len(recon.get('checked') or []))}",
                f"Detectados: {summary.get('found_total', len(recon.get('found_in') or []))}",
            ]
            if summary.get("high_signal_total"):
                meta_bits.append(f"Fuertes: {summary.get('high_signal_total')}")
            if recon.get("local_part"):
                meta_bits.append(f"Alias: {recon.get('local_part')}")
            if recon.get("domain"):
                meta_bits.append(f"Dominio: {recon.get('domain')}")
            story.append(Paragraph(" | ".join(meta_bits), body_style))
            story.append(Spacer(1, 6))

            found_services = [
                [
                    entry.get("service", ""),
                    entry.get("category", "Otro"),
                    entry.get("signal", "medium"),
                    entry.get("hint", ""),
                ]
                for entry in (recon.get("found_in") or [])
                if entry.get("service")
            ]
            if found_services:
                t = Table([["Platform", "Categoria", "Fuerza", "Pista"]] + found_services[:12], colWidths=[110, 110, 70, 210])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), Color(1, 1, 1)),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('PADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 6))
            pivots = recon.get("pivots") or []
            if pivots:
                story.append(Paragraph("Pivotes recomendados", section_style))
                for pivot in pivots[:3]:
                    label = pivot.get("label", "Pivote")
                    url = pivot.get("url", "")
                    desc = pivot.get("description", "")
                    line = f"• {label}: {url}"
                    if desc:
                        line += f" ({desc})"
                    story.append(Paragraph(line, body_style))
            story.append(Spacer(1, 10))
        
        if "whatsapp_osint" in payload:
            add_section("💚 WHATSAPP OSINT", payload["whatsapp_osint"])

        if "username_search" in payload:
            user = payload["username_search"]
            story.append(Paragraph("👤 USERNAME SEARCH", header_style))
            tg = user.get("telegram") or {}
            if tg.get("exists"):
                tg_items = [
                    ["Telegram", tg.get("url", f"https://t.me/{tg.get('username', '')}")],
                    ["Tipo", tg.get("type", "N/A")],
                ]
                if tg.get("name"):
                    tg_items.append(["Nombre", str(tg.get("name"))[:80]])
                t = Table(tg_items, colWidths=[120, 380])
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, Color(0.7, 0.7, 0.7)),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))

            socials = user.get("socials") or {}
            verified_socials = []
            ig = socials.get("instagram") or {}
            if ig.get("found"):
                ig_profile = ig.get("profile") or {}
                ig_evidence = []
                if ig_profile.get("full_name"):
                    ig_evidence.append(str(ig_profile.get("full_name"))[:40])
                ig_flags = []
                if ig_profile.get("is_verified"):
                    ig_flags.append("verificada")
                if ig_profile.get("is_private"):
                    ig_flags.append("privada")
                if ig_flags:
                    ig_evidence.append(", ".join(ig_flags))
                if ig_profile.get("followers") is not None:
                    ig_evidence.append(f"{ig_profile.get('followers', 0):,} seg.")
                verified_socials.append([
                    "Instagram",
                    " | ".join(ig_evidence[:3]) or "Perfil confirmado por IG",
                    f"https://www.instagram.com/{user.get('username', resolved_input).lstrip('@')}/",
                ])
            fb = socials.get("facebook") or {}
            if fb.get("found"):
                fb_url = fb.get("profile_url") or (
                    f"https://www.facebook.com/{fb.get('user_id')}" if fb.get("user_id") else f"https://www.facebook.com/{user.get('username', resolved_input).lstrip('@')}"
                )
                fb_evidence = []
                if fb.get("display_name"):
                    fb_evidence.append(str(fb.get("display_name"))[:40])
                if fb.get("user_id"):
                    fb_evidence.append(f"ID {fb.get('user_id')}")
                if fb.get("confidence"):
                    fb_evidence.append(f"confianza {fb.get('confidence')}")
                if fb.get("profile_pic_cdn") or (fb.get("recovery") or {}).get("profile_pic_url"):
                    fb_evidence.append("foto publica")
                verified_socials.append([
                    "Facebook",
                    " | ".join(fb_evidence[:3]) or "Perfil confirmado por FB",
                    fb_url,
                ])
            tt = socials.get("tiktok") or {}
            if isinstance(tt, dict) and not tt.get("error") and tt.get("profile_url"):
                tt_evidence = []
                if tt.get("nickname"):
                    tt_evidence.append(str(tt.get("nickname"))[:40])
                tt_flags = []
                if tt.get("verified"):
                    tt_flags.append("verificada")
                if tt.get("private"):
                    tt_flags.append("privada")
                if tt_flags:
                    tt_evidence.append(", ".join(tt_flags))
                if tt.get("followers"):
                    tt_evidence.append(f"{tt.get('followers')} seg.")
                verified_socials.append([
                    "TikTok",
                    " | ".join(tt_evidence[:3]) or "Perfil confirmado por TikTok",
                    tt.get("profile_url"),
                ])
            if verified_socials:
                t = Table([["Red Social", "Prueba", "URL"]] + verified_socials, colWidths=[80, 170, 250])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), Color(1, 1, 1)),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('PADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))

            if user.get("found"):
                found = user["found"]
                items = [[site, url] for site, url in found[:10]]
                if items:
                    t = Table([["Platform", "URL"]] + items)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), darkblue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), Color(1, 1, 1)),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('PADDING', (0, 0), (-1, -1), 3),
                    ]))
                    story.append(t)
            story.append(Spacer(1, 10))
        
        if "github_recon" in payload:
            gh = payload["github_recon"]
            if isinstance(gh, dict) and gh.get("profile"):
                add_section("💻 GITHUB RECON", {
                    "login": (gh.get("profile") or {}).get("login"),
                    "name": (gh.get("profile") or {}).get("name"),
                    "location": (gh.get("profile") or {}).get("location"),
                    "public_repos": (gh.get("stats") or {}).get("total_repos"),
                    "followers": (gh.get("stats") or {}).get("followers"),
                    "unique_leaked_emails": (gh.get("stats") or {}).get("unique_leaked_emails"),
                })

        if "people_search" in payload:
            add_section("🧑 PEOPLE SEARCH", payload["people_search"])

        if "dns_lookup" in payload:
            add_section("🌐 DOMAIN / DNS", payload["dns_lookup"])

        if "tiktok_osint" in payload:
            tt = payload["tiktok_osint"]
            if isinstance(tt, dict) and not tt.get("error"):
                story.append(Paragraph("📹 TIKTOK OSINT", header_style))
                items = [
                    ["Username", tt.get('username', 'N/A')],
                    ["Followers", str(tt.get('followers', 0))],
                    ["Following", str(tt.get('following', 0))],
                    ["Likes", str(tt.get('total_likes', 0))],
                    ["Videos", str(tt.get('video_count', 0))],
                    ["Region", tt.get('region', 'N/A')],
                ]
                t = Table(items)
                t.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
                story.append(Spacer(1, 10))
        
        story.append(Paragraph(
            "⚠️ This report is for educational purposes only. "
            "Demonstrating OSINT capabilities to raise cybersecurity awareness.",
            ParagraphStyle('Footer', parent=styles['Normal'], 
                          fontSize=9, textColor=Color(0.4, 0.4, 0.4),
                          alignment=TA_CENTER)
        ))
        
        doc.build(story)
        return buffer.getvalue()
        
    except ImportError:
        logger.warning("reportlab no instalado, usando fallback TXT")
        return generate_text_report(title, str(data)).encode()
