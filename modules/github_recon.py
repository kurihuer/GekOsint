# -*- coding: utf-8 -*-
"""
GitHub Recon — OSINT profundo sobre cuentas de GitHub.

Input: username (`octocat`, `@octocat`) o email (`foo@bar.com`).
Output:
  - Perfil completo (nombre, bio, empresa, ubicación, blog, twitter, fechas)
  - Estadísticas (followers, repos, stars totales, forks)
  - Top repos por stars (lenguaje, descripción, fork status)
  - Distribución de lenguajes
  - Organizaciones públicas
  - Gists públicos recientes
  - SSH keys y GPG keys públicas (counts)
  - **Emails leakeados en commits públicos** (la joya del módulo)
  - Actividad reciente analizada

Usa GITHUB_TOKEN para rate limit elevado (5000/hr vs 60/hr sin token).
"""

import asyncio
import logging
import re
from typing import Optional

import httpx

from config import GITHUB_TOKEN

logger = logging.getLogger("GekOsint.GithubRecon")

API_BASE = "https://api.github.com"
HEADERS_BASE = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "GekOsint-Bot",
}

# Emails noreply de GitHub que no son útiles para OSINT
NOREPLY_RE = re.compile(r"^[\d]+\+?[\w.\-]*@users\.noreply\.github\.com$", re.I)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _headers() -> dict:
    h = dict(HEADERS_BASE)
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


async def _gh(client: httpx.AsyncClient, path: str, params: Optional[dict] = None):
    """GET autenticado a la API de GitHub. Devuelve JSON o None."""
    try:
        r = await client.get(f"{API_BASE}{path}", params=params, headers=_headers())
    except httpx.HTTPError as e:
        logger.warning(f"GH {path} → red falló: {e}")
        return None

    if r.status_code == 200:
        try:
            return r.json()
        except Exception:
            return None
    if r.status_code == 404:
        return None
    if r.status_code == 403:
        # Rate limit casi seguro — log para diagnóstico
        remaining = r.headers.get("x-ratelimit-remaining", "?")
        reset = r.headers.get("x-ratelimit-reset", "?")
        logger.warning(f"GH 403 (rate limit?) — remaining={remaining} reset={reset}")
        return None
    if r.status_code == 401:
        logger.warning("GH 401 — GITHUB_TOKEN inválido o revocado")
        return None
    logger.warning(f"GH {path} → HTTP {r.status_code}")
    return None


# ── Endpoints individuales ────────────────────────────────────────────────────

async def _get_profile(client, username: str):
    return await _gh(client, f"/users/{username}")


async def _get_repos(client, username: str, limit: int = 10):
    repos = await _gh(
        client, f"/users/{username}/repos",
        params={"per_page": 100, "sort": "updated", "type": "owner"}
    )
    if not repos:
        return []
    repos.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
    return repos[:limit]


async def _get_orgs(client, username: str):
    return (await _gh(client, f"/users/{username}/orgs")) or []


async def _get_gists(client, username: str):
    return (await _gh(client, f"/users/{username}/gists",
                      params={"per_page": 30})) or []


async def _get_ssh_keys(client, username: str):
    return (await _gh(client, f"/users/{username}/keys")) or []


async def _get_gpg_keys(client, username: str):
    return (await _gh(client, f"/users/{username}/gpg_keys")) or []


async def _get_events(client, username: str, pages: int = 3):
    """
    Eventos públicos recientes — fuente principal de email leaks.
    GitHub solo devuelve los últimos ~300 eventos máximo (3 páginas de 100).
    """
    events = []
    for p in range(1, pages + 1):
        page = await _gh(
            client, f"/users/{username}/events/public",
            params={"per_page": 100, "page": p}
        )
        if not page:
            break
        events.extend(page)
        if len(page) < 100:
            break
    return events


async def _search_user_by_email(client, email: str) -> Optional[str]:
    """Buscar username por email público. Retorna login o None."""
    r = await _gh(client, "/search/users", params={"q": f"{email} in:email"})
    if not r:
        return None
    items = r.get("items") or []
    if not items:
        return None
    return items[0].get("login")


# ── Procesamiento ─────────────────────────────────────────────────────────────

