import argparse
import json
import os
import sqlite3
from datetime import datetime

from geopy.geocoders import Nominatim

DB_PATH = os.path.join("data", "locations.db")
CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS geocode_cache (
    address TEXT PRIMARY KEY,
    latitude REAL,
    longitude REAL,
    last_updated TEXT
)
"""

FETCH_SQL = "SELECT place_name, address_text, created_at FROM locations"


def ensure_cache():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CACHE_TABLE_SQL)


def query_locations():
    if not os.path.exists(DB_PATH):
        return []
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(FETCH_SQL)
        return cur.fetchall()


def get_cached_coords(address):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT latitude, longitude FROM geocode_cache WHERE address=?", (address,))
        row = cur.fetchone()
        return row if row else None


def cache_coords(address, lat, lon):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO geocode_cache (address, latitude, longitude, last_updated) VALUES (?, ?, ?, ?)",
            (address, lat, lon, datetime.utcnow().isoformat()),
        )
        conn.commit()


def geocode_address(geocoder, address):
    cached = get_cached_coords(address)
    if cached:
        return cached
    location = geocoder.geocode(address, timeout=10)
    if not location:
        return None
    cache_coords(address, location.latitude, location.longitude)
    return location.latitude, location.longitude


def build_geojson(locations):
    features = []
    geocoder = Nominatim(user_agent="dew-finds-map")
    for place_name, address_text, logged_at in locations:
        coords = geocode_address(geocoder, address_text)
        if not coords:
            print(f"Failed to geocode: {address_text}")
            continue
        lat, lon = coords
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "title": place_name,
                    "description": address_text,
                    "logged_at": logged_at,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main(output_path):
    ensure_cache()
    locations = query_locations()
    if not locations:
        print("No locations found.")
        return
    geojson = build_geojson(locations)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)
    print(f"Exported {len(geojson['features'])} entries to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Dew finds to GeoJSON")
    parser.add_argument("output", help="Output GeoJSON file path", nargs="?", default="data/locations.geojson")
    args = parser.parse_args()
    main(args.output)
