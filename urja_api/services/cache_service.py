import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from urja_api.client.upstream import UrjaUpstreamClient
from urja_api.config import settings

logger = logging.getLogger(__name__)

class LocalDataCache:
    """
    In-memory indexed cache holding meters, transformers, and telemetry.
    Supports asynchronous proactive background synchronization.
    """

    def __init__(self, client: UrjaUpstreamClient):
        self.client = client
        self.meters_by_id: Dict[str, Dict[str, Any]] = {}
        self.transformers_by_code: Dict[str, Dict[str, Any]] = {}
        self.energy_cache: Dict[str, Dict[str, Any]] = {}  # meter_id -> {timestamp, data}
        
        self.last_sync_timestamp: float = 0.0
        self.sync_in_progress: bool = False
        self._lock = asyncio.Lock()
        self._sync_task: Optional[asyncio.Task] = None

    def is_stale(self) -> bool:
        """Determines if the meter & transformer cache exceeds configured TTL."""
        if not self.last_sync_timestamp:
            return True
        return (time.time() - self.last_sync_timestamp) > settings.CACHE_TTL_SECONDS

    async def sync_all(self, force: bool = False) -> Dict[str, int]:
        """
        Fetches full meter dataset via signed HMAC bulk export and all DTs.
        """
        async with self._lock:
            if not force and not self.is_stale() and self.meters_by_id:
                return {
                    "meters": len(self.meters_by_id),
                    "transformers": len(self.transformers_by_code),
                }

            self.sync_in_progress = True
            logger.info("Starting synchronization with upstream Urja portal...")
            start_time = time.time()

            try:
                # Concurrent fetch of meters export and transformers
                meters_task = asyncio.create_task(self.client.fetch_all_meters_export())
                transformers_task = asyncio.create_task(self.client.fetch_all_transformers())
                
                raw_meters, raw_transformers = await asyncio.gather(meters_task, transformers_task)

                new_meters: Dict[str, Dict[str, Any]] = {}
                for m in raw_meters:
                    mid = m.get("meterId")
                    if mid:
                        new_meters[mid] = m

                new_transformers: Dict[str, Dict[str, Any]] = {}
                for t in raw_transformers:
                    code = t.get("code")
                    if code:
                        new_transformers[code] = t

                self.meters_by_id = new_meters
                self.transformers_by_code = new_transformers
                self.last_sync_timestamp = time.time()

                duration = time.time() - start_time
                logger.info(
                    "Sync complete in %.2fs: %d meters, %d transformers indexed.",
                    duration,
                    len(self.meters_by_id),
                    len(self.transformers_by_code),
                )

                return {
                    "meters": len(self.meters_by_id),
                    "transformers": len(self.transformers_by_code),
                    "duration_seconds": round(duration, 2),
                }
            except Exception as e:
                logger.error("Failed to sync from upstream: %s", str(e))
                if not self.meters_by_id:
                    raise
                # If we already have cached data, retain it as fallback
                return {
                    "meters": len(self.meters_by_id),
                    "transformers": len(self.transformers_by_code),
                    "warning": f"Sync failed, serving existing cache: {str(e)}",
                }
            finally:
                self.sync_in_progress = False

    async def get_meters(self) -> List[Dict[str, Any]]:
        if self.is_stale() or not self.meters_by_id:
            await self.sync_all()
        return list(self.meters_by_id.values())

    async def get_meter(self, meter_id: str) -> Optional[Dict[str, Any]]:
        if not self.meters_by_id or self.is_stale():
            await self.sync_all()
        return self.meters_by_id.get(meter_id)

    async def get_transformers(self) -> List[Dict[str, Any]]:
        if self.is_stale() or not self.transformers_by_code:
            await self.sync_all()
        return list(self.transformers_by_code.values())

    async def get_transformer(self, dt_code: str) -> Optional[Dict[str, Any]]:
        if not self.transformers_by_code or self.is_stale():
            await self.sync_all()
        return self.transformers_by_code.get(dt_code)

    async def get_meter_energy(self, meter_id: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        cached = self.energy_cache.get(meter_id)
        if cached and not force_refresh:
            if (now - cached["timestamp"]) < settings.ENERGY_CACHE_TTL_SECONDS:
                return cached["data"]

        readings = await self.client.fetch_meter_energy(meter_id)
        self.energy_cache[meter_id] = {
            "timestamp": now,
            "data": readings,
        }
        return readings

    def start_background_sync(self):
        """Starts periodic background synchronization loop."""
        async def _loop():
            while True:
                try:
                    await asyncio.sleep(settings.AUTO_SYNC_INTERVAL_SECONDS)
                    logger.info("Executing periodic background sync...")
                    await self.sync_all(force=True)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Background sync error: %s", str(e))

        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(_loop())

    def stop_background_sync(self):
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