def _extract_emails_from_events(events: list) -> dict:
    """
    Extrae emails (Author/Committer) de PushEvents.
    Filtra los @users.noreply.github.com.
    Retorna: {email: {count, names: [str], first_seen_sha: str}}
    """
    emails: dict[str, dict] = {}
    for ev in events:
        if ev.get("type") != "PushEvent":
            continue
        commits = (ev.get("payload") or {}).get("commits") or []
        for commit in commits:
            author = commit.get("author") or {}
            email = (author.get("email") or "").strip().lower()
            name = (author.get("name") or "").strip()
            if not email or not EMAIL_RE.match(email):
                continue
            if NOREPLY_RE.match(email):
                continue
            entry = emails.setdefault(email, {
                "count": 0,
                "names": set(),
                "first_seen_sha": (commit.get("sha") or "")[:7],
            })
            entry["count"] += 1
            if name:
                entry["names"].add(name)
    # sets → listas ordenadas
    for e in emails.values():
        e["names"] = sorted(e["names"])
    return emails


def _languages_distribution(repos: list) -> dict:
    counts: dict[str, int] = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ── API pública del módulo ────────────────────────────────────────────────────

async def github_recon(query: str) -> dict:
    """
    Ejecuta recon completo de GitHub. Async — diseñado para llamarse desde
    handlers async sin bloquear el event loop.

    Args:
        query: username (con o sin @) o email.

    Returns:
        dict con todas las secciones — listo para `format_github_recon()`.
    """
    out: dict = {
        "input": query,
        "input_type": "username",
        "found": False,
        "resolved_username": None,
        "profile": None,
        "repos": [],
        "orgs": [],
        "gists": [],
        "ssh_keys": [],
        "gpg_keys": [],
        "leaked_emails": {},
        "languages": {},
        "stats": {},
        "errors": [],
    }

    if not GITHUB_TOKEN:
        out["errors"].append(
            "⚠️ GITHUB_TOKEN no configurado — rate limit 60/hr puede agotarse rápido. "
            "Para producción configurá un PAT (scope=public_repo o sin scopes)."
        )

    query = (query or "").strip()
    if not query:
        out["errors"].append("Input vacío")
        return out

    is_email = "@" in query and "." in query.split("@")[-1]
    out["input_type"] = "email" if is_email else "username"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # Resolver username si es email
        if is_email:
            username = await _search_user_by_email(client, query)
            if not username:
                out["errors"].append(
                    f"No se encontró cuenta de GitHub asociada al email <code>{query}</code>. "
                    f"(GitHub solo indexa emails declarados públicamente en perfil.)"
                )
                return out
            out["resolved_username"] = username
        else:
            username = query.lstrip("@")

        # Perfil base — obligatorio
        profile = await _get_profile(client, username)
        if not profile:
            out["errors"].append(
                f"Usuario <code>@{username}</code> no existe o GitHub no respondió."
            )
            return out

        out["found"] = True
        out["profile"] = profile
        out["resolved_username"] = username

        # El resto en paralelo
        repos, orgs, gists, ssh, gpg, events = await asyncio.gather(
            _get_repos(client, username, limit=10),
            _get_orgs(client, username),
            _get_gists(client, username),
            _get_ssh_keys(client, username),
            _get_gpg_keys(client, username),
            _get_events(client, username, pages=3),
            return_exceptions=False,
        )

        out["repos"] = repos
        out["orgs"] = orgs
        out["gists"] = gists
        out["ssh_keys"] = ssh
        out["gpg_keys"] = gpg
        out["leaked_emails"] = _extract_emails_from_events(events)
        out["languages"] = _languages_distribution(repos)

        out["stats"] = {
            "total_stars":           sum(r.get("stargazers_count", 0) for r in repos),
            "total_forks":           sum(r.get("forks_count", 0) for r in repos),
            "total_repos":           profile.get("public_repos", 0),
            "total_gists":           profile.get("public_gists", 0),
            "followers":             profile.get("followers", 0),
            "following":             profile.get("following", 0),
            "events_analyzed":       len(events),
            "unique_leaked_emails":  len(out["leaked_emails"]),
            "ssh_keys_count":        len(ssh),
            "gpg_keys_count":        len(gpg),
        }

    return out
