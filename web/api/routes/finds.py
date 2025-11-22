import asyncio

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from maps.mapgen import fetch_finds
from utils.dew_map_manager import create_find, list_flavors, update_find_image
from better_profanity import profanity

profanity.load_censor_words()
from web.api.schemas import Find

router = APIRouter(tags=["finds"])
geolocator = Nominatim(user_agent="dew-map-web")
tz_finder = TimezoneFinder()
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@router.get("/finds", response_model=list[Find])
def list_finds():
    # expose every logged find so the spa can render markers
    rows = fetch_finds()
    return [_row_to_schema(row) for row in rows]


@router.get("/flavors", response_model=list[str])
def get_flavors():
    # keep dropdowns in sync with discord workflow
    return list_flavors()


@router.post("/finds", response_model=Find, status_code=status.HTTP_201_CREATED)
async def create_web_find(
    flavor: str = Form(...),
    size: str = Form(...),
    locationName: str = Form(...),
    address: str = Form(...),
    imageUrl: str | None = Form(None),
    image_file: UploadFile | None = File(None),
):
    # make sure the flavor exists to avoid typos
    flavors = list_flavors()
    if flavor not in flavors:
        raise HTTPException(status_code=400, detail="invalid_flavor")

    coords = await _geocode_address(address)
    if not coords:
        raise HTTPException(status_code=400, detail="address_not_found")
    lat, lon = coords
    tz_name = tz_finder.timezone_at(lat=lat, lng=lon) or "UTC"

    clean_location = locationName.strip()
    clean_address = address.strip()
    if profanity.contains_profanity(clean_location) or profanity.contains_profanity(clean_address):
        raise HTTPException(status_code=400, detail="invalid_text")

    find_id = create_find(
        flavor,
        size,
        clean_location,
        clean_address,
        lat,
        lon,
        tz_name,
    )
    final_image_url: str | None = None
    if image_file:
        final_image_url = await _save_image(image_file)
    elif imageUrl:
        final_image_url = imageUrl.strip()

    if final_image_url:
        update_find_image(find_id, final_image_url)
    rows = fetch_finds()
    for row in rows:
        if row["id"] == find_id:
            return _row_to_schema(row)
    raise HTTPException(status_code=500, detail="find_not_persisted")


async def _geocode_address(address: str):
    loop = asyncio.get_running_loop()

    def _lookup():
        try:
            return geolocator.geocode(address, timeout=10)
        except Exception:
            return None

    location = await loop.run_in_executor(None, _lookup)
    if not location:
        return None
    return (location.latitude, location.longitude)


def _row_to_schema(row):
    return Find(
        id=row["id"],
        flavor=row["flavor"],
        size=row["size"],
        locationName=row["location_name"],
        address=row["address"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        imageUrl=row["image_url"],
        timeZone=row["time_zone"],
        createdAt=row["created_at"],
    )


async def _save_image(upload: UploadFile) -> str:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="unsupported_image_type")
    contents = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="image_too_large")
    ext = ALLOWED_IMAGE_TYPES[upload.content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / filename
    with open(path, "wb") as f:
        f.write(contents)
    return f"/uploads/{filename}"
