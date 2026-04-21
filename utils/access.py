
import os
import json
from config import BASE_DIR, ALLOWED_USERS as INITIAL_USERS

USERS_FILE = os.path.join(BASE_DIR, "authorized_users.json")

def load_authorized_users():
    """Carga los usuarios autorizados desde el archivo JSON o usa los iniciales"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                users = set(json.load(f))
                # Asegurar que los usuarios iniciales siempre tengan acceso
                return users.union(INITIAL_USERS)
        except Exception:
            return INITIAL_USERS
    return INITIAL_USERS

def save_authorized_users(users_set):
    """Guarda la lista de usuarios en el archivo JSON"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(list(users_set), f)
        return True
    except Exception:
        return False

def add_user(user_id):
    """Añade un usuario a la lista"""
    users = load_authorized_users()
    users.add(int(user_id))
    return save_authorized_users(users)

def remove_user(user_id):
    """Elimina un usuario de la lista (no puede eliminar a los iniciales)"""
    if int(user_id) in INITIAL_USERS:
        return False
    users = load_authorized_users()
    if int(user_id) in users:
        users.remove(int(user_id))
        return save_authorized_users(users)
    return False

def get_all_users():
    """Retorna la lista de todos los usuarios autorizados"""
    return load_authorized_users()
