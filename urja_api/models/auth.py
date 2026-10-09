from typing import Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    """User credentials for logging into the Urja Meter Ops portal."""
    username: Optional[str] = Field(None, description="Username or email (defaults to configured operator)", examples=["operator@urja.local"])
    email: Optional[str] = Field(None, description="Email address (alias for username)", examples=["operator@urja.local"])
    password: Optional[str] = Field(None, description="Password (defaults to configured secret)", examples=["urja-ops-2026"])

class LoginResponse(BaseModel):
    """Authentication response with session state."""
    status: str = Field("success", description="Status string: success or error", examples=["success"])
    message: str = Field(..., description="Authentication status message", examples=["Successfully authenticated with upstream portal"])
    authenticated: bool = Field(True, description="Whether session is currently authenticated", examples=[True])
    session_token_present: bool = Field(True, description="Whether active session cookie exists", examples=[True])
    upstream_url: str = Field(..., description="Upstream portal URL", examples=["https://urja-ops.flockenergy.tech"])
