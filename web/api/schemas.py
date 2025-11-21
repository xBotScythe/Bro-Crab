from pydantic import BaseModel


class Find(BaseModel):
    """shape served to the frontend map"""

    id: str
    flavor: str
    size: str
    locationName: str
    address: str
    latitude: float
    longitude: float
    imageUrl: str | None = None
    timeZone: str | None = None
    createdAt: str
