"""
Core data models for crypto-tracker.

These models represent the domain entities and are completely
independent of any external dependencies (no requests, httpx, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(eq=False)
class Cryptocurrency:
    """
    Represents a cryptocurrency with its basic information.
    
    This is a VALUE OBJECT - it doesn't have identity beyond its data.
    Two cryptocurrencies with the same id are equal.
    """
    id: str              # CoinGecko internal ID (e.g., "bitcoin")
    symbol: str          # Trading symbol (e.g., "btc")
    name: str            # Full name (e.g., "Bitcoin")
    rank: int = 0        # Market cap rank
    
    def __eq__(self, other: object) -> bool:
        """Two cryptocurrencies are equal if they share the same id."""
        if not isinstance(other, Cryptocurrency):
            return NotImplemented
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on id so we can use these in sets."""
        return hash(self.id)
    
    def __str__(self) -> str:
        return f"{self.name} ({self.symbol.upper()})"


@dataclass
class PriceData:
    """
    Represents the price information for a cryptocurrency.
    
    Includes current price and 24h change statistics.
    """
    coin_id: str
    price: float              # Current price in USD
    change_24h: float = 0.0   # Percentage change in 24h
    volume_24h: float = 0.0   # Trading volume in 24h
    market_cap: float = 0.0   # Market capitalization
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def price_formatted(self) -> str:
        """Format price with appropriate decimal places."""
        if self.price >= 1:
            return f"${self.price:,.2f}"
        elif self.price >= 0.01:
            return f"${self.price:.4f}"
        else:
            return f"${self.price:.8f}"
    
    @property
    def change_indicator(self) -> str:
        """Return arrow indicator for price change."""
        if self.change_24h > 0:
            return "▲"
        elif self.change_24h < 0:
            return "▼"
        return "―"
    
    @property
    def change_formatted(self) -> str:
        """Format change with sign and percentage."""
        sign = "+" if self.change_24h > 0 else ""
        return f"{sign}{self.change_24h:.2f}%"


@dataclass 
class CoinSearchResult:
    """
    Combined result of a cryptocurrency with its current price.
    
    This is what users typically want to see - the coin info
    plus the current market data.
    """
    coin: Cryptocurrency
    price_data: Optional[PriceData] = None
    
    def has_price(self) -> bool:
        """Check if price data is available."""
        return self.price_data is not None


@dataclass
class FavoriteCoin:
    """
    Represents a coin saved in user's favorites list.
    
    Stores the coin symbol (user-friendly) and when it was added.
    """
    symbol: str
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self) -> None:
        """Normalize symbol to lowercase."""
        self.symbol = self.symbol.lower()


@dataclass
class PriceAlert:
    """
    Represents a price alert condition.
    
    User wants to be notified when price crosses a threshold.
    """
    coin_id: str
    target_price: float
    condition: str  # "above" or "below"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    triggered_at: Optional[datetime] = None
