from typing import List, Optional
from pydantic import BaseModel, Field

class TransformerSummary(BaseModel):
    """Distribution Transformer summary schema."""
    code: str = Field(..., description="Unique DT code", examples=["DT-001"])
    name: str = Field(..., description="Transformer location name", examples=["Malviya Nagar DT 1"])
    feeder_code: str = Field(..., description="Associated Feeder code", examples=["F-001"])
    capacity_kva: float = Field(..., description="Transformer capacity in kVA", examples=[100.0])
    connected_meters_count: int = Field(default=0, description="Total smart meters connected under this DT")

class TransformerDetail(TransformerSummary):
    """Detailed transformer schema with connected meters and load statistics."""
    installed_meters_count: int = Field(default=0, description="Active installed meters")
    faulty_meters_count: int = Field(default=0, description="Faulty meters")
    decommissioned_meters_count: int = Field(default=0, description="Decommissioned meters")
    estimated_load_kw: float = Field(default=0.0, description="Aggregated estimated connected load in kW")
    capacity_utilization_pct: float = Field(default=0.0, description="Estimated capacity utilization percentage")
    connected_meter_ids: List[str] = Field(default_factory=list, description="List of connected meter IDs")
