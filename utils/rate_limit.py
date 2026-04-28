"""
Rate limiter simple por usuario_id.
Usa una ventana deslizante de timestamps en memoria.
"""

import time
from collections import defaultdict, deque
from config import RATE_LIMIT_SECONDS, RATE_LIMIT_BURST

# {user_id: deque de timestamps de últimas consultas}
_history: dict = defaultdict(deque)

def check_rate_limit(user_id: int) -> tuple[bool, float]:
    """
    Retorna (permitido, segundos_restantes).
    Permitido = True si el usuario puede hacer la consulta ahora.
    """
    now = time.monotonic()
    dq = _history[user_id]

    # Limpiar timestamps fuera de la ventana
    while dq and now - dq[0] > RATE_LIMIT_SECONDS:
        dq.popleft()

    if len(dq) >= RATE_LIMIT_BURST:
        wait = RATE_LIMIT_SECONDS - (now - dq[0])
        return False, round(wait, 1)

    dq.append(now)
    return True, 0.0

def reset_user(user_id: int):
    """Limpia el historial de un usuario (uso admin)."""
    _history.pop(user_id, None)
