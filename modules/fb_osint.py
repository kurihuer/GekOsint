# -*- coding: utf-8 -*-
"""
Facebook OSINT — recon sobre cuentas FB.

Capacidades reales en 2026 (Meta blindó la mayoría del scraping):
  - Resolución de username/email/phone → Facebook user ID numérico
    (técnica findmyfbid). El user ID es el pivot point para todo.
  - URL REAL de la foto de perfil vía CDN de FB (scontent.fbcdn.net),
    extraída del HTML del perfil con la sesión configurada. Esta SÍ abre,
    a diferencia de graph.facebook.com/{id}/picture que para IDs nuevos
    (post-2024) devuelve un placeholder en blanco / pide access token.
  - Nombre público (display name) cuando el perfil lo expone.

Lo que YA NO funciona en 2026:
  - Recovery hints (email/teléfono parcial): Meta migró el flujo a
    Bloks/CAA con payload cifrado client-side en 2024. NO recuperable
    por ningún bot. Se deja el intento como best-effort pero no se espera
    resultado.
  - Lista de amigos, posts privados, fotos taggeadas, feed. Cerrado.

Anti-ban: rate limiter dedicado (FB es mucho más agresivo que IG).
"""

import asyncio
import logging
import os
import re
import time
import urllib.parse
from collections import defaultdict, deque

import httpx

logger = logging.getLogger("GekOsint.FBOsint")

# ── Configuración (env vars) ──────────────────────────────────────────────────
try:
    from config import FB_C_USER, FB_XS, FB_DATR, FB_FR, PROXY_URL
except ImportError:
    FB_C_USER = os.getenv("FB_C_USER", "")
    FB_XS     = os.getenv("FB_XS", "")
    FB_DATR   = os.getenv("FB_DATR", "")
    FB_FR     = os.getenv("FB_FR", "")
    PROXY_URL = os.getenv("PROXY_URL", "")

# ── Rate limiter dedicado ────────────────────────────────────────────────────
PER_USER_COOLDOWN     = 90        # FB es más estricto que IG → 90s
PER_USER_HOURLY_MAX   = 15
GLOBAL_HOURLY_MAX     = 60
FB_BAN_COOLDOWN       = 45 * 60   # pausa más larga: 45 min
INTER_REQUEST_WAIT    = 4

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

_user_history: dict[int, deque] = defaultdict(deque)
_global_history: deque = deque()
_paused_until: float = 0.0


def check_fb_rate_limit(user_id: int) -> tuple[bool, str]:
    now = time.monotonic()
    if now < _paused_until:
        wait = int(_paused_until - now)
        m, s = divmod(wait, 60)
        return False, (
            f"FB OSINT pausado por anti-ban (Meta rate limit). "
            f"Reanuda en {m}m {s}s."
        )

    user_hist = _user_history[user_id]
    while user_hist and now - user_hist[0] > 3600:
        user_hist.popleft()
    if user_hist and now - user_hist[-1] < PER_USER_COOLDOWN:
        wait = int(PER_USER_COOLDOWN - (now - user_hist[-1]))
        return False, (
            f"Esperá {wait}s entre consultas FB (anti-ban). "
            f"Meta detecta consultas rápidas y bloquea cuentas de sesión."
        )
    if len(user_hist) >= PER_USER_HOURLY_MAX:
        return False, f"Alcanzaste {PER_USER_HOURLY_MAX} consultas FB/hora."

    while _global_history and now - _global_history[0] > 3600:
        _global_history.popleft()
    if len(_global_history) >= GLOBAL_HOURLY_MAX:
        return False, "Límite global FB alcanzado, esperá unos minutos."

    user_hist.append(now)
    _global_history.append(now)
    return True, ""


def trigger_fb_pause(reason: str = "rate-limit") -> None:
    global _paused_until
    _paused_until = time.monotonic() + FB_BAN_COOLDOWN
    logger.warning(f"FB OSINT pausado {FB_BAN_COOLDOWN // 60}min por: {reason}")


# ── Helpers ───────────────────────────────────────────────────────────────────

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
UA_MOBILE = (
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
)


