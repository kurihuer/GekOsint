# -*- coding: utf-8 -*-
"""
TikTok OSINT — perfil público vía scraping del JSON embebido en la web.

No requiere API key. Extrae: nickname, bio, seguidores, likes, videos,
verificación, privacidad, región, fecha de creación.

Rate limit dedicado: 1 consulta cada 45s por usuario, 20/hora por usuario,
100/hora global. TikTok no es tan agresivo como Instagram con cloud IPs,
pero igual se aplica rate limit prudente.
"""

import asyncio
import json
import logging
import re
import time
from collections import defaultdict, deque

import httpx

from config import RAPIDAPI_KEY

logger = logging.getLogger("GekOsint.TikTok")

# ── Rate limiter ──────────────────────────────────────────────────────────────
PER_USER_COOLDOWN   = 45
PER_USER_HOURLY_MAX = 20
GLOBAL_HOURLY_MAX   = 100

_user_history: dict[int, deque] = defaultdict(deque)
_global_history: deque          = deque()


def check_tiktok_rate_limit(user_id: int) -> tuple[bool, str]:
    now = time.monotonic()

    user_hist = _user_history[user_id]
    while user_hist and now - user_hist[0] > 3600:
        user_hist.popleft()

    if user_hist and now - user_hist[-1] < PER_USER_COOLDOWN:
        wait = int(PER_USER_COOLDOWN - (now - user_hist[-1]))
        return False, f"Esperá {wait}s antes de la próxima consulta TikTok."

    if len(user_hist) >= PER_USER_HOURLY_MAX:
        return False, f"Límite de {PER_USER_HOURLY_MAX} consultas/hora alcanzado."

    while _global_history and now - _global_history[0] > 3600:
        _global_history.popleft()
    if len(_global_history) >= GLOBAL_HOURLY_MAX:
        return False, "Límite global TikTok alcanzado, esperá unos minutos."

    user_hist.append(now)
    _global_history.append(now)
    return True, ""


# ── Headers realistas ─────────────────────────────────────────────────────────
_HEADERS_WEB = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "none",
}


# ── Helpers de formato ────────────────────────────────────────────────────────

def _fmt_number(n) -> str:
    """1234567 → '1.2M', 12345 → '12.3K'"""
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return str(n)


def _fmt_date(ts) -> str:
    """Unix timestamp → fecha legible."""
    try:
        import datetime
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""


# ── Scraping principal (JSON embebido) ────────────────────────────────────────

