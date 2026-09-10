import pytest
from unittest.mock import AsyncMock
from urja_api.services.hierarchy_service import HierarchyService

@pytest.mark.asyncio
async def test_network_tree_construction():
    mock_cache = AsyncMock()
    mock_cache.get_meters.return_value = [
        {
            "meterId": "J100001",
            "dtCode": "DT-001",
            "hierarchy": {
                "zone": {"code": "Z-01", "name": "Zone 1"},
                "circle": {"code": "C-01", "name": "Circle 1"},
                "division": {"code": "D-01", "name": "Division 1"},
                "subdivision": {"code": "SD-01", "name": "Subdivision 1"},
                "substation": {"code": "SS-01", "name": "Substation 1"},
                "feeder": {"code": "F-001", "name": "Feeder 1"},
                "dt": {"code": "DT-001", "name": "DT 1"},
            }
        },
        {
            "meterId": "J100002",
            "dtCode": "DT-001",
            "hierarchy": {
                "zone": {"code": "Z-01", "name": "Zone 1"},
                "circle": {"code": "C-01", "name": "Circle 1"},
                "division": {"code": "D-01", "name": "Division 1"},
                "subdivision": {"code": "SD-01", "name": "Subdivision 1"},
                "substation": {"code": "SS-01", "name": "Substation 1"},
                "feeder": {"code": "F-001", "name": "Feeder 1"},
                "dt": {"code": "DT-001", "name": "DT 1"},
            }
        }
    ]

    service = HierarchyService(mock_cache)
    tree_res = await service.get_network_tree()
    
    assert tree_res.total_zones == 1
    assert tree_res.total_meters == 2
    assert tree_res.tree[0].id == "Z-01"
    assert tree_res.tree[0].meter_count == 2
