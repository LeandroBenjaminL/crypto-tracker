"""
Custom exceptions for crypto-tracker.

These exceptions are part of the domain layer and help
differentiate between different error types.
"""


class CryptoTrackerError(Exception):
    """
    Base exception for all crypto-tracker errors.
    
    All custom exceptions inherit from this class,
    making it easy to catch any app-specific error.
    """
    pass


class CoinNotFoundError(CryptoTrackerError):
    """
    Raised when a cryptocurrency cannot be found.
    
    Could be because:
    - Invalid coin symbol/id
    - Coin doesn't exist on the exchange
    """
    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Coin not found: '{identifier}'")


class APIError(CryptoTrackerError):
    """
    Raised when there's a problem communicating with the API.
    
    This wraps any HTTP-related errors from the adapter layer.
    """
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class RateLimitError(APIError):
    """
    Raised when API rate limit is exceeded.
    
    The user should wait before making more requests.
    """
    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        msg = "API rate limit exceeded"
        if retry_after:
            msg += f". Retry after {retry_after} seconds"
        super().__init__(msg)


class NetworkError(CryptoTrackerError):
    """
    Raised when there's a network connectivity issue.
    
    Could be:
    - No internet connection
    - DNS resolution failure
    - Connection timeout
    """
    def __init__(self, original_error: Exception | None = None):
        self.original_error = original_error
        msg = "Network error: could not reach the API"
        if original_error:
            msg += f" ({type(original_error).__name__})"
        super().__init__(msg)


class CacheError(CryptoTrackerError):
    """Raised when there's a problem with caching operations."""
    pass


class ConfigurationError(CryptoTrackerError):
    """
    Raised when there's a configuration problem.
    
    For example:
    - Missing required environment variable
    - Invalid configuration value
    """
    pass


class ValidationError(CryptoTrackerError):
    """
    Raised when input validation fails.
    
    For example:
    - Empty coin symbol
    - Invalid limit value (negative, too large)
    """
    def __init__(self, field: str, value: str, reason: str):
        self.field = field
        self.value = value
        super().__init__(f"Validation error: {field}='{value}' - {reason}")
