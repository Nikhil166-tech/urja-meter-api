import math
from typing import Any, Dict, List, Optional, Tuple

from urja_api.client.exceptions import UpstreamNotFoundError
from urja_api.client.upstream import UrjaUpstreamClient
from urja_api.models.geo import GeoLocation
from urja_api.models.hierarchy import HierarchyNodeInfo, MeterHierarchyPath
from urja_api.models.meter import (
    MeterDetail,
    MeterListResponse,
    MeterNearbyItem,
    MeterSummary,
    NameplateParameter,
)
from urja_api.services.cache_service import LocalDataCache

class MeterService:
    """Business logic for searching, filtering, geo proximity, and detailing smart meters."""

    def __init__(self, cache: LocalDataCache, client: UrjaUpstreamClient):
        self.cache = cache
        self.client = client

    def _to_meter_summary(self, raw: Dict[str, Any]) -> MeterSummary:
        geo = raw.get("geo") or {}
        location = None
        if geo.get("lat") is not None and geo.get("lng") is not None:
            try:
                location = GeoLocation(
                    latitude=float(geo["lat"]),
                    longitude=float(geo["lng"]),
                )
            except (ValueError, TypeError):
                pass

        h = raw.get("hierarchy") or {}
        feeder = h.get("feeder") or {}
        substation = h.get("substation") or {}

        return MeterSummary(
            meter_id=raw.get("meterId", ""),
            serial_no=raw.get("serialNo", ""),
            make=raw.get("make", ""),
            phase_type=raw.get("phaseType", ""),
            install_status=raw.get("installStatus", ""),
            install_type=raw.get("installType", ""),
            build=raw.get("build", ""),
            dt_code=raw.get("dtCode", ""),
            location=location,
            feeder_code=feeder.get("code") if isinstance(feeder, dict) else None,
            substation_code=substation.get("code") if isinstance(substation, dict) else None,
        )

    def _to_meter_detail(self, raw: Dict[str, Any], server_detail: Optional[Dict[str, Any]] = None) -> MeterDetail:
        summary = self._to_meter_summary(raw)
        
        # Build hierarchy
        h_raw = raw.get("hierarchy") or {}
        hierarchy_path = None
        if h_raw:
            def _node(key: str) -> HierarchyNodeInfo:
                val = h_raw.get(key, {})
                if isinstance(val, dict):
                    return HierarchyNodeInfo(name=val.get("name", ""), code=val.get("code", ""))
                return HierarchyNodeInfo(name=str(val), code=str(val))

            hierarchy_path = MeterHierarchyPath(
                zone=_node("zone"),
                circle=_node("circle"),
                division=_node("division"),
                subdivision=_node("subdivision"),
                substation=_node("substation"),
                feeder=_node("feeder"),
                dt=_node("dt"),
            )

        # Nameplate parameters
        nameplate_params: List[NameplateParameter] = []
        if server_detail and "nameplate" in server_detail:
            for item in server_detail["nameplate"]:
                nameplate_params.append(NameplateParameter(
                    name=item["parameterName"],
                    value=item["parameterValue"],
                ))
        else:
            # Fallback to standard properties
            nameplate_params = [
                NameplateParameter(name="Meter ID", value=summary.meter_id),
                NameplateParameter(name="Serial No", value=summary.serial_no),
                NameplateParameter(name="Make", value=summary.make),
                NameplateParameter(name="Phase Type", value=summary.phase_type),
                NameplateParameter(name="Installation Status", value=summary.install_status),
                NameplateParameter(name="Installation Type", value=summary.install_type),
                NameplateParameter(name="Build", value=summary.build),
                NameplateParameter(name="DT Code", value=summary.dt_code),
            ]

        return MeterDetail(
            **summary.model_dump(),
            hierarchy=hierarchy_path,
            nameplate=nameplate_params,
        )

    async def list_meters(
        self,
        q: Optional[str] = None,
        make: Optional[str] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None,
        install_type: Optional[str] = None,
        build: Optional[str] = None,
        dt_code: Optional[str] = None,
        feeder_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MeterListResponse:
        all_raw = await self.cache.get_meters()
        filtered = []

        q_lower = q.strip().lower() if q else None
        make_lower = make.strip().lower() if make else None
        phase_lower = phase.strip().lower() if phase else None
        status_lower = status.strip().lower() if status else None
        install_type_lower = install_type.strip().lower() if install_type else None
        build_lower = build.strip().lower() if build else None
        dt_lower = dt_code.strip().lower() if dt_code else None
        feeder_lower = feeder_code.strip().lower() if feeder_code else None

        for raw in all_raw:
            # Full-text / identifier search across meterId, serialNo
            if q_lower:
                m_id = (raw.get("meterId") or "").lower()
                s_no = (raw.get("serialNo") or "").lower()
                dt_c = (raw.get("dtCode") or "").lower()
                if q_lower not in m_id and q_lower not in s_no and q_lower not in dt_c:
                    continue

            # Faceted filters
            if make_lower and (raw.get("make") or "").lower() != make_lower:
                continue
            if phase_lower and (raw.get("phaseType") or "").lower() != phase_lower:
                continue
            if status_lower and (raw.get("installStatus") or "").lower() != status_lower:
                continue
            if install_type_lower and (raw.get("installType") or "").lower() != install_type_lower:
                continue
            if build_lower and (raw.get("build") or "").lower() != build_lower:
                continue
            if dt_lower and (raw.get("dtCode") or "").lower() != dt_lower:
                continue
            if feeder_lower:
                feeder_raw = (raw.get("hierarchy") or {}).get("feeder") or {}
                f_code = (feeder_raw.get("code") or "") if isinstance(feeder_raw, dict) else str(feeder_raw)
                if f_code.lower() != feeder_lower:
                    continue

            filtered.append(raw)

        total = len(filtered)
        total_pages = max(1, math.ceil(total / page_size))
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_raw = filtered[start_idx:end_idx]

        meters = [self._to_meter_summary(r) for r in paged_raw]

        return MeterListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            meters=meters,
        )

    async def get_meter_by_id(self, meter_id: str) -> MeterDetail:
        raw = await self.cache.get_meter(meter_id)
        if not raw:
            raise UpstreamNotFoundError("Meter", meter_id)

        server_detail = None
        try:
            server_detail = await self.client.fetch_meter_server_detail(meter_id)
        except Exception:
            pass

        return self._to_meter_detail(raw, server_detail)

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes great-circle distance between two points in kilometers."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    async def search_nearby(
        self,
        lat: float,
        lng: float,
        radius_km: float = 5.0,
        limit: int = 50,
        status: Optional[str] = None,
        make: Optional[str] = None,
    ) -> List[MeterNearbyItem]:
        """Finds meters within a given radius sorted by proximity."""
        all_raw = await self.cache.get_meters()
        results = []

        status_lower = status.strip().lower() if status else None
        make_lower = make.strip().lower() if make else None

        for r in all_raw:
            if status_lower and (r.get("installStatus") or "").lower() != status_lower:
                continue
            if make_lower and (r.get("make") or "").lower() != make_lower:
                continue

            geo = r.get("geo") or {}
            m_lat = geo.get("lat")
            m_lng = geo.get("lng")
            if m_lat is None or m_lng is None:
                continue

            dist = self._haversine_distance(lat, lng, float(m_lat), float(m_lng))
            if dist <= radius_km:
                summary = self._to_meter_summary(r)
                results.append(MeterNearbyItem(
                    **summary.model_dump(),
                    distance_km=round(dist, 3),
                ))

        results.sort(key=lambda x: x.distance_km)
        return results[:limit]
