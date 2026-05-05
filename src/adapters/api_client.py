"""
CoinGecko API client for crypto-tracker.

This is the ONLY module that knows about HTTP requests and the
CoinGecko API structure. If the API changes, you only change this file.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    NetworkError,
    RateLimitError,
)


class TTLCache:
    """
    Simple in-memory cache with TTL and max size.

    Stores API responses keyed by (endpoint, params) so we don't
    hit the API for the same data twice within the TTL window.
    """

    def __init__(self, maxsize: int = 128, ttl: float = 30.0) -> None:
        self._cache: OrderedDict[tuple, Any] = OrderedDict()
        self._timestamps: dict[tuple, float] = {}
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: tuple) -> Any | None:
        """Return cached value or None if expired/missing."""
        if key not in self._cache:
            return None
        if time.monotonic() - self._timestamps[key] > self._ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
        return self._cache[key]

    def set(self, key: tuple, value: Any) -> None:
        """Store a value with current timestamp."""
        # Evict oldest if at capacity
        if len(self._cache) >= self._maxsize:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            del self._timestamps[oldest]
        self._cache[key] = value
        self._timestamps[key] = time.monotonic()

    def clear(self) -> None:
        """Invalidate all cached entries."""
        self._cache.clear()
        self._timestamps.clear()


@dataclass
class RateLimiter:
    """
    Rate limiter sencillo para no romper el tier gratis de CoinGecko.

    Sin API key son ~10-30 calls/min. Nosotros usamos 5/min para dejar
    margen y que no nos banneen.

    Si se excede el límite, espera hasta max_wait segundos. Si pasa de ahí,
    levanta RateLimitError — mejor fallar rápido que dejar al usuario
    mirando un spinner 50 segundos.
    """

    max_calls: int = 5
    window_seconds: float = 60.0
    max_wait: float = 8.0  # esperamos maximo 8s antes de rendirnos
    _timestamps: list[float] = field(default_factory=list)

    def wait_if_needed(self) -> None:
        """
        Frena si nos pasamos del rate limit.

        Si hay que esperar más de max_wait, mejor tiramos error
        antes de dejar colgado al usuario.
        """
        now = time.monotonic()
        self._timestamps = [
            t for t in self._timestamps if now - t < self.window_seconds
        ]

        if len(self._timestamps) >= self.max_calls:
            sleep_for = self._timestamps[0] + self.window_seconds - now
            if sleep_for > self.max_wait:
                raise RateLimitError(retry_after=int(sleep_for))
            if sleep_for > 0:
                time.sleep(sleep_for)

        self._timestamps.append(time.monotonic())


class CoinGeckoClient:
    """
    HTTP client for the CoinGecko API (v3).

    Usage:
        client = CoinGeckoClient()
        price = client.get_price(["bitcoin", "ethereum"])
        top = client.get_top_coins(limit=10)
    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        base_url: str = BASE_URL,
        api_key: str = "",
        timeout: int = 10,
        rate_limiter: RateLimiter | None = None,
        cache_ttl: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # Sin API key somos más conservadores con el rate limit
        if rate_limiter is None:
            if api_key:
                rate_limiter = RateLimiter(max_calls=30, window_seconds=60.0)
            else:
                rate_limiter = RateLimiter(max_calls=5, window_seconds=60.0)
        self._rate_limiter = rate_limiter
        self._cache = TTLCache(ttl=cache_ttl)

        # Configure session with retry strategy for transient errors
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[
                500,
                502,
                503,
                504,
            ],  # 429 excluded — handled by RateLimiter
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session = requests.Session()
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_price(
        self,
        coin_ids: list[str],
        currency: str = "usd",
    ) -> dict[str, Any]:
        """
        Fetch current price for one or more coins.

        Returns dict keyed by coin ID, e.g.:
            {"bitcoin": {"usd": 45000.50, "usd_24h_change": 2.5}}
        """
        params: dict[str, Any] = {
            "ids": ",".join(coin_ids),
            "vs_currencies": currency,
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "include_market_cap": "true",
        }

        data = self._get("/simple/price", params)
        self._validate_coin_response(coin_ids, data)
        return cast(dict[str, Any], data)

    def get_top_coins(
        self,
        limit: int = 10,
        currency: str = "usd",
    ) -> list[dict[str, Any]]:
        """
        Fetch top cryptocurrencies by market cap.

        Returns a list of coin dicts with id, symbol, name,
        current_price, market_cap, price_change_24h, etc.
        """
        params: dict[str, Any] = {
            "vs_currency": currency,
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }

        data = self._get("/coins/markets", params)
        if not isinstance(data, list):
            raise APIError("Unexpected response format from /coins/markets")
        return data

    def search_coin(self, query: str) -> list[dict[str, Any]]:
        """
        Search for coins by name or symbol.

        Returns a list of matching coins with id, name, symbol, etc.
        """
        data = self._get("/search", {"query": query})
        coins = data.get("coins", [])
        if not isinstance(coins, list):
            return []
        return coins[:10]  # top 10 results

    def get_coin_history(
        self,
        coin_id: str,
        days: int = 7,
        currency: str = "usd",
    ) -> dict[str, Any]:
        """
        Fetch historical price data for a coin.

        Returns dict with 'prices', 'market_caps', 'total_volumes'.
        Each is a list of [timestamp, value] pairs.

        CoinGecko endpoint: /coins/{id}/market_chart
        """
        data = self._get(
            f"/coins/{coin_id}/market_chart",
            {"vs_currency": currency, "days": days},
        )
        if not isinstance(data, dict) or "prices" not in data:
            raise APIError(f"Unexpected history format for '{coin_id}'")
        return data

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Invalidate all cached API responses."""
        self._cache.clear()

    def _cache_key(self, endpoint: str, params: dict[str, Any] | None) -> tuple:
        """Build a hashable cache key from endpoint and params."""
        if params:
            # Sort params so same data always produces same key
            sorted_params = tuple(sorted(params.items()))
            return (endpoint, sorted_params)
        return (endpoint,)

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        Base GET request with caching and consistent error handling.

        Cache-aware: returns cached data if available (per-endpoint+params),
        otherwise makes the HTTP request and caches the result.
        """
        # Check cache first
        key = self._cache_key(endpoint, params)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        url = f"{self.base_url}{endpoint}"
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key

        self._rate_limiter.wait_if_needed()

        try:
            response = self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.ConnectionError as exc:
            raise NetworkError(original_error=exc) from exc
        except requests.Timeout as exc:
            raise NetworkError(original_error=exc) from exc

        if response.status_code == 429:
            # Don't cache errors — clear cache and raise
            self._cache.clear()
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                retry_after=int(retry_after) if retry_after else None,
            )

        if response.status_code == 404:
            raise APIError(
                f"API endpoint not found: {endpoint}",
                status_code=404,
            )

        if not response.ok:
            raise APIError(
                f"API request failed: {response.status_code}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except requests.JSONDecodeError:
            snippet = response.text[:200]
            raise APIError(
                f"Invalid JSON response (status {response.status_code}): {snippet}",
                status_code=response.status_code,
            )

        # Cache successful responses
        self._cache.set(key, data)
        return data

    def _validate_coin_response(
        self,
        requested_ids: list[str],
        data: dict[str, Any],
    ) -> None:
        """
        Check that all requested coins were found in the response.

        CoinGecko returns an empty object for unknown coins, e.g.:
            {"bitcoin": {...}, "nonexistentcoin": {}}
        We raise CoinNotFoundError for any missing coins.
        """
        for coin_id in requested_ids:
            result = data.get(coin_id, {})
            if not result or not isinstance(result, dict):
                raise CoinNotFoundError(coin_id)
