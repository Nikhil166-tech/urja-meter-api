class UpstreamError(Exception):
    """Base exception for upstream portal interactions."""
    def __init__(self, message: str, status_code: int = 502, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class UpstreamAuthError(UpstreamError):
    """Raised when authentication to the upstream portal fails."""
    def __init__(self, message: str = "Failed to authenticate with upstream Urja portal", details: dict = None):
        super().__init__(message, status_code=502, details=details)

class UpstreamSignatureError(UpstreamError):
    """Raised when cryptographic HMAC signing fails or signing secret is unavailable."""
    def __init__(self, message: str = "Failed to retrieve signing secret or sign upstream export request", details: dict = None):
        super().__init__(message, status_code=502, details=details)

class UpstreamNotFoundError(UpstreamError):
    """Raised when an entity is not found in the upstream portal."""
    def __init__(self, entity: str, identifier: str):
        super().__init__(f"{entity} with ID '{identifier}' not found in upstream portal.", status_code=404)
