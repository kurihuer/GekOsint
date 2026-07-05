# -*- coding: utf-8 -*-
"""
People Search — nombre completo → variantes de username, perfiles verificables,
buscadores de personas y dorks de Google/Bing/DuckDuckGo.

Mejoras v6.2:
  - Verificación de perfiles SOLO en sitios fiables (GitHub API, Reddit JSON,
    Keybase, Gravatar, Linktree, Telegram). Las redes con muro de login
    (Instagram, Facebook, TikTok, LinkedIn, X) ya NO se "confirman" por HTTP
    (daban falsos positivos) — se entregan como dorks de búsqueda.
  - Eliminado código muerto con bug latente (`_search_pipl_links`).
  - Generación de variantes de username y links a buscadores de personas.
"""

import requests
import re
import concurrent.futures
import time
import unicodedata
from config import logger, SERPAPI_KEY

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}

_CACHE = {}
_TTL = 600
_SOCIAL_DOMAINS = {
    "linkedin.com": "LinkedIn",
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "x.com": "X",
    "twitter.com": "X",
    "github.com": "GitHub",
    "reddit.com": "Reddit",
    "t.me": "Telegram",
}


def _normalize(text):
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def generate_username_variants(name, surname):
    n  = _normalize(name).replace(' ', '')
    s  = _normalize(surname).replace(' ', '')
    n1 = n[0] if n else ''
    s1 = s[0] if s else ''
    variants = list({
        f"{n}{s}", f"{n}.{s}", f"{n}_{s}", f"{n1}{s}", f"{n}.{s1}",
        f"{n}{s1}", f"{s}{n}", f"{s}.{n}", f"{s}_{n}", f"{s1}{n}",
        f"{n}-{s}", f"{n}{s[:4]}", f"{s}{n[:3]}", f"{n[:4]}{s[:4]}",
    })
    return [v for v in variants if len(v) >= 3]


# Sitios donde SÍ se puede verificar existencia de forma fiable (API/JSON/status)
VERIFIABLE_SITES = {
    "GitHub":   {"url": "https://api.github.com/users/{}",            "method": "json",
                 "display": "https://github.com/{}"},
    "Reddit":   {"url": "https://www.reddit.com/user/{}/about.json",  "method": "json",
                 "display": "https://reddit.com/user/{}"},
    "Keybase":  {"url": "https://keybase.io/_/api/1.0/user/lookup.json?username={}",
                 "method": "keybase", "display": "https://keybase.io/{}"},
    "Gravatar": {"url": "https://en.gravatar.com/{}.json",            "method": "json",
                 "display": "https://en.gravatar.com/{}"},
    "Linktree": {"url": "https://linktr.ee/{}",                       "method": "status",
                 "display": "https://linktr.ee/{}"},
}

# Redes con muro de login → no se confirman (solo dorks). Referencia informativa.
SEARCH_ONLY_NETWORKS = ["Instagram", "Facebook", "TikTok", "LinkedIn", "Twitter/X"]


def _check_verifiable(site, cfg, variant, session):
    url = cfg["url"].format(variant)
    disp = cfg.get("display", cfg["url"]).format(variant)
    try:
        if cfg["method"] == "json":
            r = session.get(url, timeout=8)
            if r.status_code == 200:
                return {"site": site, "url": disp, "username": variant}
            return None
        if cfg["method"] == "keybase":
            r = session.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data.get("status", {}).get("code") == 0 and data.get("them"):
                    return {"site": site, "url": disp, "username": variant}
            return None
        if cfg["method"] == "status":
            r = session.get(url, timeout=7, allow_redirects=True)
            if r.status_code == 200 and "not found" not in (r.text or "").lower()[:2000]:
                return {"site": site, "url": disp, "username": variant}
            return None
    except Exception:
        pass
    return None


def search_verifiable_profiles(name, surname):
    """Verifica variantes de username SOLO en sitios fiables (sin falsos positivos)."""
    variants = generate_username_variants(name, surname)[:8]
    found = []
    seen = set()
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
            futures = {}
            for v in variants:
                for site, cfg in VERIFIABLE_SITES.items():
                    fut = ex.submit(_check_verifiable, site, cfg, v, session)
                    futures[fut] = (site, v)
            for fut in concurrent.futures.as_completed(futures, timeout=40):
                try:
                    res = fut.result()
                    if res and res["url"] not in seen:
                        seen.add(res["url"])
                        found.append(res)
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"search_verifiable_profiles: {e}")
    finally:
        session.close()
    found.sort(key=lambda x: x["site"])
    return found


def _people_search_links(full_name):
    encoded = requests.utils.quote(full_name)
    return {
        "Pipl":             f"https://pipl.com/search/?q={encoded}",
        "Spokeo":           f"https://www.spokeo.com/search?q={encoded}",
        "BeenVerified":     f"https://www.beenverified.com/people/{encoded.replace('%20', '-')}",
        "FastPeopleSearch": f"https://www.fastpeoplesearch.com/name/{encoded.replace('%20', '-')}",
        "TruePeopleSearch": f"https://www.truepeoplesearch.com/results?name={encoded}",
        "WhitePages":       f"https://www.whitepages.com/name/{encoded.replace('%20', '+')}",
        "PeekYou":          f"https://www.peekyou.com/{encoded.replace('%20', '_')}",
        "Intelius":         f"https://www.intelius.com/search/people/name/{encoded}/",
        "ThatsThem":        f"https://thatsthem.com/name/{encoded.replace('%20', '-')}",
    }


