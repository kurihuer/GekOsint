
import requests
import concurrent.futures
from config import logger

SITES = {
    "GitHub": "https://github.com/{}",
    "Instagram": "https://instagram.com/{}",
    "Twitter/X": "https://x.com/{}",
    "Facebook": "https://facebook.com/{}",
    "TikTok": "https://tiktok.com/@{}",
    "Telegram": "https://t.me/{}",
    "Reddit": "https://reddit.com/user/{}",
    "Pinterest": "https://pinterest.com/{}",
    "Spotify": "https://open.spotify.com/user/{}",
    "Steam": "https://steamcommunity.com/id/{}",
    "Roblox": "https://www.roblox.com/user.aspx?username={}",
    "Twitch": "https://twitch.tv/{}",
    "SoundCloud": "https://soundcloud.com/{}",
    "Medium": "https://medium.com/@{}",
    "Pornhub": "https://pornhub.com/users/{}",
    "Vimeo": "https://vimeo.com/{}",
    "GitLab": "https://gitlab.com/{}",
    "Dev.to": "https://dev.to/{}",
    "About.me": "https://about.me/{}",
    "Freelancer": "https://www.freelancer.com/u/{}"
}

def check_site(site, url_template, username):
    url = url_template.format(username)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        r = requests.get(url, headers=headers, timeout=5)
        
        # Filtros de falsos positivos básicos
        if r.status_code == 200:
            if "not found" in r.text.lower() or "page doesn't exist" in r.text.lower():
                return None
            return (site, url)
    except:
        pass
    return None

def search_username(username):
    """Busca username en 20+ sitios en paralelo"""
    found = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_site, site, url, username) for site, url in SITES.items()]
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                found.append(result)
                
    return found
