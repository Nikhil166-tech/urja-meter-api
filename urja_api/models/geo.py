from typing import Optional
from pydantic import BaseModel, Field

class GeoLocation(BaseModel):
    """Geographic coordinate representation."""
    latitude: float = Field(..., description="Latitude in decimal degrees", ge=-90.0, le=90.0, examples=[26.938961])
    longitude: float = Field(..., description="Longitude in decimal degrees", ge=-180.0, le=180.0, examples=[75.830957])

class GeoProximityQuery(BaseModel):
    """Query schema for geospatial radius search."""
    latitude: float = Field(..., description="Center latitude", ge=-90.0, le=90.0)
    longitude: float = Field(..., description="Center longitude", ge=-180.0, le=180.0)
    radius_km: float = Field(default=5.0, description="Search radius in kilometers", gt=0, le=500.0)
    limit: int = Field(default=50, description="Maximum number of meters to return", ge=1, le=500)
