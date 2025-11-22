import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

# reuse the dew map sqlite file so everything lives together
DB_PATH = os.path.join("data", "dew_map.db")
# default ttl is 3 days unless overridden via env
SESSION_TTL_MINUTES = int(os.getenv("ADMIN_SESSION_MINUTES", "4320"))


# tiny helper so every query uses the same sqlite setup
def _connect():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# run once at import so tables exist before usage
def init_admin_tables():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES admin_users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


# simple pbkdf2 wrapper instead of storing raw passwords
def _hash_password(password: str, salt: Optional[bytes] = None) :
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return f"{salt.hex()}${hashed.hex()}"


# compare incoming password with stored pbkdf2 hash
def _check_password(password: str, stored_hash: str) :
    try:
        salt_hex, hash_hex = stored_hash.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000).hex()
    return secrets.compare_digest(expected, hash_hex)


# seed helper used by cli + future admin management
def create_admin_user(username: str, password: str):
    init_admin_tables()
    normalized = username.strip()
    if not normalized:
        raise ValueError("username required")
    hashed = _hash_password(password)
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO admin_users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (normalized, hashed, created_at),
        )
        conn.commit()


# fetch a single admin row by username
def get_admin_by_username(username: str):
    init_admin_tables()
    with _connect() as conn:
        row = conn.execute("SELECT id, username, password_hash, created_at FROM admin_users WHERE username = ?", (username.strip(),)).fetchone()
        return row


# fetch admin by id for display/audit
def get_admin_by_id(user_id: int):
    init_admin_tables()
    with _connect() as conn:
        row = conn.execute("SELECT id, username, password_hash, created_at FROM admin_users WHERE id = ?", (user_id,)).fetchone()
        return row


# validate username/password and return the row
def authenticate(username: str, password: str):
    row = get_admin_by_username(username)
    if not row:
        return None
    if not _check_password(password, row["password_hash"]):
        return None
    return row


# mint an opaque session token and store expiry
def create_session(user_id: int, ttl_minutes: int = SESSION_TTL_MINUTES):
    init_admin_tables()
    token = secrets.token_hex(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO admin_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now.isoformat(), expires_at.isoformat()),
        )
        conn.commit()
    return token, expires_at


# clean expired sessions so the table stays tiny
def _purge_expired(conn):
    conn.execute("DELETE FROM admin_sessions WHERE expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))


# resolve a session token back to the admin user
def get_user_for_session(token: str):
    if not token:
        return None
    init_admin_tables()
    with _connect() as conn:
        _purge_expired(conn)
        row = conn.execute(
            """
            SELECT admin_users.id, admin_users.username, admin_users.created_at, admin_sessions.expires_at
            FROM admin_sessions
            JOIN admin_users ON admin_users.id = admin_sessions.user_id
            WHERE admin_sessions.token = ?
            """,
            (token,),
        ).fetchone()
        return row


# drop a session token manually (logout)
def delete_session(token: str):
    if not token:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
        conn.commit()


# list all admins for future admin portal screens
def list_admin_users():
    init_admin_tables()
    with _connect() as conn:
        return conn.execute("SELECT id, username, created_at FROM admin_users ORDER BY username ASC").fetchall()


init_admin_tables()
