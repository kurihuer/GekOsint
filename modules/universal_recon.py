# -*- coding: utf-8 -*-
"""
Universal Recon - Módulo maestro de OSINT.

Detecta automáticamente el tipo de input (email, teléfono, username, IP, nombre)
y ejecuta TODOS los módulos relevantes en paralelo para generar un reporte
completo de perfil OSINT. Ideal para demostraciones de seguridad.

Nota: este módulo intenta usar los formateadores existentes para producir
salidas ricas por sección (IP, Teléfono, Email, etc.), consolidando todo
en un único mensaje HTML para Telegram.
"""

import re
import asyncio
from datetime import datetime
from html import escape

from config import PROXY_URL

# Formateadores de salida HTML (Telegram)
from ui.templates import (
    format_ip_result,
    format_phone_result,
    format_username_result,
    format_email_result,
    format_people_result,
    format_dns_result,
    format_github_recon,
    format_ig_osint,
    format_gmail_osint,
    format_fb_osint,
    format_email_recon,
    format_tiktok_osint,
)

try:
    import phonenumbers
    from phonenumbers import NumberParseException
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

# Proxies para scrapers web
_PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _is_probable_person_name(text: str) -> bool:
    words = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ]+", text or "")
    return 2 <= len(words) <= 4 and len((text or "").strip()) <= 60


def _clean_username_candidate(value: str | None) -> str | None:
    text = (value or "").strip().lstrip("@")
    if not text or " " in text or "@" in text or "." in text and "/" in text:
        return None
    if re.match(r"^[a-zA-Z0-9._-]{3,30}$", text):
        return text
    return None


def _merge_username_results(current: dict | None, new: dict | None) -> dict:
    current = current or {}
    new = new or {}

    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source in (current.get("found") or [], new.get("found") or []):
        if not isinstance(source, (list, tuple)) or len(source) != 2:
            continue
        key = (str(source[0]), str(source[1]))
        if key not in seen:
            seen.add(key)
            found.append(key)

    telegram = current.get("telegram") or new.get("telegram")
    if isinstance(new.get("telegram"), dict) and new["telegram"].get("exists"):
        telegram = new["telegram"]

    return {"found": found, "telegram": telegram}


def _append_unique(values: list[str], candidate: str | None, *, lower: bool = True) -> None:
    text = (candidate or "").strip()
    if not text:
        return
    norm = text.lower() if lower else text
    if all((v.lower() if lower else v) != norm for v in values):
        values.append(text)


