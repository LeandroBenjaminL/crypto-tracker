"""
Tests for src/config/settings.py.

Covers:
  - load_settings() defaults
  - load_settings() with environment variables
  - CACHE_TTL validation
  - _find_project_root()
  - .env loading
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config.settings import Settings, _find_project_root, load_settings
from src.core.exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# _find_project_root
# ---------------------------------------------------------------------------


class TestFindProjectRoot:
    """Tests for the internal _find_project_root helper."""

    def test_returns_existing_dir(self) -> None:
        """It should return a Path that exists (the project root)."""
        root = _find_project_root()
        assert isinstance(root, Path)
        assert root.exists()

    def test_pyproject_toml_marker(self) -> None:
        """It should find a directory containing pyproject.toml."""
        root = _find_project_root()
        assert (root / "pyproject.toml").exists()

    def test_returns_absolute_path(self) -> None:
        """The returned path should be absolute."""
        root = _find_project_root()
        assert root.is_absolute()


# ---------------------------------------------------------------------------
# Settings frozen dataclass
# ---------------------------------------------------------------------------


class TestSettingsDataclass:
    """Tests for the Settings frozen dataclass itself."""

    def test_default_coingecko_api_key_is_empty(self) -> None:
        s = Settings()
        assert s.coingecko_api_key == ""

    def test_default_coingecko_base_url(self) -> None:
        s = Settings()
        assert s.coingecko_base_url == "https://api.coingecko.com/api/v3"

    def test_default_currency_is_usd(self) -> None:
        s = Settings()
        assert s.default_currency == "usd"

    def test_default_cache_ttl_is_60(self) -> None:
        s = Settings()
        assert s.cache_ttl == 60

    def test_default_database_url_is_empty(self) -> None:
        s = Settings()
        assert s.database_url == ""

    def test_favorites_file_under_home(self) -> None:
        s = Settings()
        assert ".crypto_tracker.json" in str(s.favorites_file)

    def test_settings_is_frozen(self) -> None:
        """Settings() should be immutable (frozen dataclass)."""
        s = Settings()
        with pytest.raises(AttributeError):
            s.coingecko_api_key = "new-key"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# load_settings()
# ---------------------------------------------------------------------------


class TestLoadSettings:
    """Tests for load_settings() — the main factory function."""

    def test_loads_defaults_when_no_env(self) -> None:
        """Without env vars, load_settings() should return defaults."""
        with patch.dict(os.environ, {}, clear=True):
            s = load_settings()
            assert s.coingecko_api_key == ""
            assert s.coingecko_base_url == "https://api.coingecko.com/api/v3"
            assert s.default_currency == "usd"
            assert s.cache_ttl == 60

    def test_reads_coingecko_api_key_from_env(self) -> None:
        with patch.dict(os.environ, {"COINGECKO_API_KEY": "test-key-123"}, clear=True):
            s = load_settings()
            assert s.coingecko_api_key == "test-key-123"

    def test_reads_coingecko_base_url_from_env(self) -> None:
        with patch.dict(os.environ, {"COINGECKO_BASE_URL": "https://custom.url"}, clear=True):
            s = load_settings()
            assert s.coingecko_base_url == "https://custom.url"

    def test_reads_default_currency_from_env(self) -> None:
        with patch.dict(os.environ, {"DEFAULT_CURRENCY": "eur"}, clear=True):
            s = load_settings()
            assert s.default_currency == "eur"

    def test_reads_database_url_from_env(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}, clear=True):
            s = load_settings()
            assert s.database_url == "postgresql://user:pass@localhost/db"

    def test_cache_ttl_from_env(self) -> None:
        with patch.dict(os.environ, {"CACHE_TTL": "300"}, clear=True):
            s = load_settings()
            assert s.cache_ttl == 300

    def test_cache_ttl_invalid_raises_configuration_error(self) -> None:
        with patch.dict(os.environ, {"CACHE_TTL": "not-a-number"}, clear=True):
            with pytest.raises(ConfigurationError) as exc:
                load_settings()
            assert "CACHE_TTL" in str(exc.value)

    def test_cache_ttl_negative_not_validated(self) -> None:
        """The current code accepts negative TTL; this documents the behaviour."""
        with patch.dict(os.environ, {"CACHE_TTL": "-5"}, clear=True):
            s = load_settings()
            assert s.cache_ttl == -5

    def test_env_var_overrides_default(self) -> None:
        """A mixed environment should use the set vars and fall back to defaults."""
        with patch.dict(os.environ, {"COINGECKO_API_KEY": "key42"}, clear=True):
            s = load_settings()
            assert s.coingecko_api_key == "key42"
            assert s.default_currency == "usd"  # not set → default


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSettingsEdgeCases:
    """Edge cases and error handling."""

    def test_cache_ttl_empty_string_falls_back(self) -> None:
        """Empty CACHE_TTL should hit int('') which raises ValueError."""
        with patch.dict(os.environ, {"CACHE_TTL": ""}, clear=True):
            with pytest.raises(ConfigurationError):
                load_settings()

    def test_empty_env_vars(self) -> None:
        """Setting an env var to empty should return the empty string, not the default."""
        with patch.dict(os.environ, {"COINGECKO_API_KEY": ""}, clear=True):
            s = load_settings()
            assert s.coingecko_api_key == ""
