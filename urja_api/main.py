import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from urja_api.client.exceptions import (
    UpstreamAuthError,
    UpstreamError,
    UpstreamNotFoundError,
    UpstreamSignatureError,
)
from urja_api.client.upstream import UrjaUpstreamClient
from urja_api.config import settings
from urja_api.models.analytics import GridAnalyticsSummary
from urja_api.models.energy import EnergyConsumptionSummary
from urja_api.models.hierarchy import HierarchyTreeResponse
from urja_api.models.meter import (
    MeterDetail,
    MeterListResponse,
    MeterNearbyItem,
)
from urja_api.models.transformer import TransformerDetail, TransformerSummary
from urja_api.services.analytics_service import AnalyticsService
from urja_api.services.cache_service import LocalDataCache
from urja_api.services.energy_service import EnergyService
from urja_api.services.hierarchy_service import HierarchyService
from urja_api.services.meter_service import MeterService
from urja_api.services.transformer_service import TransformerService

# Instantiate client, cache, and services
upstream_client = UrjaUpstreamClient()
cache = LocalDataCache(upstream_client)
meter_service = MeterService(cache, upstream_client)
transformer_service = TransformerService(cache)
hierarchy_service = HierarchyService(cache)
energy_service = EnergyService(cache)
analytics_service = AnalyticsService(cache)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: perform initial sync and start background sync loop
    try:
        await cache.sync_all()
    except Exception as e:
        # Don't crash startup if network is temporarily unreachable, will retry on demand
        pass
    cache.start_background_sync()
    yield
    # Shutdown: cancel sync and close client
    cache.stop_background_sync()
    await upstream_client.close()

app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.SERVICE_VERSION,
    description="""
# Urja Meter Ops Clean API
A resilient, clean, and well-structured programmatic API gateway over the legacy **Urja Meter Ops** distribution portal.

## Key Capabilities:
- **Smart Meter Registry**: Filterable, searchable, and paginated smart meter metadata.
- **Geospatial Proximity**: Great-circle radius searches (Haversine formula) and meter geolocation.
- **Distribution Network Hierarchy**: Complete 7-tier electrical distribution tree (`Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT -> Meter`).
- **Distribution Transformers**: Load estimation, capacity utilization, and connected meter rollups.
- **Telemetry & Energy Analytics**: 30-minute interval readings, consumption aggregates, voltage sag/swell detection, and power factor analysis.
- **Resilient Upstream Gateway**: Automatic SvelteKit form authentication, HMAC-SHA256 export signing, background sync, and local caching.
""",
    openapi_tags=[
        {"name": "System & Health", "description": "Cache synchronization and service health checks"},
        {"name": "Meters", "description": "Smart meter lookup, filtering, detail, and geo proximity search"},
        {"name": "Transformers", "description": "Distribution transformer (DT) metrics and connected meters"},
        {"name": "Network Hierarchy", "description": "Electrical distribution hierarchy trees and navigation"},
        {"name": "Telemetry & Energy", "description": "Time-series energy readings and grid anomaly detection"},
        {"name": "Analytics", "description": "High-level fleet and infrastructure aggregate summaries"},
    ],
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Exception Handlers
@app.exception_handler(UpstreamNotFoundError)
async def not_found_handler(request: Request, exc: UpstreamNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Not Found", "message": exc.message},
    )

@app.exception_handler(UpstreamAuthError)
async def auth_error_handler(request: Request, exc: UpstreamAuthError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "Upstream Authentication Failed", "message": exc.message, "details": exc.details},
    )

@app.exception_handler(UpstreamError)
async def upstream_error_handler(request: Request, exc: UpstreamError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "Upstream Gateway Error", "message": exc.message},
    )

# Static directory for Dashboard UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# -------------------------------------------------------------
# System & Health Endpoints
# -------------------------------------------------------------
@app.get(
    "/api/health",
    tags=["System & Health"],
    summary="Service health and cache status",
)
async def health_check():
    """Returns service health, upstream connection state, and cache freshness."""
    meters_count = len(cache.meters_by_id)
    transformers_count = len(cache.transformers_by_code)
    age_seconds = round(time.time() - cache.last_sync_timestamp, 1) if cache.last_sync_timestamp else None

    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "cache": {
            "cached_meters": meters_count,
            "cached_transformers": transformers_count,
            "last_synced_epoch": cache.last_sync_timestamp,
            "cache_age_seconds": age_seconds,
            "is_stale": cache.is_stale(),
            "sync_in_progress": cache.sync_in_progress,
        },
        "upstream": {
            "url": settings.UPSTREAM_URL,
            "authenticated": cache.client._session_cookie is not None,
        },
    }

@app.post(
    "/api/sync",
    tags=["System & Health"],
    summary="Trigger immediate upstream synchronization",
)
async def force_sync():
    """Forces an immediate re-fetch of all meters and transformers from the upstream portal."""
    result = await cache.sync_all(force=True)
    return {"message": "Synchronization completed", "result": result}

