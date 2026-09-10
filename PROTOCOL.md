# Urja Meter Ops — Reverse-Engineered Portal Protocol & Internal Architecture

This document details the reverse engineering investigation of the legacy **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`). It explains authentication mechanics, cryptographic signatures, data serialization patterns, quirks, and hidden API endpoints.

---

## 1. System Architecture & Tech Stack

The portal is a **SvelteKit (Vite-bundled)** web application.
- **Frontend Framework**: Svelte 5 / SvelteKit with client-side hydration and SSR components.
- **Authentication**: Cookie-based session management (`__Secure-better-auth.session_token`).
- **Data Flow**: Hybrid SvelteKit `+page.server.ts` data de-serialization (`__data.json`) and direct client REST fetches to internal `/portal/*` endpoints.

---

## 2. Authentication & Session Protocol

### Upstream Endpoint
`POST https://urja-ops.flockenergy.tech/login`

### Required Request Headers
Because the portal uses SvelteKit CSRF protections and form action handlers, standard POST requests will fail with `403 Forbidden (Cross-site POST form submissions are forbidden)` or `405 Method Not Allowed` unless specific headers are supplied:

```http
POST /login HTTP/1.1
Host: urja-ops.flockenergy.tech
Content-Type: application/x-www-form-urlencoded
Origin: https://urja-ops.flockenergy.tech
Referer: https://urja-ops.flockenergy.tech/login
x-sveltekit-action: true
Accept: application/json

email=operator%40urja.local&password=urja-ops-2026
```

### Response
```json
{
  "type": "redirect",
  "status": 303,
  "location": "/meters"
}
```
**Response Header**:
```http
Set-Cookie: __Secure-better-auth.session_token=<SESSION_TOKEN>; Max-Age=3600; Path=/; HttpOnly; Secure; SameSite=Lax
```

### Session Lifecycle
- Session tokens are valid for **3600 seconds (1 hour)**.
- Subsequent requests must supply the session token in the `Cookie` header: `Cookie: __Secure-better-auth.session_token=<TOKEN>`.
- Sign-out is handled via `POST /api/auth/sign-out`.

---

## 3. Discovered Endpoints & Protocols

| Endpoint | Method | Purpose | Auth Required |
| :--- | :--- | :--- | :--- |
| `/login` | `POST` | SvelteKit form action to authenticate | No |
| `/portal/keys` | `GET` | Retrieves HMAC export signing secret | Yes (Cookie) |
| `/portal/export?page=1` | `GET` | Cryptographically signed bulk meters export | Yes (Cookie + HMAC) |
| `/portal/dts?page={page}` | `GET` | Paginated Distribution Transformers | Yes (Cookie) |
| `/portal/meters/search?q={q}&page={p}` | `GET` | Paginated search of meters | Yes (Cookie) |
| `/portal/meters/{id}/energy` | `GET` | 30-minute interval telemetry readings | Yes (Cookie) |
| `/portal/meters/{id}/geo` | `GET` | Meter latitude & longitude | Yes (Cookie) |
| `/meters/{id}/__data.json` | `GET` | SvelteKit SSR dehydrated page state | Yes (Cookie) |

---

## 4. Cryptographic HMAC-SHA256 Bulk Export Protocol

The portal exposes a high-throughput bulk export endpoint at `/portal/export`. Accessing this endpoint requires calculating an **HMAC-SHA256 signature** using a dynamic key provided by `/portal/keys`.

### Step 1: Fetch Signing Secret
```http
GET /portal/keys HTTP/1.1
Cookie: __Secure-better-auth.session_token=...

Response:
{
  "data": {
    "signingSecret": "I3dZPPf5CgTp7JyGNMI8i6z8LFR7TmSR"
  }
}
```

### Step 2: Signature Construction
1. Capture current Unix epoch timestamp in seconds: `timestamp = str(int(time.time()))`.
2. Construct canonical message to sign:
   ```
   "GET\n/portal/export\npage=1\n<timestamp>"
   ```
3. Compute HMAC-SHA256:
   ```python
   signature = hmac.new(
       key=signing_secret.encode('utf-8'),
       msg=canonical_string.encode('utf-8'),
       digestmod=hashlib.sha256
   ).hexdigest()
   ```

### Step 3: Execute Request
```http
GET /portal/export?page=1 HTTP/1.1
Host: urja-ops.flockenergy.tech
Cookie: __Secure-better-auth.session_token=...
x-timestamp: 1725969600
x-signature: <computed_hex_digest>
```

### Response Payload
Returns all **403 meters** with full 7-level hierarchy and geo coordinates in a single fast JSON response (~150KB):
```json
{
  "total": 403,
  "data": [
    {
      "meterId": "J100000",
      "serialNo": "SE33962",
      "make": "HPL",
      "phaseType": "single",
      "installStatus": "Decommissioned",
      "installType": "Whole Current",
      "build": "legacy",
      "dtCode": "DT-001",
      "hierarchy": {
        "zone": { "name": "Jaipur Zone 1", "code": "Z-01" },
        "circle": { "name": "Circle 1", "code": "C-01" },
        "division": { "name": "Division 1", "code": "D-01" },
        "subdivision": { "name": "Subdivision 1", "code": "SD-01" },
        "substation": { "name": "Substation 1", "code": "SS-01" },
        "feeder": { "name": "Feeder 1", "code": "F-001" },
        "dt": { "name": "Malviya Nagar DT 1", "code": "DT-001" }
      },
      "geo": {
        "lat": 26.938961002479868,
        "lng": 75.83095696146852
      }
    }
  ]
}
```

---

## 5. Quirks, Inconsistencies & Edge Cases Discovered

### 1. Heterogeneous Meter Schema: Legacy vs V2 Meters
- **Legacy Meters (`build: "legacy"`, 238 meters)**:
  In SvelteKit page state (`/meters/{id}/__data.json`), nameplate data is formatted as an array of key-value tuples:
  `detail: { data: [{ parameterName: "Make", parameterValue: "HPL" }, ...] }`.
- **V2 Meters (`build: "v2"`, 165 meters)**:
  Nameplate data is formatted as an escaped JSON string:
  `detail: { classData: "{\"installed_meter\": {\"Make\": \"Genus\", ...}}" }`.
- **Clean Gateway Solution**: The gateway client normalizes both formats into a uniform array of `NameplateParameter(name, value)`.

### 2. Time-Series Telemetry Format
- Timestamps in `/portal/meters/{id}/energy` are formatted as `"DD/MM/YYYY HH:MM"` (e.g. `"24/06/2026 00:00"`).
- Reading fields (`kwh`, `kvah`, `voltR`) are returned as strings or `"—"` for missing intervals.
- **Clean Gateway Solution**: Values are parsed into numeric floats, `"—"` is mapped to `null`, and consecutive intervals are analyzed to calculate incremental kWh delta, power factor (`ΔkWh / ΔkVAh`), and detect grid anomalies.

### 3. SvelteKit SSR De-serialization
- Route `/meters/{id}` loads data server-side and serves a deval-compressed index map at `/__data.json`.
- The gateway includes a recursive pointer resolver that walks index references to extract raw fields when direct page SSR is inspected.

---

## 6. Distribution Network Hierarchy Specification

The portal models the electrical distribution network across 7 distinct tiers:
1. **Zone**: Top-level geographical area (`Jaipur Zone 1 [Z-01]`, `Jaipur Zone 2 [Z-02]`).
2. **Circle**: Administrative district (`Circle 1 [C-01]`, `Circle 2 [C-02]`).
3. **Division**: Operational division (`Division 1 [D-01]`, `Division 2 [D-02]`).
4. **Subdivision**: Local utility subdivision (`Subdivision 1 [SD-01]`, `Subdivision 2 [SD-02]`).
5. **Substation**: 33kV/11kV electrical substation (`Substation 1 [SS-01]`, `Substation 2 [SS-02]`).
6. **Feeder**: 11kV primary feeder lines (`Feeder 1 [F-001]`, `Feeder 2 [F-002]`).
7. **Distribution Transformer (DT)**: 11kV/415V step-down transformers (`DT-001` through `DT-040`).
8. **Smart Meter**: Consumer endpoint (`J100000` through `J100402`).

All 403 meters have complete mapping across all 7 hierarchy levels.
