# -*- coding: utf-8 -*-
"""
IG OSINT — recon profundo sobre cuentas de Instagram.

Combina dos motores:
  1. Instaloader  → perfil completo, posts recientes, geotags, stats
  2. Toutatis     → email/teléfono parcialmente ofuscados desde el endpoint
                    público de password recovery de IG (técnica única)

Incluye un rate limiter dedicado a IG (separado del global del bot) para
evitar bloqueos de la cuenta de sesión:
  - 1 lookup cada 60s por usuario
  - Máx 20 lookups/hora por usuario
  - Máx 80 lookups/hora globales
  - Si IG devuelve 401/429 → pausa global de 30 min

Sesión: usa cookies (sessionid + ds_user_id + csrftoken) inyectadas vía
variables de entorno. Sin sesión, funciona en modo anónimo (muy limitado).
Cómo conseguir las cookies está en el README/docstring de _setup_instaloader.
"""

import asyncio
import logging
import os
import re
import time
from collections import defaultdict, deque
from typing import Optional

import httpx

logger = logging.getLogger("GekOsint.IGOsint")

# ── Configuración (env vars) ──────────────────────────────────────────────────
try:
    from config import (
        IG_USERNAME, IG_SESSIONID, IG_DS_USER_ID, IG_CSRFTOKEN,
    )
except ImportError:
    IG_USERNAME   = os.getenv("IG_USERNAME", "")
    IG_SESSIONID  = os.getenv("IG_SESSIONID", "")
    IG_DS_USER_ID = os.getenv("IG_DS_USER_ID", "")
    IG_CSRFTOKEN  = os.getenv("IG_CSRFTOKEN", "")

# ── Constantes del rate limiter dedicado ──────────────────────────────────────
PER_USER_COOLDOWN     = 60        # 1 lookup IG cada 60s por usuario
PER_USER_HOURLY_MAX   = 20        # máx 20 lookups/hora por usuario
GLOBAL_HOURLY_MAX     = 80        # máx 80 lookups/hora todos los usuarios
IG_BAN_COOLDOWN       = 30 * 60   # pausa de 30 min si IG nos pega 401/429
IG_INTER_REQUEST_WAIT = 3         # ≥3s entre llamadas internas a IG

# Validación username IG
IG_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")

# Estado en memoria (per-process). Para multi-proceso usar Redis.
_user_history: dict[int, deque] = defaultdict(deque)
_global_history: deque = deque()
_ig_paused_until: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  RATE LIMITER ESPECÍFICO DE IG
# ─────────────────────────────────────────────────────────────────────────────

def check_ig_rate_limit(user_id: int) -> tuple[bool, str]:
    """
    Verifica si user_id puede hacer un lookup IG ahora.
    Si SI permitido: registra el evento y devuelve (True, "").
    Si NO: devuelve (False, "razón humana del rechazo").

    Llamar ANTES de invocar `ig_lookup`.
    """
    now = time.monotonic()

    # 1) Pausa global por anti-ban
    if now < _ig_paused_until:
        wait = int(_ig_paused_until - now)
        mins, secs = divmod(wait, 60)
        return False, (
            f"IG OSINT pausado por anti-ban (rate limit de IG). "
            f"Reanuda en {mins}m {secs}s."
        )

    # 2) Per-user: limpiar historia vieja (>1h)
    user_hist = _user_history[user_id]
    while user_hist and now - user_hist[0] > 3600:
        user_hist.popleft()

    # 2a) Cooldown entre consultas
    if user_hist:
        elapsed = now - user_hist[-1]
        if elapsed < PER_USER_COOLDOWN:
            wait = int(PER_USER_COOLDOWN - elapsed)
            return False, (
                f"Esperá {wait}s entre consultas de IG (anti-ban). "
                f"IG bloquea cuentas que consultan muy rápido."
            )

    # 2b) Cap por hora
    if len(user_hist) >= PER_USER_HOURLY_MAX:
        return False, (
            f"Alcanzaste {PER_USER_HOURLY_MAX} consultas IG en la última hora. "
            f"Intentá más tarde."
        )

    # 3) Global: limpiar historia vieja
    while _global_history and now - _global_history[0] > 3600:
        _global_history.popleft()

    if len(_global_history) >= GLOBAL_HOURLY_MAX:
        return False, (
            "Límite global de IG alcanzado para esta hora. "
            "Esperá unos minutos."
        )

    # OK — registrar
    user_hist.append(now)
    _global_history.append(now)
    return True, ""


def trigger_ig_pause(reason: str = "rate-limit") -> None:
    """
    Activa la pausa global de IG OSINT por anti-ban.
    Se llama automáticamente desde dentro del módulo si IG nos da 401/429.
    """
    global _ig_paused_until
    _ig_paused_until = time.monotonic() + IG_BAN_COOLDOWN
    logger.warning(
        f"IG OSINT pausado {IG_BAN_COOLDOWN // 60}min por: {reason}"
    )


