import datetime
import re
from typing import Any


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
URL_RE = re.compile(r"https?://[^\s<>{}\"']+")
DOMAIN_RE = re.compile(r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")
HANDLE_RE = re.compile(r"@([A-Za-z0-9._]{2,40})")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")

PLATFORM_HINTS = {
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "facebook": "Facebook",
    "github": "GitHub",
    "telegram": "Telegram",
    "gmail": "Google",
    "google": "Google",
    "whatsapp": "WhatsApp",
    "x.com": "X",
    "twitter": "X",
    "linkedin": "LinkedIn",
    "youtube": "YouTube",
    "discord": "Discord",
    "reddit": "Reddit",
}

NOISE_URL_HOSTS = {
    "haveibeenpwned.com",
    "intelx.io",
    "dehashed.com",
    "psbdmp.ws",
    "securitytrails.com",
    "who.is",
    "censys.io",
    "shodan.io",
    "virustotal.com",
    "abuseipdb.com",
    "ipvoid.com",
    "viewdns.info",
    "google.com",
    "maps.google.com",
    "yandex.com",
    "tineye.com",
    "facecheck.id",
    "pimeyes.com",
    "search4faces.com",
}

NOISE_KEY_TOKENS = (
    "osint", "source", "dork", "search", "map", "mx", "ns", "spf", "dmarc",
    "whois", "registrar", "header", "server", "evidence", "links", "record",
    "breach", "provider", "metadata", "gravatar", "dns", "abuse", "blacklist",
)

NOISE_EXACT_KEYS = {
    "links",
    "source_links",
    "emailrep",
    "hunter",
    "holehe",
    "haveibeenpwned",
    "intelx",
    "dehashed",
    "psbdmp",
    "google_dork",
    "mx_records",
    "dns_security",
}

PERSONAL_URL_KEYS = (
    "bio", "profile", "website", "social", "avatar", "photo", "image", "input", "query", "url"
)

DATE_LIKE_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}$")
COMPACT_DATE_RE = re.compile(r"^(19|20)\d{6}$")


def _dedupe(values: list[str], limit: int = 8) -> list[str]:
    seen = set()
    out = []
    for value in values:
        clean = (value or "").strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def _normalize_phone(value: str) -> str | None:
    raw = (value or "").strip()
    if DATE_LIKE_RE.fullmatch(raw):
        return None
    digits = re.sub(r"\D", "", value or "")
    if COMPACT_DATE_RE.fullmatch(digits):
        return None
    if 8 <= len(digits) <= 15:
        return digits
    return None


def _looks_like_noise_key(key: str) -> bool:
    low_key = (key or "").lower()
    if low_key in NOISE_EXACT_KEYS:
        return True
    return any(token in low_key for token in NOISE_KEY_TOKENS)


def _looks_like_personal_url_key(key: str) -> bool:
    low_key = (key or "").lower()
    return any(token in low_key for token in PERSONAL_URL_KEYS)


def _normalize_url(url: str) -> str:
    return (url or "").rstrip(").,;!?]}>\"'")


def _extract_host(url: str) -> str:
    clean = re.sub(r"^https?://", "", _normalize_url(url), flags=re.IGNORECASE)
    return clean.split("/", 1)[0].split("?", 1)[0].lower()


def _is_noise_url(url: str, key: str) -> bool:
    host = _extract_host(url)
    if not host:
        return True
    if host in NOISE_URL_HOSTS:
        return True
    if _looks_like_noise_key(key) and not _looks_like_personal_url_key(key):
        return True
    return False


def _is_noise_domain(domain: str, key: str) -> bool:
    low_domain = (domain or "").lower()
    if low_domain in NOISE_URL_HOSTS:
        return True
    if low_domain.endswith(".google.com") or low_domain.endswith(".googleusercontent.com"):
        return _looks_like_noise_key(key)
    if _looks_like_noise_key(key) and not _looks_like_personal_url_key(key):
        return True
    return False


def _entity_bucket() -> dict[str, list[str]]:
    return {
        "emails": [],
        "phones": [],
        "ips": [],
        "domains": [],
        "urls": [],
        "usernames": [],
        "names": [],
        "locations": [],
        "coordinates": [],
        "platforms": [],
    }


def _add_platform_hints(target: dict[str, list[str]], text: str) -> None:
    low = text.lower()
    for hint, platform in PLATFORM_HINTS.items():
        if hint in low:
            target["platforms"].append(platform)


