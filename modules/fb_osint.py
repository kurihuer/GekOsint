# -*- coding: utf-8 -*-
"""
Facebook OSINT — recon sobre cuentas FB.

Capacidades reales en 2026 (Meta blindó la mayoría del scraping):
  - Recovery hints (email/teléfono parcialmente ofuscados) — técnica
    Toutatis adaptada al endpoint público `/login/identify`.
  - Resolución de username/email/phone → Facebook user ID numérico
    (técnica findmyfbid). El user ID es el pivot point para todo.
  - URL de la foto de perfil pública vía CDN de FB.
  - Información extendida de Pages (NO perfiles personales) si hay
    cookies de sesión configuradas (c_user + xs).

Lo que YA NO funciona en 2026: lista de amigos, posts privados, fotos
taggeadas, scraping del feed. Meta los cerró todos.

Anti-ban: rate limiter dedicado (FB es mucho más agresivo que IG).
"""

import asyncio
import logging
import os
import re
import time
from collections import defaultdict, deque

import httpx

logger = logging.getLogger("GekOsint.FBOsint")

# ── Configuración (env vars) ──────────────────────────────────────────────────
try:
    from config import FB_C_USER, FB_XS, FB_DATR, FB_FR
except ImportError:
    FB_C_USER = os.getenv("FB_C_USER", "")
    FB_XS     = os.getenv("FB_XS", "")
    FB_DATR   = os.getenv("FB_DATR", "")
    FB_FR     = os.getenv("FB_FR", "")

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
    if FB_FR:     cookies["fr"]     = FB_FR
    return cookies


# ── Recovery hints (sin auth) ────────────────────────────────────────────────

