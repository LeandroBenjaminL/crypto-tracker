"""
Price service — the heart of the business logic.

This module is PURE Python: no HTTP, no I/O, no external dependencies.
All data comes through the API client interface, injected at runtime.

This is what makes clean architecture powerful: you can test every
business rule without touching the network.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.core.models import (
    CoinSearchResult,
    Cryptocurrency,
    PriceData,
    PriceAlert,
)
from src.core.exceptions import APIError, CoinNotFoundError, ValidationError


# ------------------------------------------------------------------
# Protocol: the contract that any API client must fulfill
# ------------------------------------------------------------------

class CoinGeckoClientProtocol(Protocol):
    """
    Interface that the PriceService expects from an API client.

    By defining this as a Protocol, we use STRUCTURAL TYPING
    (duck typing) instead of inheritance. Any object with these
    methods works — no need to subclass.
    """

    def get_price(
        self,
        coin_ids: list[str],
        currency: str = "usd",
    ) -> dict[str, Any]:
        """Fetch current price for one or more coins."""
        ...

    def get_top_coins(
        self,
        limit: int = 10,
        currency: str = "usd",
    ) -> list[dict[str, Any]]:
        """Fetch top coins by market cap."""
        ...

    def search_coin(self, query: str) -> list[dict[str, Any]]:
        """Search for coins by name or symbol."""
        ...

    def get_coin_history(
        self,
        coin_id: str,
        days: int = 7,
        currency: str = "usd",
    ) -> dict[str, Any]:
        """Fetch historical price data for a coin."""
        ...


# ------------------------------------------------------------------
# Known symbol ↔ id mapping (for quick lookups without API calls)
# ------------------------------------------------------------------

# Common coins mapped from symbol to CoinGecko ID.
# No API call needed for these — pure local data.
SYMBOL_TO_ID: dict[str, str] = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "xrp": "ripple",
    "ada": "cardano",
    "doge": "dogecoin",
    "dot": "polkadot",
    "avax": "avalanche-2",
    "matic": "matic-network",
    "link": "chainlink",
    "uni": "uniswap",
    "atom": "cosmos",
    "ltc": "litecoin",
    "bch": "bitcoin-cash",
    "trx": "tron",
    "xlm": "stellar",
    "etc": "ethereum-classic",
    "fil": "filecoin",
    "apt": "aptos",
    "sui": "sui",
    "op": "optimism",
    "arb": "arbitrum",
    "near": "near",
    "icp": "internet-computer",
    "vet": "vechain",
    "aave": "aave",
    "grt": "the-graph",
    "sand": "the-sandbox",
    "mana": "decentraland",
    "axs": "axie-infinity",
}

# Reverse map: CoinGecko ID → trading symbol.
# Auto-generated from SYMBOL_TO_ID so they stay in sync.
ID_TO_SYMBOL: dict[str, str] = {
    coin_id: symbol
    for symbol, coin_id in SYMBOL_TO_ID.items()
}


def _normalize_query(query: str) -> str:
    """Lowercase and strip whitespace from a user query."""
    cleaned = query.strip().lower()
    if not cleaned:
        raise ValidationError("query", query, "cannot be empty")
    return cleaned


def _try_resolve_id(query: str) -> str | None:
    """
    Try to find a CoinGecko ID from a symbol or name.

    Checks the local SYMBOL_TO_ID map first (fast, no API call).
    Returns None if we can't resolve it locally.
    """
    normalized = query.strip().lower()
    return SYMBOL_TO_ID.get(normalized)


def _build_coin_from_api_dict(raw: dict[str, Any]) -> Cryptocurrency:
    """
    Convert a raw API dict to a Cryptocurrency model.

    CoinGecko returns different shapes depending on the endpoint.
    This function normalizes them.
    """
    return Cryptocurrency(
        id=raw.get("id", ""),
        symbol=raw.get("symbol", ""),
        name=raw.get("name", ""),
        rank=raw.get("market_cap_rank", 0) or 0,
    )


def _build_price_data(
    coin_id: str,
    price_dict: dict[str, Any],
    currency: str = "usd",
) -> PriceData:
    """
    Convert a raw price dict to a PriceData model.

    The /simple/price endpoint returns nested dicts like:
        {"usd": 45000, "usd_24h_change": 2.5, ...}
    """
    return PriceData(
        coin_id=coin_id,
        price=float(price_dict.get(currency, 0) or 0),
        change_24h=float(price_dict.get(f"{currency}_24h_change", 0) or 0),
        volume_24h=float(price_dict.get(f"{currency}_24h_vol", 0) or 0),
        market_cap=float(price_dict.get(f"{currency}_market_cap", 0) or 0),
    )


def _build_price_data_from_market(raw: dict[str, Any]) -> PriceData:
    """
    Convert a market-list API dict to a PriceData model.

    The /coins/markets endpoint returns flat dicts with fields like:
        {"current_price": 45000, "price_change_percentage_24h": 2.5, ...}
    """
    return PriceData(
        coin_id=raw.get("id", ""),
        price=float(raw.get("current_price", 0) or 0),
        change_24h=float(raw.get("price_change_percentage_24h", 0) or 0),
        volume_24h=float(raw.get("total_volume", 0) or 0),
        market_cap=float(raw.get("market_cap", 0) or 0),
    )


# ------------------------------------------------------------------
# The service itself
# ------------------------------------------------------------------

class PriceService:
    """
    Business logic for cryptocurrency price operations.

    This class:
    - Receives an API client via constructor (dependency injection)
    - Maps raw API responses to domain models (Cryptocurrency, PriceData)
    - Validates inputs
    - Knows NOTHING about HTTP, JSON, or the outside world

    Usage:
        client = CoinGeckoClient()
        service = PriceService(api_client=client)
        result = service.get_price("bitcoin")
    """

    def __init__(self, api_client: CoinGeckoClientProtocol) -> None:
        self._client = api_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_price(self, query: str, currency: str = "usd") -> CoinSearchResult:
        """
        Get the current price for a single coin.

        The query can be:
        - A CoinGecko ID: "bitcoin"
        - A symbol: "btc", "BTC"
        - A name: "Bitcoin"

        Returns a CoinSearchResult with the coin info + price data.
        """
        coin_id = self._resolve_to_id(query)
        prices = self._client.get_price([coin_id], currency=currency)
        price_dict = prices.get(coin_id, {})

        symbol = ID_TO_SYMBOL.get(coin_id, coin_id)
        coin = Cryptocurrency(id=coin_id, symbol=symbol, name=coin_id.replace("-", " ").title())
        price_data = _build_price_data(coin_id, price_dict, currency=currency) if price_dict else None
        return CoinSearchResult(coin=coin, price_data=price_data)

    def get_prices(
        self,
        queries: list[str],
        currency: str = "usd",
    ) -> list[CoinSearchResult]:
        """
        Get prices for multiple coins at once.

        More efficient than calling get_price() in a loop
        because it batches all IDs into a single API call.
        """
        if not queries:
            raise ValidationError("queries", str(queries), "list cannot be empty")

        coin_ids = [self._resolve_to_id(q) for q in queries]
        prices = self._client.get_price(coin_ids, currency=currency)

        results: list[CoinSearchResult] = []
        for coin_id in coin_ids:
            symbol = ID_TO_SYMBOL.get(coin_id, coin_id)
            price_dict = prices.get(coin_id, {})
            if price_dict:
                coin = Cryptocurrency(id=coin_id, symbol=symbol, name=coin_id.replace("-", " ").title())
                price_data = _build_price_data(coin_id, price_dict, currency=currency)
                results.append(CoinSearchResult(coin=coin, price_data=price_data))
            else:
                results.append(
                    CoinSearchResult(
                        coin=Cryptocurrency(id=coin_id, symbol=symbol, name=coin_id.replace("-", " ").title()),
                    )
                )

        return results

    def search(self, query: str) -> list[Cryptocurrency]:
        """
        Search for coins by name or symbol.

        Returns a list of matching Cryptocurrency objects.
        """
        normalized = _normalize_query(query)
        raw_results = self._client.search_coin(normalized)
        return [_build_coin_from_api_dict(r) for r in raw_results]

    def list_top(self, limit: int = 10, currency: str = "usd") -> list[CoinSearchResult]:
        """
        Get the top N cryptocurrencies by market cap.

        Each result includes current price data.
        """
        if limit < 1 or limit > 250:
            raise ValidationError(
                "limit",
                str(limit),
                "must be between 1 and 250",
            )

        raw_coins = self._client.get_top_coins(limit=limit, currency=currency)

        results: list[CoinSearchResult] = []
        for raw in raw_coins:
            coin = _build_coin_from_api_dict(raw)
            price_data = _build_price_data_from_market(raw)
            results.append(CoinSearchResult(coin=coin, price_data=price_data))

        return results

    def get_history(
        self,
        query: str,
        days: int = 7,
        currency: str = "usd",
    ) -> list[dict[str, float]]:
        """
        Get historical price data for a coin.

        Returns a list of {timestamp, price} dicts sorted by time,
        ready to feed into a charting library.

        Days: 1, 7, 14, 30, 90, 180, 365, or 'max'
        """
        coin_id = self._resolve_to_id(query)
        raw = self._client.get_coin_history(coin_id, days=days, currency=currency)

        prices = raw.get("prices", [])
        # Cada elemento es [timestamp_ms, price]
        return [
            {"timestamp": ts, "price": price}
            for ts, price in prices
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_to_id(self, query: str) -> str:
        """
        Resolve a user query to a CoinGecko ID.

        Strategy:
        1. Check local SYMBOL_TO_ID map (no API call)
        2. Try searching via the API
        3. If nothing works, assume the query IS the ID (let the
           API client raise CoinNotFoundError if it's invalid)
        """
        normalized = _normalize_query(query)

        # Step 1: local map
        resolved = _try_resolve_id(normalized)
        if resolved:
            return resolved

        # Step 2: API search
        try:
            results = self._client.search_coin(normalized)
            if results:
                return results[0]["id"]
        except (APIError, CoinNotFoundError):
            pass  # fall through — let the real API call fail naturally

        # Step 3: use as-is
        return normalized
