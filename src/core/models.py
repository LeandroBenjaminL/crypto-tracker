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

    id: str  # CoinGecko internal ID (e.g., "bitcoin")
    symbol: str  # Trading symbol (e.g., "btc")
    name: str  # Full name (e.g., "Bitcoin")
    rank: int = 0  # Market cap rank

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
    price: float  # Current price in USD
    change_24h: float = 0.0  # Percentage change in 24h
    volume_24h: float = 0.0  # Trading volume in 24h
    market_cap: float = 0.0  # Market capitalization
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


@dataclass
class PortfolioHolding:
    """
    Represents a cryptocurrency holding in the user's portfolio.

    Tracks the coin, quantity held, and purchase price for P&L calculations.
    """

    id: int = 0  # DB auto-increment primary key
    coin_id: str = ""  # CoinGecko ID (e.g., "bitcoin")
    symbol: str = ""  # Trading symbol (e.g., "btc")
    quantity: float = 0.0  # Amount held
    purchase_price: float = 0.0  # Price per unit when bought (USD)
    current_price: float = 0.0  # Current market price (USD)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    @property
    def cost_basis(self) -> float:
        """Total cost of the holding (quantity * purchase_price)."""
        return self.quantity * self.purchase_price

    @property
    def current_value(self) -> float:
        """Current market value (quantity * current_price)."""
        return self.quantity * self.current_price

    @property
    def pnl(self) -> float:
        """Profit/Loss in USD (current_value - cost_basis)."""
        return self.current_value - self.cost_basis

    @property
    def pnl_percent(self) -> float:
        """Profit/Loss percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.pnl / self.cost_basis) * 100

    @property
    def cost_basis_formatted(self) -> str:
        """Format cost basis with appropriate decimals."""
        return f"${self.cost_basis:,.2f}"

    @property
    def current_value_formatted(self) -> str:
        """Format current value with appropriate decimals."""
        if self.current_value >= 1:
            return f"${self.current_value:,.2f}"
        elif self.current_value >= 0.01:
            return f"${self.current_value:.4f}"
        else:
            return f"${self.current_value:.8f}"

    @property
    def pnl_formatted(self) -> str:
        """Format P/L with sign."""
        sign = "+" if self.pnl >= 0 else ""
        if abs(self.pnl) >= 1:
            return f"{sign}${self.pnl:,.2f}"
        elif abs(self.pnl) >= 0.01:
            return f"{sign}${self.pnl:.4f}"
        else:
            return f"{sign}${self.pnl:.8f}"

    @property
    def pnl_percent_formatted(self) -> str:
        """Format P/L percentage with sign."""
        sign = "+" if self.pnl_percent >= 0 else ""
        return f"{sign}{self.pnl_percent:.2f}%"
