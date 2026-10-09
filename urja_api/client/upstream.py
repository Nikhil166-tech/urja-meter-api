import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from bs4 import BeautifulSoup

from urja_api.config import settings
from urja_api.client.exceptions import (
    UpstreamAuthError,
    UpstreamError,
    UpstreamNotFoundError,
    UpstreamSignatureError,
)

logger = logging.getLogger(__name__)

class UrjaUpstreamClient:
    """
    Reverse-engineered client for the legacy Urja Meter Ops portal.
    Features:
    - SvelteKit form-action authentication handling (with x-sveltekit-action header).
    - Session cookie extraction and persistent reuse.
    - Automatic session renewal on expiration.
    - HMAC-SHA256 signature calculation for protected export routes using dynamic keys.
    - Robust retry logic with exponential backoff.
    - Normalization of heterogeneous meter schemas (legacy data arrays vs v2 classData JSON).
    - BeautifulSoup HTML parsing fallback for direct SSR web pages.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.UPSTREAM_URL).rstrip("/")
        self.username = settings.UPSTREAM_USERNAME
        self.password = settings.UPSTREAM_PASSWORD
        self._session_cookie: Optional[str] = None
        self._signing_secret: Optional[str] = None
        self._signing_secret_cached_at: float = 0
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop = None
        self._lock_obj: Optional[asyncio.Lock] = None
        self._lock_loop = None

    @property
    def lock(self) -> asyncio.Lock:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if self._lock_obj is None or self._lock_loop != current_loop:
            self._lock_obj = asyncio.Lock()
            self._lock_loop = current_loop
        return self._lock_obj

    async def get_http_client(self) -> httpx.AsyncClient:
        current_loop = asyncio.get_running_loop()
        if (
            self._client is None
            or self._client.is_closed
            or self._client_loop != current_loop
        ):
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.UPSTREAM_TIMEOUT_SECONDS),
                headers={
                    "User-Agent": "Urja-Clean-API-Gateway/1.0",
                    "Accept": "application/json, text/html, */*",
                },
                follow_redirects=True,
            )
            self._client_loop = current_loop
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        force: bool = False,
    ) -> str:
        """
        Authenticates against SvelteKit form action at /login.
        Requires x-sveltekit-action, Origin, and Referer headers.
        """
        async with self.lock:
            login_user = username or self.username
            login_pass = password or self.password

            if self._session_cookie and not force and (login_user == self.username):
                return self._session_cookie

            logger.info("Authenticating with upstream Urja portal at %s/login", self.base_url)
            client = await self.get_http_client()
            login_url = f"{self.base_url}/login"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/login",
                "x-sveltekit-action": "true",
                "Accept": "application/json",
            }
            data = {
                "email": login_user,
                "password": login_pass,
            }

            try:
                response = await client.post(login_url, data=data, headers=headers)
            except Exception as e:
                raise UpstreamAuthError(f"Network failure during upstream login: {str(e)}")

            if response.status_code not in (200, 303):
                raise UpstreamAuthError(
                    f"Upstream login returned status {response.status_code}",
                    details={"body": response.text[:200]},
                )

            # Look for session cookie in client cookie jar or Set-Cookie header
            session_cookie = None
            for cookie in client.cookies.jar:
                if "session_token" in cookie.name:
                    session_cookie = f"{cookie.name}={cookie.value}"
                    break

            if not session_cookie:
                # Inspect headers directly
                set_cookie = response.headers.get("set-cookie", "")
                if "session_token" in set_cookie:
                    parts = set_cookie.split(";")
                    for p in parts:
                        if "session_token" in p:
                            session_cookie = p.strip()
                            break

            if not session_cookie:
                raise UpstreamAuthError("Upstream login succeeded but session cookie was not provided.")

            self._session_cookie = session_cookie
            logger.info("Upstream authentication successful.")
            return self._session_cookie

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        retry_auth: bool = True,
    ) -> httpx.Response:
        """Executes an authenticated HTTP request with retry & auto-reauth handling."""
        client = await self.get_http_client()
        cookie = await self.login()
        req_headers = {
            "Cookie": cookie,
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        url = f"{self.base_url}{path}"
        retries = settings.MAX_RETRIES

        for attempt in range(1, retries + 1):
            try:
                resp = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=req_headers,
                    data=data,
                )

                # Check if session expired or rejected (401, 403, or redirected to /login)
                if resp.status_code in (401, 403) and retry_auth:
                    logger.warning("Upstream returned %d, refreshing session token...", resp.status_code)
                    await self.login(force=True)
                    req_headers["Cookie"] = self._session_cookie
                    return await self._request(
                        method, path, params, headers, data, retry_auth=False
                    )

                if resp.status_code >= 500 and attempt < retries:
                    backoff = settings.RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning("Upstream %d error on %s, retrying in %.2fs...", resp.status_code, path, backoff)
                    await asyncio.sleep(backoff)
                    continue

                return resp
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                if attempt < retries:
                    backoff = settings.RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning("Upstream network error on %s: %s. Retrying in %.2fs...", path, str(exc), backoff)
                    await asyncio.sleep(backoff)
                else:
                    raise UpstreamError(f"Upstream request failed after {retries} attempts: {str(exc)}")

        raise UpstreamError(f"Upstream request failed: {method} {path}")

    async def get_signing_secret(self, force_refresh: bool = False) -> str:
        """Fetches the HMAC signing secret from /portal/keys."""
        now = time.time()
        if self._signing_secret and not force_refresh and (now - self._signing_secret_cached_at < 3600):
            return self._signing_secret

        resp = await self._request("GET", "/portal/keys")
        if resp.status_code != 200:
            raise UpstreamSignatureError(f"Failed to fetch keys (status {resp.status_code})")

        try:
            payload = resp.json()
            secret = payload.get("data", {}).get("signingSecret")
            if not secret:
                raise UpstreamSignatureError("signingSecret missing in keys response")
            self._signing_secret = secret
            self._signing_secret_cached_at = now
            return secret
        except Exception as e:
            raise UpstreamSignatureError(f"Error parsing upstream signing secret: {str(e)}")

    def compute_export_signature(self, query_string: str, timestamp: str, secret: str) -> str:
        """
        Calculates HMAC-SHA256 signature for /portal/export.
        Protocol:
            Message: "GET\n/portal/export\n<query_string>\n<timestamp>"
            Signature: HMAC_SHA256(secret, Message).hexdigest()
        """
        message = f"GET\n/portal/export\n{query_string}\n{timestamp}"
        return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    async def fetch_all_meters_export(self) -> List[Dict[str, Any]]:
        """
        Fetches the complete dataset of meters with full 7-level hierarchy and geo coords
        using the cryptographically signed bulk export endpoint.
        """
        secret = await self.get_signing_secret()
        query_params = "page=1"
        timestamp = str(int(time.time()))
        signature = self.compute_export_signature(query_params, timestamp, secret)

        headers = {
            "x-timestamp": timestamp,
            "x-signature": signature,
        }

        resp = await self._request("GET", f"/portal/export?{query_params}", headers=headers)
        if resp.status_code == 403:
            # Secret might have rotated, retry once with fresh secret
            secret = await self.get_signing_secret(force_refresh=True)
            timestamp = str(int(time.time()))
            signature = self.compute_export_signature(query_params, timestamp, secret)
            headers = {"x-timestamp": timestamp, "x-signature": signature}
            resp = await self._request("GET", f"/portal/export?{query_params}", headers=headers)

        if resp.status_code != 200:
            raise UpstreamError(f"Failed to export meters from portal (status {resp.status_code})")

        payload = resp.json()
        return payload.get("data", [])

    async def fetch_all_transformers(self) -> List[Dict[str, Any]]:
        """Fetches all Distribution Transformers (DTs) across all pages."""
        transformers = []
        page = 1
        while True:
            resp = await self._request("GET", f"/portal/dts?page={page}")
            if resp.status_code != 200:
                raise UpstreamError(f"Failed to fetch transformers page {page} (status {resp.status_code})")
            
            payload = resp.json()
            data = payload.get("data", [])
            if not data:
                break
            transformers.extend(data)
            total = payload.get("total", 0)
            if len(transformers) >= total:
                break
            page += 1
        return transformers

    async def fetch_meter_energy(self, meter_id: str) -> List[Dict[str, Any]]:
        """Fetches time-series telemetry / energy readings for a specific meter."""
        resp = await self._request("GET", f"/portal/meters/{meter_id}/energy")
        if resp.status_code == 404:
            raise UpstreamNotFoundError("Meter", meter_id)
        if resp.status_code != 200:
            raise UpstreamError(f"Failed to fetch energy for meter {meter_id} (status {resp.status_code})")
        
        payload = resp.json()
        return payload.get("data", [])

    async def fetch_meter_geo(self, meter_id: str) -> Dict[str, Any]:
        """Fetches geolocation coordinates for a specific meter."""
        resp = await self._request("GET", f"/portal/meters/{meter_id}/geo")
        if resp.status_code == 404:
            raise UpstreamNotFoundError("Meter", meter_id)
        if resp.status_code != 200:
            raise UpstreamError(f"Failed to fetch geo for meter {meter_id} (status {resp.status_code})")
        
        payload = resp.json()
        return payload.get("data", {})

    async def fetch_meter_server_detail(self, meter_id: str) -> Dict[str, Any]:
        """
        Fetches SvelteKit SSR __data.json for a meter and normalizes heterogeneous
        'legacy' ({data: [{parameterName, parameterValue}]}) vs 'v2' ({classData: "..."}) nameplates.
        Falls back to parsing raw HTML with BeautifulSoup if __data.json is unavailable.
        """
        try:
            resp = await self._request("GET", f"/meters/{meter_id}/__data.json")
            if resp.status_code == 200:
                raw_json = resp.json()
                return self._parse_sveltekit_meter_data(raw_json, meter_id)
            elif resp.status_code == 404:
                raise UpstreamNotFoundError("Meter", meter_id)
        except UpstreamNotFoundError:
            raise
        except Exception as e:
            logger.debug("Could not fetch __data.json for %s, falling back to HTML: %s", meter_id, e)

        # Fallback to direct HTML fetching and BeautifulSoup parsing
        resp_html = await self._request("GET", f"/meters/{meter_id}")
        if resp_html.status_code == 404:
            raise UpstreamNotFoundError("Meter", meter_id)
        if resp_html.status_code == 200:
            return self.parse_meter_html_detail(resp_html.text, meter_id)

        raise UpstreamError(f"Failed to fetch detail for meter {meter_id} (status {resp_html.status_code})")

    def parse_meter_html_detail(self, html_content: str, meter_id: str) -> Dict[str, Any]:
        """
        Parses raw HTML from /meters/{meter_id} using BeautifulSoup.
        Extracts nameplate specification parameters from <dl> or <table> tags,
        strips whitespace, and normalizes values.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        nameplate_entries = []

        # 1. Parse <dl> definitions (standard Urja SvelteKit nameplate component)
        dl = soup.find("dl")
        if dl:
            for div in dl.find_all("div"):
                dt = div.find("dt")
                dd = div.find("dd")
                if dt and dd:
                    p_name = dt.get_text(strip=True)
                    p_val = dd.get_text(strip=True)
                    if p_name and p_val:
                        nameplate_entries.append({
                            "parameterName": p_name,
                            "parameterValue": p_val,
                        })

        # 2. Parse <table> rows fallback
        if not nameplate_entries:
            table = soup.find("table")
            if table:
                for row in table.find_all("tr"):
                    cells = row.find_all(["th", "td"])
                    if len(cells) == 2:
                        p_name = cells[0].get_text(strip=True)
                        p_val = cells[1].get_text(strip=True)
                        if p_name and p_val:
                            nameplate_entries.append({
                                "parameterName": p_name,
                                "parameterValue": p_val,
                            })

        # 3. Extract hierarchy breadcrumbs from nav if present
        hierarchy_dict = {}
        nav = soup.find("nav")
        if nav:
            spans = [s.get_text(strip=True) for s in nav.find_all("span") if s.get_text(strip=True)]
            hierarchy_keys = ["Zone", "Circle", "Division", "Subdivision", "Sub Station", "Feeder", "DT"]
            for idx, text in enumerate(spans):
                if idx < len(hierarchy_keys):
                    hierarchy_dict[hierarchy_keys[idx]] = text

        return {
            "meterId": meter_id,
            "nameplate": nameplate_entries,
            "hierarchy": hierarchy_dict,
        }

    def _parse_sveltekit_meter_data(self, svelte_data: Dict[str, Any], meter_id: str) -> Dict[str, Any]:
        """
        Reconstructs the de-serialized SvelteKit payload into a clean, unified dictionary.
        """
        nodes = svelte_data.get("nodes", [])
        if len(nodes) < 3 or not nodes[2] or "data" not in nodes[2]:
            return {"meterId": meter_id, "nameplate": [], "hierarchy": {}}

        arr = nodes[2]["data"]
        # In SvelteKit deval serialization, arr[0] is root object mapping keys to index pointers
        root_map = arr[0] if isinstance(arr[0], dict) else {}
        
        nameplate_entries = []
        hierarchy_dict = {}

        # Resolve detail
        detail_ptr = root_map.get("detail")
        if detail_ptr is not None and detail_ptr < len(arr):
            detail_obj = arr[detail_ptr]
            if isinstance(detail_obj, dict):
                if "classData" in detail_obj:
                    class_data_str = arr[detail_obj["classData"]] if isinstance(detail_obj["classData"], int) else detail_obj["classData"]
                    try:
                        parsed = json.loads(class_data_str)
                        installed = parsed.get("installed_meter", {})
                        for k, v in installed.items():
                            nameplate_entries.append({"parameterName": k, "parameterValue": str(v)})
                    except Exception:
                        pass
                elif "data" in detail_obj:
                    items_ptr = detail_obj["data"]
                    if isinstance(items_ptr, int) and items_ptr < len(arr):
                        pointers = arr[items_ptr]
                        if isinstance(pointers, list):
                            for p in pointers:
                                if isinstance(p, int) and p < len(arr):
                                    item = arr[p]
                                    if isinstance(item, dict):
                                        p_name_idx = item.get("parameterName")
                                        p_val_idx = item.get("parameterValue")
                                        name = arr[p_name_idx] if isinstance(p_name_idx, int) and p_name_idx < len(arr) else str(p_name_idx)
                                        val = arr[p_val_idx] if isinstance(p_val_idx, int) and p_val_idx < len(arr) else str(p_val_idx)
                                        nameplate_entries.append({"parameterName": str(name), "parameterValue": str(val)})

        # Resolve hierarchy
        hierarchy_ptr = root_map.get("hierarchy")
        if hierarchy_ptr is not None and hierarchy_ptr < len(arr):
            raw_h = arr[hierarchy_ptr]
            if isinstance(raw_h, dict):
                for k, v_idx in raw_h.items():
                    val = arr[v_idx] if isinstance(v_idx, int) and v_idx < len(arr) else str(v_idx)
                    hierarchy_dict[k] = str(val)

        return {
            "meterId": meter_id,
            "nameplate": nameplate_entries,
            "hierarchy": hierarchy_dict,
        }

    # Compatibility methods matching UrjaPortalClient snippet in reference doc
    def get_meter_details(self, meter_id: str) -> Dict[str, Any]:
        """Synchronous/convenience wrapper matching reference doc UrjaPortalClient."""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a separate thread or new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.fetch_meter_server_detail(meter_id)).result()
        return asyncio.run(self.fetch_meter_server_detail(meter_id))


# Canonical alias matching assignment reference doc snippet
UrjaPortalClient = UrjaUpstreamClient

