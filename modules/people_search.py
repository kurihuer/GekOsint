
import requests
import re
import concurrent.futures
import time
import unicodedata
from config import logger

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}

_CACHE = {}
_TTL  = 600


def _normalize(text):
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def generate_username_variants(name, surname):
    n  = _normalize(name).replace(' ', '')
    s  = _normalize(surname).replace(' ', '')
    n1 = n[0] if n else ''
    s1 = s[0] if s else ''
    variants = list({
        f"{n}{s}",
        f"{n}.{s}",
        f"{n}_{s}",
        f"{n1}{s}",
        f"{n}.{s1}",
        f"{n}{s1}",
        f"{s}{n}",
        f"{s}.{n}",
        f"{s}_{n}",
        f"{s1}{n}",
        f"{n}-{s}",
        f"{n}{s[:4]}",
        f"{s}{n[:3]}",
        f"{n[:4]}{s[:4]}",
    })
    return [v for v in variants if len(v) >= 3]


SOCIAL_SITES = {
    "Instagram":   "https://instagram.com/{}",
    "Twitter/X":   "https://x.com/{}",
    "Facebook":    "https://facebook.com/{}",
    "TikTok":      "https://tiktok.com/@{}",
    "Reddit":      "https://reddit.com/user/{}",
    "LinkedIn":    "https://linkedin.com/in/{}",
    "GitHub":      "https://github.com/{}",
    "Telegram":    "https://t.me/{}",
    "Pinterest":   "https://pinterest.com/{}",
    "Twitch":      "https://twitch.tv/{}",
    "Spotify":     "https://open.spotify.com/user/{}",
    "SoundCloud":  "https://soundcloud.com/{}",
    "Medium":      "https://medium.com/@{}",
    "Linktree":    "https://linktr.ee/{}",
    "Threads":     "https://www.threads.net/@{}",
    "Gravatar":    "https://en.gravatar.com/{}",
    "Keybase":     "https://keybase.io/{}",
    "Patreon":     "https://www.patreon.com/{}",
    "Behance":     "https://www.behance.net/{}",
    "Dribbble":    "https://dribbble.com/{}",
}

NOT_FOUND_PATTERNS = [
    "page not found", "user not found", "profile not found",
    "doesn't exist", "no longer exists", "isn't available",
    "404", "no results", "hmm...this page", "sorry, this page",
    "this account doesn't exist", "page doesn't exist",
    "nothing here", "user not available", "cuenta no disponible",
    "we couldn't find", "no encontramos", "usuario no encontrado",
]


def _check_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if r.status_code == 404:
            return False
        if r.status_code == 200:
            txt = r.text.lower()[:3000]
            return not any(p in txt for p in NOT_FOUND_PATTERNS)
    except Exception:
        pass
    return False


def _search_social_for_variant(variant):
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = {
            ex.submit(_check_url, tmpl.format(variant)): (site, tmpl.format(variant))
            for site, tmpl in SOCIAL_SITES.items()
        }
        for future in concurrent.futures.as_completed(futures, timeout=20):
            site, url = futures[future]
            try:
                if future.result():
                    found.append({"site": site, "url": url, "username": variant})
            except Exception:
                pass
    return found


def search_social_profiles(name, surname):
    variants  = generate_username_variants(name, surname)
    all_found = []
    seen_urls = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_search_social_for_variant, v): v for v in variants[:8]}
        for fut in concurrent.futures.as_completed(futures, timeout=60):
            try:
                results = fut.result()
                for r in results:
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_found.append(r)
            except Exception:
                pass

    all_found.sort(key=lambda x: x["site"])
    return all_found


def _search_pipl_links(full_name):
    encoded = requests.utils.quote(full_name)
    return {
        "Pipl":          f"https://pipl.com/search/?q={encoded}",
        "Spokeo":        f"https://www.spokeo.com/search?q={encoded}",
        "BeenVerified":  f"https://www.beenverified.com/people/{encoded.replace('%20', '-')}",
        "Intelius":      f"https://www.intelius.com/people-search/results/?firstName={requests.utils.quote(name)}&lastName={requests.utils.quote(surname)}" if False else f"https://www.intelius.com/search/people/name/{encoded}/",
        "FastPeopleSearch": f"https://www.fastpeoplesearch.com/name/{encoded.replace('%20', '-')}",
        "TruePeopleSearch": f"https://www.truepeoplesearch.com/results?name={encoded}",
        "WhitePages":    f"https://www.whitepages.com/name/{encoded.replace('%20', '+')}",
        "192.com":       f"https://www.192.com/people/find/{encoded.replace('%20', '-')}/",
        "PeekYou":       f"https://www.peekyou.com/{encoded.replace('%20', '_')}",
    }


