import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import folium
from folium.plugins import MarkerCluster, MiniMap, Fullscreen
from utils.dew_map_manager import prune_expired_finds

DB_PATH = os.path.join("data", "dew_map.db")
OUTPUT_PATH = os.path.join("maps", "index.html")
DEFAULT_CENTER = [39.8283, -98.5795]
DEFAULT_ZOOM = 4


def fetch_finds(db_path=DB_PATH):
    # pull all logged finds
    if not os.path.exists(db_path):
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT id, flavor, size, location_name, address, latitude, longitude, image_url, time_zone, created_at FROM finds"
        ).fetchall()


def _format_local_time(created_at, tz_name):
    # convert stored utc iso to user tz string
    try:
        ts = datetime.fromisoformat(created_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return created_at
    try:
        tz = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
        ts = ts.astimezone(tz)
    except Exception:
        pass
    return ts.strftime("%A, %B %d %Y at %I:%M %p %Z")


def build_map(rows):
    m = folium.Map(location=DEFAULT_CENTER, zoom_start=DEFAULT_ZOOM, tiles="CartoDB positron")
    MiniMap(toggle_display=True).add_to(m)
    Fullscreen().add_to(m)
    cluster = MarkerCluster(name="Dew Finds", show=True).add_to(m)

    for row in rows:
        logged_local = _format_local_time(row["created_at"], row["time_zone"])
        popup_html = [
            f"<strong>{row['flavor']} ({row['size']})</strong>",
            f"Location: {row['location_name']}",
            f"Address: {row['address']}",
            f"Find ID: {row['id']}",
            f"Logged: {logged_local}",
        ]
        if row["image_url"]:
            popup_html.append(f"<img src='{row['image_url']}' width='220'>")
        popup = folium.Popup("<br>".join(popup_html), max_width=320)
        tooltip = f"{row['flavor']} ({row['size']})"
        folium.Marker(
            [row["latitude"], row["longitude"]],
            popup=popup,
            tooltip=tooltip,
            icon=folium.Icon(color="green", icon="info-sign"),
        ).add_to(cluster)

    folium.LayerControl().add_to(m)
    return m


def generate_map(db_path=DB_PATH, output_path=OUTPUT_PATH):
    # regenerate html map
    prune_expired_finds()
    rows = fetch_finds(db_path)
    print(f"Loaded {len(rows)} finds from {db_path}")
    m = build_map(rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    m.save(output_path)
    print(f"Map written to {output_path}")


def main():
    generate_map()


if __name__ == "__main__":
    main()