def _extract_from_scalar(key: str, value: str, target: dict[str, list[str]]) -> None:
    if not value:
        return

    low_key = key.lower()
    is_noise_key = _looks_like_noise_key(low_key) and not _looks_like_personal_url_key(low_key)
    emails_found = EMAIL_RE.findall(value)
    sanitized = value
    for email in emails_found:
        sanitized = sanitized.replace(email, " ")

    if not is_noise_key:
        for email in emails_found:
            target["emails"].append(email)

    if not is_noise_key and not any(token in low_key for token in ("date", "time", "created", "expired", "register")):
        for phone in PHONE_RE.findall(value):
            normalized = _normalize_phone(phone)
            if normalized:
                target["phones"].append(normalized)

    if not is_noise_key:
        for ip in IP_RE.findall(value):
            target["ips"].append(ip)

    for url in URL_RE.findall(value):
        clean_url = _normalize_url(url)
        if not _is_noise_url(clean_url, low_key):
            target["urls"].append(clean_url)
            _add_platform_hints(target, clean_url)

    for domain in DOMAIN_RE.findall(sanitized):
        if "@" not in domain and not IP_RE.fullmatch(domain) and not _is_noise_domain(domain, low_key):
            target["domains"].append(domain)
            _add_platform_hints(target, domain)

    for handle in HANDLE_RE.findall(sanitized):
        if 2 <= len(handle) <= 40:
            target["usernames"].append(handle)

    if "user" in low_key or "handle" in low_key or "nickname" in low_key or "alias" in low_key:
        if "@" not in value and len(value) <= 40 and " " not in value and "/" not in value:
            target["usernames"].append(value.lstrip("@"))

    if not is_noise_key and "name" in low_key and len(value) <= 80 and "http" not in value.lower():
        target["names"].append(value)

    if not is_noise_key and any(token in low_key for token in ("city", "country", "region", "location", "timezone")):
        target["locations"].append(value)

    if not is_noise_key and any(token in low_key for token in ("coords", "coordinate", "lat", "lon", "map")):
        if re.search(r"-?\d+\.\d+", value):
            target["coordinates"].append(value)

    if not is_noise_key:
        _add_platform_hints(target, value)


def _walk_entities(node: Any, key: str, target: dict[str, list[str]]) -> None:
    if node is None:
        return
    if isinstance(node, dict):
        for child_key, child_value in node.items():
            _walk_entities(child_value, str(child_key), target)
        return
    if isinstance(node, (list, tuple, set)):
        for item in node:
            _walk_entities(item, key, target)
        return
    if isinstance(node, (int, float, bool)):
        text = str(node)
    else:
        text = str(node).strip()
    _extract_from_scalar(key, text, target)


def extract_entities(query: str, raw_data: dict[str, Any] | None) -> dict[str, list[str]]:
    entities = _entity_bucket()
    _walk_entities(query, "query", entities)
    _walk_entities(raw_data or {}, "root", entities)
    return {name: _dedupe(values) for name, values in entities.items()}


def _severity_weight(severity: str) -> int:
    return {"high": 18, "medium": 10, "low": 4}.get(severity, 0)


def _signal(label: str, severity: str, evidence: str) -> dict[str, str]:
    return {"label": label, "severity": severity, "evidence": evidence}


