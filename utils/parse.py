"""
Utilidades de parseo de texto para los handlers.
Extraer teléfono, IP y hostname de un texto libre.
"""

import re

_IP_RE   = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_IPV6_RE = re.compile(r'\b(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b', re.IGNORECASE)
_HOST_RE = re.compile(r'^[a-z0-9.-]+\.[a-z]{2,63}$', re.IGNORECASE)
_SEP_RE  = re.compile(r'[|,;\n\r\t]')


def extract_phone_and_target(raw: str) -> tuple[str, str | None]:
    """
    Dado un texto como '+52 55 1234 5678 | 8.8.8.8'
    devuelve (numero_telefono, ip_o_hostname_o_None).

    El teléfono se identifica como el token con 7+ dígitos que no sea IP ni URL.
    El target es la primera IP/hostname encontrado fuera del teléfono.
    """
    cleaned = _SEP_RE.sub(" ", raw)
    tokens  = cleaned.split()

    phone_token  = None
    target_token = None

    # 1. Buscar IP explícita
    m4 = _IP_RE.search(raw)
    if m4:
        target_token = m4.group(0)

    if not target_token:
        m6 = _IPV6_RE.search(raw)
        if m6:
            target_token = m6.group(0)

    # 2. Buscar hostname explícito (si no hay IP)
    if not target_token:
        for tok in tokens:
            t = tok.strip().lower()
            # Limpiar esquema y path
            if t.startswith(("http://", "https://")):
                t = t.split("://", 1)[1]
            t = t.split("/")[0].split("?")[0]
            if not t or t.startswith("+") or "@" in t:
                continue
            if "." in t and _HOST_RE.match(t) and not _IP_RE.match(t):
                target_token = t
                break

    # 3. Buscar número de teléfono
    for tok in tokens:
        digits = re.sub(r'\D', '', tok)
        # Evitar confundir la IP detectada con un teléfono
        if len(digits) >= 7 and "." not in tok and "/" not in tok:
            if target_token and digits == re.sub(r'\D', '', target_token):
                continue
            phone_token = tok
            break

    return (phone_token or raw.strip(), target_token)
