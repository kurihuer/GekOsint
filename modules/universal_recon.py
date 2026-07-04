# -*- coding: utf-8 -*-
"""
Universal Recon - Módulo maestro de OSINT.

Detecta automáticamente el tipo de input (email, teléfono, username, IP, nombre)
y ejecuta TODOS los módulos relevantes en paralelo para generar un reporte
completo de perfil OSINT. Ideal para demostraciones de seguridad.
"""

import re
import asyncio
from datetime import datetime
from typing import Optional
import httpx

from config import logger, RAPIDAPI_KEY, NUMVERIFY_KEY, SHODAN_API_KEY, VT_API_KEY, ABUSEIPDB_KEY, GREYNOISE_API_KEY, PROXY_URL

try:
    import phonenumbers
    from phonenumbers import NumberParseException
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

# Proxies para scrapers web
_PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


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


async def _parallel_modules(phone: str = None, email: str = None, username: str = None, 
                            ip: str = None, name: str = None) -> dict:
    """Ejecuta módulos en paralelo según el tipo de input."""
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
    
    if ip:
        tasks.append(run_with_name(_fetch_ip_info(ip), "ip_lookup"))
    
    if phone:
        tasks.append(run_with_name(_fetch_phone_intel(phone), "phone_intel"))
    
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
        tasks.append(run_with_name(_fetch_tiktok(search_target), "tiktok_osint"))
    
    await asyncio.gather(*tasks)
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
        return email_recon(email)
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
        return tiktok_lookup(username)
    except Exception as e:
        return {"error": str(e)}


def format_universal_report(data: dict, input_text: str, input_type: str) -> str:
    """Formatea un reporte profesional con todos los resultados."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    txt = (
        f"🔍 <b>UNIVERSAL OSINT RECON</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Input:</b> <code>{input_text}</code>\n"
        f"📋 <b>Detectado como:</b> {input_type.upper()}\n"
        f"🕐 <b>Fecha:</b> {timestamp}\n\n"
    )
    
    # Email Analysis
    if "email_analysis" in data:
        email_data = data["email_analysis"]
        if "error" not in email_data:
            txt += f"📧 <b>EMAIL ANALYSIS</b>\n"
            txt += f"   🌐 Dominio: <code>{email_data.get('domain', 'N/A')}</code>\n"
            if email_data.get("leaked"):
                txt += f"   🚨 <b>Brechas:</b> {len(email_data['breaches'])} encontradas\n"
            txt += "\n"
    
    # Email Recon multi-plataforma
    if "email_recon" in data:
        recon = data["email_recon"]
        if "error" not in recon:
            found = [s for s in recon.get("services", {}).values() if s]
            txt += f"📨 <b>EMAIL RECON</b>\n"
            txt += f"   ✅ Encontrado en {len(found)} servicios\n"
            if found:
                txt += f"   📊 {', '.join(found[:5])}\n"
            txt += "\n"
    
    # IP Lookup
    if "ip_lookup" in data:
        ip_data = data["ip_lookup"]
        if "error" not in ip_data:
            txt += f"🌐 <b>IP INTELLIGENCE</b>\n"
            txt += f"   🏙️ Ubicación: {ip_data.get('city', 'N/A')}, {ip_data.get('country', 'N/A')}\n"
            txt += f"   🏢 ISP: {ip_data.get('isp', 'N/A')}\n"
            txt += f"   ⚠️ Riesgo: {ip_data.get('risk', 'N/A')} ({ip_data.get('risk_score', 0)}/100)\n"
            txt += "\n"
    
    # Phone Intel
    if "phone_intel" in data:
        phone = data["phone_intel"]
        if "error" not in phone:
            txt += f"📱 <b>PHONE INTELLIGENCE</b>\n"
            txt += f"   🌍 País: {phone.get('country', 'N/A')}\n"
            txt += f"   📡 Operadora: {phone.get('carrier', 'N/A')}\n"
            if phone.get("caller_name"):
                txt += f"   👤 Nombre: {phone['caller_name']}\n"
            if phone.get("spam", {}).get("reported"):
                txt += f"   🚨 SPAM REPORTADO\n"
            txt += "\n"
    
    # Username Search
    if "username_search" in data:
        user_data = data["username_search"]
        if "error" not in user_data and user_data.get("found"):
            txt += f"👤 <b>USERNAME SEARCH</b>\n"
            txt += f"   ✅ Encontrado en {len(user_data['found'])} plataformas\n"
            txt += "\n"
    
    # People Search
    if "people_search" in data:
        people = data["people_search"]
        if "error" not in people:
            profiles = people.get("social_profiles", [])
            txt += f"🧑 <b>PEOPLE SEARCH</b>\n"
            txt += f"   📋 Perfiles: {len(profiles)} encontrados\n"
            txt += "\n"
    
    # TikTok OSINT
    if "tiktok_osint" in data:
        tt = data["tiktok_osint"]
        if "error" not in tt and tt.get("found"):
            txt += f"📹 <b>TIKTOK OSINT</b>\n"
            txt += f"   👥 Seguidores: {tt.get('followers', 'N/A'):,}\n"
            txt += f"   🎥 Videos: {tt.get('videos', 'N/A')}\n"
            txt += "\n"
    
    txt += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    txt += f"<i>⚠️ Reporte generado para fines de concientización en ciberseguridad</i>"
    
    return txt


def universal_recon(text: str) -> tuple:
    """
    Función principal del módulo universal.
    Devuelve (tipo_detectado, resultados_dict) para uso async.
    """
    input_type = _detect_input_type(text)
    return input_type