"""
CLI commands for crypto-tracker.

This is the user-facing layer. It:
- Receives user input (symbols, limits, queries)
- Calls the PriceService (which calls the API client)
- Formats and displays results

It knows NOTHING about HTTP. That's the adapter's job.
"""

from __future__ import annotations

import click

from src.adapters.api_client import CoinGeckoClient
from src.config import settings
from src.core.exceptions import (
    APIError,
    CoinNotFoundError,
    CryptoTrackerError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from src.core.models import CoinSearchResult
from src.core.price_service import PriceService

# ------------------------------------------------------------------
# Wire up: create the service with its dependencies
# ------------------------------------------------------------------


def _build_service() -> PriceService:
    """
    Assemble the dependency graph.

    This is the Composition Root — the only place where we
    wire together the API client and the price service.
    """
    client = CoinGeckoClient(
        base_url=settings.coingecko_base_url,
        api_key=settings.coingecko_api_key,
    )
    return PriceService(api_client=client)


# ------------------------------------------------------------------
# Shared formatting utilities
# ------------------------------------------------------------------


def _format_price(price: float) -> str:
    """Format a price value based on magnitude."""
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def _format_change(change: float) -> str:
    """Format a % change with color indicators."""
    if change > 0:
        return click.style(f"▲ +{change:.2f}%", fg="green")
    elif change < 0:
        return click.style(f"▼ {change:.2f}%", fg="red")
    else:
        return click.style("― 0.00%", fg="white")


def _format_market_cap(value: float) -> str:
    """Format market cap in human-readable form."""
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    else:
        return f"${value:,.0f}"


def _print_result(result: CoinSearchResult) -> None:
    """Print a single CoinSearchResult to the terminal."""
    coin = result.coin

    # Header: name + symbol
    click.echo(
        click.style(f"\n{coin.name} ", bold=True)
        + click.style(f"({coin.symbol.upper()})", dim=True)
    )

    if result.has_price() and result.price_data:
        pd = result.price_data
        click.echo(f"  Price:     {_format_price(pd.price)}")
        click.echo(f"  24h:       {_format_change(pd.change_24h)}")
        if pd.market_cap > 0:
            click.echo(f"  MarketCap: {_format_market_cap(pd.market_cap)}")
        if pd.volume_24h > 0:
            click.echo(f"  Volume:    {_format_market_cap(pd.volume_24h)}")
    else:
        click.echo(click.style("  No price data available", fg="yellow"))


def _print_table_row(
    rank: int, name: str, symbol: str, price: float, change: float
) -> None:
    """Print a single row of the top-coins table."""
    name_col = click.style(f"{name:<16}", bold=True)
    symbol_col = click.style(f"{symbol.upper():>6}", dim=True)
    rank_col = click.style(f"#{rank:>3}", dim=True)
    row = (
        f"{rank_col}  "
        f"{name_col} "
        f"{symbol_col}  "
        f"{_format_price(price):>12}  "
        f"{_format_change(change)}"
    )
    click.echo(row)


# ------------------------------------------------------------------
# Shared error handler
# ------------------------------------------------------------------


def _handle_error(error: CryptoTrackerError) -> None:
    """Map domain exceptions to user-friendly error messages."""
    if isinstance(error, ValidationError):
        click.echo(click.style(f"[!] Invalid input: {error}", fg="red"), err=True)
    elif isinstance(error, CoinNotFoundError):
        click.echo(click.style(f"[X] {error}", fg="yellow"), err=True)
    elif isinstance(error, RateLimitError):
        click.echo(
            click.style(
                "[-] API rate limit hit. Wait a bit and try again.",
                fg="yellow",
            ),
            err=True,
        )
    elif isinstance(error, NetworkError):
        click.echo(
            click.style(
                "[!] Network error -- check your internet connection.",
                fg="red",
            ),
            err=True,
        )
    elif isinstance(error, APIError):
        click.echo(
            click.style(
                f"[!] API error: {error}",
                fg="red",
            ),
            err=True,
        )
    else:
        click.echo(click.style(f"[!] Unexpected error: {error}", fg="red"), err=True)


# ------------------------------------------------------------------
# CLI commands
# ------------------------------------------------------------------


@click.group()
@click.version_option(version="0.1.0", prog_name="crypto-tracker")
def cli() -> None:
    """
    Crypto Tracker — track cryptocurrency prices from your terminal.

    Powered by the CoinGecko API. No account needed.
    """


@cli.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option(
    "--currency",
    "-c",
    default="usd",
    show_default=True,
    help="Currency for price display (usd, eur, ars, etc.)",
)
def price(symbols: tuple[str, ...], currency: str) -> None:
    """
    Get current prices for one or more cryptocurrencies.

    SYMBOLS can be CoinGecko IDs, trading symbols, or names.
    Examples: btc, ethereum, SOL, bitcoin eth solana
    """
    service = _build_service()

    try:
        if len(symbols) == 1:
            result = service.get_price(symbols[0], currency=currency)
            _print_result(result)
        else:
            results = service.get_prices(list(symbols), currency=currency)
            for result in results:
                _print_result(result)
    except CryptoTrackerError as e:
        _handle_error(e)


@cli.command()
@click.option(
    "--limit",
    "-l",
    default=10,
    show_default=True,
    help="Number of top coins to show (max 250)",
)
@click.option(
    "--currency",
    "-c",
    default="usd",
    show_default=True,
    help="Currency for price display",
)
def list_coins(limit: int, currency: str) -> None:
    """List top cryptocurrencies by market cap."""
    service = _build_service()

    try:
        results = service.list_top(limit=limit, currency=currency)

        click.echo()
        click.echo(
            click.style(
                f"  Top {limit} Cryptocurrencies\n",
                bold=True,
            )
        )

        for result in results:
            pd = result.price_data
            if pd:
                _print_table_row(
                    rank=result.coin.rank,
                    name=result.coin.name,
                    symbol=result.coin.symbol,
                    price=pd.price,
                    change=pd.change_24h,
                )
    except CryptoTrackerError as e:
        _handle_error(e)


@cli.command()
@click.argument("query", required=True)
def search(query: str) -> None:
    """Search for cryptocurrencies by name or symbol."""
    service = _build_service()

    try:
        results = service.search(query)

        if not results:
            click.echo(
                click.style(
                    f"No coins found matching '{query}'",
                    fg="yellow",
                )
            )
            return

        click.echo()
        click.echo(click.style(f"  Search results for '{query}':\n", bold=True))

        for coin in results[:10]:
            rank_str = f"#{coin.rank}" if coin.rank else "—"
            name_col = click.style(f"{coin.name:<20}", bold=True)
            symbol_col = click.style(f"{coin.symbol.upper():<8}", dim=True)
            id_col = click.style(f"{coin.id:<30}", dim=True)
            click.echo(f"  {name_col} {symbol_col} {id_col}  Rank: {rank_str}")
    except CryptoTrackerError as e:
        _handle_error(e)


@cli.command()
@click.option(
    "--top",
    "-n",
    default=100,
    show_default=True,
    help="Cuantas monedas traer (max 250)",
)
def pipeline(top: int) -> None:
    """
    Ejecuta el pipeline ETL: CoinGecko → PostgreSQL.

    Extrae las top N criptos y guarda snapshots de precios.
    Si pasaron más de 6h desde la última vez, también actualiza
    el histórico de precios (7d, 30d, 90d) para las top 20 monedas.
    """
    from src.core.pipeline import PipelineError, run as run_pipeline

    click.echo(click.style("▶  Pipeline ETL", bold=True))
    click.echo(f"   Monedas: {top}")
    click.echo(f"   DB:      {settings.database_url or '❌ no configurada'}")

    if not settings.database_url:
        click.echo(
            click.style(
                "\n[!] DATABASE_URL no está configurada. Seteala en .env",
                fg="red",
            )
        )
        return

    try:
        stats = run_pipeline(top_n=top)
        snapshots = stats.get("snapshots", 0)
        history = stats.get("history_updated", 0)
        click.echo(
            click.style(
                f"\n✅ Pipeline completado: {snapshots} snapshots, "
                f"{history} históricos actualizados",
                fg="green",
            )
        )
    except PipelineError as e:
        click.echo(click.style(f"\n[X] Error en pipeline: {e}", fg="red"))
    except Exception as e:
        click.echo(click.style(f"\n[!] Error inesperado: {e}", fg="red"))


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main() -> None:
    """Entry point for the CLI (called from pyproject.toml scripts)."""
    cli()


if __name__ == "__main__":
    main()
