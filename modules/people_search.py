import os
import re
import time
import httpx
import urllib.parse
from difflib import SequenceMatcher

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_SITES = [
    "instagram.com", "facebook.com", "linkedin.com", "x.com", "twitter.com",
    "tiktok.com", "reddit.com", "medium.com"
]

def _norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()

def _score(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def _ddg_links(html):
    out = []
    for href in re.findall(r'href="(https?://[^"]+)"', html):
        if "duckduckgo.com/l/?" in href and "uddg=" in href:
            try:
                q = urllib.parse.urlparse(href).query
                uddg = urllib.parse.parse_qs(q).get("uddg", [""])[0]
                if uddg and uddg.startswith("http"):
                    out.append(urllib.parse.unquote(uddg))
            except Exception:
                pass
        elif any(d in href for d in _SITES):
            out.append(href)
    return list(dict.fromkeys(out))

def _ddg_site_search(name, domain, limit=4):
    q = f'site:{domain} "{name}"'
    try:
        with httpx.Client(headers=_HEADERS, timeout=12.0) as c:
            r = c.get("https://duckduckgo.com/html/", params={"q": q})
            if r.status_code != 200:
                return []
            links = _ddg_links(r.text)
            return links[:limit]
    except Exception:
        return []

def _github_search(name):
    token = os.getenv("GITHUB_TOKEN", "")
    url = "https://api.github.com/search/users"
    params = {"q": name, "per_page": "5"}
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GekOsint-Bot"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        with httpx.Client(timeout=12.0) as c:
            r = c.get(url, params=params, headers=headers)
            if r.status_code != 200:
                return []
            items = r.json().get("items", [])
            out = []
            for it in items[:5]:
                login = it.get("login", "")
                html = it.get("html_url", "")
                s = _score(name, login)
                out.append({"site": "GitHub", "title": login, "url": html, "confidence": s})
            return out
    except Exception:
        return []

def _keybase_search(name):
    try:
        with httpx.Client(headers=_HEADERS, timeout=12.0) as c:
            r = c.get("https://keybase.io/_/api/1.0/user/lookup.json", params={"search": name, "num_wanted": "10"})
            if r.status_code != 200:
                return []
            them = r.json().get("them", []) or []
            out = []
            for t in them[:5]:
                basics = t.get("basics", {}) if isinstance(t, dict) else {}
                uname = basics.get("username", "")
                fname = basics.get("full_name", "")
                title = fname or uname
                s = _score(name, title)
                out.append({"site": "Keybase", "title": title, "url": f"https://keybase.io/{uname}", "confidence": s})
            return out
    except Exception:
        return []

def search_person(name):
    name = name.strip()
    if not name or len(name) < 2:
        return {"query": name, "total": 0, "results": []}
    results = []
    results.extend(_github_search(name))
    results.extend(_keybase_search(name))
    for d in _SITES:
        links = _ddg_site_search(name, d, 3)
        for u in links:
            host = urllib.parse.urlparse(u).netloc
            title = host
            s = _score(name, title)
            results.append({"site": host, "title": title, "url": u, "confidence": s})
    seen = set()
    dedup = []
    for r in results:
        k = r["url"]
        if k in seen:
            continue
        seen.add(k)
        dedup.append(r)
    dedup.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    top = dedup[:20]
    return {"query": name, "total": len(dedup), "results": top}
