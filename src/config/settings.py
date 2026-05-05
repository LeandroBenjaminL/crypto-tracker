"""
Application settings loaded from environment variables.

Follows the principle: fail fast on missing config, provide
sensible defaults for optional values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from src.core.exceptions import ConfigurationError


def _find_project_root() -> Path:
    """
    Walk up from this file to find the project root.

    We look for a `.env` file or the `pyproject.toml` as markers.
    This lets us load .env regardless of where the user runs the CLI from.
    """
    current = Path(__file__).resolve().parent  # src/config/
    for parent in [current, *current.parents]:
        if (parent / ".env").exists() or (parent / "pyproject.toml").exists():
            return parent
    return current  # fallback


@dataclass(frozen=True)
class Settings:
    """
    Immutable configuration container.

    All values are read from environment variables at startup.
    Using a frozen dataclass means you can't accidentally mutate
    the config at runtime — a nice safety net.
    """

    # --- CoinGecko API ---
    coingecko_api_key: str = ""
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"

    # --- Defaults ---
    default_currency: str = "usd"

    # --- Rate limiting & cache ---
    cache_ttl: int = 60  # seconds

    # --- Database ---
    database_url: str = ""  # Postgres: postgresql://user:pass@host:5432/dbname

    # --- Paths ---
    favorites_file: Path = field(
        default_factory=lambda: Path.home() / ".crypto_tracker.json"
    )


def load_settings() -> Settings:
    """
    Load configuration from environment variables.

    Tries to load a .env file from the project root (next to pyproject.toml),
    then falls back to system environment variables.
    """
    project_root = _find_project_root()
    dotenv_path = project_root / ".env"

    if dotenv_path.exists():
        load_dotenv(dotenv_path)
    else:
        # Try loading .env from the current working directory too
        cwd_dotenv = Path.cwd() / ".env"
        if cwd_dotenv.exists():
            load_dotenv(cwd_dotenv)

    cache_ttl_raw = os.getenv("CACHE_TTL", "60")
    try:
        cache_ttl = int(cache_ttl_raw)
    except ValueError:
        raise ConfigurationError(
            f"CACHE_TTL must be an integer (seconds), got: '{cache_ttl_raw}'",
        )

    return Settings(
        coingecko_api_key=os.getenv("COINGECKO_API_KEY", ""),
        coingecko_base_url=os.getenv(
            "COINGECKO_BASE_URL",
            "https://api.coingecko.com/api/v3",
        ),
        default_currency=os.getenv("DEFAULT_CURRENCY", "usd"),
        cache_ttl=cache_ttl,
        database_url=os.getenv("DATABASE_URL", ""),
    )
