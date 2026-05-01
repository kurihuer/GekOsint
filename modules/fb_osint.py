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

    minimal_headers = {
        "User-Agent":      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Recovery usa solo datr (cookie de navegador, no de sesión).
    # Con c_user+xs activos FB manda checkpoint por "otra cuenta".
    _anon_cookies = {k: v for k, v in _fb_cookies().items() if k == "datr" and v}
    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    if PROXY_URL:
        # Mostrar solo host:port del proxy en logs (sin user:pass) para diagnóstico
        try:
            from urllib.parse import urlparse
            _pu = urlparse(PROXY_URL)
            logger.info(f"FB recovery: usando proxy {_pu.scheme}://{_pu.hostname}:{_pu.port}")
        except Exception:
            logger.info("FB recovery: proxy configurado")
    else:
        logger.info("FB recovery: SIN proxy (alta probabilidad de 400 desde cloud IP)")

    # Probar mbasic primero, luego m., luego www. (residencial)
    base_urls = [
        "https://mbasic.facebook.com/login/identify/",
        "https://m.facebook.com/login/identify/",
        "https://www.facebook.com/login/identify/",
    ]

    try:
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True,
            cookies=_anon_cookies,
            **_proxy,
        ) as client:
            html = None
            base_url = None

            # ── Prefetch CSRF desde mbasic login.php ─────────────────────────
            # La identify page es JS-rendered en 2026; login.php aún tiene HTML.
            mbasic_lsd = None
            mbasic_jazoest = None
            try:
                r_pre = await client.get(
                    "https://mbasic.facebook.com/login.php",
                    headers=minimal_headers,
                )
                if r_pre.status_code == 200:
                    lm = re.search(r'name="lsd"\s+value="([^"]+)"',     r_pre.text)
                    jm = re.search(r'name="jazoest"\s+value="([^"]+)"', r_pre.text)
                    mbasic_lsd     = lm.group(1) if lm else None
                    mbasic_jazoest = jm.group(1) if jm else None
                    logger.debug(
                        f"FB mbasic login.php CSRF prefetch: "
                        f"lsd={bool(mbasic_lsd)} jazoest={bool(mbasic_jazoest)}"
                    )
            except Exception as e:
                logger.debug(f"FB mbasic login.php prefetch error: {e}")
            await asyncio.sleep(0.8)

            for url in base_urls:
                domain = url.split("/")[2]
                # Tokens prefetched son válidos solo para el mismo subdominio
                prefetch_lsd     = mbasic_lsd     if domain == "mbasic.facebook.com" else None
                prefetch_jazoest = mbasic_jazoest if domain == "mbasic.facebook.com" else None

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

                logger.debug(f"FB GET {url} → HTTP {r1.status_code} final_url={r1.url}")
                if r1.status_code != 200:
                    continue

                # Pausa "humana" entre el GET y el POST
                await asyncio.sleep(1.5)

                # Extraer tokens CSRF del identify page (o desde JS embebido)
                lsd_m     = (
                    re.search(r'name="lsd"\s+value="([^"]+)"',     r1.text) or
                    re.search(r'"LSD"[^}]*?"token":"([^"]+)"',     r1.text) or
                    re.search(r'\["LSD","([^"]+)"\]',              r1.text)
                )
                jazoest_m = re.search(r'name="jazoest"\s+value="([^"]+)"', r1.text)
                fb_dtsg_m = re.search(r'name="fb_dtsg"\s+value="([^"]+)"', r1.text)

                # Fallback: usar tokens del prefetch si la identify page es JS-rendered
                lsd_val     = (lsd_m.group(1)     if lsd_m     else None) or prefetch_lsd
                jazoest_val = (jazoest_m.group(1) if jazoest_m else None) or prefetch_jazoest

                logger.debug(
                    f"FB CSRF — identify page: lsd={bool(lsd_m)} jazoest={bool(jazoest_m)} | "
                    f"prefetch: lsd={bool(prefetch_lsd)} | final lsd={bool(lsd_val)}"
                )

                if not lsd_val:
                    logger.debug(f"FB: sin CSRF tokens para {domain}, probando siguiente URL")
                    continue

                data = {"email": query}
                data["lsd"] = lsd_val
                if jazoest_val: data["jazoest"] = jazoest_val
                if fb_dtsg_m:   data["fb_dtsg"] = fb_dtsg_m.group(1)

                # 2) POST al mismo dominio
                origin = "https://" + domain
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

                logger.debug(f"FB POST {url} → HTTP {r2.status_code} final_url={r2.url}")

                if r2.status_code in (401, 429):
                    out["error"] = f"FB rate limit ({r2.status_code})"
                    trigger_fb_pause(f"identify {r2.status_code}")
                    return out

                if r2.status_code == 400:
                    continue

                if r2.status_code == 200:
                    html = r2.text or ""
                    base_url = url
                    break

                logger.debug(f"FB POST {url} → HTTP {r2.status_code}")

            if not html:
                out["error"] = (
                    "FB recovery bloqueado. Posibles causas: IP bloqueada, "
                    "no se obtuvieron tokens CSRF, o cuenta no encontrada. "
                    "Intentá desde IP residencial o configurá PROXY_URL."
                )
                return out

            # Si la página redirigió al paso "How do you want to login?",
            # significa que la cuenta existe → extraer datos
            html_lower = html.lower()

            # Keywords paso 1: "¿es tu cuenta?" Y paso 2: opciones de recovery
            step1_indicators = [
                # Inglés — paso 1 (account found, confirm)
                "is this your account", "this is my account",
                "we found your account", "find your account",
                "identify your account", "is this you",
                # Español — paso 1
                "¿esta es tu cuenta", "esta es mi cuenta",
                "encontramos tu cuenta", "identificar tu cuenta",
                # Portugués — paso 1
                "encontramos sua conta", "essa é sua conta",
            ]
            step2_indicators = [
                # Inglés — paso 2 (recovery options con hints)
                "recover your account", "how do you want to login",
                "send_code", "confirm your identity", "confirmation code",
                "reset your password", "send_confirmation",
                # Español — paso 2
                "recuperar tu cuenta", "recuperar cuenta",
                "código de confirmación", "cómo quieres",
                "restablecer tu contraseña",
                # Portugués — paso 2
                "recuperar sua conta",
                # Estructurales
                "checkpoint", "recover_account", "confirmation_code",
                '"recovery"', "send_to",
            ]
            all_indicators = step1_indicators + step2_indicators

            # Caracteres de ofuscación que FB usa en distintas versiones del HTML.
            # En 2026 vimos: *, •, ·, ×, x (ASCII), _, −, –, U+2022, espacios entre dígitos.
            OBFUSC_CHARS = ('*', '•', '·', '×', '_', '−', '–', '─')
            # Char-class regex con todos los chars de ofuscación + dígitos/letras
            OBFUSC_CC = r"\*•·×_−–─x"

            def _extract_email(src):
                """
                Busca emails ofuscados. Soporta ofuscación con cualquier char
                de OBFUSC_CHARS. Devuelve (match, source_pattern) para diag.
                Solo cuenta como hint si tiene AL MENOS 1 char de ofuscación,
                porque sino estaríamos devolviendo emails reales del HTML
                (UA strings, footers, etc.).
                """
                candidates = []
                for tag, pat in [
                    ("between_tags",  rf'>([a-zA-Z0-9][\w.{OBFUSC_CC}]*@[\w.{OBFUSC_CC}]+\.[a-z]{{2,}})<'),
                    ("in_quotes",     rf'"([a-zA-Z0-9][\w.{OBFUSC_CC}]*@[\w.{OBFUSC_CC}]+\.[a-z]{{2,}})"'),
                    ("in_json_value", rf':\s*"([a-zA-Z0-9][\w.{OBFUSC_CC}]*@[\w.{OBFUSC_CC}]+\.[a-z]{{2,}})"'),
                ]:
                    for m in re.finditer(pat, src):
                        val = m.group(1)
                        candidates.append((tag, val))
                        if any(c in val for c in OBFUSC_CHARS):
                            logger.debug(f"FB recovery email match ({tag}): {val!r}")
                            return m
                if candidates:
                    logger.info(
                        f"FB recovery extract_email: {len(candidates)} emails "
                        f"candidatos SIN ofuscación, descartados. Primero: "
                        f"{candidates[0][1]!r}"
                    )
                else:
                    logger.info("FB recovery extract_email: 0 candidatos")
                return None

            def _extract_phone(src):
                candidates = []
                for tag, pat in [
                    ("between_tags",  rf'>(\+?[0-9\s{OBFUSC_CC}]{{4,25}})<'),
                    ("in_quotes",     rf'"(\+?[0-9][0-9\s{OBFUSC_CC}]{{4,23}})"'),
                    ("in_json_value", rf':\s*"(\+?[0-9][0-9\s{OBFUSC_CC}]{{4,23}})"'),
                ]:
                    for m in re.finditer(pat, src):
                        val = m.group(1).strip()
                        # Filtrar valores muy cortos o que parezcan timestamps
                        if len(val) < 4:
                            continue
                        candidates.append((tag, val))
                        if any(c in val for c in OBFUSC_CHARS):
                            logger.debug(f"FB recovery phone match ({tag}): {val!r}")
                            return m
                if candidates:
                    logger.info(
                        f"FB recovery extract_phone: {len(candidates)} phones "
                        f"candidatos SIN ofuscación, descartados. Primero: "
                        f"{candidates[0][1]!r}"
                    )
                else:
                    logger.info("FB recovery extract_phone: 0 candidatos")
                return None

            # Resumen del HTML antes de extraer
            logger.info(
                f"FB recovery HTML paso1: len={len(html)} "
                f"has_at={'@' in html} has_obfusc={any(c in html for c in '*•·×')} "
                f"url={r2.url!r}"
            )

            em_m = _extract_email(html)
            ph_m = _extract_phone(html)

            page_found = (
                any(kw in html_lower for kw in all_indicators)
                or "recover_account" in r2.url.path
                or em_m is not None
                or ph_m is not None
            )

            if page_found:
                out["found"] = True

                # Display name
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

                # Log para debug — ver qué devuelve FB
                logger.debug(f"FB recovery HTML paso1 (1500c): {html[:1500]}")

                # User ID — FB a veces HTML-encodea los corchetes
                uid_m = (
                    re.search(r'name="c\[0\]"[^>]*value="(\d{8,17})"', html) or
                    re.search(r'value="(\d{8,17})"[^>]*name="c\[0\]"', html) or
                    re.search(r'name="c(?:&#x5B;|%5B)0(?:&#x5D;|%5D)"[^>]*value="(\d{8,17})"', html) or
                    re.search(r'"u":"(\d{8,17})"', html) or
                    re.search(r'c\[0\]=(\d{8,17})', html) or
                    re.search(r'profile\.php\?id=(\d{8,17})', html) or
                    re.search(r'/(\d{8,17})/picture', html)
                )
                if uid_m:
                    out["user_id"] = uid_m.group(1)

                # Acción del formulario del paso 2
                form_action_m = re.search(r'<form[^>]+action="([^"]+)"', html)
                step2_url = (
                    form_action_m.group(1).replace("&amp;", "&")
                    if form_action_m else base_url + "?ctx=recover"
                )
                # Si la acción es relativa, completar con dominio base
                if step2_url.startswith("/"):
                    step2_url = "https://" + base_url.split("/")[2] + step2_url

                # Si ya tenemos hints en la primera respuesta, listo
                if em_m:
                    out["obfuscated_email"] = em_m.group(1).strip()
                if ph_m:
                    out["obfuscated_phone"] = ph_m.group(1).strip()

                # Si no hay hints aún, hacer el segundo POST para confirmar la cuenta
                # y llegar a la página de opciones de recovery (donde aparecen los hints)
                if not out["obfuscated_email"] and not out["obfuscated_phone"]:
                    uid_val = out.get("user_id")
                    await asyncio.sleep(1.0)

                    # Tokens CSRF del HTML de paso 1 (o prefetch como fallback)
                    lsd_m2     = re.search(r'name="lsd"\s+value="([^"]+)"',     html)
                    jazoest_m2 = re.search(r'name="jazoest"\s+value="([^"]+)"', html)
                    fb_dtsg_m2 = re.search(r'name="fb_dtsg"\s+value="([^"]+)"', html)
                    lsd_val2     = (lsd_m2.group(1)     if lsd_m2     else None) or lsd_val
                    jazoest_val2 = (jazoest_m2.group(1) if jazoest_m2 else None) or jazoest_val

                    data2 = {"did_submit": "1"}
                    if uid_val:
                        data2["c[0]"] = uid_val
                    if lsd_val2:     data2["lsd"]     = lsd_val2
                    if jazoest_val2: data2["jazoest"] = jazoest_val2
                    if fb_dtsg_m2:   data2["fb_dtsg"] = fb_dtsg_m2.group(1)

                    try:
                        r3 = await client.post(
                            step2_url,
                            data=data2,
                            headers={
                                **minimal_headers,
                                "Content-Type": "application/x-www-form-urlencoded",
                                "Origin":       "https://" + base_url.split("/")[2],
                                "Referer":      base_url + "?ctx=recover",
                            },
                        )
                        logger.debug(f"FB paso2 status: {r3.status_code} url: {r3.url}")
                        if r3.status_code == 200:
                            html2 = r3.text or ""
                            _dbg = os.path.join(
                                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "fb_debug_paso2.html"
                            )
                            with open(_dbg, "w", encoding="utf-8") as _f:
                                _f.write(html2)
                            logger.debug(f"FB paso2 HTML guardado en {_dbg}")
                            em_m2 = _extract_email(html2)
                            ph_m2 = _extract_phone(html2)
                            if em_m2:
                                out["obfuscated_email"] = em_m2.group(1).strip()
                            if ph_m2:
                                out["obfuscated_phone"] = ph_m2.group(1).strip()
                    except Exception as e2:
                        logger.debug(f"FB recovery paso 2 excepción: {e2}")
            else:
                logger.debug(f"FB recovery HTML snippet: {html[:500]}")
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

    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True,
            cookies=_fb_cookies(),
            **_proxy,
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

    # Detectar tipo de input.
    # Orden importa: user_id (puro dígito) ANTES que phone (debe llevar +),
    # para que un FB user ID largo no se confunda con número telefónico.
    if EMAIL_RE.match(query):
        out["input_type"] = "email"
    elif re.match(r"^\d{8,17}$", query):
        # Puro número de 8-17 dígitos sin + → User ID de Facebook
        out["input_type"] = "user_id"
        out["user_id"] = query
    elif re.match(r"^\+\d[\d\s\-]{6,}$", query):
        # Empieza con + → teléfono internacional
        out["input_type"] = "phone"
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
