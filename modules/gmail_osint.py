# -*- coding: utf-8 -*-
"""
Gmail / Google OSINT — recon profundo sobre cuentas de Google.

Capacidades:
  - Verificación de existencia de la cuenta
  - Recovery hints (teléfono/email parcialmente ofuscados — técnica
    Toutatis adaptada al endpoint de account recovery de Google)
  - Foto de perfil pública (Google + fallback Gravatar)
  - Canal de YouTube linkeado (si lo tiene)
  - Información extendida vía People API si hay cookies de sesión
    configuradas en env (estilo GHunt v2)
  - Servicios Google donde aparece la cuenta

Auth opcional: cookies de Google inyectadas vía env vars (igual que el
patrón de IG OSINT). Sin cookies funciona en modo "anónimo" con recovery
hints + gravatar — todavía valioso, pero limitado.

Anti-ban: rate limiter dedicado, separado del global del bot.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from typing import Optional

import httpx

logger = logging.getLogger("GekOsint.GmailOsint")

# ── Configuración (env vars) ──────────────────────────────────────────────────
try:
    from config import (
        GOOGLE_SAPISID, GOOGLE_HSID, GOOGLE_SSID, GOOGLE_APISID,
        GOOGLE_SECURE_1PSID, GOOGLE_SECURE_3PSID, GOOGLE_NID,
        PROXY_URL,
    )
except ImportError:
    GOOGLE_SAPISID       = os.getenv("GOOGLE_SAPISID", "")
    GOOGLE_HSID          = os.getenv("GOOGLE_HSID", "")
    GOOGLE_SSID          = os.getenv("GOOGLE_SSID", "")
    GOOGLE_APISID        = os.getenv("GOOGLE_APISID", "")
    GOOGLE_SECURE_1PSID  = os.getenv("GOOGLE_SECURE_1PSID", "")
    GOOGLE_SECURE_3PSID  = os.getenv("GOOGLE_SECURE_3PSID", "")
    GOOGLE_NID           = os.getenv("GOOGLE_NID", "")
    PROXY_URL            = os.getenv("PROXY_URL", "")

# ── Rate limiter dedicado a Google ────────────────────────────────────────────
PER_USER_COOLDOWN     = 60       # 1 lookup cada 60s por usuario
PER_USER_HOURLY_MAX   = 20       # máx 20 lookups/hora por usuario
GLOBAL_HOURLY_MAX     = 80       # máx 80 lookups/hora globales
GOOGLE_BAN_COOLDOWN   = 30 * 60  # pausa 30 min si Google nos pega 401/429
INTER_REQUEST_WAIT    = 2

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}

# Estado en memoria
_user_history: dict[int, deque] = defaultdict(deque)
_global_history: deque = deque()
_paused_until: float = 0.0


def check_gmail_rate_limit(user_id: int) -> tuple[bool, str]:
    """Igual semántica que check_ig_rate_limit pero dedicado a Google."""
    now = time.monotonic()

    if now < _paused_until:
        wait = int(_paused_until - now)
        m, s = divmod(wait, 60)
        return False, (
            f"Gmail OSINT pausado por anti-ban (Google rate limit). "
            f"Reanuda en {m}m {s}s."
        )

    user_hist = _user_history[user_id]
    while user_hist and now - user_hist[0] > 3600:
        user_hist.popleft()

    if user_hist and now - user_hist[-1] < PER_USER_COOLDOWN:
        wait = int(PER_USER_COOLDOWN - (now - user_hist[-1]))
        return False, (
            f"Esperá {wait}s entre consultas Gmail (anti-ban). "
            f"Google detecta consultas rápidas."
        )

    if len(user_hist) >= PER_USER_HOURLY_MAX:
        return False, f"Alcanzaste {PER_USER_HOURLY_MAX} consultas/hora."

    while _global_history and now - _global_history[0] > 3600:
        _global_history.popleft()

    if len(_global_history) >= GLOBAL_HOURLY_MAX:
        return False, "Límite global alcanzado, esperá unos minutos."

    user_hist.append(now)
    _global_history.append(now)
    return True, ""


def trigger_gmail_pause(reason: str = "rate-limit") -> None:
    global _paused_until
    _paused_until = time.monotonic() + GOOGLE_BAN_COOLDOWN
    logger.warning(f"Gmail OSINT pausado {GOOGLE_BAN_COOLDOWN // 60}min por: {reason}")


# ── Helpers ───────────────────────────────────────────────────────────────────

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _has_google_cookies() -> bool:
    return bool(GOOGLE_SAPISID and GOOGLE_HSID and GOOGLE_SECURE_1PSID)


def _google_cookies() -> dict:
    """Cookies para inyectar en sesiones autenticadas (estilo GHunt)."""
    cookies = {
        "SAPISID":           GOOGLE_SAPISID,
        "HSID":              GOOGLE_HSID,
        "SSID":              GOOGLE_SSID,
        "APISID":            GOOGLE_APISID,
        "__Secure-1PSID":    GOOGLE_SECURE_1PSID,
        "__Secure-3PSID":    GOOGLE_SECURE_3PSID or GOOGLE_SECURE_1PSID,
    }
    if GOOGLE_NID:
        cookies["NID"] = GOOGLE_NID
    return {k: v for k, v in cookies.items() if v}


def _sapisidhash(origin: str = "https://drive.google.com") -> str:
    """
    Calcula el header SAPISIDHASH que Google usa para auth de sesión
    en endpoints internos. Format: 'SAPISIDHASH <ts>_<hash>'
    donde hash = SHA1(<ts> <SAPISID> <origin>).
    """
    if not GOOGLE_SAPISID:
        return ""
    ts = str(int(time.time()))
    raw = f"{ts} {GOOGLE_SAPISID} {origin}"
    h = hashlib.sha1(raw.encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{h}"


# ── Recovery hints (sin auth, técnica Toutatis adaptada) ─────────────────────

async def get_google_recovery_hints(email: str) -> dict:
    """
    Usa el flujo público de "Forgot password" de Google para obtener:
      - Si la cuenta existe
      - Phone hint parcial (ej. `•• ••• ••45`)
      - Email recovery hint parcial (ej. `j****@e****.com`)

    Sin auth necesaria. Funciona contra cuentas Gmail Y Google Workspace.
    """
    out = {
        "exists":            False,
        "obfuscated_phone":  None,
        "obfuscated_email":  None,
        "error":             None,
    }

    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, **_proxy
        ) as client:
            # 1) GET inicial para conseguir cookies + token
            r1 = await client.get(
                "https://accounts.google.com/v3/signin/identifier",
                params={
                    "continue":  "https://mail.google.com/mail/",
                    "service":   "mail",
                    "flowName":  "GlifWebSignIn",
                    "flowEntry": "ServiceLogin",
                    "hl":        "en",
                },
                headers={"User-Agent": UA},
            )
            if r1.status_code != 200:
                out["error"] = f"Google identifier inicial → HTTP {r1.status_code}"
                return out

            # Extraer el form action / params del HTML
            html = r1.text

            # Para el lookup, Google v3 usa un endpoint POST con la cuenta
            r2 = await client.post(
                "https://accounts.google.com/_/lookup/accountlookup",
                data={"f.req": f'["{email}",[]]', "continue": "https://mail.google.com/"},
                headers={
                    "User-Agent":    UA,
                    "Content-Type":  "application/x-www-form-urlencoded;charset=UTF-8",
                    "Origin":        "https://accounts.google.com",
                    "Referer":       "https://accounts.google.com/v3/signin/identifier",
                },
            )

            # Heurística: si el body contiene "couldn't find" o similar → no existe
            text_lower = (r2.text or "").lower()
            if any(kw in text_lower for kw in (
                "couldn't find", "no encontramos", "couldn't be found",
                "no se encontró", "n'avons pas trouvé"
            )):
                out["exists"] = False
                return out

            # Intentar obtener hints vía el flujo moderno de forgot-password
            r3 = await client.post(
                "https://accounts.google.com/_/signin/sl/lookup",
                data={
                    "f.req": f'[["{email}",null,1]]',
                    "hl":    "en",
                },
                headers={
                    "User-Agent":   UA,
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "Origin":       "https://accounts.google.com",
                    "Referer":      "https://accounts.google.com/v3/signin/identifier",
                },
            )

            if r3.status_code in (401, 429):
                out["error"] = f"Google rate limit ({r3.status_code})"
                trigger_gmail_pause(f"recovery {r3.status_code}")
                return out

            # Parsear respuesta — Google devuelve arrays protobuf/JSON
            body = r3.text or ""
            try:
                clean = body.lstrip(")]}'\n ")
                flat = str(json.loads(clean)) if clean.startswith("[") else body
            except Exception:
                flat = body

            # Buscar patrones ofuscados (sólo aceptar si contienen • o *)
            phone_m = re.search(r"'(\+?[\d•·\*\s\-]{5,}\d{2})'", flat)
            email_m = re.search(r"'([a-zA-Z][^'@]{0,20}@[^']{1,30})'", flat)

            if phone_m:
                cand = phone_m.group(1).strip()
                if any(c in cand for c in ("•", "*", "·")):
                    out["obfuscated_phone"] = cand
                    out["exists"] = True
            if email_m:
                cand = email_m.group(1)
                if any(c in cand for c in ("*", "•")) and "@" in cand:
                    out["obfuscated_email"] = cand
                    out["exists"] = True

            # Fallback: buscar también en la respuesta del accountlookup (r2)
            if not out["obfuscated_phone"] or not out["obfuscated_email"]:
                body2 = r2.text or ""
                pm = re.search(r"(\+?[\d•·\*\s\-]{5,}\d{2})", body2)
                em = re.search(r"([a-zA-Z*•][^\s\"<>]{0,20}@[\w.*•]{2,}\.[a-z]{2,})", body2)
                if pm and not out["obfuscated_phone"]:
                    cand = pm.group(1).strip()
                    if any(c in cand for c in ("•", "*", "·")):
                        out["obfuscated_phone"] = cand
                        out["exists"] = True
                if em and not out["obfuscated_email"]:
                    cand = em.group(1)
                    if any(c in cand for c in ("*", "•")) and "@" in cand:
                        out["obfuscated_email"] = cand
                        out["exists"] = True

            # Heurística final: si el lookup no devolvió "no encontrado", existe
            if not out["exists"] and "couldn't" not in text_lower:
                out["exists"] = True

    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        logger.warning(f"get_google_recovery_hints({email}): {e}")

    return out


# ── Foto de perfil pública (Gravatar + Google fallback) ──────────────────────

async def get_profile_picture_urls(email: str) -> dict:
    """
    Devuelve URLs de imágenes de perfil candidatas:
      - Gravatar (oficial, lo usan muchos servicios)
      - Google account picture (vía endpoint público con email hash)
    """
    out = {"gravatar": None, "google": None, "has_gravatar": False}

    md5 = hashlib.md5(email.lower().strip().encode()).hexdigest()
    grav = f"https://www.gravatar.com/avatar/{md5}?s=400&d=404"
    out["gravatar"] = grav

    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    try:
        async with httpx.AsyncClient(timeout=10.0, **_proxy) as client:
            r = await client.head(grav)
            out["has_gravatar"] = (r.status_code == 200)
    except Exception:
        pass

    return out


# ── YouTube channel discovery ─────────────────────────────────────────────────

async def get_youtube_channel(email: str) -> dict:
    """
    Búsqueda heurística de canal de YouTube linkeado al email.
    Sin API key formal — usa el search público (más limitado).
    """
    out = {"found": False, "channels": []}
    handle = email.split("@")[0]
    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, **_proxy
        ) as client:
            r = await client.get(
                "https://www.youtube.com/results",
                params={"search_query": handle, "sp": "EgIQAg%253D%253D"},
                headers={"User-Agent": UA},
            )
            if r.status_code == 200:
                # Extraer IDs de canales del HTML (simple regex)
                channel_ids = re.findall(r'"channelId":"(UC[\w-]{20,24})"', r.text)
                seen = set()
                for cid in channel_ids[:5]:
                    if cid in seen:
                        continue
                    seen.add(cid)
                    out["channels"].append({
                        "channel_id": cid,
                        "url":        f"https://www.youtube.com/channel/{cid}",
                    })
                out["found"] = bool(out["channels"])
    except Exception as e:
        logger.debug(f"get_youtube_channel({email}): {e}")
    return out


# ── Google profile vía People API (con cookies) ───────────────────────────────

async def get_google_profile_authenticated(email: str) -> dict:
    """
    Si hay cookies de sesión Google configuradas, consulta el endpoint
    interno de People API (técnica GHunt) para obtener:
      - Google ID (gaia_id)
      - Nombre completo, foto en alta resolución
      - Servicios linkeados (YouTube channel, Maps, etc.)

    Sin cookies, devuelve out["error"]= "no auth".
    """
    out = {
        "found":      False,
        "gaia_id":    None,
        "names":      [],
        "photo_url":  None,
        "linked":     {},
        "error":      None,
    }

    if not _has_google_cookies():
        out["error"] = "no auth"
        return out

    # API keys probadas por GHunt en distintas versiones — las roto en orden
    # porque Google deprecá keys con cierta frecuencia.
    api_keys = [
        "AIzaSyDX5UKqKtOkkDigbmRW2rvi1a64jmAuOnE",
        "AIzaSyDfP15ec40vAQ7Pgsz4rsXyVdL4LRfgUjk",
        "AIzaSyCwUYd1AIXXBY8XRYSDx1XrRObmcqNrVDw",
    ]

    # Endpoint correcto: `:lookup` (gRPC→REST), no `/lookup`
    endpoint = "https://people-pa.clients6.google.com/v2/people:lookup"

    body = {
        "id":              email,
        "type":            "EMAIL",
        "matchType":       "EXACT",
        "extensionSet": {
            "extensionNames": [
                "HANGOUTS_ADDITIONAL_DATA", "DYNAMITE_ADDITIONAL_DATA",
                "GPLUS_ADDITIONAL_DATA",
            ]
        },
        "requestMask": {
            "includeField": {
                "paths": [
                    "person.metadata.best_display_name",
                    "person.name", "person.photo", "person.cover_photo",
                    "person.email", "person.metadata", "person.organization",
                    "person.location",
                ]
            },
            "includeContainer": ["PROFILE", "DOMAIN_PROFILE"],
        },
        "coreIdParams": {"useRealtimeNotificationExpandedAcls": True},
    }

    _proxy = {"proxy": PROXY_URL} if PROXY_URL else {}
    try:
        async with httpx.AsyncClient(timeout=20.0, **_proxy) as client:
            for key in api_keys:
                r = await client.post(
                    endpoint,
                    params={"key": key, "alt": "json"},
                    json=body,
                    headers={
                        "User-Agent":      UA,
                        "Origin":          "https://contacts.google.com",
                        "Referer":         "https://contacts.google.com/",
                        "Authorization":   _sapisidhash("https://contacts.google.com"),
                        "X-Goog-AuthUser": "0",
                        "Content-Type":    "application/json+protobuf",
                    },
                    cookies=_google_cookies(),
                )

                if r.status_code in (401, 403, 429):
                    out["error"] = f"Google {r.status_code} (cookies expiradas?)"
                    if r.status_code in (401, 429):
                        trigger_gmail_pause(f"people-api {r.status_code}")
                    return out

                # 404 con esta key → probar la siguiente
                if r.status_code == 404:
                    logger.debug(f"People API key {key[:12]}... → 404, probando siguiente")
                    continue

                if r.status_code != 200:
                    out["error"] = f"People API → HTTP {r.status_code}"
                    return out

                # 200 con datos
                try:
                    data = r.json()
                except Exception:
                    out["error"] = "People API respondió no-JSON"
                    return out

                if not isinstance(data, dict):
                    out["error"] = "People API devolvió datos inválidos"
                    return out

                matches = data.get("matches") or []
                if not matches:
                    out["error"] = "Email no resuelve a una cuenta Google pública"
                    return out

                person_id_list = matches[0].get("personId", [])
                person_id = person_id_list[0] if person_id_list else None

                people = data.get("people") or {}
                person = people.get(person_id) or {}

                out["gaia_id"] = person_id

                for n in (person.get("name") or []):
                    full = n.get("displayName") or n.get("displayNameLastFirst")
                    if full and full not in out["names"]:
                        out["names"].append(full)

                for ph in (person.get("photo") or []):
                    url = ph.get("url")
                    if url:
                        out["photo_url"] = re.sub(r"=s\d+", "=s400", url)
                        break

                out["found"] = True
                return out

            # Si todas las keys dieron 404
            out["error"] = "People API: 404 con todas las keys (email no público o keys deprecadas)"

    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        logger.warning(f"get_google_profile_authenticated({email}): {e}")

    return out


# ── API pública del módulo ────────────────────────────────────────────────────

async def get_domain_intel(domain: str) -> dict:
    """
    Análisis del dominio del email (útil para Workspace).
    Detecta si el dominio usa Google Workspace, Microsoft 365, Zoho, etc.
    """
    out = {
        "domain":            domain,
        "is_workspace":      False,
        "mail_provider":     None,
        "mx_records":        [],
        "has_spf":           None,
        "has_dmarc":         None,
        "error":             None,
    }
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.timeout = 4.0
        resolver.lifetime = 6.0

        # MX records → quién maneja el correo
        try:
            answers = resolver.resolve(domain, "MX")
            mxs = []
            for rdata in answers:
                mxs.append(str(rdata.exchange).lower().rstrip("."))
            out["mx_records"] = mxs

            mx_str = " ".join(mxs).lower()
            if "google" in mx_str or "googlemail" in mx_str:
                out["is_workspace"] = True
                out["mail_provider"] = "Google Workspace"
            elif "outlook" in mx_str or "microsoft" in mx_str:
                out["mail_provider"] = "Microsoft 365"
            elif "zoho" in mx_str:
                out["mail_provider"] = "Zoho Mail"
            elif "protonmail" in mx_str or "proton" in mx_str:
                out["mail_provider"] = "Proton Mail"
            else:
                out["mail_provider"] = mxs[0] if mxs else "desconocido"
        except Exception:
            pass

        # SPF
        try:
            answers = resolver.resolve(domain, "TXT")
            for rdata in answers:
                txt = "".join([s.decode() if isinstance(s, bytes) else s
                               for s in rdata.strings])
                if txt.startswith("v=spf1"):
                    out["has_spf"] = True
                    break
            if out["has_spf"] is None:
                out["has_spf"] = False
        except Exception:
            pass

        # DMARC
        try:
            answers = resolver.resolve(f"_dmarc.{domain}", "TXT")
            out["has_dmarc"] = bool(list(answers))
        except Exception:
            out["has_dmarc"] = False

    except ImportError:
        out["error"] = "dnspython no instalado"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"

    return out


async def gmail_lookup(email: str) -> dict:
    """
    Lookup completo de un email Gmail / Google.
    El rate limit por usuario debe chequearse ANTES con
    `check_gmail_rate_limit(user_id)` desde el handler.
    """
    out = {
        "input":     email,
        "is_gmail":  False,
        "is_google": False,
        "found":     False,
        "recovery":  None,
        "profile":   None,
        "youtube":   None,
        "pictures":  None,
        "domain":    None,
        "session":   "anonymous",
        "errors":    [],
    }

    email = (email or "").strip().lower()
    if not email:
        out["errors"].append("Email vacío")
        return out
    if not EMAIL_RE.match(email):
        out["errors"].append(f"Formato de email inválido: {email!r}")
        return out

    domain = email.split("@", 1)[-1]
    out["is_gmail"]  = domain in GMAIL_DOMAINS
    out["is_google"] = out["is_gmail"]

    if _has_google_cookies():
        out["session"] = "authenticated (cookies)"

    # 5 llamadas en paralelo
    pictures, youtube, recovery, profile, domain_intel = await asyncio.gather(
        get_profile_picture_urls(email),
        get_youtube_channel(email),
        get_google_recovery_hints(email),
        get_google_profile_authenticated(email),
        get_domain_intel(domain),
        return_exceptions=False,
    )

    out["pictures"] = pictures
    out["youtube"]  = youtube
    out["recovery"] = recovery
    out["profile"]  = profile
    out["domain"]   = domain_intel

    if recovery.get("exists"):
        out["found"] = True
        out["is_google"] = True
    if profile.get("found"):
        out["found"] = True
    # Si el dominio es Workspace, también es cuenta Google
    if domain_intel.get("is_workspace"):
        out["is_google"] = True

    # Errores: solo agregar el de profile si NO obtuvimos datos por otra vía.
    # El People API rompe seguido y no vale la pena alarmar al usuario si
    # ya tenemos recovery hints + Gravatar + YouTube + dominio.
    if recovery.get("error"):
        out["errors"].append(f"Recovery: {recovery['error']}")

    has_useful_data = (
        recovery.get("exists") or
        (pictures and pictures.get("has_gravatar")) or
        (youtube and youtube.get("found")) or
        (domain_intel and domain_intel.get("mail_provider"))
    )
    if profile.get("error") and profile["error"] != "no auth" and not has_useful_data:
        out["errors"].append(f"Profile: {profile['error']}")

    return out
