# -*- coding: utf-8 -*-
"""
Rate limiter dedicado para Universal Recon.
Rate limit: 1/45s, 10/hora (más restrictivo por consultas múltiples).
"""

import time
import threading
from config import logger

_UNIVERSAL_COOLDOWNS = {}
_LOCK = threading.Lock()

UNIVERSAL_LIMIT_SECONDS = 45
UNIVERSAL_LIMIT_MAX = 10
UNIVERSAL_WINDOW_SECONDS = 3600


def check_universal_rate_limit(user_id: int) -> tuple:
    """
    Verifica si el usuario puede ejecutar Universal Recon.
    Returns: (allowed: bool, wait_seconds: int)
    """
    now = int(time.time())
    
    with _LOCK:
        user_data = _UNIVERSAL_COOLDOWNS.get(user_id, {"timestamps": []})
        timestamps = [t for t in user_data["timestamps"] if now - t < UNIVERSAL_WINDOW_SECONDS]
        
        if len(timestamps) >= UNIVERSAL_LIMIT_MAX:
            oldest = min(timestamps)
            wait = max(1, UNIVERSAL_WINDOW_SECONDS - (now - oldest))
            return False, min(wait, UNIVERSAL_LIMIT_SECONDS)
        
        timestamps.append(now)
        _UNIVERSAL_COOLDOWNS[user_id] = {"timestamps": timestamps}
        
        return True, 0