def ig_status() -> dict:
    """Estado actual del rate limiter — para /admin o debugging."""
    now = time.monotonic()
    return {
        "paused":        now < _ig_paused_until,
        "paused_for":    max(0, int(_ig_paused_until - now)),
        "global_used":   len(_global_history),
        "global_max":    GLOBAL_HOURLY_MAX,
        "active_users":  len(_user_history),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  TOUTATIS — recovery hints (email/phone ofuscados)
# ─────────────────────────────────────────────────────────────────────────────

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
UA_MOBILE = (
    "Instagram 219.0.0.12.117 Android (28/9; 320dpi; 720x1280; "
    "Xiaomi; Redmi 6; cereus; Mediatek MT6762; en_US)"
)


async def get_recovery_hints(username: str) -> dict:
    """
    Usa el endpoint público de password recovery de IG para revelar
    email y teléfono parcialmente ofuscados (`j****@gmail.com`,
    `+57 ** **** **45`). Es la técnica de Toutatis.

    No requiere autenticación. Pero:
      - Necesita csrftoken fresco del homepage de IG.
      - IG puede devolver 429 si abusamos.
    """
    out: dict = {
        "obfuscated_email":  None,
        "obfuscated_phone":  None,
        "found":             False,
        "error":             None,
    }

    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True
        ) as client:
            # 1) Conseguir csrftoken
            r1 = await client.get(
                "https://www.instagram.com/accounts/login/",
                headers={"User-Agent": UA_DESKTOP},
            )
            csrftoken = r1.cookies.get("csrftoken")
            if not csrftoken:
                out["error"] = "No se pudo obtener csrftoken de IG"
                return out

            # 2) POST al recovery endpoint
            r2 = await client.post(
                "https://i.instagram.com/api/v1/accounts/account_recovery_send_ajax/",
                headers={
                    "User-Agent":   UA_MOBILE,
                    "X-Csrftoken":  csrftoken,
                    "X-IG-App-ID":  "936619743392459",
                    "Referer":      "https://www.instagram.com/accounts/password/reset/",
                    "Origin":       "https://www.instagram.com",
                },
                data={"query": username, "adid": ""},
                cookies={"csrftoken": csrftoken},
            )

            if r2.status_code == 404:
                out["error"] = f"@{username} no existe en IG"
                return out
            if r2.status_code in (401, 429):
                out["error"] = f"IG rate-limit ({r2.status_code}) en recovery endpoint"
                trigger_ig_pause(f"recovery {r2.status_code}")
                return out
            if r2.status_code != 200:
                out["error"] = f"Recovery endpoint respondió {r2.status_code}"
                return out

            try:
                body = r2.json()
            except Exception:
                out["error"] = "Recovery endpoint: respuesta no JSON"
                return out

            email = body.get("obfuscated_email") or ""
            phone = body.get("obfuscated_phone_number") or ""
            contact = body.get("contact_point") or ""

            # Si vienen vacíos pero hay contact_point, parsear
            if not email and "@" in contact:
                email = contact
            if not phone and contact.startswith("+"):
                phone = contact

            if email or phone:
                out["obfuscated_email"] = email or None
                out["obfuscated_phone"] = phone or None
                out["found"] = True
            else:
                # IG respondió 200 pero sin hints — usuario sin recovery configurado
                out["error"] = "IG no devolvió hints (cuenta sin email/phone público)"

    except Exception as e:
        out["error"] = f"Excepción: {type(e).__name__}: {e}"
        logger.warning(f"get_recovery_hints({username}): {e}")

    return out


# ─────────────────────────────────────────────────────────────────────────────
#  INSTALOADER — perfil + posts (sync, se llama vía asyncio.to_thread)
# ─────────────────────────────────────────────────────────────────────────────

def _setup_instaloader():
    """
    Crea instancia de Instaloader con sesión inyectada vía cookies.

    Cómo conseguir las cookies (UNA VEZ, en una compu de confianza):
      1. Logueate en instagram.com con la cuenta dedicada.
      2. DevTools → Application → Cookies → instagram.com.
      3. Copiá los valores de `sessionid`, `ds_user_id`, `csrftoken`.
      4. En Koyeb → Environment Variables (Secret):
           IG_USERNAME    = nombre_de_la_cuenta
           IG_SESSIONID   = (valor de sessionid)
           IG_DS_USER_ID  = (valor de ds_user_id)
           IG_CSRFTOKEN   = (valor de csrftoken)
      5. Redeploy.

    Sin sesión, IG bloquea casi todo en 2026 — modo anónimo solo da
    nombre/bio/follower-count y nada más.
    """
    try:
        from instaloader import Instaloader
    except ImportError:
        return None, "instaloader no instalado (agregá 'instaloader' a requirements.txt)"

    L = Instaloader(
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False,
        compress_json=False, request_timeout=20.0,
        max_connection_attempts=2, quiet=True,
    )

    if IG_SESSIONID and IG_DS_USER_ID:
        sess = L.context._session
        sess.cookies.set("sessionid",  IG_SESSIONID,  domain=".instagram.com")
        sess.cookies.set("ds_user_id", IG_DS_USER_ID, domain=".instagram.com")
        if IG_CSRFTOKEN:
            sess.cookies.set("csrftoken", IG_CSRFTOKEN, domain=".instagram.com")
        L.context.username = IG_USERNAME or "_session_user_"
        return L, None

    return L, "Sin sesión IG (modo anónimo, datos limitados)"


