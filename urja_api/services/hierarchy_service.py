from typing import Any, Dict, List, Optional
from urja_api.models.hierarchy import HierarchyTreeResponse, NetworkTreeNode
from urja_api.services.cache_service import LocalDataCache

class HierarchyService:
    """
    Reconstructs the 7-level distribution network hierarchy tree:
    Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT -> Meters.
    Handles data normalization and tree traversal.
    """

    def __init__(self, cache: LocalDataCache):
        self.cache = cache

    async def get_network_tree(self) -> HierarchyTreeResponse:
        meters = await self.cache.get_meters()
        
        # Build nested tree dictionary
        # root -> zones -> circles -> divisions -> subdivisions -> substations -> feeders -> dts
        tree_dict: Dict[str, Any] = {}
        total_meters = len(meters)

        for m in meters:
            h = m.get("hierarchy") or {}
            
            zone = h.get("zone") or {"code": "Z-UNKNOWN", "name": "Unknown Zone"}
            circle = h.get("circle") or {"code": "C-UNKNOWN", "name": "Unknown Circle"}
            division = h.get("division") or {"code": "D-UNKNOWN", "name": "Unknown Division"}
            subdiv = h.get("subdivision") or {"code": "SD-UNKNOWN", "name": "Unknown Subdivision"}
            substation = h.get("substation") or {"code": "SS-UNKNOWN", "name": "Unknown Substation"}
            feeder = h.get("feeder") or {"code": "F-UNKNOWN", "name": "Unknown Feeder"}
            dt = h.get("dt") or {"code": m.get("dtCode", "DT-UNKNOWN"), "name": "DT " + m.get("dtCode", "UNKNOWN")}

            z_code, z_name = zone.get("code", ""), zone.get("name", "")
            c_code, c_name = circle.get("code", ""), circle.get("name", "")
            d_code, d_name = division.get("code", ""), division.get("name", "")
            sd_code, sd_name = subdiv.get("code", ""), subdiv.get("name", "")
            ss_code, ss_name = substation.get("code", ""), substation.get("name", "")
            f_code, f_name = feeder.get("code", ""), feeder.get("name", "")
            dt_code, dt_name = dt.get("code", ""), dt.get("name", "")

            # Traverse / instantiate nodes
            if z_code not in tree_dict:
                tree_dict[z_code] = {"name": z_name, "level": "zone", "meters": 0, "children": {}}
            tree_dict[z_code]["meters"] += 1

            z_node = tree_dict[z_code]["children"]
            if c_code not in z_node:
                z_node[c_code] = {"name": c_name, "level": "circle", "meters": 0, "children": {}}
            z_node[c_code]["meters"] += 1

            c_node = z_node[c_code]["children"]
            if d_code not in c_node:
                c_node[d_code] = {"name": d_name, "level": "division", "meters": 0, "children": {}}
            c_node[d_code]["meters"] += 1

            d_node = c_node[d_code]["children"]
            if sd_code not in d_node:
                d_node[sd_code] = {"name": sd_name, "level": "subdivision", "meters": 0, "children": {}}
            d_node[sd_code]["meters"] += 1

            sd_node = d_node[sd_code]["children"]
            if ss_code not in sd_node:
                sd_node[ss_code] = {"name": ss_name, "level": "substation", "meters": 0, "children": {}}
            sd_node[ss_code]["meters"] += 1

            ss_node = sd_node[ss_code]["children"]
            if f_code not in ss_node:
                ss_node[f_code] = {"name": f_name, "level": "feeder", "meters": 0, "children": {}}
            ss_node[f_code]["meters"] += 1

            f_node = ss_node[f_code]["children"]
            if dt_code not in f_node:
                f_node[dt_code] = {"name": dt_name, "level": "dt", "meters": 0, "children": {}}
            f_node[dt_code]["meters"] += 1

        def _convert_to_nodes(d: Dict[str, Any]) -> List[NetworkTreeNode]:
            nodes = []
            for code, val in sorted(d.items(), key=lambda x: x[0]):
                children = _convert_to_nodes(val["children"]) if "children" in val else []
                nodes.append(NetworkTreeNode(
                    id=code,
                    name=val["name"],
                    level=val["level"],
                    meter_count=val["meters"],
                    children=children,
                ))
            return nodes

        zone_nodes = _convert_to_nodes(tree_dict)

        return HierarchyTreeResponse(
            total_zones=len(zone_nodes),
            total_meters=total_meters,
            tree=zone_nodes,
        )
