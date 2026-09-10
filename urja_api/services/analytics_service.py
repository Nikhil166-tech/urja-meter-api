from collections import Counter
from typing import Dict, List
from urja_api.models.analytics import GridAnalyticsSummary
from urja_api.services.cache_service import LocalDataCache

class AnalyticsService:
    """Computes high-level grid infrastructure summaries and asset breakdowns."""

    def __init__(self, cache: LocalDataCache):
        self.cache = cache

    async def get_grid_summary(self) -> GridAnalyticsSummary:
        meters = await self.cache.get_meters()
        transformers = await self.cache.get_transformers()

        status_counts = Counter(m.get("installStatus", "Unknown") for m in meters)
        make_counts = Counter(m.get("make", "Unknown") for m in meters)
        phase_counts = Counter(m.get("phaseType", "Unknown") for m in meters)
        type_counts = Counter(m.get("installType", "Unknown") for m in meters)
        build_counts = Counter(m.get("build", "Unknown") for m in meters)

        zone_counts = Counter()
        dt_counts = Counter()

        for m in meters:
            h = m.get("hierarchy") or {}
            zone = h.get("zone") or {}
            z_name = zone.get("name", "Unknown Zone") if isinstance(zone, dict) else str(zone)
            zone_counts[z_name] += 1

            dt_code = m.get("dtCode", "Unknown")
            dt_counts[dt_code] += 1

        total_cap = sum(float(t.get("capacityKva", 0)) for t in transformers)

        top_dts = []
        for dt_code, count in dt_counts.most_common(5):
            top_dts.append({"dt_code": dt_code, "meter_count": str(count)})

        return GridAnalyticsSummary(
            total_meters=len(meters),
            total_transformers=len(transformers),
            total_transformer_capacity_kva=round(total_cap, 1),
            status_distribution=dict(status_counts),
            make_distribution=dict(make_counts),
            phase_distribution=dict(phase_counts),
            install_type_distribution=dict(type_counts),
            build_version_distribution=dict(build_counts),
            zone_meter_counts=dict(zone_counts),
            top_loaded_transformers=top_dts,
        )
