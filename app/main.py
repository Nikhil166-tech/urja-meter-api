"""
App entry point forwarding to the production urja_api implementation.
Allows running with `uvicorn app.main:app` or importing `from app.main import app`.
"""
from urja_api.main import app

__all__ = ["app"]
