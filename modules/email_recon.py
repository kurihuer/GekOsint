# -*- coding: utf-8 -*-
"""
Email Multi-Platform Recon — chequea un email contra ~12 servicios populares
en paralelo, reportando dónde está registrado y extrayendo hints parciales
de teléfono/email cuando el servicio los filtra (técnica Holehe de megadose).

Diseñado para complementar IG/Gmail OSINT: muchos servicios tienen flows
de signup/recovery que devuelven respuestas distintas según si el email
existe o no, sin requerir auth.

Anti-ban: rate limiter dedicado (suave, porque estos endpoints son de
signup público y no son agresivos contra cloud IPs).
"""

import asyncio
import logging
import re
import time
import urllib.parse
from collections import defaultdict, deque
from typing import Optional

import httpx

logger = logging.getLogger("GekOsint.EmailRecon")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

SERVICE_META = {
    "X (Twitter)": {"category": "Red social", "signal": "medium"},
    "Microsoft": {"category": "Identidad", "signal": "high"},
    "Apple ID": {"category": "Identidad", "signal": "high"},
    "Spotify": {"category": "Consumo", "signal": "medium"},
    "Adobe": {"category": "Identidad", "signal": "high"},
    "Pinterest": {"category": "Red social", "signal": "medium"},
    "LastPass": {"category": "Seguridad", "signal": "high"},
    "GitHub": {"category": "Desarrollo", "signal": "high"},
    "Duolingo": {"category": "Consumo", "signal": "medium"},
    "Imgur": {"category": "Contenido", "signal": "medium"},
    "Strava": {"category": "Consumo", "signal": "medium"},
    "Proton Mail": {"category": "Identidad", "signal": "high"},
}

# ── Rate limiter (suave) ─────────────────────────────────────────────────────
PER_USER_COOLDOWN   = 30
PER_USER_HOURLY_MAX = 30
GLOBAL_HOURLY_MAX   = 200
INTER_REQUEST_WAIT  = 0.5

_user_history: dict[int, deque] = defaultdict(deque)
_global_history: deque = deque()


def check_email_recon_rate_limit(user_id: int) -> tuple[bool, str]:
    now = time.monotonic()
    user_hist = _user_history[user_id]
    while user_hist and now - user_hist[0] > 3600:
        user_hist.popleft()

    if user_hist and now - user_hist[-1] < PER_USER_COOLDOWN:
        wait = int(PER_USER_COOLDOWN - (now - user_hist[-1]))
        return False, f"Esperá {wait}s entre consultas Email Recon."

    if len(user_hist) >= PER_USER_HOURLY_MAX:
        return False, f"Alcanzaste {PER_USER_HOURLY_MAX} consultas/hora."

    while _global_history and now - _global_history[0] > 3600:
        _global_history.popleft()

    if len(_global_history) >= GLOBAL_HOURLY_MAX:
        return False, "Límite global alcanzado, esperá unos minutos."

    user_hist.append(now)
    _global_history.append(now)
    return True, ""


