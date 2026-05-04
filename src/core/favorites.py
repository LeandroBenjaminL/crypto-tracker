"""
Favorites manager — persistent local storage for user's favorite coins.

Reads and writes a JSON file in the user's home directory.
Keeps it simple: no DB, no API, just a file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.exceptions import CryptoTrackerError
from src.core.models import FavoriteCoin


class FavoritesError(CryptoTrackerError):
    """Something went wrong with the favorites file."""
    pass


class FavoritesManager:
    """
    Manages a user's list of favorite coins.

    Stores favorites as a JSON array in a local file.
    Each entry: {"symbol": "btc", "added_at": "2026-05-04T..."}
    """

    def __init__(self, file_path: Path | None = None) -> None:
        self._file = file_path or Path.home() / ".crypto_tracker.json"
        self._cache: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_all(self) -> list[FavoriteCoin]:
        """Return all saved favorites."""
        raw = self._load()
        return [
            FavoriteCoin(
                symbol=entry["symbol"],
                added_at=datetime.fromisoformat(entry["added_at"]),
            )
            for entry in raw
        ]

    def add(self, symbol: str) -> None:
        """Add a coin to favorites (idempotent — no duplicates)."""
        normalized = symbol.strip().lower()
        if not normalized:
            return

        raw = self._load()

        # No duplicados
        if any(e["symbol"] == normalized for e in raw):
            return

        raw.append({
            "symbol": normalized,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save(raw)

    def remove(self, symbol: str) -> None:
        """Remove a coin from favorites."""
        normalized = symbol.strip().lower()
        raw = self._load()
        raw = [e for e in raw if e["symbol"] != normalized]
        self._save(raw)

    def is_favorite(self, symbol: str) -> bool:
        """Check if a symbol is already in favorites."""
        normalized = symbol.strip().lower()
        raw = self._load()
        return any(e["symbol"] == normalized for e in raw)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _load(self) -> list[dict[str, Any]]:
        """Read favorites from disk (with caching)."""
        if self._cache is not None:
            return self._cache

        if not self._file.exists():
            self._cache = []
            return self._cache

        try:
            with open(self._file, encoding="utf-8") as f:
                data = json.load(f)
            self._cache = data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as e:
            raise FavoritesError(f"Can't read favorites: {e}") from e

        return self._cache

    def _save(self, data: list[dict[str, Any]]) -> None:
        """Write favorites to disk and update cache."""
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._cache = data
        except OSError as e:
            raise FavoritesError(f"Can't write favorites: {e}") from e