def _has_fb_cookies() -> bool:
    return bool(FB_C_USER and FB_XS)


def _fb_cookies() -> dict:
    cookies = {}
    if FB_C_USER: cookies["c_user"] = FB_C_USER
    if FB_XS:     cookies["xs"]     = FB_XS
    if FB_DATR:   cookies["datr"]   = FB_DATR
    if FB_FR:     cookies["fr"]      = FB_FR
    return cookies


def _clean_cdn_url(url: str) -> str:
    """Normaliza una URL de imagen del CDN de FB para que abra en el navegador."""
    if not url:
        return ""
    return (
        url.replace("&amp;", "&")
           .replace("\\/", "/")
           .replace("\\u0026", "&")
           .strip()
    )


def _extract_profile_pic(html: str) -> str | None:
    """
    Extrae la URL REAL de la foto de perfil (CDN scontent.fbcdn.net) del HTML
    de un perfil de Facebook. Esta URL sí abre en el navegador (caduca en horas/
    días, pero es la foto real), a diferencia de graph.facebook.com/{id}/picture.
    Prueba varias huellas en orden de fiabilidad.
    """
    if not html:
        return None

    patterns = [
        # og:image (m.facebook / www) — suele ser la foto de perfil en alta
        r'<meta\s+property="og:image"\s+content="(https://[^"]*scontent[^"]+)"',
        r'"profilePicLarge"\s*:\s*\{\s*"uri"\s*:\s*"(https:[^"]+)"',
        r'"profile_picture"\s*:\s*\{[^}]*"uri"\s*:\s*"(https:[^"]+)"',
        r'"profilePicThumbnail"\s*:\s*\{\s*"uri"\s*:\s*"(https:[^"]+)"',
        # <img> de perfil en mbasic (primera scontent .jpg/.png)
        r'<img[^>]+src="(https://[^"]*scontent[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
        # cualquier scontent embebida
        r'"(https://scontent[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            url = _clean_cdn_url(m.group(1))
            low = url.lower()
            if "scontent" in low and not any(
                bad in low for bad in ("static.", "/rsrc.php", "sprite", "icon")
            ):
                return url
    return None


def _extract_display_name(html: str) -> str | None:
    """Extrae el nombre público del perfil desde og:title o <title>."""
    if not html:
        return None
    for pat in (
        r'<meta\s+property="og:title"\s+content="([^"]{2,80})"',
        r'<title[^>]*>([^<]{2,80})</title>',
        r'"NAME"\s*:\s*"([^"]{2,80})"',
    ):
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            low = name.lower()
            if low and not any(
                g in low for g in (
                    "facebook", "log in", "iniciar sesión", "inicia sesión",
                    "entrar", "página no", "content not found",
                )
            ):
                return name.replace("&amp;", "&")
    return None


def _build_manual_search_links(query: str, input_type: str) -> dict:
    text = (query or "").strip()
    encoded = urllib.parse.quote_plus(text)
    quoted = urllib.parse.quote_plus(f'"{text}"')
    links = {
        "google": f"https://www.google.com/search?q=site%3Afacebook.com+{quoted}",
        "facebook_search": f"https://www.facebook.com/search/top/?q={encoded}",
    }
    if input_type == "phone":
        normalized = re.sub(r"\D", "", text)
        links["google_phone"] = (
            "https://www.google.com/search?q="
            + urllib.parse.quote_plus(f'site:facebook.com "{text}" OR "{normalized}"')
        )
    elif input_type == "email":
        local_part = text.split("@", 1)[0]
        links["google_email"] = (
            "https://www.google.com/search?q="
            + urllib.parse.quote_plus(f'site:facebook.com "{text}" OR "{local_part}"')
        )
    return links


# ── Conversión username/ID → datos públicos del perfil (findmyfbid) ───────────

async def resolve_fb_profile(identifier: str) -> dict:
    """
    Dado un username público o un user ID numérico de FB, devuelve:
      - user_id (numérico)
      - profile_pic (URL real del CDN — abre en navegador)
      - display_name (nombre público)

    Usa `mbasic.facebook.com` (versión sin JS, menos anti-bot) y cae a
    `m.facebook.com` / `www`. Reutiliza la sesión (cookies) y el PROXY_URL.
    """
    out = {"user_id": None, "profile_pic": None, "display_name": None, "error": None}

    id_patterns = [
        r'"userID":"(\d{8,17})"',
        r'"profile_id":(\d{8,17})',
        r'fb://profile/(\d{8,17})',
        r'content="fb://profile/(\d{8,17})"',
        r'entity_id":"(\d{8,17})"',
        r'profile\.php\?id=(\d{8,17})',
        r'/photos/(\d{8,17})/',
        r'/(\d{8,17})/picture',
    ]

    # ── Normalizar el input ───────────────────────────────────────────────
    # Acepta: URL completa de FB, profile.php?id=NUM, /people/Nombre/NUM,
    # @usuario, usuario o ID numérico puro.
    ident = (identifier or "").strip()
    forced_id = None
    m = re.search(r'(?:facebook|fb)\.com/(?:profile\.php\?id=)?(\d{8,17})', ident)
    if not m:
        m = re.search(r'facebook\.com/people/[^/]+/(\d{8,17})', ident)
    if m:
        forced_id = m.group(1)
    else:
        um = re.search(r'(?:facebook|fb)\.com/([A-Za-z0-9.\-]+)', ident)
        if um:
            ident = um.group(1).split('?')[0]
    ident = ident.lstrip('@').strip('/')
    if re.match(r'^\d{8,17}$', ident):
        forced_id = ident

    if forced_id:
        out["user_id"] = forced_id
        path_variants = [f"profile.php?id={forced_id}"]
    else:
        path_variants = [ident]

    # URLs: www (desktop, suele traer og:image) primero, luego m y mbasic.
    candidate_urls = []
    for p in path_variants:
        candidate_urls += [
            f"https://www.facebook.com/{p}",
            f"https://m.facebook.com/{p}",
            f"https://mbasic.facebook.com/{p}",
        ]

    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    try:
        async with httpx.AsyncClient(
            timeout=18.0, follow_redirects=True,
            cookies=_fb_cookies(),
            **_proxy,
        ) as client:
            for url in candidate_urls:
                ua = UA_DESKTOP if "www.facebook" in url else UA_MOBILE
                try:
                    r = await client.get(
                        url,
                        headers={
                            "User-Agent":      ua,
                            "Accept":          "text/html,application/xhtml+xml",
                            "Accept-Language": "en-US,en;q=0.9",
                        },
                    )
                except Exception as e:
                    logger.debug(f"resolve_fb_profile GET {url}: {e}")
                    continue

                if r.status_code != 200:
                    logger.debug(f"resolve_fb_profile: {url} → HTTP {r.status_code}")
                    continue

                html = r.text or ""

                if not out["user_id"]:
                    for pat in id_patterns:
                        mm = re.search(pat, html)
                        if mm:
                            out["user_id"] = mm.group(1)
                            break

                pic = _extract_profile_pic(html)
                if pic and not out["profile_pic"]:
                    out["profile_pic"] = pic
                name = _extract_display_name(html)
                if name and not out["display_name"]:
                    out["display_name"] = name

                # Tenemos ID y foto → listo. Si falta la foto, seguimos probando
                # las otras URLs (mbasic/m) por si una la expone.
                if out["user_id"] and out["profile_pic"]:
                    return out

            if not out["user_id"] and not out["profile_pic"]:
                out["error"] = (
                    "User ID no encontrado (perfil privado, no existe, "
                    "o FB nos detectó como bot — renová cookies o revisá el proxy)"
                )
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        logger.warning(f"resolve_fb_profile({identifier}): {e}")
    return out


# Alias retrocompatible (por si otras partes importan el nombre viejo)
async def resolve_fb_user_id(username: str) -> dict:
    res = await resolve_fb_profile(username)
    return {"user_id": res.get("user_id"), "error": res.get("error")}


# ── Recovery hints (best-effort; Meta los bloqueó en 2024) ───────────────────

async def get_fb_recovery_hints(query: str) -> dict:
    """
    Intento best-effort. En 2026 Meta migró el flujo a Bloks/CAA con payload
    cifrado client-side, por lo que NO se esperan obfuscated_email/phone. Se
    mantiene para extraer, si aparece, display_name / foto del HTML inicial.
    """
    out = {
        "found":            False,
        "user_id":          None,
        "display_name":     None,
        "profile_pic_url":  None,
        "obfuscated_email": None,
        "obfuscated_phone": None,
        "error":            None,
    }

    minimal_headers = {
        "User-Agent":      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    _anon_cookies = {k: v for k, v in _fb_cookies().items() if k == "datr" and v}
    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    if PROXY_URL:
        try:
            from urllib.parse import urlparse
            _pu = urlparse(PROXY_URL)
            logger.info(f"FB recovery: usando proxy {_pu.scheme}://{_pu.hostname}:{_pu.port}")
        except Exception:
            logger.info("FB recovery: proxy configurado")
    else:
        logger.info("FB recovery: SIN proxy (alta probabilidad de bloqueo desde cloud IP)")

    base_urls = [
        "https://mbasic.facebook.com/login/identify/",
        "https://m.facebook.com/login/identify/",
    ]

    try:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True,
            cookies=_anon_cookies,
            **_proxy,
        ) as client:
            for url in base_urls:
                try:
                    r1 = await client.get(
                        url, params={"ctx": "recover"}, headers=minimal_headers,
                    )
                except Exception as e:
                    logger.debug(f"FB recovery GET {url}: {e}")
                    continue

                if r1.status_code in (401, 429):
                    trigger_fb_pause(f"identify {r1.status_code}")
                    out["error"] = f"FB rate limit ({r1.status_code})"
                    return out

                if r1.status_code != 200:
                    continue

                html = r1.text or ""
                name = _extract_display_name(html)
                pic  = _extract_profile_pic(html)
                if name:
                    out["display_name"] = name
                    out["found"] = True
                if pic:
                    out["profile_pic_url"] = pic
                break

            if not out["found"] and not out["error"]:
                out["error"] = (
                    "Recovery hints no disponibles (Meta los cifró en 2024). "
                    "Solo se puede resolver User ID + foto."
                )
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        logger.warning(f"get_fb_recovery_hints({query}): {e}")

    return out


# ── Foto de perfil vía CDN (fallback) ─────────────────────────────────────────

def fb_profile_picture_urls(user_id: str) -> list[str]:
    """
    URLs candidatas vía graph.facebook.com. OJO: para IDs nuevos (post-2024)
    estas suelen devolver placeholder en blanco o exigir access token.
    Se mantienen solo como fallback; la buena es la del CDN (profile_pic_cdn).
    """
    return [
        f"https://graph.facebook.com/{user_id}/picture?type=large&width=800&height=800",
        f"https://graph.facebook.com/{user_id}/picture?type=normal",
    ]


# ── API pública del módulo ────────────────────────────────────────────────────

async def fb_lookup(query: str) -> dict:
    """
    Lookup combinado de un username/email/teléfono/ID en Facebook.
    El rate limit por usuario debe chequearse ANTES con
    `check_fb_rate_limit(user_id)` desde el handler.
    """
    out = {
        "input":            query,
        "input_type":       "unknown",
        "found":            False,
        "user_id":          None,
        "display_name":     None,
        "profile_url":      None,
        "profile_pic_cdn":  None,
        "profile_pic_urls": [],
        "recovery":         None,
        "session":          "authenticated" if _has_fb_cookies() else "anonymous",
        "confidence":       "low",
        "evidence_signals": [],
        "notes":            [],
        "search_links":     {},
        "errors":           [],
    }

    query = (query or "").strip().lstrip("@")
    if not query:
        out["errors"].append("Input vacío")
        return out

    # Detectar tipo de input. Orden importa.
    if EMAIL_RE.match(query):
        out["input_type"] = "email"
    elif re.match(r"^\d{8,17}$", query):
        out["input_type"] = "user_id"
        out["user_id"] = query
    elif re.match(r"^\+\d[\d\s\-]{6,}$", query):
        out["input_type"] = "phone"
    else:
        out["input_type"] = "username"
    out["search_links"] = _build_manual_search_links(query, out["input_type"])
    if out["input_type"] == "username":
        out["profile_url"] = f"https://www.facebook.com/{query}"
    elif out["input_type"] == "user_id" and out.get("user_id"):
        out["profile_url"] = f"https://www.facebook.com/{out['user_id']}"

    # 1) username o user_id → resolver perfil (ID + foto CDN + nombre)
    if out["input_type"] in ("username", "user_id"):
        resolved = await resolve_fb_profile(query) or {}
        if not isinstance(resolved, dict):
            resolved = {}
        if resolved.get("user_id"):
            out["user_id"] = resolved["user_id"]
            out["found"]   = True
            if out["input_type"] == "user_id":
                out["profile_url"] = f"https://www.facebook.com/{resolved['user_id']}"
        if resolved.get("display_name"):
            out["display_name"] = resolved["display_name"]
        if resolved.get("profile_pic"):
            out["profile_pic_cdn"] = resolved["profile_pic"]
        if resolved.get("error") and not resolved.get("user_id"):
            out["errors"].append(f"Resolve: {resolved['error']}")

    # 2) Recovery hints — best-effort (no se esperan email/phone)
    await asyncio.sleep(INTER_REQUEST_WAIT)
    recovery = await get_fb_recovery_hints(query) or {}
    if not isinstance(recovery, dict):
        recovery = {}
    out["recovery"] = recovery

    if recovery.get("found"):
        out["found"] = True
        if recovery.get("user_id") and not out["user_id"]:
            out["user_id"] = recovery["user_id"]
        if recovery.get("display_name") and not out["display_name"]:
            out["display_name"] = recovery["display_name"]
    if recovery.get("profile_pic_url") and not out["profile_pic_cdn"]:
        out["profile_pic_cdn"] = recovery["profile_pic_url"]

    # 3) Inyectar la foto real del CDN en recovery para que el template la
    #    muestre como "HD (CDN real)" (el template lee recovery.profile_pic_url).
    if out["profile_pic_cdn"]:
        if not isinstance(out["recovery"], dict):
            out["recovery"] = {}
        if not out["recovery"].get("profile_pic_url"):
            out["recovery"]["profile_pic_url"] = out["profile_pic_cdn"]

    # 4) URLs de foto vía graph (fallback; pueden venir en blanco en IDs nuevos)
    if out["user_id"]:
        out["profile_pic_urls"] = fb_profile_picture_urls(out["user_id"])
        out["found"] = True
        if not out.get("profile_url"):
            out["profile_url"] = f"https://www.facebook.com/{out['user_id']}"

    if not out["found"] and out["input_type"] in ("phone", "email"):
        out["notes"].append(
            "Meta ya no permite verificar de forma fiable perfiles por teléfono o email desde este flujo."
        )
        out["notes"].append(
            "Este resultado no demuestra que la cuenta no exista; solo indica que Facebook no devolvió datos públicos reutilizables al bot."
        )

    evidence_signals: list[str] = []
    if out.get("display_name"):
        evidence_signals.append("nombre público")
    if out.get("user_id"):
        evidence_signals.append("user ID numérico")
    if out.get("profile_pic_cdn"):
        evidence_signals.append("foto pública CDN")
    if (out.get("recovery") or {}).get("profile_pic_url"):
        evidence_signals.append("foto visible en recovery HTML")
    if out.get("profile_url"):
        evidence_signals.append("URL de perfil verificable")

    if out.get("found"):
        if out.get("user_id") and out.get("profile_pic_cdn"):
            out["confidence"] = "high"
        elif out.get("user_id") or out.get("display_name"):
            out["confidence"] = "medium"
        else:
            out["confidence"] = "low"

    deduped: list[str] = []
    for signal in evidence_signals:
        if signal not in deduped:
            deduped.append(signal)
    out["evidence_signals"] = deduped

    return out
