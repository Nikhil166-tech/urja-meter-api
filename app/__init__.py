"""
App package wrapper providing full compatibility with the assignment's recommended layout:
from app.client import UrjaPortalClient
from app.main import app
"""
from urja_api.main import app
from urja_api.client.upstream import UrjaPortalClient, UrjaUpstreamClient
from urja_api.config import settings

__all__ = ["app", "UrjaPortalClient", "UrjaUpstreamClient", "settings"]
