import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join("data", "dew_map.db")
FIND_TTL = timedelta(weeks=5)

SCHEMA = """
CREATE TABLE IF NOT EXISTS flavors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS finds (
    id TEXT PRIMARY KEY,
    flavor TEXT NOT NULL,
    size TEXT NOT NULL,
    location_name TEXT NOT NULL,
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    image_url TEXT,
    time_zone TEXT,
    created_at TEXT NOT NULL
);
"""


def _connect():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)
        _ensure_columns(conn)


def _ensure_columns(conn):
    cur = conn.execute("PRAGMA table_info(finds)")
    columns = {row[1] for row in cur.fetchall()}
    if "time_zone" not in columns:
        conn.execute("ALTER TABLE finds ADD COLUMN time_zone TEXT")
    conn.commit()


def _prune_old_finds(conn):
    cutoff = (datetime.now(timezone.utc) - FIND_TTL).isoformat()
    cur = conn.execute("DELETE FROM finds WHERE created_at < ?", (cutoff,))
    conn.commit()
    return cur.rowcount

def add_flavors(flavors):
    init_db()
    cleaned = {name.strip() for name in flavors if name.strip()}
    with _connect() as conn:
        for flavor in cleaned:
            try:
                conn.execute("INSERT OR IGNORE INTO flavors (name) VALUES (?)", (flavor,))
            except sqlite3.Error:
                pass
        conn.commit()
    return list(cleaned)


def remove_flavors(flavors):
    init_db()
    cleaned = {name.strip() for name in flavors if name.strip()}
    with _connect() as conn:
        for flavor in cleaned:
            conn.execute("DELETE FROM flavors WHERE name = ?", (flavor,))
        conn.commit()
    return list(cleaned)


def list_flavors():
    init_db()
    with _connect() as conn:
        cur = conn.execute("SELECT name FROM flavors ORDER BY name ASC")
        return [row["name"] for row in cur.fetchall()]


def create_find(flavor, size, location_name, address, latitude, longitude, time_zone=None):
    init_db()
    find_id = str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        _prune_old_finds(conn)
        conn.execute(
            """
            INSERT INTO finds (id, flavor, size, location_name, address, latitude, longitude, image_url, time_zone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (find_id, flavor, size, location_name, address, latitude, longitude, time_zone, created_at),
        )
        conn.commit()
    return find_id


def update_find_image(find_id, image_url):
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE finds SET image_url=? WHERE id=?", (image_url, find_id))
        conn.commit()


def delete_find(find_id):
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM finds WHERE id=?", (find_id,))
        conn.commit()
        return cur.rowcount > 0


def prune_expired_finds():
    init_db()
    with _connect() as conn:
        return _prune_old_finds(conn)
