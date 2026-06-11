"""
Tests for src/core/exceptions.py.

Covers:
  - Inheritance hierarchy (all exceptions → CryptoTrackerError → Exception)
  - Custom __init__ methods and attributes
  - Error messages
  - Catch-by-parent behaviour
"""

from __future__ import annotations

import pytest

from src.core.exceptions import (
    APIError,
    CacheError,
    CoinNotFoundError,
    ConfigurationError,
    CryptoTrackerError,
    NetworkError,
    RateLimitError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestInheritance:
    """All custom exceptions should inherit from CryptoTrackerError."""

    def test_cryptotracker_error_is_exception(self) -> None:
        assert issubclass(CryptoTrackerError, Exception)

    def test_coin_not_found_inherits(self) -> None:
        assert issubclass(CoinNotFoundError, CryptoTrackerError)

    def test_api_error_inherits(self) -> None:
        assert issubclass(APIError, CryptoTrackerError)

    def test_rate_limit_inherits(self) -> None:
        assert issubclass(RateLimitError, APIError)
        assert issubclass(RateLimitError, CryptoTrackerError)

    def test_network_error_inherits(self) -> None:
        assert issubclass(NetworkError, CryptoTrackerError)

    def test_cache_error_inherits(self) -> None:
        assert issubclass(CacheError, CryptoTrackerError)

    def test_configuration_error_inherits(self) -> None:
        assert issubclass(ConfigurationError, CryptoTrackerError)

    def test_validation_error_inherits(self) -> None:
        assert issubclass(ValidationError, CryptoTrackerError)


# ---------------------------------------------------------------------------
# CryptoTrackerError (base)
# ---------------------------------------------------------------------------


class TestCryptoTrackerError:
    """Base exception behaviour."""

    def test_can_be_raised_directly(self) -> None:
        with pytest.raises(CryptoTrackerError):
            raise CryptoTrackerError("base error")

    def test_message_is_preserved(self) -> None:
        exc = CryptoTrackerError("something went wrong")
        assert str(exc) == "something went wrong"

    def test_catches_concrete_via_parent(self) -> None:
        """A bare CryptoTrackerError except should catch any subclass."""
        with pytest.raises(CryptoTrackerError):
            raise CoinNotFoundError("btc")


# ---------------------------------------------------------------------------
# CoinNotFoundError
# ---------------------------------------------------------------------------


class TestCoinNotFoundError:
    """CoinNotFoundError stores the identifier."""

    def test_identifier_is_stored(self) -> None:
        exc = CoinNotFoundError("bitcoin")
        assert exc.identifier == "bitcoin"

    def test_message_includes_identifier(self) -> None:
        exc = CoinNotFoundError("eth")
        assert "eth" in str(exc)
        assert "not found" in str(exc).lower()


# ---------------------------------------------------------------------------
# APIError
# ---------------------------------------------------------------------------


class TestAPIError:
    """APIError can carry an optional status_code."""

    def test_message_and_status(self) -> None:
        exc = APIError("bad request", status_code=400)
        assert str(exc) == "bad request"
        assert exc.status_code == 400

    def test_default_status_is_none(self) -> None:
        exc = APIError("generic")
        assert exc.status_code is None


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------


class TestRateLimitError:
    """RateLimitError inherits from APIError and adds retry_after."""

    def test_inherits_from_api_error(self) -> None:
        exc = RateLimitError()
        assert isinstance(exc, APIError)

    def test_retry_after_is_stored(self) -> None:
        exc = RateLimitError(retry_after=30)
        assert exc.retry_after == 30

    def test_retry_after_default_none(self) -> None:
        exc = RateLimitError()
        assert exc.retry_after is None

    def test_message_includes_retry_when_provided(self) -> None:
        exc = RateLimitError(retry_after=60)
        assert "60" in str(exc)

    def test_message_without_retry(self) -> None:
        exc = RateLimitError()
        assert "rate limit" in str(exc).lower()


# ---------------------------------------------------------------------------
# NetworkError
# ---------------------------------------------------------------------------


class TestNetworkError:
    """NetworkError wraps the original exception."""

    def test_original_error_is_stored(self) -> None:
        inner = ConnectionError("DNS failure")
        exc = NetworkError(original_error=inner)
        assert exc.original_error is inner

    def test_original_error_default_none(self) -> None:
        exc = NetworkError()
        assert exc.original_error is None

    def test_message_mentions_error_type_wrapped(self) -> None:
        exc = NetworkError(original_error=TimeoutError())
        assert "TimeoutError" in str(exc)


# ---------------------------------------------------------------------------
# CacheError
# ---------------------------------------------------------------------------


class TestCacheError:
    """CacheError is a simple marker exception."""

    def test_can_be_raised(self) -> None:
        with pytest.raises(CacheError):
            raise CacheError("cache miss")

    def test_message(self) -> None:
        exc = CacheError("write failed")
        assert str(exc) == "write failed"


# ---------------------------------------------------------------------------
# ConfigurationError
# ---------------------------------------------------------------------------


class TestConfigurationError:
    """ConfigurationError for missing/invalid config."""

    def test_raised_on_bad_config(self) -> None:
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("MISSING_API_KEY")

    def test_message(self) -> None:
        exc = ConfigurationError("DATABASE_URL not set")
        assert "DATABASE_URL" in str(exc)


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------


class TestValidationError:
    """ValidationError carries field, value, and reason."""

    def test_attributes(self) -> None:
        exc = ValidationError(field="symbol", value="", reason="cannot be empty")
        assert exc.field == "symbol"
        assert exc.value == ""

    def test_message_contains_all_parts(self) -> None:
        exc = ValidationError(field="limit", value="-1", reason="must be positive")
        msg = str(exc)
        assert "limit" in msg
        assert "-1" in msg
        assert "must be positive" in msg
