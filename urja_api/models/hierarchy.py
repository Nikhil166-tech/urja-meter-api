from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class HierarchyNodeInfo(BaseModel):
    """Information for a single level in the distribution hierarchy."""
    name: str = Field(..., description="Node name", examples=["Jaipur Zone 1"])
    code: str = Field(..., description="Node identifier code", examples=["Z-01"])

class MeterHierarchyPath(BaseModel):
    """7-level distribution network path for a meter."""
    zone: HierarchyNodeInfo = Field(..., description="Zone level")
    circle: HierarchyNodeInfo = Field(..., description="Circle level")
    division: HierarchyNodeInfo = Field(..., description="Division level")
    subdivision: HierarchyNodeInfo = Field(..., description="Subdivision level")
    substation: HierarchyNodeInfo = Field(..., description="Substation level")
    feeder: HierarchyNodeInfo = Field(..., description="Feeder level")
    dt: HierarchyNodeInfo = Field(..., description="Distribution Transformer level")

class NetworkTreeNode(BaseModel):
    """Generic tree node representing any level of the electrical network."""
    id: str = Field(..., description="Unique node identifier (e.g. Z-01, DT-001)")
    name: str = Field(..., description="Display name")
    level: str = Field(..., description="Hierarchy tier: zone, circle, division, subdivision, substation, feeder, dt")
    meter_count: int = Field(default=0, description="Total meters under this node")
    children: List["NetworkTreeNode"] = Field(default_factory=list, description="Child network nodes")

NetworkTreeNode.model_rebuild()

class HierarchyTreeResponse(BaseModel):
    """Full distribution network hierarchy tree response."""
    total_zones: int = Field(..., description="Total top-level zones")
    total_meters: int = Field(..., description="Total meters organized in the tree")
    tree: List[NetworkTreeNode] = Field(..., description="Hierarchical forest of zones")