def _collect_identity_signals(data: dict, input_text: str, input_type: str) -> dict:
    names: list[str] = []
    usernames: list[str] = []
    emails: list[str] = []
    phones: list[str] = []
    domains: list[str] = []
    profile_urls: list[str] = []

    if input_type == "name":
        _append_unique(names, input_text, lower=False)
    elif input_type == "username":
        _append_unique(usernames, input_text)
    elif input_type == "email":
        _append_unique(emails, input_text)
        _append_unique(domains, input_text.split("@", 1)[-1])
    elif input_type == "phone":
        _append_unique(phones, input_text, lower=False)
    elif input_type == "domain":
        _append_unique(domains, input_text)

    phone_intel = data.get("phone_intel") or {}
    if isinstance(phone_intel, dict):
        _append_unique(names, phone_intel.get("caller_name"), lower=False)
        _append_unique(phones, phone_intel.get("number"), lower=False)

    username_search = data.get("username_search") or {}
    if isinstance(username_search, dict):
        tg = username_search.get("telegram") or {}
        _append_unique(usernames, tg.get("username"))
        _append_unique(profile_urls, tg.get("url"), lower=False)

    gmail = data.get("gmail_osint") or {}
    if isinstance(gmail, dict):
        rec = gmail.get("recovery") or {}
        dom = gmail.get("domain") or {}
        _append_unique(phones, rec.get("obfuscated_phone"), lower=False)
        _append_unique(emails, rec.get("obfuscated_email"))
        _append_unique(domains, dom.get("domain"))

    fb = data.get("fb_osint") or {}
    if isinstance(fb, dict):
        _append_unique(names, fb.get("display_name"), lower=False)
        if fb.get("user_id"):
            _append_unique(profile_urls, f"https://www.facebook.com/{fb['user_id']}", lower=False)

    ig = data.get("ig_osint") or {}
    if isinstance(ig, dict):
        profile = ig.get("profile") or {}
        recovery = ig.get("recovery") or {}
        _append_unique(names, profile.get("full_name"), lower=False)
        _append_unique(usernames, profile.get("username"))
        _append_unique(emails, recovery.get("obfuscated_email"))
        _append_unique(phones, recovery.get("obfuscated_phone"), lower=False)
        if profile.get("username"):
            _append_unique(profile_urls, f"https://www.instagram.com/{profile['username']}/", lower=False)

    gh = data.get("github_recon") or {}
    if isinstance(gh, dict):
        profile = gh.get("profile") or {}
        _append_unique(usernames, gh.get("resolved_username"))
        _append_unique(usernames, profile.get("login"))
        _append_unique(names, profile.get("name"), lower=False)
        _append_unique(emails, profile.get("email"))
        _append_unique(profile_urls, profile.get("html_url"), lower=False)
        for leaked_email in list((gh.get("leaked_emails") or {}).keys())[:5]:
            _append_unique(emails, leaked_email)

    people = data.get("people_search") or {}
    if isinstance(people, dict):
        _append_unique(names, people.get("full_name"), lower=False)
        for profile in (people.get("social_profiles") or [])[:5]:
            _append_unique(usernames, profile.get("username"))
            _append_unique(profile_urls, profile.get("url"), lower=False)

    email_analysis = data.get("email_analysis") or {}
    if isinstance(email_analysis, dict):
        _append_unique(emails, email_analysis.get("email"))
        _append_unique(domains, email_analysis.get("domain"))

    dns = data.get("dns_lookup") or {}
    if isinstance(dns, dict):
        _append_unique(domains, dns.get("domain"))

    tiktok = data.get("tiktok_osint") or {}
    if isinstance(tiktok, dict):
        _append_unique(usernames, tiktok.get("username"))
        if tiktok.get("username"):
            _append_unique(profile_urls, f"https://www.tiktok.com/@{tiktok['username']}", lower=False)

    return {
        "names": names[:6],
        "usernames": usernames[:8],
        "emails": emails[:8],
        "phones": phones[:6],
        "domains": domains[:6],
        "profile_urls": profile_urls[:8],
    }


def _detect_input_type(text: str) -> str:
    """Detecta el tipo de input: phone, email, ip, username, name, domain."""
    text = text.strip().lower()
    
    # Email
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', text):
        return "email"
    
    # IP
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
        parts = text.split('.')
        if all(0 <= int(p) <= 255 for p in parts):
            return "ip"
    
    # Teléfono (con o sin código de país)
    digits = re.sub(r'\D', '', text)
    if len(digits) >= 7 and len(digits) <= 15:
        if HAS_PHONENUMBERS:
            try:
                parsed = phonenumbers.parse(text, None)
                if phonenumbers.is_valid_number(parsed):
                    return "phone"
            except Exception:
                pass
    
    # URL/Dominio
    if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text) and '.' in text:
        return "domain"
    
    # Nombre (2+ palabras, solo letras/espacios)
    words = re.findall(r'[a-zA-ZáéíóúñÁÉÍÓÚÑ]+', text)
    if len(words) >= 2 and len(words) <= 4 and len(text) <= 60:
        return "name"
    
    if len(text) >= 3 and len(text) <= 30 and not re.match(r'^[a-f0-9]{32,}$', text):
        return "username"
    
    return "unknown"


