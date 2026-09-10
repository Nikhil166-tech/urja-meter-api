# Urja Meter Ops — Clean API Service & Modern Operations Dashboard

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![OpenAPI 3.1](https://img.shields.io/badge/OpenAPI-3.1-6BA539.svg?logo=openapi-initiative&logoColor=white)](openapi.json)
[![Tests Passing](https://img.shields.io/badge/Tests-12%20Passed-brightgreen.svg)]()

A production-grade, resilient, and well-structured API service built on top of the legacy internal **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`).

This service enables data and engineering teams to programmatically consume smart meter metadata, distribution transformers, 7-tier distribution network hierarchy, geospatial queries, and time-series telemetry with zero browser interaction.

---

## 📑 Key Deliverables & Quick Links

- 📖 [**PROTOCOL.md**](PROTOCOL.md) — Comprehensive reverse engineering report (Authentication, HMAC-SHA256 signatures, schema normalization, and hidden endpoints).
- 📜 [**openapi.json**](openapi.json) — Complete OpenAPI 3.1 specification.
- 🤔 [**REFLECTION.md**](REFLECTION.md) — Engineering reflections, assumptions, trade-offs, and critical review.
- 📚 **Interactive Swagger UI**: Served at `http://localhost:8000/docs`
- 📑 **Scalar API Reference**: Served at `http://localhost:8000/scalar`
- 🗺️ **Modern Web Dashboard**: Served at `http://localhost:8000/dashboard` (or `http://localhost:8000/`)

---

## ✨ Features & Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                      Urja Clean API Architecture                                  |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [ Modern Web Dashboard ]      [ Downstream Services / CLI ]       [ Swagger UI / Scalar Docs ]   |
|            │                                  │                                  │                |
|            └──────────────────────────────────┼──────────────────────────────────┘                |
|                                               ▼                                                   |
|                         ┌───────────────────────────────────────────┐                             |
|                         │           FastAPI Gateway Router          │                             |
|                         │   (Meters, Transformers, Hierarchy, Geo)  │                             |
|                         └─────────────────────┬─────────────────────┘                             |
|                                               │                                                   |
|                         ┌─────────────────────▼─────────────────────┐                             |
|                         │     In-Memory Index & Proactive Cache     │                             |
|                         │   (Haversine Geo, Hierarchy Tree Index)   │                             |
|                         └─────────────────────┬─────────────────────┘                             |
|                                               │                                                   |
|                         ┌─────────────────────▼─────────────────────┐                             |
|                         │        Resilient Upstream Client          │                             |
|                         │  • SvelteKit Session & Re-Auth Handler    │                             |
|                         │  • HMAC-SHA256 Cryptographic Exporter     │                             |
|                         │  • Schema Normalizer (legacy vs v2)       │                             |
|                         └─────────────────────┬─────────────────────┘                             |
|                                               │                                                   |
|                                               ▼                                                   |
|                         ┌───────────────────────────────────────────┐                             |
|                         │   Legacy Urja Meter Ops Upstream Portal   │                             |
|                         │    (https://urja-ops.flockenergy.tech)    │                             |
|                         └───────────────────────────────────────────┘                             |
+---------------------------------------------------------------------------------------------------+
```

### 1. Smart Meter Registry (`/api/meters`)
- Multi-field faceted filtering: `q` (meter ID / serial / DT), `make`, `phase`, `status`, `install_type`, `build`, `dt_code`, `feeder_code`.
- Pagination support with metadata (`total`, `page`, `page_size`, `total_pages`).
- Detailed nameplate extraction unifying heterogeneous `legacy` (`{data}`) and `v2` (`{classData}`) upstream structures.

### 2. Geospatial Proximity Search (`/api/meters/nearby`)
- Radius search in kilometers around any `(lat, lng)` center point using great-circle **Haversine formula**.
- Proximity-sorted meters with exact `distance_km` calculations.

### 3. Reconstructed 7-Tier Network Hierarchy (`/api/hierarchy`)
- Full tree representation matching electricity distribution topology:
  `Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT -> Meters`
- Rollup counts of smart meters at every node in the hierarchy.

### 4. Distribution Transformers & Load Analytics (`/api/transformers`)
- Listing of all 40 DTs with capacity in kVA, parent feeder code, and connected meters list.
- Estimated load calculation and capacity utilization percentage.

### 5. Telemetry & Energy Analytics (`/api/meters/{id}/energy`)
- 30-minute interval readings (kWh, kVAh, Voltage R-phase, calculated power factor).
- Anomaly detection engine flagging **voltage sags (<205V)**, **voltage swells (>250V)**, and **consumption spikes**.

### 6. Modern Interactive Web Client (`/dashboard`)
- **Interactive Dark-Themed Map (Leaflet.js)** displaying meters color-coded by status with point-and-click radius queries.
- **Energy Telemetry Charts (Chart.js)** graphing voltage and energy curves.
- **Live Hierarchy Tree Explorer** with expandable distribution tiers.
- **Fleet Analytics Doughnuts** visualizing make, phase, and status breakdowns.

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.10+ (tested with Python 3.13)
- No database or paid external services required.

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone <your-repo-url>
cd urja-meter-api

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configuration
Default credentials for the Urja portal are pre-configured in `urja_api/config.py`. You can override them via environment variables:
```bash
# Optional overrides:
set URJA_UPSTREAM_URL=https://urja-ops.flockenergy.tech
set URJA_UPSTREAM_USERNAME=operator@urja.local
set URJA_UPSTREAM_PASSWORD=urja-ops-2026
```

### 3. Run the Service
```bash
python run.py --port 8000
```
Open your browser to:
- **Operations Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Scalar API Reference**: [http://localhost:8000/scalar](http://localhost:8000/scalar)

### 4. Run Automated Tests
```bash
pytest -v
```

---

## 📡 Sample API Requests

### 1. List Installed 3-Phase Meters (Genus)
```bash
curl -X GET "http://localhost:8000/api/meters?make=Genus&phase=three&status=Installed&page=1&page_size=10"
```
**Response**:
```json
{
  "total": 35,
  "page": 1,
  "page_size": 10,
  "total_pages": 4,
  "meters": [
    {
      "meter_id": "J100007",
      "serial_no": "GE83049",
      "make": "Genus",
      "phase_type": "three",
      "install_status": "Installed",
      "install_type": "CT Operated",
      "build": "v2",
      "dt_code": "DT-008",
      "location": {
        "latitude": 26.897412,
        "longitude": 75.765032
      },
      "feeder_code": "F-008",
      "substation_code": "SS-08"
    }
  ]
}
```

### 2. Find Meters Within 3 km Radius
```bash
curl -X GET "http://localhost:8000/api/meters/nearby?lat=26.9124&lng=75.7873&radius_km=3.0"
```

### 3. Get Meter Energy Telemetry & Anomaly Assessment
```bash
curl -X GET "http://localhost:8000/api/meters/J100000/energy"
```
**Response**:
```json
{
  "meter_id": "J100000",
  "total_readings": 337,
  "earliest_reading": "23/06/2026 23:30",
  "latest_reading": "30/06/2026 23:30",
  "start_kwh": 48438.74,
  "end_kwh": 48580.12,
  "net_consumption_kwh": 141.38,
  "avg_voltage": 228.4,
  "min_voltage": 204.0,
  "max_voltage": 242.0,
  "avg_power_factor": 0.92,
  "anomalies": [
    {
      "type": "voltage_sag",
      "severity": "medium",
      "timestamp": "25/06/2026 14:00",
      "description": "Voltage sag detected at 204.0V (Nominal: 230V)",
      "observed_value": 204.0,
      "threshold_value": 205.0
    }
  ]
}
```

### 4. Transformer Capacity & Connected Meters Rollup
```bash
curl -X GET "http://localhost:8000/api/transformers/DT-001"
```

### 5. Fetch 7-Level Network Hierarchy
```bash
curl -X GET "http://localhost:8000/api/hierarchy"
```

---

## ⚖️ Design Decisions & Trade-Offs

1. **HMAC-SHA256 Bulk Export vs Individual Scraping**:
   - *Decision*: Reverse engineered the `/portal/keys` and `/portal/export` endpoints to pull all 403 meters with hierarchy in one authenticated, cryptographically signed HTTP call.
   - *Trade-off*: Greatly speeds up sync (under 1.5 seconds) and minimizes upstream load compared to making 400+ sequential scraping requests.
2. **In-Memory Thread-Safe Indexing with Background Refresh**:
   - *Decision*: Store indexed meters in memory with a 15-minute TTL and automatic background sync.
   - *Trade-off*: Eliminates database setup complexity while delivering sub-millisecond query responses. For scale > 1,000,000 meters, an R-Tree / PostGIS database would be introduced.
3. **Pydantic V2 Schema Validation**:
   - *Decision*: Used strict Pydantic models for request/response serialization.
   - *Benefit*: Auto-generated OpenAPI 3.1 documentation, instant validation errors, and clear typing for consumers.

---

## 🔍 What Was Intentionally Skipped
- **Persistent Database (PostgreSQL/MongoDB)**: Skipped to ensure zero-dependency local setup (`pip install -r requirements.txt && python run.py`). The in-memory cache fully accommodates the 403 meters and 40 DTs.
- **Write/Mutation APIs**: The assignment specified treating the portal as read-only.
- **OAuth2 / JWT Gateway Auth**: Skipped client authentication layer to keep the service immediately consumable by internal teams without requiring API key management.

---

## 🔮 What We'd Improve With More Time
- **External Redis Cache**: Allow multi-worker deployments to share cached state across processes.
- **Spatial Indexing (PostGIS / SQLite R*Tree)**: Accelerate polygon and bounding-box queries for millions of meters.
- **WebSocket Telemetry Stream**: Push real-time voltage alarms directly to operational dispatch dashboards.