def collect_signals(module_name: str, query: str, raw_data: dict[str, Any] | None,
                    entities: dict[str, list[str]]) -> list[dict[str, str]]:
    data = raw_data or {}
    signals: list[dict[str, str]] = []

    if data.get("error"):
        signals.append(_signal("Consulta limitada o bloqueada", "medium", str(data.get("error"))[:180]))

    missing_keys = [k for k in (data.get("missing_keys") or []) if k]
    if missing_keys:
        signals.append(_signal("Fuentes opcionales faltantes", "low", ", ".join(missing_keys[:4])))

    if data.get("blacklisted"):
        reports = data.get("abuse_reports", 0) or 0
        signals.append(_signal("IP reportada en listas de abuso", "high", f"{reports} reportes o reputacion negativa"))

    open_ports = data.get("open_ports") or []
    if open_ports and open_ports != ["Ninguno detectado"]:
        preview = ", ".join(str(p) for p in open_ports[:4])
        signals.append(_signal("Servicios expuestos detectados", "high", preview))

    spam = data.get("spam") or {}
    if spam.get("reported"):
        total = spam.get("total_reports", 0) or 0
        signals.append(_signal("Numero asociado a spam", "high", f"{total} reportes en bases consultadas"))

    presence = data.get("presence") or {}
    if presence.get("whatsapp_registered") is True:
        signals.append(_signal("Numero activo en WhatsApp", "medium", "Permite contacto directo o suplantacion"))

    if data.get("business") or data.get("is_business"):
        signals.append(_signal("Cuenta comercial identificada", "low", "Perfil con huella publica ampliada"))

    if data.get("has_face"):
        signals.append(_signal("Rostro detectado en imagen", "medium", "Habilita busqueda facial o correlacion visual"))

    if data.get("coords") or data.get("map") or entities.get("coordinates"):
        signals.append(_signal("Coordenadas o mapa detectados", "high", "Posible exposicion de ubicacion precisa"))

    if data.get("bio_link"):
        signals.append(_signal("Link externo en biografia", "medium", "Puede enlazar otras identidades o dominios"))

    exposure = data.get("exposure") or {}
    if any(exposure.get(k) for k in ("emails", "phones", "urls", "handles")):
        pieces = []
        if exposure.get("emails"):
            pieces.append(f"{len(exposure['emails'])} email(s)")
        if exposure.get("phones"):
            pieces.append(f"{len(exposure['phones'])} telefono(s)")
        if exposure.get("handles"):
            pieces.append(f"{len(exposure['handles'])} handle(s)")
        signals.append(_signal("Datos sensibles visibles en bio", "high", ", ".join(pieces)))

    found = data.get("found") if isinstance(data.get("found"), list) else None
    if found and len(found) >= 2:
        signals.append(_signal("Alias presente en varias plataformas", "medium", f"{len(found)} coincidencias publicas"))

    found_in = data.get("found_in") or []
    if found_in:
        signals.append(_signal("Email registrado en multiples servicios", "medium", f"{len(found_in)} servicio(s) detectados"))

    if data.get("verified"):
        signals.append(_signal("Cuenta verificada o oficial", "low", "Aumenta confianza de la correlacion"))

    if data.get("private") or data.get("privateAccount"):
        signals.append(_signal("Perfil privado o parcialmente restringido", "low", "La visibilidad publica puede ser limitada"))

    if len(entities.get("platforms", [])) >= 2:
        signals.append(_signal("Presencia multiplataforma", "medium", ", ".join(entities["platforms"][:4])))

    if len(entities.get("emails", [])) and len(entities.get("usernames", [])):
        signals.append(_signal("Correo y alias correlacionables", "high", "Facilita phishing dirigido y suplantacion"))

    if len(entities.get("domains", [])) and len(entities.get("emails", [])):
        signals.append(_signal("Dominio y correo relacionados", "medium", "Puede exponer identidad profesional u organizacional"))

    if len(entities.get("urls", [])) >= 2:
        signals.append(_signal("Multiples enlaces publicos", "medium", f"{len(entities['urls'])} URL(s) asociadas"))

    if module_name in {"menu_fb", "menu_ig", "menu_gmail", "menu_tiktok"} and data.get("error"):
        signals.append(_signal("Plataforma con protecciones anti-bot", "low", "Requiere cookies, proxy o una fuente alternativa"))

    deduped = []
    seen = set()
    for signal in signals:
        key = (signal["label"], signal["evidence"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped[:8]


def _exposure_from_entities(entities: dict[str, list[str]]) -> int:
    score = 0
    score += min(len(entities["emails"]) * 12, 24)
    score += min(len(entities["phones"]) * 14, 28)
    score += min(len(entities["usernames"]) * 6, 18)
    score += min(len(entities["ips"]) * 10, 20)
    score += min(len(entities["domains"]) * 8, 16)
    score += min(len(entities["urls"]) * 3, 12)
    score += min(len(entities["platforms"]) * 4, 16)
    score += 25 if entities["coordinates"] else 0
    return score


def _derive_exposure_score(entities: dict[str, list[str]], signals: list[dict[str, str]]) -> int:
    score = _exposure_from_entities(entities)
    for signal in signals:
        score += _severity_weight(signal["severity"])
    return max(0, min(score, 100))


def _derive_confidence_score(raw_data: dict[str, Any] | None, entities: dict[str, list[str]],
                             signals: list[dict[str, str]]) -> int:
    data = raw_data or {}
    score = 35
    score += min(sum(1 for values in entities.values() if values) * 8, 32)
    score += min(len(signals) * 4, 20)
    if data.get("error"):
        score -= 18
    if data.get("missing_keys"):
        score -= min(len(data["missing_keys"]) * 4, 12)
    if not any(entities.values()):
        score -= 15
    return max(10, min(score, 95))


def _risk_level(score: int) -> str:
    if score >= 70:
        return "ALTO"
    if score >= 40:
        return "MEDIO"
    return "BAJO"


def _entity_overview(entities: dict[str, list[str]]) -> list[str]:
    labels = {
        "emails": ("correo", "correos"),
        "phones": ("telefono", "telefonos"),
        "ips": ("IP", "IPs"),
        "domains": ("dominio", "dominios"),
        "urls": ("URL", "URLs"),
        "usernames": ("alias", "alias"),
        "names": ("nombre", "nombres"),
        "locations": ("ubicacion", "ubicaciones"),
        "coordinates": ("coordenada", "coordenadas"),
        "platforms": ("plataforma", "plataformas"),
    }
    out = []
    for key, values in entities.items():
        if not values:
            continue
        singular, plural = labels[key]
        count = len(values)
        out.append(f"{count} {singular if count == 1 else plural}")
    return out[:5]


def _build_summary(module_name: str, query: str, entities: dict[str, list[str]],
                   signals: list[dict[str, str]], risk_level: str) -> str:
    overview = _entity_overview(entities)
    if overview:
        entity_text = ", ".join(overview)
    else:
        entity_text = "sin entidades claras"
    signal_text = f"{len(signals)} hallazgo(s) clave" if signals else "sin hallazgos fuertes"
    return (
        f"Consulta {module_name.replace('menu_', '').upper()} sobre '{query}': "
        f"{entity_text}, {signal_text}, riesgo {risk_level.lower()}."
    )


def _build_recommendations(entities: dict[str, list[str]], signals: list[dict[str, str]]) -> list[str]:
    recommendations = []
    if entities.get("emails") or entities.get("phones"):
        recommendations.append("Reducir la exposicion de correos y telefonos en biografias, perfiles y repositorios publicos.")
    if entities.get("usernames") and len(entities["usernames"]) >= 2:
        recommendations.append("Evitar reutilizar el mismo alias en multiples plataformas para dificultar la correlacion.")
    if entities.get("coordinates"):
        recommendations.append("Eliminar metadatos GPS o desactivar la geolocalizacion en capturas y publicaciones.")
    if entities.get("urls") or entities.get("domains"):
        recommendations.append("Revisar enlaces publicos hacia blogs, dominios personales o formularios que revelen identidad adicional.")
    if any(signal["label"] == "Numero activo en WhatsApp" for signal in signals):
        recommendations.append("Limitar la visibilidad del numero y reforzar privacidad en mensajeria para reducir suplantacion.")
    if any(signal["label"] == "IP reportada en listas de abuso" for signal in signals):
        recommendations.append("Auditar la IP o infraestructura asociada y revisar exposiciones de servicios o reputacion.")
    if any(signal["label"] == "Datos sensibles visibles en bio" for signal in signals):
        recommendations.append("Mover datos sensibles fuera de la bio publica y usar canales de contacto menos expuestos.")
    if not recommendations:
        recommendations.append("Mantener configuraciones de privacidad y revisar periodicamente la huella digital publica.")
    return recommendations[:4]


def build_intel_envelope(module_name: str, query: str, raw_data: dict[str, Any] | None) -> dict[str, Any]:
    data = raw_data or {}
    entities = extract_entities(query, data)
    signals = collect_signals(module_name, query, data, entities)
    exposure_score = _derive_exposure_score(entities, signals)
    confidence_score = _derive_confidence_score(data, entities, signals)
    risk_level = _risk_level(exposure_score)

    return {
        "module": module_name,
        "query": query,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "error" if data.get("error") else "ok",
        "summary": _build_summary(module_name, query, entities, signals, risk_level),
        "scores": {
            "exposure": exposure_score,
            "confidence": confidence_score,
            "risk_level": risk_level,
        },
        "entities": entities,
        "entity_samples": {
            key: values[:3]
            for key, values in entities.items()
            if values and key in {"emails", "phones", "domains", "urls", "usernames", "ips"}
        },
        "signals": signals,
        "recommendations": _build_recommendations(entities, signals),
        "raw": data,
    }