async def _parallel_modules(
    *,
    user_id: int = 0,
    phone: str | None = None,
    email: str | None = None,
    username: str | None = None,
    ip: str | None = None,
    name: str | None = None,
    domain: str | None = None,
) -> dict:
    """Ejecuta módulos en paralelo según el tipo de input.

    Devuelve un dict con claves por módulo (ip_lookup, phone_intel, email_analysis, etc.).
    """
    results = {}
    
    async def run_with_name(coro, name: str):
        try:
            result = await coro
            results[name] = result
        except Exception as e:
            results[name] = {"error": str(e)}
    
    tasks = []
    
    if email:
        tasks.append(run_with_name(_fetch_email_basic(email), "email_analysis"))
        tasks.append(run_with_name(_fetch_email_recon(email), "email_recon"))
        tasks.append(run_with_name(_fetch_dns_info(email.split("@", 1)[-1]), "dns_lookup"))
        # Gmail / Google OSINT (respetar rate limit si está disponible)
        try:
            from modules.gmail_osint import gmail_lookup, check_gmail_rate_limit
            allowed, _ = check_gmail_rate_limit(user_id) if user_id else (True, "")
            if allowed:
                async def _gmail():
                    try:
                        return await gmail_lookup(email)
                    except Exception as e:
                        return {"error": str(e)}
                tasks.append(run_with_name(_gmail(), "gmail_osint"))
        except Exception:
            pass

        # Facebook OSINT también acepta email
        try:
            from modules.fb_osint import fb_lookup, check_fb_rate_limit
            allowed, _ = check_fb_rate_limit(user_id) if user_id else (True, "")
            if allowed:
                async def _fb_from_email():
                    try:
                        return await fb_lookup(email)
                    except Exception as e:
                        return {"error": str(e)}
                tasks.append(run_with_name(_fb_from_email(), "fb_osint"))
        except Exception:
            pass

        # GitHub acepta email público como entrada
        async def _gh_from_email():
            try:
                from modules.github_recon import github_recon
                return await github_recon(email)
            except Exception as e:
                return {"error": str(e)}
        tasks.append(run_with_name(_gh_from_email(), "github_recon"))
    
    if ip:
        tasks.append(run_with_name(_fetch_ip_info(ip), "ip_lookup"))
    
    if phone:
        tasks.append(run_with_name(_fetch_phone_intel(phone), "phone_intel"))
        # WhatsApp OSINT
        try:
            from modules.whatsapp_osint import analyze_whatsapp
            async def _wa():
                try:
                    from asyncio import to_thread
                    return await to_thread(analyze_whatsapp, phone)
                except Exception as e:
                    return {"error": str(e)}
            tasks.append(run_with_name(_wa(), "whatsapp_osint"))
        except Exception:
            pass

        # Facebook OSINT también acepta teléfono
        try:
            from modules.fb_osint import fb_lookup, check_fb_rate_limit
            allowed, _ = check_fb_rate_limit(user_id) if user_id else (True, "")
            if allowed:
                async def _fb_from_phone():
                    try:
                        return await fb_lookup(phone)
                    except Exception as e:
                        return {"error": str(e)}
                tasks.append(run_with_name(_fb_from_phone(), "fb_osint"))
        except Exception:
            pass
    
    search_target = None
    if username:
        search_target = username
        tasks.append(run_with_name(_fetch_username_search(username), "username_search"))
    elif email:
        uname = email.split('@')[0]
        if uname and len(uname) >= 3:
            search_target = uname
            tasks.append(run_with_name(_fetch_username_search(uname), "username_search"))

    if name:
        tasks.append(run_with_name(_fetch_people_search(name), "people_search"))

    if search_target and len(search_target) >= 3:
        # TikTok (respetar rate limit si está disponible)
        try:
            from modules.tiktok_osint import check_tiktok_rate_limit
            allowed, _ = check_tiktok_rate_limit(user_id) if user_id else (True, "")
            if allowed:
                tasks.append(run_with_name(_fetch_tiktok(search_target), "tiktok_osint"))
        except Exception:
            tasks.append(run_with_name(_fetch_tiktok(search_target), "tiktok_osint"))

        if not email:
            # GitHub Recon (seguro)
            async def _gh():
                try:
                    from modules.github_recon import github_recon
                    return await github_recon(search_target)
                except Exception as e:
                    return {"error": str(e)}
            tasks.append(run_with_name(_gh(), "github_recon"))

            # Facebook también admite username público
            try:
                from modules.fb_osint import fb_lookup, check_fb_rate_limit
                allowed, _ = check_fb_rate_limit(user_id) if user_id else (True, "")
                if allowed:
                    async def _fb_from_username():
                        try:
                            return await fb_lookup(search_target)
                        except Exception as e:
                            return {"error": str(e)}
                    tasks.append(run_with_name(_fb_from_username(), "fb_osint"))
            except Exception:
                pass

        # Instagram (si hay sesión y respeta rate limit)
        try:
            from modules.ig_osint import ig_lookup, check_ig_rate_limit
            allowed, _ = check_ig_rate_limit(user_id) if user_id else (True, "")
            if allowed:
                async def _ig():
                    try:
                        return await ig_lookup(search_target)
                    except Exception as e:
                        return {"error": str(e)}
                tasks.append(run_with_name(_ig(), "ig_osint"))
        except Exception:
            pass

    # Dominio
    if domain:
        async def _dns():
            try:
                from modules.dns_lookup import get_dns_info
                from asyncio import to_thread
                return await to_thread(get_dns_info, domain)
            except Exception as e:
                return {"error": str(e)}
        tasks.append(run_with_name(_dns(), "dns_lookup"))

    await asyncio.gather(*tasks)

    # Segunda pasada: pivote por nombre derivado.
    derived_name = None
    for candidate in (
        ((results.get("phone_intel") or {}).get("caller_name") if isinstance(results.get("phone_intel"), dict) else None),
        ((results.get("fb_osint") or {}).get("display_name") if isinstance(results.get("fb_osint"), dict) else None),
        (((results.get("ig_osint") or {}).get("profile") or {}).get("full_name") if isinstance(results.get("ig_osint"), dict) else None),
        (((results.get("github_recon") or {}).get("profile") or {}).get("name") if isinstance(results.get("github_recon"), dict) else None),
    ):
        if _is_probable_person_name(candidate or ""):
            derived_name = candidate.strip()
            break

    if derived_name:
        results["derived_name"] = derived_name
        if "people_search" not in results or not (results.get("people_search") or {}).get("social_profiles"):
            results["people_search"] = await _fetch_people_search(derived_name)

    # Segunda pasada: si GitHub resolvió un username mejor que el alias del mail,
    # úsalo para completar módulos sociales.
    derived_username = None
    gh = results.get("github_recon") if isinstance(results.get("github_recon"), dict) else {}
    gh_profile = (gh or {}).get("profile") or {}
    for candidate in (
        (gh or {}).get("resolved_username"),
        gh_profile.get("login"),
    ):
        normalized = _clean_username_candidate(candidate)
        if normalized and normalized != (search_target or ""):
            derived_username = normalized
            break

    if derived_username:
        results["derived_username"] = derived_username
        derived_username_result = await _fetch_username_search(derived_username)
        results["username_search"] = _merge_username_results(results.get("username_search"), derived_username_result)

        if not isinstance(results.get("tiktok_osint"), dict) or results["tiktok_osint"].get("error"):
            try:
                from modules.tiktok_osint import check_tiktok_rate_limit
                allowed, _ = check_tiktok_rate_limit(user_id) if user_id else (True, "")
                if allowed:
                    results["tiktok_osint"] = await _fetch_tiktok(derived_username)
            except Exception:
                pass

        if not isinstance(results.get("ig_osint"), dict) or not results["ig_osint"].get("found"):
            try:
                from modules.ig_osint import check_ig_rate_limit
                allowed, _ = check_ig_rate_limit(user_id) if user_id else (True, "")
                if allowed:
                    async def _ig_second_pass():
                        from modules.ig_osint import ig_lookup
                        return await ig_lookup(derived_username)
                    results["ig_osint"] = await _ig_second_pass()
            except Exception:
                pass

        if not isinstance(results.get("fb_osint"), dict) or not results["fb_osint"].get("found"):
            try:
                from modules.fb_osint import check_fb_rate_limit, fb_lookup
                allowed, _ = check_fb_rate_limit(user_id) if user_id else (True, "")
                if allowed:
                    results["fb_osint"] = await fb_lookup(derived_username)
            except Exception:
                pass

    return results


