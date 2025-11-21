from fastapi import APIRouter

from maps.mapgen import fetch_finds
from web.api.schemas import Find

router = APIRouter(tags=["finds"])


@router.get("/finds", response_model=list[Find])
def list_finds():
    # expose every logged find so the spa can render markers
    rows = fetch_finds()
    return [
        Find(
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
        for row in rows
    ]