# ── HTTP helpers ──────────────────────────────────────────────────────────────

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _build_email_pivots(email: str) -> list[dict]:
    local, domain = email.split("@", 1)
    exact_email = urllib.parse.quote_plus(f'"{email}"')
    local_q = urllib.parse.quote_plus(f'"{local}"')
    domain_q = urllib.parse.quote_plus(domain)
    return [
        {
            "label": "Google exacto",
            "url": f"https://www.google.com/search?q={exact_email}",
            "description": "Busca el correo exacto en resultados indexados.",
        },
        {
            "label": "Google local-part",
            "url": f"https://www.google.com/search?q={local_q}+{domain_q}",
            "description": "Cruza alias y dominio para pivotes manuales.",
        },
        {
            "label": "GitHub por email",
            "url": f"https://github.com/search?q={urllib.parse.quote_plus(email)}&type=users",
            "description": "Verifica si el email aparece expuesto en GitHub.",
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  CHECKERS — uno por servicio. Todos devuelven:
#    {"service": str, "found": bool, "hint": Optional[str], "error": Optional[str]}
# ─────────────────────────────────────────────────────────────────────────────

async def _check_twitter(client: httpx.AsyncClient, email: str) -> dict:
    """X/Twitter — endpoint público de email_available."""
    out = {"service": "X (Twitter)", "found": False, "hint": None, "error": None}
    try:
        r = await client.get(
            "https://api.x.com/i/users/email_available.json",
            params={"email": email, "suggest_similar": "false"},
            headers={"User-Agent": UA},
        )
        if r.status_code == 200:
            data = r.json()
            # taken=True significa que el email YA está registrado
            if data.get("taken") is True or data.get("valid") is False:
                out["found"] = True
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_microsoft(client: httpx.AsyncClient, email: str) -> dict:
    """Microsoft Live (Hotmail/Outlook/Live)."""
    out = {"service": "Microsoft", "found": False, "hint": None, "error": None}
    try:
        r = await client.post(
            "https://login.live.com/getCredentialType.srf",
            json={
                "username":         email,
                "uaid":             "00000000000000000000000000000000",
                "isOtherIdpSupported":         False,
                "checkPhones":                False,
                "isRemoteNGCSupported":        True,
                "isCookieBannerShown":         False,
                "isFidoSupported":             False,
            },
            headers={
                "User-Agent":   UA,
                "Content-Type": "application/json",
                "hpgid":        "GIF_LOGON_PAGE",
                "client-request-id": "00000000-0000-0000-0000-000000000000",
            },
        )
        if r.status_code == 200:
            data = r.json()
            # IfExistsResult: 0 = existe, 1 = no existe, 5/6 = error
            result = data.get("IfExistsResult")
            if result == 0:
                out["found"] = True
                # A veces incluye flowToken con info adicional (sin hint útil)
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_apple(client: httpx.AsyncClient, email: str) -> dict:
    """Apple ID — endpoint de iforgot."""
    out = {"service": "Apple ID", "found": False, "hint": None, "error": None}
    try:
        r = await client.post(
            "https://iforgot.apple.com/password/verify/appleid",
            json={"id": email},
            headers={
                "User-Agent":   UA,
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Origin":  "https://iforgot.apple.com",
                "Referer": "https://iforgot.apple.com/password/verify/appleid",
            },
        )
        # Apple responde 200 con JSON {validation: {isValidAppleID: ...}}
        if r.status_code == 200:
            try:
                data = r.json()
                vmsg = (data or {}).get("validationErrors") or []
                if not vmsg:
                    out["found"] = True
            except Exception:
                pass
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_spotify(client: httpx.AsyncClient, email: str) -> dict:
    """Spotify signup endpoint."""
    out = {"service": "Spotify", "found": False, "hint": None, "error": None}
    try:
        r = await client.get(
            "https://spclient.wg.spotify.com/signup/public/v1/account",
            params={"validate": "1", "email": email},
            headers={"User-Agent": UA},
        )
        if r.status_code == 200:
            data = r.json()
            # status=1: válido y disponible. 20: ya registrado.
            if data.get("status") == 20:
                out["found"] = True
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_adobe(client: httpx.AsyncClient, email: str) -> dict:
    """Adobe — checa existencia vía endpoint de auth."""
    out = {"service": "Adobe", "found": False, "hint": None, "error": None}
    try:
        r = await client.post(
            "https://auth.services.adobe.com/signin/v2/users",
            json={"username": email},
            headers={
                "User-Agent":   UA,
                "Content-Type": "application/json",
                "X-IMS-ClientId": "adobedotcom2",
            },
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("isExistingUser") is True:
                out["found"] = True
            return out
        if r.status_code == 404:
            return out  # no existe
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_pinterest(client: httpx.AsyncClient, email: str) -> dict:
    """Pinterest signup."""
    out = {"service": "Pinterest", "found": False, "hint": None, "error": None}
    try:
        r = await client.post(
            "https://www.pinterest.com/_ngjs/resource/EmailExistsResource/get/",
            data={
                "source_url": "/",
                "data": '{"options":{"email":"' + email + '"},"context":{}}',
            },
            headers={
                "User-Agent":      UA,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if r.status_code == 200:
            data = r.json()
            if (data.get("resource_response") or {}).get("data") is True:
                out["found"] = True
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_lastpass(client: httpx.AsyncClient, email: str) -> dict:
    """LastPass — endpoint de iterations expone si la cuenta existe."""
    out = {"service": "LastPass", "found": False, "hint": None, "error": None}
    try:
        r = await client.get(
            "https://lastpass.com/iterations.php",
            params={"email": email},
            headers={"User-Agent": UA},
        )
        if r.status_code == 200:
            txt = (r.text or "").strip()
            # Responde con un número de iterations si existe; "0" o vacío si no
            if txt.isdigit() and int(txt) > 1:
                out["found"] = True
                out["hint"] = f"PBKDF2 iterations: {txt}"
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_github(client: httpx.AsyncClient, email: str) -> dict:
    """GitHub — search por email (público, requiere user con email visible)."""
    out = {"service": "GitHub", "found": False, "hint": None, "error": None}
    try:
        r = await client.get(
            "https://api.github.com/search/users",
            params={"q": f"{email} in:email"},
            headers={"User-Agent": UA, "Accept": "application/vnd.github+json"},
        )
        if r.status_code == 200:
            data = r.json()
            items = data.get("items") or []
            if items:
                out["found"] = True
                out["hint"] = f"@{items[0].get('login', '?')}"
            return out
        if r.status_code == 403:
            out["error"] = "Rate limit (configurá GITHUB_TOKEN)"
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_duolingo(client: httpx.AsyncClient, email: str) -> dict:
    """Duolingo — endpoint público de validación."""
    out = {"service": "Duolingo", "found": False, "hint": None, "error": None}
    try:
        r = await client.get(
            "https://www.duolingo.com/2017-06-30/users",
            params={"email": email},
            headers={"User-Agent": UA},
        )
        if r.status_code == 200:
            data = r.json()
            users = data.get("users") or []
            if users:
                out["found"] = True
                handle = users[0].get("username")
                if handle:
                    out["hint"] = f"@{handle}"
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_imgur(client: httpx.AsyncClient, email: str) -> dict:
    """Imgur — endpoint de validación de email."""
    out = {"service": "Imgur", "found": False, "hint": None, "error": None}
    try:
        r = await client.post(
            "https://api.imgur.com/account/v1/emails/verify",
            json={"email": email},
            headers={
                "User-Agent":     UA,
                "Content-Type":   "application/json",
                "Authorization":  "Client-ID 546c25a59c58ad7",
            },
        )
        if r.status_code == 200:
            return out  # email disponible (no registrado)
        if r.status_code == 409:
            out["found"] = True
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_strava(client: httpx.AsyncClient, email: str) -> dict:
    """Strava — endpoint de signup."""
    out = {"service": "Strava", "found": False, "hint": None, "error": None}
    try:
        r = await client.post(
            "https://www.strava.com/frontend/users/email_unique",
            data={"email": email},
            headers={"User-Agent": UA},
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("unique") is False:
                out["found"] = True
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_protonmail(client: httpx.AsyncClient, email: str) -> dict:
    """Proton Mail — solo aplica si el dominio es proton.me / protonmail.com."""
    out = {"service": "Proton Mail", "found": False, "hint": None, "error": None}
    domain = email.split("@", 1)[-1].lower()
    if domain not in ("protonmail.com", "proton.me", "pm.me"):
        out["error"] = "no-aplica"
        return out
    try:
        r = await client.get(
            f"https://api.protonmail.ch/users/available",
            params={"Name": email.split("@", 1)[0]},
            headers={"User-Agent": UA},
        )
        if r.status_code == 200:
            data = r.json()
            # Code 12106 → ya está tomado
            if data.get("Code") == 12106:
                out["found"] = True
            return out
        out["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["error"] = str(e)
    return out


# ── Orquestador ─────────────────────────────────────────────────────────────

CHECKERS = [
    _check_twitter,
    _check_microsoft,
    _check_apple,
    _check_spotify,
    _check_adobe,
    _check_pinterest,
    _check_lastpass,
    _check_github,
    _check_duolingo,
    _check_imgur,
    _check_strava,
    _check_protonmail,
]


async def email_recon(email: str) -> dict:
    """
    Chequea el email contra ~12 servicios en paralelo.
    El rate limit por usuario debe chequearse ANTES con
    `check_email_recon_rate_limit(user_id)`.
    """
    out = {
        "input":    email,
        "valid":    False,
        "found_in": [],
        "checked":  [],
        "errors":   [],
        "hints":    [],
        "local_part": "",
        "domain": "",
        "summary": {},
        "pivots": [],
    }

    email = (email or "").strip().lower()
    if not email or not EMAIL_RE.match(email):
        out["errors"].append(f"Email inválido: {email!r}")
        return out
    out["valid"] = True
    out["local_part"], out["domain"] = email.split("@", 1)
    out["pivots"] = _build_email_pivots(email)

    async with httpx.AsyncClient(
        timeout=12.0, follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *[checker(client, email) for checker in CHECKERS],
            return_exceptions=True,
        )

    for r in results:
        if isinstance(r, Exception):
            out["errors"].append(f"Excepción: {r}")
            continue
        out["checked"].append(r["service"])
        if r.get("found"):
            meta = SERVICE_META.get(r["service"], {})
            entry = {
                "service": r["service"],
                "category": meta.get("category", "Otro"),
                "signal": meta.get("signal", "medium"),
            }
            if r.get("hint"):
                entry["hint"] = r["hint"]
                out["hints"].append(f"{r['service']}: {r['hint']}")
            out["found_in"].append(entry)
        elif r.get("error") and r["error"] not in ("no-aplica",):
            # Solo agregamos errores reales (no los "no aplica")
            logger.debug(f"{r['service']}: {r['error']}")

    signal_rank = {"high": 0, "medium": 1, "low": 2}
    out["found_in"].sort(
        key=lambda item: (
            signal_rank.get(str(item.get("signal", "medium")).lower(), 9),
            str(item.get("category", "")),
            str(item.get("service", "")),
        )
    )
    out["summary"] = {
        "checked_total": len(out["checked"]),
        "found_total": len(out["found_in"]),
        "high_signal_total": sum(1 for item in out["found_in"] if item.get("signal") == "high"),
        "categories": sorted({item.get("category", "Otro") for item in out["found_in"]}),
    }

    return out