# Funciones de fetch para cada módulo (versión async)

async def _fetch_ip_info(ip: str) -> dict:
    """Fetch IP info usando módulo existente."""
    try:
        from modules.ip_lookup import get_ip_info
        return await asyncio.to_thread(get_ip_info, ip)
    except Exception as e:
        return {"error": str(e)}


async def _fetch_phone_intel(phone: str) -> dict:
    """Fetch phone intel usando módulo existente."""
    try:
        from modules.phone_lookup import analyze_phone
        return await asyncio.to_thread(analyze_phone, phone)
    except Exception as e:
        return {"error": str(e)}


async def _fetch_email_basic(email: str) -> dict:
    """Fetch email analysis usando módulo existente."""
    try:
        from modules.email_analysis import analyze_email
        return await asyncio.to_thread(analyze_email, email)
    except Exception as e:
        return {"error": str(e)}


async def _fetch_email_recon(email: str) -> dict:
    """Fetch email recon usando módulo existente."""
    try:
        from modules.email_recon import email_recon
        return await email_recon(email)
    except Exception as e:
        return {"error": str(e)}


async def _fetch_username_search(username: str) -> dict:
    """Fetch username search usando módulo existente."""
    try:
        from modules.username_search import search_username
        found, tg = await asyncio.to_thread(search_username, username)
        return {"found": found, "telegram": tg}
    except Exception as e:
        return {"error": str(e)}