def _google_dorks(full_name, name, surname, context=None):
    q_full    = requests.utils.quote(f'"{full_name}"')
    q_social  = requests.utils.quote(f'"{full_name}" site:linkedin.com OR site:facebook.com OR site:instagram.com')
    q_email   = requests.utils.quote(f'"{full_name}" email OR correo OR "@"')
    q_phone   = requests.utils.quote(f'"{full_name}" telefono OR phone OR celular')
    q_news    = requests.utils.quote(f'"{full_name}" site:news.google.com OR inurl:noticias')
    q_docs    = requests.utils.quote(f'"{full_name}" filetype:pdf OR filetype:doc OR filetype:docx')
    q_images  = requests.utils.quote(f'"{full_name}" site:instagram.com OR site:facebook.com OR site:tiktok.com')
    q_user    = requests.utils.quote(f'"{name} {surname}" (username OR usuario OR handle OR "@")')
    q_ctx     = requests.utils.quote(f'"{full_name}" "{context}"') if context else None
    q_ctx_soc = requests.utils.quote(f'"{full_name}" "{context}" site:linkedin.com OR site:facebook.com OR site:instagram.com') if context else None
    return {
        "Busqueda general":   f"https://www.google.com/search?q={q_full}",
        "Redes sociales":     f"https://www.google.com/search?q={q_social}",
        "Email/Correo":       f"https://www.google.com/search?q={q_email}",
        "Telefono":           f"https://www.google.com/search?q={q_phone}",
        "Noticias":           f"https://www.google.com/search?q={q_news}",
        "Documentos":         f"https://www.google.com/search?q={q_docs}",
        "Imagenes":           f"https://www.google.com/search?q={q_images}&tbm=isch",
        "Usernames":          f"https://www.google.com/search?q={q_user}",
        "Contexto":           f"https://www.google.com/search?q={q_ctx}" if q_ctx else None,
        "Contexto + redes":   f"https://www.google.com/search?q={q_ctx_soc}" if q_ctx_soc else None,
        "Bing":               f"https://www.bing.com/search?q={requests.utils.quote(full_name)}",
        "DuckDuckGo":         f"https://duckduckgo.com/?q={requests.utils.quote(full_name)}",
    }


def _extract_username_from_url(url: str) -> str | None:
    if not url:
        return None
    cleaned = re.sub(r"https?://(www\.)?", "", url, flags=re.I).split("?", 1)[0].rstrip("/")
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) < 2:
        return None
    candidate = parts[-1].lstrip("@")
    candidate = re.sub(r"\.(html|php)$", "", candidate, flags=re.I)
    if re.match(r"^[A-Za-z0-9._-]{3,40}$", candidate):
        return candidate
    return None


def _serpapi_people_hits(full_name: str, context: str | None = None) -> dict:
    if not SERPAPI_KEY:
        return {"hits": [], "candidate_profiles": []}

    query = f'"{full_name}"'
    if context:
        query += f' "{context}"'

    try:
        r = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 10,
                "hl": "es",
                "gl": "mx",
            },
            headers=HEADERS,
            timeout=18,
        )
        if r.status_code != 200:
            logger.debug(f"people_search SerpAPI status={r.status_code}")
            return {"hits": [], "candidate_profiles": []}

        payload = r.json()
        hits = []
        candidate_profiles = []
        seen_urls = set()

        for item in payload.get("organic_results", [])[:10]:
            link = (item.get("link") or "").strip()
            title = (item.get("title") or "").strip()
            snippet = (item.get("snippet") or "").strip()
            if link and link not in seen_urls:
                seen_urls.add(link)
                hits.append({
                    "title": title or link,
                    "url": link,
                    "snippet": snippet[:220],
                })
            low = link.lower()
            site = None
            for domain, label in _SOCIAL_DOMAINS.items():
                if domain in low:
                    site = label
                    break
            if site and link:
                candidate_profiles.append({
                    "site": site,
                    "url": link,
                    "username": _extract_username_from_url(link) or "?",
                    "title": title,
                })

        dedup_profiles = []
        seen_profiles = set()
        for profile in candidate_profiles:
            key = (profile["site"], profile["url"])
            if key in seen_profiles:
                continue
            seen_profiles.add(key)
            dedup_profiles.append(profile)

        return {"hits": hits[:8], "candidate_profiles": dedup_profiles[:10]}
    except Exception as e:
        logger.debug(f"people_search SerpAPI error: {e}")
        return {"hits": [], "candidate_profiles": []}


def search_people(full_input):
    raw = (full_input or "").strip()
    context = None
    if "|" in raw:
        left, right = raw.split("|", 1)
        raw = left.strip()
        context = right.strip() or None
    parts = raw.split()
    if len(parts) < 2:
        return {"error": "Ingresa nombre Y apellido. Ej: Juan García"}

    name    = parts[0]
    surname = ' '.join(parts[1:])
    full    = f"{name} {surname}"

    ck    = ("people", full.lower())
    now   = int(time.time())
    entry = _CACHE.get(ck)
    if entry and now - entry[0] <= _TTL:
        return entry[1]

    verified = search_verifiable_profiles(name, surname)
    serp = _serpapi_people_hits(full, context=context)

    result = {
        "full_name":          full,
        "name":               name,
        "surname":            surname,
        "variants_checked":   generate_username_variants(name, surname)[:8],
        "social_profiles":    verified,            # solo perfiles CONFIRMADOS
        "candidate_profiles": serp.get("candidate_profiles", []),
        "serpapi_hits":       serp.get("hits", []),
        "search_networks":    SEARCH_ONLY_NETWORKS,  # estos van por dorks
        "osint_links":        _people_search_links(full),
        "dorks":              {k: v for k, v in _google_dorks(full, name, surname, context=context).items() if v},
        "context":            context,
    }

    _CACHE[ck] = (now, result)
    return result