# -------------------------------------------------------------
# Meters Endpoints
# -------------------------------------------------------------
@app.get(
    "/api/meters",
    response_model=MeterListResponse,
    tags=["Meters"],
    summary="List and filter smart meters",
)
async def list_meters(
    q: Optional[str] = Query(None, description="Search query matching meter ID, serial number, or DT code"),
    make: Optional[str] = Query(None, description="Filter by manufacturer (HPL, Genus, Secure, Allied, L&T)"),
    phase: Optional[str] = Query(None, description="Filter by phase (single, three)"),
    status: Optional[str] = Query(None, description="Filter by operational status (Installed, Faulty, Decommissioned)"),
    install_type: Optional[str] = Query(None, description="Filter by install type (Whole Current, CT Operated)"),
    build: Optional[str] = Query(None, description="Filter by meter build version (legacy, v2)"),
    dt_code: Optional[str] = Query(None, description="Filter by Distribution Transformer code (e.g. DT-001)"),
    feeder_code: Optional[str] = Query(None, description="Filter by parent Feeder code (e.g. F-001)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=500, description="Number of items per page"),
):
    """Retrieve a paginated, filterable list of smart meters."""
    return await meter_service.list_meters(
        q=q,
        make=make,
        phase=phase,
        status=status,
        install_type=install_type,
        build=build,
        dt_code=dt_code,
        feeder_code=feeder_code,
        page=page,
        page_size=page_size,
    )

@app.get(
    "/api/meters/nearby",
    response_model=List[MeterNearbyItem],
    tags=["Meters"],
    summary="Find meters near geographic coordinates",
)
async def find_nearby_meters(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Center latitude", examples=[26.9124]),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Center longitude", examples=[75.7873]),
    radius_km: float = Query(5.0, gt=0, le=500.0, description="Search radius in kilometers"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results to return"),
    status: Optional[str] = Query(None, description="Filter by status (Installed, Faulty, Decommissioned)"),
    make: Optional[str] = Query(None, description="Filter by manufacturer make"),
):
    """Performs great-circle geospatial radius search using the Haversine formula."""
    return await meter_service.search_nearby(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        limit=limit,
        status=status,
        make=make,
    )

@app.get(
    "/api/meters/{meter_id}",
    response_model=MeterDetail,
    tags=["Meters"],
    summary="Get comprehensive meter details",
)
async def get_meter(meter_id: str):
    """Retrieves unified meter details, including full 7-level distribution hierarchy and normalized nameplate."""
    return await meter_service.get_meter_by_id(meter_id)

@app.get(
    "/api/meters/{meter_id}/energy",
    response_model=EnergyConsumptionSummary,
    tags=["Telemetry & Energy"],
    summary="Get meter interval telemetry & anomaly analysis",
)
async def get_meter_energy(
    meter_id: str,
    refresh: bool = Query(False, description="Bypass cache and force refresh from upstream"),
):
    """
    Retrieves time-series 30-minute interval telemetry readings, computes net consumption,
    calculates voltage metrics, and flags power quality anomalies (voltage sags, swells, spikes).
    """
    # Verify meter exists
    await meter_service.get_meter_by_id(meter_id)
    return await energy_service.get_meter_telemetry(meter_id, force_refresh=refresh)

# -------------------------------------------------------------
# Transformers Endpoints
# -------------------------------------------------------------
@app.get(
    "/api/transformers",
    response_model=List[TransformerSummary],
    tags=["Transformers"],
    summary="List distribution transformers",
)
async def list_transformers(
    feeder_code: Optional[str] = Query(None, description="Filter by parent Feeder code (e.g. F-001)"),
):
    """Lists all Distribution Transformers with connected meter counts."""
    return await transformer_service.list_transformers(feeder_code=feeder_code)

@app.get(
    "/api/transformers/{dt_code}",
    response_model=TransformerDetail,
    tags=["Transformers"],
    summary="Get transformer details, connected meters, and load utilization",
)
async def get_transformer(dt_code: str):
    """Retrieves transformer specifications, connected meter IDs, active breakdown, and estimated capacity utilization."""
    return await transformer_service.get_transformer_by_code(dt_code)

# -------------------------------------------------------------
# Hierarchy Endpoints
# -------------------------------------------------------------
@app.get(
    "/api/hierarchy",
    response_model=HierarchyTreeResponse,
    tags=["Network Hierarchy"],
    summary="Get full 7-tier distribution network hierarchy tree",
)
async def get_network_hierarchy():
    """
    Reconstructs the electrical network tree:
    Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT -> Meters.
    """
    return await hierarchy_service.get_network_tree()

# -------------------------------------------------------------
# Analytics Endpoints
# -------------------------------------------------------------
@app.get(
    "/api/analytics/summary",
    response_model=GridAnalyticsSummary,
    tags=["Analytics"],
    summary="Get high-level grid asset analytics and fleet breakdowns",
)
async def get_grid_analytics():
    """Returns comprehensive asset distributions across status, manufacturer, phase, and DT loading."""
    return await analytics_service.get_grid_summary()

# -------------------------------------------------------------
# Scalar Interactive API Reference
# -------------------------------------------------------------
@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    """Renders modern Scalar API interactive documentation."""
    return HTMLResponse("""
    <!doctype html>
    <html>
      <head>
        <title>Urja Meter Ops API — Scalar Docs</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <script id="api-reference" data-url="/openapi.json"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    """)

# -------------------------------------------------------------
# Web Client Dashboard Mount
# -------------------------------------------------------------
@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serves the modern interactive dashboard UI."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Urja Meter Ops API</h1><p>Visit <a href='/docs'>/docs</a> for Swagger UI.</p>")
