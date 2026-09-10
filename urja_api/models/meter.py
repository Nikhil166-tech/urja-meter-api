from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from urja_api.models.geo import GeoLocation
from urja_api.models.hierarchy import MeterHierarchyPath

class NameplateParameter(BaseModel):
    """Single nameplate specification parameter."""
    name: str = Field(..., description="Parameter name", examples=["Make", "Phase Type"])
    value: str = Field(..., description="Parameter value", examples=["HPL", "single"])

class MeterSummary(BaseModel):
    """Clean representation of a smart meter."""
    meter_id: str = Field(..., description="Unique meter ID (e.g. J100000)", examples=["J100000"])
    serial_no: str = Field(..., description="Manufacturer hardware serial number", examples=["SE33962"])
    make: str = Field(..., description="Meter manufacturer make", examples=["HPL"])
    phase_type: str = Field(..., description="Phase configuration: single or three", examples=["single"])
    install_status: str = Field(..., description="Operational status: Installed, Faulty, or Decommissioned", examples=["Installed"])
    install_type: str = Field(..., description="Installation mechanism: Whole Current or CT Operated", examples=["Whole Current"])
    build: str = Field(..., description="Meter build version: legacy or v2", examples=["legacy"])
    dt_code: str = Field(..., description="Connected Distribution Transformer code", examples=["DT-001"])
    location: Optional[GeoLocation] = Field(None, description="GPS coordinates")
    feeder_code: Optional[str] = Field(None, description="Parent Feeder code", examples=["F-001"])
    substation_code: Optional[str] = Field(None, description="Parent Substation code", examples=["SS-01"])

class MeterDetail(MeterSummary):
    """Comprehensive meter model with full 7-tier hierarchy and nameplate parameters."""
    hierarchy: Optional[MeterHierarchyPath] = Field(None, description="Full 7-level network distribution hierarchy")
    nameplate: List[NameplateParameter] = Field(default_factory=list, description="Normalized nameplate specifications")

class MeterNearbyItem(MeterSummary):
    """Meter returned from geospatial proximity search with distance."""
    distance_km: float = Field(..., description="Distance from search center in kilometers", examples=[1.42])

class MeterListResponse(BaseModel):
    """Paginated list of smart meters."""
    total: int = Field(..., description="Total matching meters count", examples=[403])
    page: int = Field(..., description="Current page number (1-indexed)", examples=[1])
    page_size: int = Field(..., description="Items per page", examples=[20])
    total_pages: int = Field(..., description="Total pages available", examples=[21])
    meters: List[MeterSummary] = Field(..., description="List of meters on the current page")