async def _scrape_web(username: str, client: httpx.AsyncClient) -> dict | None:
    """
    Intenta extraer el JSON __UNIVERSAL_DATA_FOR_REHYDRATION__ del HTML de TikTok.
    Este script contiene toda la info del perfil sin necesitar API key.
    """
    url = f"https://www.tiktok.com/@{username}"
    try:
        r = await client.get(url, headers=_HEADERS_WEB)
    except Exception as e:
        logger.debug(f"TikTok scrape error HTTP: {e}")
        return None

    if r.status_code == 404:
        return {"_not_found": True}
    if r.status_code != 200:
        logger.debug(f"TikTok scrape: HTTP {r.status_code}")
        return None

    html = r.text

    # 1) Intentar con el JSON universal
    m = re.search(
        r'<script[^>]+id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    if m:
        try:
            data   = json.loads(m.group(1))
            scope  = data.get("__DEFAULT_SCOPE__", {})
            detail = scope.get("webapp.user-detail", {})
            ui     = detail.get("userInfo", {})
            user   = ui.get("user", {})
            stats  = ui.get("stats", {})
            if user and user.get("id"):
                return {"user": user, "stats": stats, "_source": "universal_json"}
        except Exception as e:
            logger.debug(f"TikTok universal JSON parse: {e}")

    # 2) Fallback: regex sobre el HTML crudo (menos confiable)
    def _re_str(pattern):
        mo = re.search(pattern, html)
        return mo.group(1) if mo else ""
    def _re_int(pattern):
        mo = re.search(pattern, html)
        try:
            return int(mo.group(1)) if mo else 0
        except Exception:
            return 0

    uid       = _re_str(r'"id"\s*:\s*"(\d{10,})"')
    nickname  = _re_str(r'"nickname"\s*:\s*"([^"]{1,60})"')
    followers = _re_int(r'"followerCount"\s*:\s*(\d+)')
    likes     = _re_int(r'"heartCount"\s*:\s*(\d+)')
    videos    = _re_int(r'"videoCount"\s*:\s*(\d+)')

    if uid or followers:
        return {
            "_source": "html_regex",
            "user": {
                "id":             uid,
                "uniqueId":       username,
                "nickname":       nickname or username,
                "signature":      "",
                "verified":       False,
                "privateAccount": False,
                "region":         "",
                "createTime":     0,
            },
            "stats": {
                "followerCount": followers,
                "followingCount": _re_int(r'"followingCount"\s*:\s*(\d+)'),
                "heartCount":    likes,
                "videoCount":    videos,
                "diggCount":     _re_int(r'"diggCount"\s*:\s*(\d+)'),
            }
        }

    # El perfil existe pero TikTok bloqueó la extracción
    if len(html) > 3000:
        return {"_bot_check": True}

    return None


# ── Fallback RapidAPI (si hay clave) ──────────────────────────────────────────

async def _rapidapi_lookup(username: str, client: httpx.AsyncClient) -> dict | None:
    """
    Intenta los 3 mejores endpoints de TikTok en RapidAPI en orden.
    Todos usan la misma RAPIDAPI_KEY — solo cambia el host.
    Orden: TiKWM (tiktok-scraper7) → ScrapTik → TokApi
    """
    if not RAPIDAPI_KEY:
        return None

    # (url, host, parser_fn)
    endpoints = [
        # 1) TiKWM — tiktok-scraper7 (score 10, 888ms) — el que estaba antes
        (
            "https://tiktok-scraper7.p.rapidapi.com/user/info",
            "tiktok-scraper7.p.rapidapi.com",
            {"params": {"unique_id": username}},
            lambda d: (
                (d.get("data") or {}).get("user", {}),
                (d.get("data") or {}).get("stats", {}),
            ),
        ),
        # 2) ScrapTik — scraptik (score 9.9, 1150ms)
        (
            "https://scraptik.p.rapidapi.com/get-user",
            "scraptik.p.rapidapi.com",
            {"params": {"username": username}},
            lambda d: (
                d.get("user_info", {}).get("user", {}),
                d.get("user_info", {}).get("stats", {}),
            ),
        ),
        # 3) TokApi mobile — somjik (score 9.9, 1638ms)
        (
            "https://tokapi-mobile-version.p.rapidapi.com/v1/user",
            "tokapi-mobile-version.p.rapidapi.com",
            {"params": {"username": username, "region": "US"}},
            lambda d: (
                (d.get("user_info") or {}).get("user", {}),
                (d.get("user_info") or {}).get("stats", {}),
            ),
        ),
    ]

    for url, host, req_kwargs, parser in endpoints:
        try:
            r = await client.get(
                url,
                headers={"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": host},
                timeout=15.0,
                **req_kwargs,
            )
            if r.status_code == 200:
                d     = r.json()
                user, stats = parser(d)
                if user and user.get("id"):
                    logger.debug(f"TikTok RapidAPI OK via {host}")
                    return {"user": user, "stats": stats, "_source": f"rapidapi:{host}"}
            logger.debug(f"TikTok RapidAPI {host}: HTTP {r.status_code}")
        except Exception as e:
            logger.debug(f"TikTok RapidAPI {host} error: {e}")

    return None


# ── Punto de entrada principal ────────────────────────────────────────────────

async def tiktok_lookup(raw_input: str) -> dict:
    """
    Lookup de perfil TikTok. Acepta:
      - username sin @ → 'cristiano'
      - username con @ → '@cristiano'
      - URL completa  → 'https://www.tiktok.com/@cristiano'
    """
    # Normalizar input
    username = raw_input.strip()
    if username.startswith("https://") or username.startswith("http://"):
        m = re.search(r'tiktok\.com/@?([\w.]+)', username)
        username = m.group(1) if m else username
    username = username.lstrip("@").strip()

    if not username or len(username) > 50:
        return {"error": "Username inválido.", "username": raw_input}

    result: dict = {
        "username":    username,
        "profile_url": f"https://www.tiktok.com/@{username}",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        http2=False,
    ) as client:

        # Intentar scraping web primero
        raw = await _scrape_web(username, client)

        # Si el scraping falló o devolvió bot-check, intentar RapidAPI
        rapidapi_tried = False
        if raw is None or raw.get("_bot_check"):
            rapidapi_tried = True
            raw = await _rapidapi_lookup(username, client)

        if raw is None:
            has_key = bool(RAPIDAPI_KEY)
            if has_key and rapidapi_tried:
                diag = (
                    "TikTok y RapidAPI fallaron desde esta IP.\n"
                    "Posibles causas:\n"
                    "- No suscripto al plan de TiKWM/ScrapTik en RapidAPI\n"
                    "- Key incorrecta o expirada\n\n"
                    f"Ver perfil: https://www.tiktok.com/@{username}"
                )
            elif not has_key:
                diag = (
                    "TikTok bloquea IPs de servidor. Configura RAPIDAPI_KEY\n\n"
                    f"Ver perfil: https://www.tiktok.com/@{username}"
                )
            else:
                diag = (
                    "TikTok bloquea IPs de servidor cloud.\n\n"
                    f"Ver perfil: https://www.tiktok.com/@{username}"
                )
            return {
                "error": diag,
                "username": username,
                "_blocked": True,
            }

        if raw.get("_not_found"):
            return {"error": "Usuario no encontrado en TikTok.", "username": username}

        if raw.get("_bot_check"):
            result["note"] = (
                "⚠️ TikTok devolvió un bot-check desde esta IP.\n"
                "Prueba en: https://www.tiktok.com/@" + username
            )
            return result

    # Mapear datos
    user  = raw.get("user",  {})
    stats = raw.get("stats", {})
    src   = raw.get("_source", "")

    result.update({
        "user_id":      user.get("id", ""),
        "nickname":     user.get("nickname", username),
        "bio":          user.get("signature", ""),
        "verified":     bool(user.get("verified", False)),
        "private":      bool(user.get("privateAccount", False)),
        "region":       user.get("region", ""),
        "create_time":  _fmt_date(user.get("createTime", 0)),
        "avatar_url":   user.get("avatarLarger", user.get("avatarMedium", "")),

        # Stats
        "followers":    _fmt_number(stats.get("followerCount",  0)),
        "following":    _fmt_number(stats.get("followingCount", 0)),
        "total_likes":  _fmt_number(stats.get("heartCount",     0)),
        "video_count":  _fmt_number(stats.get("videoCount",     0)),
        "digg_count":   _fmt_number(stats.get("diggCount",      0)),

        # Raws para comparación
        "_followers_raw": stats.get("followerCount",  0),
        "_source":         src,
    })

    # Engagement rate estimado (likes totales / seguidores)
    try:
        f = int(stats.get("followerCount", 0) or 0)
        h = int(stats.get("heartCount",    0) or 0)
        v = int(stats.get("videoCount",    0) or 1)
        if f > 0 and v > 0:
            avg_likes_per_video = h / v if v else 0
            engagement = (avg_likes_per_video / f) * 100
            result["engagement_est"] = f"{engagement:.2f}%"
    except Exception:
        pass

    # Info de comercio si existe
    commerce = user.get("commerceUserInfo") or user.get("commerce", {})
    if commerce:
        result["commerce"] = {
            "ad_authorized":   bool(commerce.get("adAuthorized", False)),
            "live_authorized": bool(commerce.get("livePermission", False)),
        }

    # Links externos que TikTok a veces expone en el bio
    bio_links = user.get("bioLink", {})
    if bio_links and bio_links.get("link"):
        result["bio_link"] = bio_links["link"]

    return result