def _google_dorks(full_name, name, surname):
    q_full    = requests.utils.quote(f'"{full_name}"')
    q_social  = requests.utils.quote(f'"{full_name}" site:linkedin.com OR site:facebook.com OR site:instagram.com')
    q_email   = requests.utils.quote(f'"{full_name}" email OR correo OR "@"')
    q_phone   = requests.utils.quote(f'"{full_name}" telefono OR phone OR celular')
    q_news    = requests.utils.quote(f'"{full_name}" site:news.google.com OR inurl:noticias')
    return {
        "Busqueda general":   f"https://www.google.com/search?q={q_full}",
        "Redes sociales":     f"https://www.google.com/search?q={q_social}",
        "Email/Correo":       f"https://www.google.com/search?q={q_email}",
        "Telefono":           f"https://www.google.com/search?q={q_phone}",
        "Noticias":           f"https://www.google.com/search?q={q_news}",
        "Bing":               f"https://www.bing.com/search?q={requests.utils.quote(full_name)}",
        "DuckDuckGo":         f"https://duckduckgo.com/?q={requests.utils.quote(full_name)}",
    }


def _check_linkedin(name, surname):
    result = {"found": False, "profiles": []}
    try:
        search_url = (
            f"https://www.linkedin.com/pub/dir/{requests.utils.quote(name)}"
            f"/{requests.utils.quote(surname)}"
        )
        r = requests.get(search_url, headers=HEADERS, timeout=8, allow_redirects=True)
        if r.status_code == 200 and "profile-card" in r.text.lower():
            result["found"] = True
            matches = re.findall(r'href="(https://www\.linkedin\.com/in/[^"?]+)"', r.text)
            result["profiles"] = list(set(matches))[:5]
    except Exception as e:
        logger.debug(f"LinkedIn search error: {e}")
    return result


def _check_facebook(full_name):
    result = {"found": False, "url": ""}
    try:
        search_url = f"https://www.facebook.com/public/{requests.utils.quote(full_name.replace(' ', '-'))}"
        r = requests.get(search_url, headers=HEADERS, timeout=8, allow_redirects=True)
        if r.status_code == 200 and full_name.lower().split()[0] in r.text.lower():
            result["found"] = True
            result["url"]   = search_url
    except Exception as e:
        logger.debug(f"Facebook search error: {e}")
    return result


def search_people(full_input):
    parts = full_input.strip().split()
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

    social_profiles = search_social_profiles(name, surname)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut_li = ex.submit(_check_linkedin, name, surname)
        fut_fb = ex.submit(_check_facebook, full)
        try:    linkedin = fut_li.result(timeout=12)
        except: linkedin = {"found": False, "profiles": []}
        try:    facebook = fut_fb.result(timeout=12)
        except: facebook = {"found": False, "url": ""}

    result = {
        "full_name":       full,
        "name":            name,
        "surname":         surname,
        "variants_checked": generate_username_variants(name, surname)[:8],
        "social_profiles": social_profiles,
        "linkedin":        linkedin,
        "facebook":        facebook,
        "osint_links":     _pipl_links(full),
        "dorks":           _google_dorks(full, name, surname),
    }

    _CACHE[ck] = (now, result)
    return result


def _pipl_links(full_name):
    encoded = requests.utils.quote(full_name)
    parts   = full_name.split()
    fname   = requests.utils.quote(parts[0]) if parts else ""
    lname   = requests.utils.quote(' '.join(parts[1:])) if len(parts) > 1 else ""
    return {
        "Pipl":             f"https://pipl.com/search/?q={encoded}",
        "Spokeo":           f"https://www.spokeo.com/search?q={encoded}",
        "BeenVerified":     f"https://www.beenverified.com/people/{encoded.replace('%20', '-')}",
        "FastPeopleSearch": f"https://www.fastpeoplesearch.com/name/{encoded.replace('%20', '-')}",
        "TruePeopleSearch": f"https://www.truepeoplesearch.com/results?name={encoded}",
        "WhitePages":       f"https://www.whitepages.com/name/{encoded.replace('%20', '+')}",
        "PeekYou":          f"https://www.peekyou.com/{encoded.replace('%20', '_')}",
        "Intelius":         f"https://www.intelius.com/search/people/name/{encoded}/",
        "PimEyes (cara)":   "https://pimeyes.com/en",
    }
