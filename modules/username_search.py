# -*- coding: utf-8 -*-
"""
Username Search — verificación de presencia de un username en 50+ plataformas.

Mejoras v6.2 (anti-falsos-positivos):
  - Detección por sitio con método explícito en vez del genérico "200 = existe":
      • "status"  → existe si HTTP 200 y no aparece huella de "no existe";
                    no existe si 404.
      • "text"    → sitios que SIEMPRE responden 200; se decide por la
                    presencia/ausencia de una huella de "no existe".
      • "json"    → endpoints JSON fiables (GitHub, Reddit, GitLab) → 200/404.
      • "wall"    → sitios con muro de login (Instagram, Facebook, TikTok,
                    LinkedIn...) que responden 200 SIEMPRE: NO se pueden
                    verificar por HTTP, así que NO se reportan como encontrados
                    (evita el falso positivo). Para esos están los módulos
                    dedicados (IG OSINT, FB OSINT, TikTok OSINT).
  - Sesión HTTP reutilizada, timeouts cortos y concurrencia controlada.
  - Resultado de alta confianza: si aparece en la lista, es porque se confirmó.
"""

import requests
import concurrent.futures
import re
from config import logger, BOT_TOKEN

# ── Catálogo de plataformas con método de detección ──────────────────────────
# method:
#   "status" → 200 = existe (validado con huella de "no existe")
#   "text"   → siempre 200; existe si NO aparece huella de "no existe"
#   "json"   → endpoint JSON; 200 = existe, 404 = no
#   "wall"   → no verificable por HTTP (muro de login) → no se reporta
SITES = {
    # ── Redes sociales (muro de login → no verificable por HTTP) ──────────────
    "Instagram":  {"url": "https://instagram.com/{}",            "method": "wall"},
    "Facebook":   {"url": "https://facebook.com/{}",             "method": "wall"},
    "TikTok":     {"url": "https://tiktok.com/@{}",              "method": "wall"},
    "LinkedIn":   {"url": "https://linkedin.com/in/{}",          "method": "wall"},
    "Snapchat":   {"url": "https://www.snapchat.com/add/{}",     "method": "wall"},
    "Threads":    {"url": "https://www.threads.net/@{}",         "method": "wall"},
    "Twitter/X":  {"url": "https://x.com/{}",                    "method": "wall"},
    "Clubhouse":  {"url": "https://www.clubhouse.com/@{}",       "method": "wall"},

    # ── Verificables por status / json ────────────────────────────────────────
    "Reddit":     {"url": "https://www.reddit.com/user/{}/about.json", "method": "json",
                   "display": "https://reddit.com/user/{}"},
    "GitHub":     {"url": "https://api.github.com/users/{}",     "method": "json",
                   "display": "https://github.com/{}"},
    "GitLab":     {"url": "https://gitlab.com/api/v4/users?username={}", "method": "json_list",
                   "display": "https://gitlab.com/{}"},
    "Pinterest":  {"url": "https://www.pinterest.com/{}/",       "method": "status"},
    "Tumblr":     {"url": "https://{}.tumblr.com",               "method": "status"},

    # Desarrollo
    "Dev.to":     {"url": "https://dev.to/{}",                   "method": "status"},
    "Codepen":    {"url": "https://codepen.io/{}",               "method": "status"},
    "Replit":     {"url": "https://replit.com/@{}",              "method": "status"},
    "HackerRank": {"url": "https://www.hackerrank.com/{}",       "method": "status"},
    "LeetCode":   {"url": "https://leetcode.com/{}",             "method": "status"},
    "Kaggle":     {"url": "https://www.kaggle.com/{}",           "method": "status"},
    "npm":        {"url": "https://www.npmjs.com/~{}",           "method": "status"},
    "PyPI":       {"url": "https://pypi.org/user/{}",            "method": "status"},
    "Docker Hub": {"url": "https://hub.docker.com/u/{}",         "method": "status"},
    "Bitbucket":  {"url": "https://bitbucket.org/{}/",           "method": "status"},

    # Gaming
    "Steam":      {"url": "https://steamcommunity.com/id/{}",    "method": "text",
                   "absent": ["the specified profile could not be found"]},
    "Twitch":     {"url": "https://twitch.tv/{}",                "method": "status"},
    "Chess.com":  {"url": "https://www.chess.com/member/{}",     "method": "status"},
    "Lichess":    {"url": "https://lichess.org/@/{}",            "method": "status"},

    # Multimedia
    "Spotify":    {"url": "https://open.spotify.com/user/{}",    "method": "status"},
    "SoundCloud": {"url": "https://soundcloud.com/{}",           "method": "status"},
    "Vimeo":      {"url": "https://vimeo.com/{}",                "method": "status"},
    "Flickr":     {"url": "https://www.flickr.com/people/{}",    "method": "status"},
    "Dailymotion":{"url": "https://www.dailymotion.com/{}",      "method": "status"},
    "Bandcamp":   {"url": "https://{}.bandcamp.com",             "method": "status"},
    "Last.fm":    {"url": "https://www.last.fm/user/{}",         "method": "status"},

    # Blogs y contenido
    "Medium":     {"url": "https://medium.com/@{}",              "method": "status"},
    "WordPress":  {"url": "https://{}.wordpress.com",            "method": "status"},
    "Blogger":    {"url": "https://{}.blogspot.com",             "method": "status"},
    "Substack":   {"url": "https://{}.substack.com",             "method": "status"},

    # Profesional
    "About.me":   {"url": "https://about.me/{}",                 "method": "status"},
    "Quora":      {"url": "https://quora.com/profile/{}",        "method": "status"},
    "Gravatar":   {"url": "https://en.gravatar.com/{}.json",     "method": "json",
                   "display": "https://en.gravatar.com/{}"},
    "Keybase":    {"url": "https://keybase.io/_/api/1.0/user/lookup.json?username={}",
                   "method": "keybase", "display": "https://keybase.io/{}"},
    "Patreon":    {"url": "https://www.patreon.com/{}",          "method": "status"},
    "BuyMeACoffee":{"url": "https://www.buymeacoffee.com/{}",    "method": "status"},
    "Ko-fi":      {"url": "https://ko-fi.com/{}",                "method": "status"},

    # Foros y comunidades
    "HackerNews": {"url": "https://hacker-news.firebaseio.com/v0/user/{}.json",
                   "method": "hackernews", "display": "https://news.ycombinator.com/user?id={}"},
    "ProductHunt":{"url": "https://www.producthunt.com/@{}",     "method": "status"},
    "Dribbble":   {"url": "https://dribbble.com/{}",             "method": "status"},
    "Behance":    {"url": "https://www.behance.net/{}",          "method": "status"},
    "500px":      {"url": "https://500px.com/p/{}",              "method": "status"},

    # Otros
    "Linktree":   {"url": "https://linktr.ee/{}",               "method": "status"},
    "Telegram":   {"url": "https://t.me/{}",                     "method": "wall"},
    "Mastodon":   {"url": "https://mastodon.social/@{}",         "method": "status"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

# Huellas genéricas de "no existe" (para method=status / text)
_NOT_FOUND = [
    "not found", "page doesn't exist", "doesn't exist", "no results",
    "user not found", "profile not found", "is available",
    "this page is not available", "account not found", "user doesn't exist",
    "this account doesn't exist", "nothing here", "page not found",
    "sorry, this page", "hmm...this page", "the page you were looking for",
    "we couldn't find", "this user has not", "no user found",
    "404", "couldn't find this account",
]


def get_telegram_info(username):
    """Obtiene información pública de un usuario/canal/bot de Telegram."""
    result = {
        "exists": False, "type": None, "name": None, "bio": None,
        "username": username, "id": None, "photo": None, "members": None,
        "is_verified": False, "is_bot": False, "is_scam": False,
        "is_fake": False, "url": f"https://t.me/{username}",
    }

    def _scrape_tme():
        try:
            r3 = requests.get(
                f"https://t.me/{username}", timeout=10,
                headers={"User-Agent": HEADERS["User-Agent"], "Accept": HEADERS["Accept"]},
                allow_redirects=True,
            )
            if r3.status_code != 200:
                return
            html = r3.text or ""
            html_low = html.lower()
            if "tgme_page_error" in html_low or "this page is not found" in html_low:
                return
            if 'tgme_page_title' not in html and 'og:title' not in html:
                return
            result["exists"] = True
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
            members_match = re.search(r'(\d[\d\s]*)\s*(?:members|subscribers|suscriptores|miembros)', html, re.IGNORECASE)
            if title_match:
                result["name"] = title_match.group(1)
            if desc_match:
                result["bio"] = desc_match.group(1)
            if members_match:
                result["members"] = members_match.group(1).replace(" ", "")
            result["type"] = "Canal/Grupo" if "tgme_page_extra" in html else "Usuario/Bot"
        except Exception as e:
            logger.debug(f"Telegram scrape error: {e}")

    if BOT_TOKEN and len(BOT_TOKEN) >= 20 and "tu_token" not in BOT_TOKEN:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
                params={"chat_id": f"@{username}"}, timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") and data.get("result"):
                    chat = data["result"]
                    result["exists"] = True
                    result["id"] = chat.get("id")
                    result["name"] = chat.get("first_name") or chat.get("title")
                    result["bio"] = chat.get("bio") or chat.get("description")
                    result["is_verified"] = chat.get("is_verified", False)
                    result["is_bot"] = chat.get("type") == "private" and chat.get("is_bot", False)
                    result["is_scam"] = chat.get("is_scam", False)
                    result["is_fake"] = chat.get("is_fake", False)
                    chat_type = chat.get("type", "")
                    if chat_type == "private":
                        result["type"] = "Usuario" if not result["is_bot"] else "Bot"
                    elif chat_type in ["group", "supergroup"]:
                        result["type"] = "Grupo"
                    elif chat_type == "channel":
                        result["type"] = "Canal"
        except Exception as e:
            logger.debug(f"Telegram getChat error: {e}")

    if result["exists"] and result["type"] in ["Grupo", "Canal"]:
        try:
            r2 = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount",
                params={"chat_id": f"@{username}"}, timeout=8,
            )
            if r2.status_code == 200:
                data2 = r2.json()
                if data2.get("ok"):
                    result["members"] = data2.get("result")
        except Exception as e:
            logger.debug(f"Telegram getMemberCount error: {e}")

    if not result["exists"]:
        _scrape_tme()

    return result


def _display_url(cfg, username):
    """URL legible para mostrar (no la del endpoint API)."""
    tpl = cfg.get("display") or cfg["url"]
    return tpl.format(username)


def check_site(site, cfg, username, session):
    """Verifica si un username existe en un sitio. Devuelve (site, url) o None."""
    method = cfg["method"]
    if method == "wall":
        return None  # no verificable por HTTP → no se reporta (evita falso positivo)

    url = cfg["url"].format(username)
    disp = _display_url(cfg, username)
    try:
        # JSON de listado (GitLab): existe si la lista no está vacía
        if method == "json_list":
            r = session.get(url, timeout=8)
            if r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0:
                return (site, disp)
            return None

        if method == "json":
            r = session.get(url, timeout=8)
            return (site, disp) if r.status_code == 200 else None

        if method == "hackernews":
            r = session.get(url, timeout=8)
            # Firebase devuelve "null" (texto) si no existe
            if r.status_code == 200 and r.text.strip().lower() not in ("null", ""):
                return (site, disp)
            return None

        if method == "keybase":
            r = session.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data.get("status", {}).get("code") == 0 and data.get("them"):
                    return (site, disp)
            return None

        # method == "status" o "text"
        r = session.get(url, timeout=7, allow_redirects=True)
        text_lower = (r.text or "").lower()

        if method == "status" and r.status_code == 404:
            return None

        # Huellas específicas de "no existe" para este sitio
        for marker in cfg.get("absent", []):
            if marker.lower() in text_lower:
                return None

        if r.status_code == 200:
            # Huellas genéricas
            for pattern in _NOT_FOUND:
                if pattern in text_lower:
                    return None
            # Página muy corta con error
            if len(r.text or "") < 500 and ("error" in text_lower or "404" in text_lower):
                return None
            # Redirección a home (cuenta inexistente que redirige)
            base = cfg["url"].split("/{")[0].split("{")[0].rstrip("/.")
            if r.url and r.url.rstrip("/") == base.rstrip("/"):
                return None
            return (site, disp)

        return None

    except requests.exceptions.Timeout:
        logger.debug(f"Timeout verificando {site}")
    except requests.exceptions.ConnectionError:
        logger.debug(f"Connection error en {site}")
    except Exception as e:
        logger.debug(f"Error verificando {site}: {e}")
    return None


def search_username(username):
    """Busca username en plataformas verificables + Telegram lookup."""
    if not username or len(username) < 2:
        return [], None

    username = username.strip().replace('@', '')
    found = []

    telegram_data = get_telegram_info(username)

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = {
                executor.submit(check_site, site, cfg, username, session): site
                for site, cfg in SITES.items()
            }
            for future in concurrent.futures.as_completed(futures, timeout=25):
                try:
                    result = future.result()
                    if result:
                        found.append(result)
                except Exception as e:
                    site = futures[future]
                    logger.debug(f"Error en futuro {site}: {e}")
    except Exception as e:
        logger.error(f"Error en búsqueda de username: {e}")
    finally:
        session.close()

    found.sort(key=lambda x: x[0])
    return found, telegram_data
