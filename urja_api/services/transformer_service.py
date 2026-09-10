from collections import defaultdict
from typing import Any, Dict, List, Optional

from urja_api.client.exceptions import UpstreamNotFoundError
from urja_api.models.transformer import TransformerDetail, TransformerSummary
from urja_api.services.cache_service import LocalDataCache

class TransformerService:
    """Manages Distribution Transformers and aggregates load and meter connectivity metrics."""

    def __init__(self, cache: LocalDataCache):
        self.cache = cache

    def _build_dt_meter_index(self, meters: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        dt_map = defaultdict(list)
        for m in meters:
            dt_code = m.get("dtCode")
            if dt_code:
                dt_map[dt_code].append(m)
        return dt_map

    async def list_transformers(self, feeder_code: Optional[str] = None) -> List[TransformerSummary]:
        raw_dts = await self.cache.get_transformers()
        raw_meters = await self.cache.get_meters()
        dt_meter_map = self._build_dt_meter_index(raw_meters)

        results = []
        feeder_lower = feeder_code.strip().lower() if feeder_code else None

        for dt in raw_dts:
            f_code = dt.get("feederCode", "")
            if feeder_lower and f_code.lower() != feeder_lower:
                continue

            code = dt.get("code", "")
            connected_meters = dt_meter_map.get(code, [])

            results.append(TransformerSummary(
                code=code,
                name=dt.get("name", ""),
                feeder_code=f_code,
                capacity_kva=float(dt.get("capacityKva", 0.0)),
                connected_meters_count=len(connected_meters),
            ))

        return sorted(results, key=lambda x: x.code)

    async def get_transformer_by_code(self, dt_code: str) -> TransformerDetail:
        raw_dt = await self.cache.get_transformer(dt_code)
        if not raw_dt:
            raise UpstreamNotFoundError("Transformer", dt_code)

        raw_meters = await self.cache.get_meters()
        dt_meter_map = self._build_dt_meter_index(raw_meters)
        connected_meters = dt_meter_map.get(dt_code, [])

        installed_count = sum(1 for m in connected_meters if m.get("installStatus") == "Installed")
        faulty_count = sum(1 for m in connected_meters if m.get("installStatus") == "Faulty")
        decom_count = sum(1 for m in connected_meters if m.get("installStatus") == "Decommissioned")

        # Estimation heuristic:
        # Average residential connected load: single-phase ~ 3 kW, three-phase ~ 10 kW
        est_load_kw = 0.0
        for m in connected_meters:
            if m.get("installStatus") == "Installed":
                if m.get("phaseType") == "three":
                    est_load_kw += 10.0
                else:
                    est_load_kw += 3.0

        capacity_kva = float(raw_dt.get("capacityKva", 0.0))
        # Power factor assumed ~ 0.9 for capacity conversion
        capacity_kw = capacity_kva * 0.9 if capacity_kva > 0 else 1.0
        utilization_pct = round((est_load_kw / capacity_kw) * 100.0, 1) if capacity_kw > 0 else 0.0

        return TransformerDetail(
            code=dt_code,
            name=raw_dt.get("name", ""),
            feeder_code=raw_dt.get("feederCode", ""),
            capacity_kva=capacity_kva,
            connected_meters_count=len(connected_meters),
            installed_meters_count=installed_count,
            faulty_meters_count=faulty_count,
            decommissioned_meters_count=decom_count,
            estimated_load_kw=est_load_kw,
            capacity_utilization_pct=utilization_pct,
            connected_meter_ids=[m["meterId"] for m in connected_meters if "meterId" in m],
        )
