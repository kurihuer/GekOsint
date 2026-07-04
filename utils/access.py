"""
Gestión de usuarios autorizados con caché en memoria.
El archivo JSON persiste cambios hechos con /admin en runtime.
Los usuarios en ALLOWED_USERS (config) y ADMIN_ID siempre tienen acceso
y NO pueden ser eliminados.
"""

import os
import json
import time
from config import BASE_DIR, ALLOWED_USERS as INITIAL_USERS, ADMIN_ID

USERS_FILE = os.path.join(BASE_DIR, "authorized_users.json")

# ── Caché en memoria ──────────────────────────────────────────────────────────
_cache: set = set()
_cache_ts: float = 0.0
_CACHE_TTL = 60.0   # segundos; relee el JSON a lo mucho 1 vez por minuto

def _load_from_disk() -> set:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def _save_to_disk(users: set) -> bool:
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(list(users), f)
        return True
    except Exception:
        return False

def _invalidate_cache():
    global _cache_ts
    _cache_ts = 0.0

def get_all_users() -> set:
    """Retorna el conjunto completo de usuarios autorizados (con caché)."""
    global _cache, _cache_ts
    if time.monotonic() - _cache_ts > _CACHE_TTL:
        _cache = _load_from_disk().union(INITIAL_USERS)
        if ADMIN_ID > 0:
            _cache.add(ADMIN_ID)
        _cache_ts = time.monotonic()
    return _cache

def load_authorized_users() -> set:
    return get_all_users()

def add_user(user_id) -> bool:
    uid = int(user_id)
    users = get_all_users().copy()
    users.add(uid)
    ok = _save_to_disk(users - INITIAL_USERS)   # no duplicar los iniciales en el JSON
    if ok:
        _invalidate_cache()
    return ok

def remove_user(user_id) -> bool:
    uid = int(user_id)
    # Proteger admin y usuarios iniciales
    if uid in INITIAL_USERS or uid == ADMIN_ID:
        return False
    users = _load_from_disk()
    if uid not in users:
        return False
    users.discard(uid)
    ok = _save_to_disk(users)
    if ok:
        _invalidate_cache()
    return ok
