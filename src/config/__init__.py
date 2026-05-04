"""
Config module for crypto-tracker.

Centralizes all configuration from environment variables.
Import the singleton settings object to access config values.
"""

from src.config.settings import Settings, load_settings

settings: Settings = load_settings()

__all__ = ["settings", "Settings", "load_settings"]