async def get_fb_recovery_hints(query: str) -> dict:
    """
    Usa el flujo público de "Forgot password" de FB para obtener hints
    parcialmente ofuscados de email y teléfono asociados a la cuenta.

    Usa `m.facebook.com` (versión mobile) en vez de `www.facebook.com`
    porque desde IPs de cloud (Koyeb/etc) el sitio principal devuelve
    400/captcha por anti-bot, mientras que el mobile es mucho más laxo.
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

    # Headers ultra-minimalistas — cuanto más simulamos un Nokia viejo
    # accediendo a mbasic, menos anti-bot triggea Meta.
    minimal_headers = {
        "User-Agent":      "Mozilla/5.0 (Linux; U; Android 9; en-US) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Probar mbasic primero (el más laxo), después m.facebook.com como fallback
    base_urls = [
        "https://mbasic.facebook.com/login/identify/",
        "https://m.facebook.com/login/identify/",
    ]

    try:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True,
            cookies=_fb_cookies(),
        ) as client:
            html = None
            base_url = None

            for url in base_urls:
                # 1) GET inicial
                try:
                    r1 = await client.get(
                        url,
                        params={"ctx": "recover"},
                        headers=minimal_headers,
                    )
                except Exception as e:
                    logger.debug(f"FB GET {url} excepción: {e}")
                    continue

                if r1.status_code != 200:
                    logger.debug(f"FB GET {url} → HTTP {r1.status_code}")
                    continue

                # Pausa "humana" entre el GET y el POST
                await asyncio.sleep(1.5)

                # Extraer tokens CSRF
                lsd_m     = re.search(r'name="lsd"\s+value="([^"]+)"',     r1.text)
                jazoest_m = re.search(r'name="jazoest"\s+value="([^"]+)"', r1.text)
                fb_dtsg_m = re.search(r'name="fb_dtsg"\s+value="([^"]+)"', r1.text)

                data = {"email": query}
                if lsd_m:     data["lsd"]     = lsd_m.group(1)
                if jazoest_m: data["jazoest"] = jazoest_m.group(1)
                if fb_dtsg_m: data["fb_dtsg"] = fb_dtsg_m.group(1)

                # 2) POST al mismo dominio
                origin = "https://" + url.split("/")[2]
                r2 = await client.post(
                    url + "?ctx=recover",
                    data=data,
                    headers={
                        **minimal_headers,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin":       origin,
                        "Referer":      url + "?ctx=recover",
                    },
                )

                if r2.status_code in (401, 429):
                    out["error"] = f"FB rate limit ({r2.status_code})"
                    trigger_fb_pause(f"identify {r2.status_code}")
                    return out

                if r2.status_code == 400:
                    logger.debug(f"FB POST {url} → 400 (anti-bot agresivo aquí)")
                    continue

                if r2.status_code == 200:
                    html = r2.text or ""
                    base_url = url
                    break

                logger.debug(f"FB POST {url} → HTTP {r2.status_code}")

            if not html:
                out["error"] = (
                    "FB recovery bloqueado desde IP de cloud. "
                    "Las cookies funcionan pero el endpoint de recovery está "
                    "más restringido. Probá desde una IP residencial o proxy."
                )
                return out

            # Si la página redirigió al paso "How do you want to login?",
            # significa que la cuenta existe → extraer datos
            if (
                "Recover your account" in html
                or "How do you want to login" in html
                or "send_code" in html
                or "recover_account" in r2.url.path
            ):
                out["found"] = True

                # Display name (nombre completo en el header)
                name_m = re.search(
                    r'<div[^>]+class="[^"]*name[^"]*"[^>]*>([^<]{2,80})</div>',
                    html
                )
                if name_m:
                    out["display_name"] = name_m.group(1).strip()

                # Foto de perfil
                pic_m = re.search(r'<img[^>]+src="(https://[^"]+scontent[^"]+)"', html)
                if pic_m:
                    out["profile_pic_url"] = pic_m.group(1).replace("&amp;", "&")

                # User ID — aparece en URLs de form
                uid_m = re.search(r'(?:c\[0\]|"u":")(\d{8,17})', html)
                if uid_m:
                    out["user_id"] = uid_m.group(1)

                # Email parcial: patrones tipo "j****@gmail.com"
                em_m = re.search(
                    r'>([a-zA-Z0-9][\w.*•]*@[\w.*•]+\.[a-z]{2,})<',
                    html
                )
                if em_m:
                    out["obfuscated_email"] = em_m.group(1).strip()

                # Phone parcial: tipo "+•• ••• ••45" o "+57 ••• ••45"
                ph_m = re.search(
                    r'>(\+?[0-9\s•·\*]{4,}\d{2})<',
                    html
                )
                if ph_m:
                    out["obfuscated_phone"] = ph_m.group(1).strip()
            else:
                out["error"] = "FB no encontró cuenta o respuesta no parseable"

    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        logger.warning(f"get_fb_recovery_hints({query}): {e}")

    return out


# ── Conversión username → FB user ID (findmyfbid pattern) ─────────────────────

async def resolve_fb_user_id(username: str) -> dict:
    """
    Convierte un username público de FB a user ID numérico.
    Usa `mbasic.facebook.com` que es la versión más simple del sitio
    (sin JS, sin anti-bot agresivo) — ideal para scrape desde cloud IPs.

    Si mbasic falla, intenta m.facebook.com como fallback.
    """
    out = {"user_id": None, "error": None}

    # Patrones de user_id en HTML de FB
    patterns = [
        r'"userID":"(\d{8,17})"',
        r'"profile_id":(\d{8,17})',
        r'fb://profile/(\d{8,17})',
        r'content="fb://profile/(\d{8,17})"',
        r'entity_id":"(\d{8,17})"',
        r'profile\.php\?id=(\d{8,17})',
        r'/photos/(\d{8,17})/',
    ]

    candidate_urls = [
        f"https://mbasic.facebook.com/{username}",
        f"https://m.facebook.com/{username}",
    ]

    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True,
            cookies=_fb_cookies(),
        ) as client:
            for url in candidate_urls:
                r = await client.get(
                    url,
                    headers={
                        "User-Agent":      UA_MOBILE,
                        "Accept":          "text/html,application/xhtml+xml",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                if r.status_code != 200:
                    logger.debug(f"resolve_fb_user_id: {url} → HTTP {r.status_code}")
                    continue

                html = r.text or ""
                for pat in patterns:
                    m = re.search(pat, html)
                    if m:
                        out["user_id"] = m.group(1)
                        return out

            out["error"] = (
                "User ID no encontrado (perfil privado, no existe, "
                "o FB nos detectó como bot — renová cookies)"
            )
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        logger.warning(f"resolve_fb_user_id({username}): {e}")
    return out


# ── Foto de perfil vía CDN ────────────────────────────────────────────────────

def fb_profile_picture_urls(user_id: str) -> list[str]:
    """
    Construye URLs candidatas para la foto de perfil dado un user ID.
    No requiere request — son URLs públicas servidas por CDN de FB.
    """
    return [
        f"https://graph.facebook.com/{user_id}/picture?type=large",
        f"https://graph.facebook.com/{user_id}/picture?type=normal",
        f"https://graph.facebook.com/{user_id}/picture?width=800",
    ]


# ── API pública del módulo ────────────────────────────────────────────────────

async def fb_lookup(query: str) -> dict:
    """
    Lookup combinado de un username/email/teléfono/ID en Facebook.
    El rate limit por usuario debe chequearse ANTES con
    `check_fb_rate_limit(user_id)` desde el handler.
    """
    out = {
        "input":           query,
        "input_type":      "unknown",
        "found":           False,
        "user_id":         None,
        "display_name":    None,
        "profile_pic_urls": [],
        "recovery":        None,
        "session":         "authenticated" if _has_fb_cookies() else "anonymous",
        "errors":          [],
    }

    query = (query or "").strip().lstrip("@")
    if not query:
        out["errors"].append("Input vacío")
        return out

    # Detectar tipo de input
    if EMAIL_RE.match(query):
        out["input_type"] = "email"
    elif re.match(r"^\+?\d[\d\s\-]{6,}$", query):
        out["input_type"] = "phone"
    elif re.match(r"^\d{8,17}$", query):
        out["input_type"] = "user_id"
        out["user_id"] = query
    else:
        out["input_type"] = "username"

    # 1) Si es username, resolver primero a user_id
    if out["input_type"] == "username" and not out["user_id"]:
        resolved = await resolve_fb_user_id(query)
        if resolved.get("user_id"):
            out["user_id"] = resolved["user_id"]
            out["found"]   = True
        elif resolved.get("error"):
            out["errors"].append(f"Resolve: {resolved['error']}")

    # 2) Recovery hints — funciona con cualquier tipo de input
    await asyncio.sleep(INTER_REQUEST_WAIT)
    recovery = await get_fb_recovery_hints(query)
    out["recovery"] = recovery

    if recovery.get("found"):
        out["found"] = True
        if recovery.get("user_id") and not out["user_id"]:
            out["user_id"] = recovery["user_id"]
        if recovery.get("display_name"):
            out["display_name"] = recovery["display_name"]
    if recovery.get("error") and recovery["error"] not in (None, ""):
        out["errors"].append(f"Recovery: {recovery['error']}")

    # 3) Generar URLs de foto de perfil si tenemos user_id
    if out["user_id"]:
        out["profile_pic_urls"] = fb_profile_picture_urls(out["user_id"])

    return out