def _profile_to_dict(profile) -> dict:
    """Aplana un Profile de Instaloader a dict serializable."""
    out: dict = {
        "username":          profile.username,
        "user_id":           profile.userid,
        "full_name":         profile.full_name or None,
        "biography":         profile.biography or None,
        "external_url":      profile.external_url or None,
        "is_private":        bool(profile.is_private),
        "is_verified":       bool(profile.is_verified),
        "is_business":       bool(profile.is_business_account),
        "business_category": (
            profile.business_category_name
            if profile.is_business_account else None
        ),
        "followers":         profile.followers,
        "followees":         profile.followees,
        "posts_count":       profile.mediacount,
        "igtv_count":        getattr(profile, "igtvcount", 0) or 0,
        "profile_pic_url":   profile.profile_pic_url,
        "has_highlights":    bool(profile.has_highlight_reels),
    }

    # Posts recientes — solo si NO es privada
    recent_posts = []
    if not profile.is_private:
        try:
            for i, post in enumerate(profile.get_posts()):
                if i >= 5:
                    break
                recent_posts.append({
                    "shortcode":  post.shortcode,
                    "url":        f"https://www.instagram.com/p/{post.shortcode}/",
                    "date":       post.date_utc.isoformat(),
                    "likes":      post.likes,
                    "comments":   post.comments,
                    "is_video":   bool(post.is_video),
                    "caption":    (post.caption or "")[:100] if post.caption else None,
                    "location":   post.location.name if post.location else None,
                    "location_id": post.location.id if post.location else None,
                })
        except Exception as e:
            logger.debug(f"get_posts({profile.username}): {e}")

    out["recent_posts"] = recent_posts
    return out


def _instaloader_profile_sync(username: str) -> dict:
    """SÍNCRONO — siempre llamar vía asyncio.to_thread."""
    out = {"profile": None, "error": None, "session": "anonymous"}

    L, warn = _setup_instaloader()
    if L is None:
        out["error"] = warn
        return out

    if IG_SESSIONID and IG_DS_USER_ID:
        out["session"] = f"as @{IG_USERNAME}" if IG_USERNAME else "authenticated"

    try:
        from instaloader import Profile
        profile = Profile.from_username(L.context, username)
        out["profile"] = _profile_to_dict(profile)
    except Exception as e:
        msg = str(e).lower()
        if "404" in msg or "not found" in msg or "does not exist" in msg:
            out["error"] = f"@{username} no existe en IG"
        elif any(k in msg for k in ("401", "checkpoint", "login_required",
                                    "redirect", "please wait")):
            out["error"] = f"IG bloqueó la sesión: {e}"
            trigger_ig_pause(f"instaloader 401/checkpoint")
        elif "429" in msg or "too many" in msg:
            out["error"] = "IG nos rate-limiteó (429)"
            trigger_ig_pause("instaloader 429")
        else:
            out["error"] = str(e)
        logger.warning(f"_instaloader_profile_sync({username}): {e}")

    return out


# ─────────────────────────────────────────────────────────────────────────────
#  API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

async def ig_lookup(username: str) -> dict:
    """
    Recon completo de un username de IG.
    Combina Instaloader (perfil + posts) + Toutatis (recovery hints).

    El rate limit por usuario debe chequearse ANTES con
    `check_ig_rate_limit(user_id)` desde el handler.
    """
    out: dict = {
        "input":    username,
        "found":    False,
        "profile":  None,
        "recovery": None,
        "session":  None,
        "errors":   [],
    }

    username = (username or "").strip().lstrip("@")
    if not username:
        out["errors"].append("Username vacío")
        return out

    if not IG_USERNAME_RE.match(username):
        out["errors"].append(
            f"Username '{username}' inválido para IG "
            f"(solo a-z, 0-9, ., _, máx 30 chars)"
        )
        return out

    # 1) Instaloader (perfil + posts) — sync, en thread
    profile_data = await asyncio.to_thread(_instaloader_profile_sync, username)
    out["session"] = profile_data.get("session")
    if profile_data.get("error"):
        out["errors"].append(profile_data["error"])
    if profile_data.get("profile"):
        out["found"] = True
        out["profile"] = profile_data["profile"]

    # 2) Recovery hints (Toutatis) — pequeña pausa anti-ban
    user_doesnt_exist = any("no existe" in e.lower() for e in out["errors"])
    if not user_doesnt_exist:
        await asyncio.sleep(IG_INTER_REQUEST_WAIT)
        recovery = await get_recovery_hints(username)
        out["recovery"] = recovery
        # Si recovery encontró hints, marcamos como "found" aunque
        # Instaloader haya fallado (caso anonymous bloqueado)
        if recovery.get("found") and not out["found"]:
            out["found"] = True

    return out
