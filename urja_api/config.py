from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Configuration settings for Urja Meter Ops Clean API."""
    UPSTREAM_URL: str = Field(default="https://urja-ops.flockenergy.tech", description="Base URL of the upstream Urja portal")
    UPSTREAM_USERNAME: str = Field(default="operator@urja.local", description="Upstream operator email")
    UPSTREAM_PASSWORD: str = Field(default="urja-ops-2026", description="Upstream operator password")
    
    UPSTREAM_TIMEOUT_SECONDS: float = Field(default=30.0, description="HTTP timeout for upstream requests")
    MAX_RETRIES: int = Field(default=3, description="Maximum retry count on upstream network failures")
    RETRY_BACKOFF_FACTOR: float = Field(default=1.5, description="Backoff factor for retries")
    
    CACHE_TTL_SECONDS: int = Field(default=900, description="Cache TTL for meters and transformers (15 mins)")
    ENERGY_CACHE_TTL_SECONDS: int = Field(default=300, description="Cache TTL for meter energy telemetry (5 mins)")
    AUTO_SYNC_INTERVAL_SECONDS: int = Field(default=600, description="Background sync interval (10 mins)")
    
    SERVICE_NAME: str = "Urja Meter Ops Clean API"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = False

    class Config:
        env_prefix = "URJA_"
        case_sensitive = False

settings = Settings()
