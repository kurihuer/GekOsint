import requests
import concurrent.futures
import re
from config import logger, BOT_TOKEN
import time

SITES = {
    "Instagram": "https://instagram.com/{}",
    "Twitter/X": "https://x.com/{}",
    "Facebook": "https://facebook.com/{}",
    "TikTok": "https://tiktok.com/@{}",
    "Reddit": "https://reddit.com/user/{}",
    "Pinterest": "https://pinterest.com/{}",
    "LinkedIn": "https://linkedin.com/in/{}",
    "Snapchat": "https://www.snapchat.com/add/{}",
    "Tumblr": "https://{}.tumblr.com",
    "GitHub": "https://github.com/{}",
    "GitLab": "https://gitlab.com/{}",
    "Dev.to": "https://dev.to/{}",
    "Stack Overflow": "https://stackoverflow.com/users/{}",
    "Codepen": "https://codepen.io/{}",
    "Replit": "https://replit.com/@{}",
    "HackerRank": "https://www.hackerrank.com/{}",
    "LeetCode": "https://leetcode.com/{}",
    "Kaggle": "https://www.kaggle.com/{}",
    "npm": "https://www.npmjs.com/~{}",
    "PyPI": "https://pypi.org/user/{}",
    "Docker Hub": "https://hub.docker.com/u/{}",
    "Bitbucket": "https://bitbucket.org/{}",
    "Steam": "https://steamcommunity.com/id/{}",
    "Roblox": "https://www.roblox.com/user.aspx?username={}",
    "Twitch": "https://twitch.tv/{}",
    "Xbox": "https://account.xbox.com/profile?gamertag={}",
    "Chess.com": "https://www.chess.com/member/{}",
    "Lichess": "https://lichess.org/@/{}",
    "Spotify": "https://open.spotify.com/user/{}",
    "SoundCloud": "https://soundcloud.com/{}",
    "Vimeo": "https://vimeo.com/{}",
    "Flickr": "https://www.flickr.com/people/{}",
    "Dailymotion": "https://www.dailymotion.com/{}",
    "Bandcamp": "https://{}.bandcamp.com",
    "Last.fm": "https://www.last.fm/user/{}",
    "Medium": "https://medium.com/@{}",
    "WordPress": "https://{}.wordpress.com",
    "Blogger": "https://{}.blogspot.com",
    "Substack": "https://{}.substack.com",
    "About.me": "https://about.me/{}",
    "Quora": "https://quora.com/profile/{}",
    "Gravatar": "https://en.gravatar.com/{}",
    "Keybase": "https://keybase.io/{}",
    "Patreon": "https://www.patreon.com/{}",
    "BuyMeACoffee": "https://www.buymeacoffee.com/{}",
    "Ko-fi": "https://ko-fi.com/{}",
    "HackerNews": "https://news.ycombinator.com/user?id={}",
    "ProductHunt": "https://www.producthunt.com/@{}",
    "Dribbble": "https://dribbble.com/{}",
    "Behance": "https://www.behance.net/{}",
    "500px": "https://500px.com/p/{}",
    "Fiverr": "https://www.fiverr.com/{}",
    "OpenSea": "https://opensea.io/{}",
    "Linktree": "https://linktr.ee/{}",
    "Telegram": "https://t.me/{}",
    "Clubhouse": "https://www.clubhouse.com/@{}",
    "Mastodon": "https://mastodon.social/@{}",
    "Threads": "https://www.threads.net/@{}",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

_CACHE = {}
_TTL = 600

def get_telegram_info(username):
    result = {
        "exists": False,
        "type": None,
        "name": None,
        "bio": None,
        "username": username,
        "id": None,
        "photo": None,
        "members": None,
        "is_verified": False,
        "is_bot": False,
        "is_scam": False,
        "is_fake": False,
        "url": f"https://t.me/{username}"
    }

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getChat",
            params={"chat_id": f"@{username}"},
            timeout=10
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
                params={"chat_id": f"@{username}"},
                timeout=8
            )
            if r2.status_code == 200:
                data2 = r2.json()
                if data2.get("ok"):
                    result["members"] = data2.get("result")
        except Exception as e:
            logger.debug(f"Telegram getMemberCount error: {e}")

    if not result["exists"]:
        try:
            r3 = requests.get(
                f"https://t.me/{username}",
                timeout=10,
                headers={"User-Agent": "TelegramBot (like TwitterBot)"},
                allow_redirects=True
            )
            if r3.status_code == 200:
                html = r3.text
                if 'tgme_page_title' in html or 'og:title' in html:
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

                    if "tgme_page_extra" in html:
                        result["type"] = "Canal/Grupo"
                    else:
                        result["type"] = "Usuario/Bot"
        except Exception as e:
            logger.debug(f"Telegram scrape error: {e}")

    return result

def check_site(site, url_template, username):
    url = url_template.format(username)
    try:
        h = requests.head(url, headers=HEADERS, timeout=6, allow_redirects=True)
        if h.status_code in [200, 301, 302]:
            if h.url and h.url.rstrip('/') in [
                url_template.split('/{}')[0],
                url_template.split('/@{}')[0],
                url_template.split('/{}.')[0]
            ]:
                pass
            else:
                if h.status_code == 200:
                    return (site, url)
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            text_lower = r.text.lower()
            not_found_patterns = [
                "not found", "page doesn't exist", "doesn't exist",
                "no results", "user not found", "profile not found",
                "is available", "this page is not available", 
                "account not found", "user doesn't exist",
                "this account doesn't exist", "nothing here",
                "page not found", "sorry, this page", "hmm...this page",
                "the page you were looking for", "we couldn't find",
                "this user has not", "no user found"
            ]
            for pattern in not_found_patterns:
                if pattern in text_lower:
                    return None
            if len(r.text) < 500 and ("error" in text_lower or "404" in text_lower):
                return None
            if r.url and r.url.rstrip('/') in [
                url_template.split('/{}')[0],
                url_template.split('/@{}')[0],
                url_template.split('/{}.')[0]
            ]:
                return None
            return (site, url)
        elif r.status_code == 404:
            return None
    except requests.exceptions.Timeout:
        logger.debug(f"Timeout verificando {site}")
    except requests.exceptions.ConnectionError:
        logger.debug(f"Connection error en {site}")
    except Exception as e:
        logger.debug(f"Error verificando {site}: {e}")
    return None

def search_username(username):
    if not username or len(username) < 2:
        return [], None
    
    username = username.strip().replace('@', '')
    ck = ("user", username)
    now = int(time.time())
    cached = _CACHE.get(ck)
    if cached and now - cached[0] <= _TTL:
        return cached[1], cached[2]
    found = []
    
    telegram_data = get_telegram_info(username)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            futures = {executor.submit(check_site, site, url, username): site 
                     for site, url in SITES.items()}
            for future in concurrent.futures.as_completed(futures, timeout=45):
                try:
                    result = future.result()
                    if result:
                        found.append(result)
                except Exception as e:
                    site = futures[future]
                    logger.debug(f"Error en futuro {site}: {e}")
    except Exception as e:
        logger.error(f"Error en búsqueda de username: {e}")
    
    found.sort(key=lambda x: x[0])
    
    _CACHE[ck] = (now, found, telegram_data)
    return found, telegram_data