async def _fetch_people_search(name: str) -> dict:
    """Fetch people search usando módulo existente."""
    try:
        from modules.people_search import search_people
        return await asyncio.to_thread(search_people, name)
    except Exception as e:
        return {"error": str(e)}


async def _fetch_tiktok(username: str) -> dict:
    """Fetch TikTok OSINT usando módulo existente."""
    try:
        from modules.tiktok_osint import tiktok_lookup
        return await tiktok_lookup(username)
    except Exception as e:
        return {"error": str(e)}


async def _fetch_dns_info(domain: str) -> dict:
    try:
        from modules.dns_lookup import get_dns_info
        return await asyncio.to_thread(get_dns_info, domain)
    except Exception as e:
        return {"error": str(e)}


def format_universal_report(data: dict, input_text: str, input_type: str) -> str:
    """Formatea un reporte profesional con todos los resultados.

    Usa formateadores por módulo cuando sea posible, para entregar
    salidas ricas y homogéneas.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header = (
        f"🔍 <b>UNIVERSAL OSINT RECON</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Input:</b> <code>{input_text}</code>\n"
        f"📋 <b>Detectado como:</b> {input_type.upper()}\n"
        f"🕐 <b>Fecha:</b> {timestamp}\n\n"
    )

    sections: list[str] = []
    ok_modules: list[str] = []
    error_modules: list[str] = []

    def track_ok(name: str):
        if name not in ok_modules:
            ok_modules.append(name)

    def track_error(name: str):
        if name not in error_modules:
            error_modules.append(name)
    
    # Email Analysis
    if "email_analysis" in data and isinstance(data.get("email_analysis"), dict):
        ea = data["email_analysis"]
        if "error" not in ea:
            try:
                sections.append(format_email_result(ea))
                track_ok("Email Analysis")
            except Exception:
                pass
        else:
            track_error("Email Analysis")
    
    # Email Recon multi-plataforma
    if "email_recon" in data and isinstance(data.get("email_recon"), dict):
        er = data["email_recon"]
        if "error" not in er:
            try:
                sections.append(format_email_recon(er))
                track_ok("Email Recon")
            except Exception:
                pass
        else:
            track_error("Email Recon")

    if "gmail_osint" in data and isinstance(data.get("gmail_osint"), dict):
        gd = data["gmail_osint"]
        if "error" not in gd:
            try:
                sections.append(format_gmail_osint(gd))
                track_ok("Gmail OSINT")
            except Exception:
                pass
        else:
            track_error("Gmail OSINT")
    
    # IP Lookup
    if "ip_lookup" in data and isinstance(data.get("ip_lookup"), dict):
        ipd = data["ip_lookup"]
        if "error" not in ipd:
            try:
                sections.append(format_ip_result(ipd))
                track_ok("IP Lookup")
            except Exception:
                pass
        else:
            track_error("IP Lookup")
    
    # Phone Intel
    if "phone_intel" in data and isinstance(data.get("phone_intel"), dict):
        pd = data["phone_intel"]
        if "error" not in pd:
            try:
                sections.append(format_phone_result(pd))
                track_ok("Phone Intelligence")
            except Exception:
                pass
        else:
            track_error("Phone Intelligence")
    if "whatsapp_osint" in data and isinstance(data.get("whatsapp_osint"), dict):
        try:
            from ui.templates import format_whatsapp_result
            sections.append(format_whatsapp_result(data["whatsapp_osint"]))
            track_ok("WhatsApp OSINT")
        except Exception:
            pass
    
    # Username Search
    if "username_search" in data and isinstance(data.get("username_search"), dict):
        ud = data["username_search"]
        if "error" not in ud:
            try:
                uname = (ud.get("telegram") or {}).get("username") or input_text
                sections.append(format_username_result(uname, ud.get("found", []), ud.get("telegram")))
                track_ok("Username Search")
            except Exception:
                pass
        else:
            track_error("Username Search")
    if "github_recon" in data and isinstance(data.get("github_recon"), dict):
        try:
            sections.append(format_github_recon(data["github_recon"]))
            track_ok("GitHub Recon")
        except Exception:
            pass
    if "ig_osint" in data and isinstance(data.get("ig_osint"), dict):
        try:
            sections.append(format_ig_osint(data["ig_osint"]))
            track_ok("IG OSINT")
        except Exception:
            pass
    if "fb_osint" in data and isinstance(data.get("fb_osint"), dict):
        try:
            sections.append(format_fb_osint(data["fb_osint"]))
            track_ok("FB OSINT")
        except Exception:
            pass
    
    # People Search
    if "people_search" in data and isinstance(data.get("people_search"), dict):
        ps = data["people_search"]
        if "error" not in ps:
            try:
                sections.append(format_people_result(ps))
                track_ok("People Search")
            except Exception:
                pass
        else:
            track_error("People Search")
    
    # TikTok OSINT
    if "tiktok_osint" in data and isinstance(data.get("tiktok_osint"), dict):
        tt = data["tiktok_osint"]
        if "error" not in tt:
            try:
                sections.append(format_tiktok_osint(tt))
                track_ok("TikTok OSINT")
            except Exception:
                pass
        else:
            track_error("TikTok OSINT")

    if "dns_lookup" in data and isinstance(data.get("dns_lookup"), dict):
        dl = data["dns_lookup"]
        if "error" not in dl:
            try:
                sections.append(format_dns_result(dl))
                track_ok("DNS Lookup")
            except Exception:
                pass
        else:
            track_error("DNS Lookup")

    summary_lines = []
    if ok_modules:
        summary_lines.append(f"✅ <b>Módulos con datos:</b> {', '.join(ok_modules)}")
    if data.get("derived_name"):
        summary_lines.append(f"🧩 <b>Pivote derivado:</b> nombre detectado <code>{data['derived_name']}</code>")
    if data.get("derived_username"):
        summary_lines.append(f"🔗 <b>Username derivado:</b> <code>@{escape(data['derived_username'])}</code>")
    if error_modules:
        summary_lines.append(f"⚠️ <b>Módulos sin respuesta útil:</b> {', '.join(error_modules)}")
    if summary_lines:
        sections.insert(0, "📊 <b>RESUMEN EJECUTIVO</b>\n" + "\n".join(summary_lines))

    identity = _collect_identity_signals(data, input_text, input_type)
    correlation_lines: list[str] = []
    if identity["names"]:
        correlation_lines.append("🧑 <b>Nombres:</b> " + " | ".join(escape(x) for x in identity["names"]))
    if identity["usernames"]:
        correlation_lines.append("👤 <b>Usernames:</b> " + " | ".join(f"<code>@{escape(x)}</code>" for x in identity["usernames"]))
    if identity["emails"]:
        correlation_lines.append("📧 <b>Emails:</b> " + " | ".join(f"<code>{escape(x)}</code>" for x in identity["emails"]))
    if identity["phones"]:
        correlation_lines.append("📱 <b>Phones:</b> " + " | ".join(f"<code>{escape(x)}</code>" for x in identity["phones"]))
    if identity["domains"]:
        correlation_lines.append("🌐 <b>Dominios:</b> " + " | ".join(f"<code>{escape(x)}</code>" for x in identity["domains"]))
    if identity["profile_urls"]:
        profile_parts = []
        for idx, url in enumerate(identity["profile_urls"][:6], 1):
            profile_parts.append(f"<a href='{escape(url, quote=True)}'>Perfil {idx}</a>")
        correlation_lines.append("🔎 <b>Perfiles:</b> " + " | ".join(profile_parts))
    if correlation_lines:
        sections.insert(1 if summary_lines else 0, "🧠 <b>CORRELACIÓN DE IDENTIDADES</b>\n" + "\n".join(correlation_lines))
    
    body = "\n\n".join(s for s in sections if s)
    footer = (
        f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚠️ Reporte generado para fines de concientización en ciberseguridad</i>"
    )
    return header + (body or "Sin datos adicionales disponibles.") + footer


def universal_recon(text: str) -> str:
    """Devuelve el tipo detectado para compatibilidad retro."""
    return _detect_input_type(text)


async def run_universal(text: str, user_id: int = 0) -> tuple[str, dict, str]:
    """
    Ejecuta Universal Recon end-to-end.
    Retorna: (input_type, results_dict, html)
    """
    input_type = _detect_input_type(text)

    # Determinar dominio cuando aplica
    dom = None
    if input_type == "domain":
        dom = text.strip().lower()

    results = await _parallel_modules(
        user_id=user_id,
        phone=text if input_type == "phone" else None,
        email=text if input_type == "email" else None,
        username=text if input_type == "username" else None,
        ip=text if input_type == "ip" else None,
        name=text if input_type == "name" else None,
        domain=dom,
    )
    html = format_universal_report(results, text, input_type)
    return input_type, results, html
