# -*- coding: utf-8 -*-
"""
GekOsint — Persistencia SQLite.
Registra consultas, usuarios y errores. Sin dependencias externas (stdlib sqlite3).
"""

import sqlite3
import os
import time
import logging
import datetime
from config import BASE_DIR

logger = logging.getLogger("GekOsint.DB")

DB_PATH = os.path.join(BASE_DIR, "gekosint.db")

# Mapeo bonito para nombres de módulos en reportes
MODULE_LABELS = {
    "menu_ip":          "IP Lookup",
    "menu_phone":       "Phone Intel",
    "menu_user":        "Username Search",
    "menu_email":       "Email Analysis",
    "menu_wa":          "WhatsApp OSINT",
    "menu_exif":        "EXIF + Face Search",
    "menu_dns":         "Domain/DNS",
    "menu_people":      "People Search",
    "menu_github":      "GitHub Recon",
    "menu_ig":          "IG OSINT",
    "menu_gmail":       "Gmail OSINT",
    "menu_fb":          "FB OSINT",
    "menu_emailrecon":  "Email Recon",
    "menu_tiktok":      "TikTok OSINT",
    "menu_geo":         "Geo Tracker",
    "menu_cam":         "Camera Trap",
}


# ── Conexión ──────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


# ── Inicialización ────────────────────────────────────────────────────────────

def init_db():
    """Crea las tablas si no existen. Llamar una vez al inicio del bot."""
    try:
        with _conn() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS queries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    module      TEXT    NOT NULL,
                    query_text  TEXT    DEFAULT '',
                    timestamp   REAL    NOT NULL,
                    success     INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT    DEFAULT '',
                    full_name   TEXT    DEFAULT '',
                    first_seen  REAL    NOT NULL,
                    last_seen   REAL    NOT NULL,
                    query_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS errors (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    module      TEXT    DEFAULT '',
                    error_text  TEXT    DEFAULT '',
                    timestamp   REAL    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_queries_user   ON queries(user_id);
                CREATE INDEX IF NOT EXISTS idx_queries_module ON queries(module);
                CREATE INDEX IF NOT EXISTS idx_queries_ts     ON queries(timestamp);
            """)
        logger.info(f"DB inicializada en {DB_PATH}")
    except Exception as e:
        logger.error(f"init_db error: {e}")


# ── Escritura ─────────────────────────────────────────────────────────────────

def log_query(user_id: int, module: str, query_text: str = "", success: bool = True):
    """Registra una consulta y actualiza el contador del usuario."""
    try:
        now = time.time()
        safe_query = (query_text or "")[:200]
        with _conn() as con:
            con.execute(
                "INSERT INTO queries (user_id, module, query_text, timestamp, success) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, module, safe_query, now, int(success))
            )
            con.execute("""
                INSERT INTO users (user_id, username, full_name, first_seen, last_seen, query_count)
                VALUES (?, '', '', ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_seen   = excluded.last_seen,
                    query_count = query_count + 1
            """, (user_id, now, now))
    except Exception as e:
        logger.error(f"log_query error: {e}")


def upsert_user(user_id: int, username: str, full_name: str):
    """Guarda/actualiza nombre y username del usuario (llamar en /start)."""
    try:
        now = time.time()
        with _conn() as con:
            con.execute("""
                INSERT INTO users (user_id, username, full_name, first_seen, last_seen, query_count)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    username  = excluded.username,
                    full_name = excluded.full_name,
                    last_seen = excluded.last_seen
            """, (user_id, username or "", full_name or "", now, now))
    except Exception as e:
        logger.error(f"upsert_user error: {e}")


def log_error(module: str, error_text: str):
    """Registra un error en un módulo."""
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO errors (module, error_text, timestamp) VALUES (?, ?, ?)",
                (module, str(error_text)[:500], time.time())
            )
    except Exception as e:
        logger.error(f"log_error error: {e}")


# ── Lectura / Stats ───────────────────────────────────────────────────────────

def get_global_stats() -> dict:
    """Estadísticas globales para /admin stats."""
    try:
        with _conn() as con:
            now = time.time()

            total = con.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
            last_24h = con.execute(
                "SELECT COUNT(*) FROM queries WHERE timestamp > ?",
                (now - 86400,)
            ).fetchone()[0]
            last_7d = con.execute(
                "SELECT COUNT(*) FROM queries WHERE timestamp > ?",
                (now - 604800,)
            ).fetchone()[0]

            top_raw = con.execute("""
                SELECT module, COUNT(*) as cnt
                FROM queries
                GROUP BY module
                ORDER BY cnt DESC
                LIMIT 6
            """).fetchall()
            top_modules = [(MODULE_LABELS.get(r[0], r[0]), r[1]) for r in top_raw]

            total_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active_24h  = con.execute(
                "SELECT COUNT(DISTINCT user_id) FROM queries WHERE timestamp > ?",
                (now - 86400,)
            ).fetchone()[0]

            errors_24h = con.execute(
                "SELECT COUNT(*) FROM errors WHERE timestamp > ?",
                (now - 86400,)
            ).fetchone()[0]

            success_rate_row = con.execute(
                "SELECT AVG(success) FROM queries WHERE timestamp > ?",
                (now - 86400,)
            ).fetchone()[0]
            success_rate = round((success_rate_row or 1.0) * 100, 1)

        return {
            "total":        total,
            "last_24h":     last_24h,
            "last_7d":      last_7d,
            "top_modules":  top_modules,
            "total_users":  total_users,
            "active_24h":   active_24h,
            "errors_24h":   errors_24h,
            "success_rate": success_rate,
        }
    except Exception as e:
        logger.error(f"get_global_stats error: {e}")
        return {}


def get_user_stats(user_id: int) -> dict:
    """Estadísticas individuales de un usuario."""
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT query_count, first_seen, last_seen, username, full_name "
                "FROM users WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if not row:
                return {}

            fav_raw = con.execute("""
                SELECT module, COUNT(*) as cnt
                FROM queries WHERE user_id = ?
                GROUP BY module ORDER BY cnt DESC LIMIT 3
            """, (user_id,)).fetchall()
            fav_modules = [(MODULE_LABELS.get(r[0], r[0]), r[1]) for r in fav_raw]

            def fmt_ts(ts):
                if not ts:
                    return "N/A"
                return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

        return {
            "query_count": row["query_count"],
            "first_seen":  fmt_ts(row["first_seen"]),
            "last_seen":   fmt_ts(row["last_seen"]),
            "username":    row["username"],
            "full_name":   row["full_name"],
            "fav_modules": fav_modules,
        }
    except Exception as e:
        logger.error(f"get_user_stats error: {e}")
        return {}


def get_recent_queries(limit: int = 20) -> list:
    """Últimas N consultas globales (para /admin log)."""
    try:
        with _conn() as con:
            rows = con.execute("""
                SELECT q.user_id, q.module, q.query_text, q.timestamp, q.success,
                       u.username, u.full_name
                FROM queries q
                LEFT JOIN users u ON q.user_id = u.user_id
                ORDER BY q.timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
        result = []
        for r in rows:
            result.append({
                "user_id":    r["user_id"],
                "module":     MODULE_LABELS.get(r["module"], r["module"]),
                "query_text": r["query_text"],
                "timestamp":  datetime.datetime.fromtimestamp(r["timestamp"]).strftime("%m-%d %H:%M"),
                "success":    bool(r["success"]),
                "username":   r["username"] or str(r["user_id"]),
            })
        return result
    except Exception as e:
        logger.error(f"get_recent_queries error: {e}")
        return []
