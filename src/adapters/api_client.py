"""
CoinGecko API client for crypto-tracker.

This is the ONLY module that knows about HTTP requests and the
CoinGecko API structure. If the API changes, you only change this file.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    NetworkError,
    RateLimitError,
)


@dataclass
class RateLimiter:
    """
    Simple rate limiter to avoid hitting API limits.

    Tracks request timestamps and sleeps if we're going too fast.
    CoinGecko free tier: ~10-30 calls/min.
    """

    max_calls: int = 10  # max requests per window
    window_seconds: float = 60.0  # rolling window
    _timestamps: list[float] = field(default_factory=list)

    def wait_if_needed(self) -> None:
        """Block if we've exceeded the rate limit in the current window."""
        now = time.monotonic()
        # Drop timestamps outside the window
        self._timestamps = [
            t for t in self._timestamps if now - t < self.window_seconds
        ]

        if len(self._timestamps) >= self.max_calls:
            # Sleep until the oldest timestamp falls out of the window
            sleep_for = self._timestamps[0] + self.window_seconds - now
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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._rate_limiter = rate_limiter or RateLimiter()

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
        return data

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

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Base GET request with consistent error handling."""
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
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                retry_after=int(retry_after) if retry_after else None,
            )

        if response.status_code == 404:
            # The endpoint itself wasn't found — not a coin issue
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
            return response.json()
        except requests.JSONDecodeError:
            snippet = response.text[:200]
            raise APIError(
                f"Invalid JSON response (status {response.status_code}): {snippet}",
                status_code=response.status_code,
            )

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
