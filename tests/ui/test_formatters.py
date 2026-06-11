"""
Tests for UI formatters (pure functions, no mocking needed).

Covers fmt_price, fmt_change, fmt_cap, delta_color, fmt_volume, fmt_supply.
"""

from __future__ import annotations

from src.ui.formatters import (
    delta_color,
    fmt_cap,
    fmt_change,
    fmt_price,
    fmt_supply,
    fmt_volume,
)


class TestFmtPrice:
    """Tests for fmt_price."""

    def test_price_above_1(self) -> None:
        """Prices >= 1 use 2 decimal places with commas."""
        assert fmt_price(1234.56) == "$1,234.56"
        assert fmt_price(1.00) == "$1.00"
        assert fmt_price(99999.99) == "$99,999.99"

    def test_price_between_001_and_1(self) -> None:
        """Prices between 0.01 and 0.9999 use 4 decimal places."""
        assert fmt_price(0.023) == "$0.0230"
        assert fmt_price(0.99) == "$0.9900"
        assert fmt_price(0.01234) == "$0.0123"

    def test_price_below_001(self) -> None:
        """Very small prices use 8 decimal places."""
        assert fmt_price(0.00000012) == "$0.00000012"
        assert fmt_price(0.00000001) == "$0.00000001"
        assert fmt_price(0.0001) == "$0.00010000"

    def test_price_zero(self) -> None:
        """Zero is treated as < 0.01, so 8 decimal places."""
        result = fmt_price(0.0)
        assert result == "$0.00000000"

    def test_price_negative(self) -> None:
        """Negative prices are formatted (unlikely but should not crash)."""
        result = fmt_price(-50.0)
        assert "$" in result and "-" in result


class TestFmtChange:
    """Tests for fmt_change."""

    def test_positive_change(self) -> None:
        """Positive change gets a + prefix."""
        assert fmt_change(5.23) == "+5.23%"

    def test_negative_change(self) -> None:
        """Negative change keeps its - sign."""
        assert fmt_change(-2.10) == "-2.10%"

    def test_zero_change(self) -> None:
        """Zero change shows 0.00% (no + prefix for zero)."""
        assert fmt_change(0.0) == "0.00%"

    def test_small_positive(self) -> None:
        """Very small positive change."""
        assert fmt_change(0.01) == "+0.01%"

    def test_rounding(self) -> None:
        """Values are rounded to 2 decimal places."""
        assert fmt_change(3.456) == "+3.46%"


class TestFmtCap:
    """Tests for fmt_cap (market cap abbreviation)."""

    def test_trillions(self) -> None:
        """Values >= 1T show as T."""
        assert fmt_cap(1_234_567_890_123) == "$1.23T"

    def test_billions(self) -> None:
        """Values between 1B and 1T show as B."""
        assert fmt_cap(456_789_000_000) == "$456.79B"

    def test_millions(self) -> None:
        """Values between 1M and 1B show as M."""
        assert fmt_cap(12_345_678) == "$12.35M"

    def test_below_million(self) -> None:
        """Values < 1M show as raw number."""
        assert fmt_cap(500_000) == "$500,000"
        assert fmt_cap(0) == "$0"

    def test_boundary_billion(self) -> None:
        """Exactly 1B shows as B."""
        assert fmt_cap(1_000_000_000) == "$1.00B"

    def test_boundary_million(self) -> None:
        """Exactly 1M shows as M."""
        assert fmt_cap(1_000_000) == "$1.00M"


class TestDeltaColor:
    """Tests for delta_color."""

    def test_positive_returns_normal(self) -> None:
        """Positive change returns 'normal'."""
        assert delta_color(5.0) == "normal"

    def test_negative_returns_inverse(self) -> None:
        """Negative change returns 'inverse'."""
        assert delta_color(-3.0) == "inverse"

    def test_zero_returns_normal(self) -> None:
        """Zero change returns 'normal'."""
        assert delta_color(0.0) == "normal"

    def test_small_positive(self) -> None:
        """Even tiny positives are 'normal'."""
        assert delta_color(0.001) == "normal"


class TestFmtVolume:
    """Tests for fmt_volume (aliases fmt_cap)."""

    def test_volume_delegates_to_fmt_cap(self) -> None:
        """fmt_volume should produce same output as fmt_cap."""
        assert fmt_volume(1_500_000_000) == fmt_cap(1_500_000_000)
        assert fmt_volume(50_000) == fmt_cap(50_000)


class TestFmtSupply:
    """Tests for fmt_supply."""

    def test_billions(self) -> None:
        """Supply >= 1B shows as B."""
        assert fmt_supply(21_000_000_000) == "21.00B"

    def test_millions(self) -> None:
        """Supply between 1M and 1B shows as M."""
        assert fmt_supply(120_000_000) == "120.00M"

    def test_thousands(self) -> None:
        """Supply between 1K and 1M shows as K."""
        assert fmt_supply(5_400) == "5.40K"

    def test_below_thousand(self) -> None:
        """Supply < 1K shows as raw number."""
        assert fmt_supply(999) == "999"
        assert fmt_supply(0) == "0"
