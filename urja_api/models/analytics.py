from typing import Dict, List
from pydantic import BaseModel, Field

class GridAnalyticsSummary(BaseModel):
    """Overview analytics of the metering infrastructure."""
    total_meters: int = Field(..., description="Total number of smart meters")
    total_transformers: int = Field(..., description="Total number of distribution transformers")
    total_transformer_capacity_kva: float = Field(..., description="Total DT capacity in kVA")
    status_distribution: Dict[str, int] = Field(..., description="Counts grouped by install status (Installed, Faulty, Decommissioned)")
    make_distribution: Dict[str, int] = Field(..., description="Counts grouped by manufacturer make")
    phase_distribution: Dict[str, int] = Field(..., description="Counts grouped by phase type (single, three)")
    install_type_distribution: Dict[str, int] = Field(..., description="Counts grouped by install type")
    build_version_distribution: Dict[str, int] = Field(..., description="Counts grouped by build version (legacy, v2)")
    zone_meter_counts: Dict[str, int] = Field(..., description="Counts grouped by top-level Zone")
    top_loaded_transformers: List[Dict[str, str]] = Field(..., description="Transformers with the most connected meters")
