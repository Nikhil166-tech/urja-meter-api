# Engineering Reflection

### 1. What assumptions did you make?
- **Read-Only Portal Guarantees**: Assumed the upstream portal is strictly read-only and that polling periodic bulk data wouldn't disrupt normal operations or trigger rate-limit bans if kept within reasonable intervals (10–15 minutes).
- **Session Token Validity**: Observed that the `__Secure-better-auth.session_token` cookie has a 1-hour expiration. Assumed that caching the cookie across client requests and refreshing it on `401/403` status codes provides optimal upstream efficiency without incurring login overhead on every request.
- **HMAC Export Stability**: Assumed `/portal/export` is the authoritative and canonical data source for fleet synchronization, as it returns complete hierarchy trees and geo-coordinates in a single signed request.
- **Estimated DT Load**: For transformer capacity utilization, assumed standard Indian LT residential baseline estimates (single-phase ~3 kW average load, three-phase ~10 kW load, power factor ~0.9) to compute estimated DT peak loading since real-time concurrent transformer telemetry was not separately metered on the upstream DT summary page.

---

### 2. Which part was the most difficult, and how did you get unstuck?
- **The Challenge**: Initial direct POST requests to `/login` returned `403 Forbidden (Cross-site POST form submissions are forbidden)` and subsequently `405 Method Not Allowed`. Additionally, SvelteKit client routes dehydrate state into `/__data.json` using integer pointer indexing rather than standard JSON objects.
- **Getting Unstuck**: I downloaded and analyzed the Vite-bundled JS chunks (`app.03ZTmlg3.js`, `7.OkXSQ8CK.js`, `4.2Bgc2kUI.js`). Inspecting `7.OkXSQ8CK.js` revealed the required `x-sveltekit-action: true`, `Origin`, and `Referer` headers. Furthermore, inspecting `4.2Bgc2kUI.js` uncovered the hidden `/portal/keys` endpoint and the exact HMAC-SHA256 signature construction string for `/portal/export`, transforming what would have been 400+ sequential HTTP requests into a single fast, cryptographically authenticated bulk synchronization.

---

### 3. If you had another day, what would you improve?
- **SQLite / Postgres Spatial Index (PostGIS / R-Tree)**: Currently, geospatial queries compute great-circle distances via in-memory Haversine calculations over 403 meters in < 1ms. For datasets exceeding 1,000,000 meters, I would implement an R-Tree spatial index (or PostGIS `ST_DWithin`) to maintain sub-millisecond proximity queries.
- **Redis Distributed Cache & Pub/Sub**: Replace the single-node in-memory cache with Redis to allow multi-instance API gateway scaling.
- **WebSocket Live Stream for Telemetry**: Add WebSocket endpoints (`/ws/meters/{id}/live`) for real-time telemetry streaming and live voltage threshold alert notifications.
- **Historical Telemetry Aggregations**: Pre-compute rolling hourly and daily kWh consumption trends and export CSV/Parquet bulk datasets.

---

### 4. What mistake did you make while solving this (there's always one)?
- **Initial Form Submission Assumption**: Initially, I attempted to submit the login credentials to `/` instead of `/login`. SvelteKit routes form actions to the matching route path (`/login`), which produced a `405 Method Not Allowed`.
- **Resolution**: Checking `app.03ZTmlg3.js` route dictionary confirmed `"/login": [-8]`, prompting the switch to POSTing to `/login` with the proper `x-sveltekit-action` header.

---

### 5. If you were reviewing your own submission, what would you criticise?
- **Single-Node In-Memory Cache**: The in-memory cache is ideal and blisteringly fast for the 403 meters in this assignment, but in a production environment with hundreds of thousands of meters across multiple load-balanced worker processes, an external cache store (Redis) and relational database (PostgreSQL) would be required for persistent indexing and inter-process sync.
- **Energy Telemetry Upstream Coupling**: Energy telemetry is currently fetched on-demand per meter (with a 5-minute cache). If 100 users simultaneously queried energy for all 403 meters, it would generate 403 upstream requests. Implementing a batch queue worker with request collapsing would mitigate potential upstream throttling.
