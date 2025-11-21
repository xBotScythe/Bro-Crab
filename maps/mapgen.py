import os
import sqlite3

DB_PATH = os.path.join("data", "dew_map.db")


def fetch_finds(db_path=DB_PATH):
    # pull all logged finds for the website + api
    if not os.path.exists(db_path):
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT id, flavor, size, location_name, address, latitude, longitude, image_url, time_zone, created_at FROM finds"
        ).fetchall()
