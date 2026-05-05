# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ARCHITECTURE.md documenting clean architecture decisions.
- CHANGELOG.md to track version history.

## [0.2.0] — 2026-05-05

### Added
- **Streamlit dashboard** (`app.py`) with 4 pages: Favoritos, Precio, Top Monedas, Buscar.
- **Interactive historical charts** using Plotly (7d, 30d, 90d, 1y).
- **Favorites system** with persistent JSON storage (`~/.crypto_tracker.json`).
- **CSV export** from the Top Monedas dashboard page.
- **Auto-refresh toggle** and manual refresh button with cache clearing.
- **Expanded coin symbol map** with 50+ popular cryptocurrencies for fast local resolution.
- **API key status indicator** in the Streamlit sidebar.
- **Market cap treemap** visualization on the Top Monedas page.
- **Rate limiter** and **TTL cache** in the API client for resilience and efficiency.

### Changed
- Switched from `st.cache_data` to `st.cache_resource` to avoid pickle errors with domain objects.
- Reduced rate limit to a conservative 5 requests/minute for the free CoinGecko tier.
- Improved error display in the dashboard with friendly messages and retry buttons.

### Fixed
- Resolved `AttributeError` on the price page caused by pandas variable shadowing.
- Resolved 13 mypy type errors across `app.py`, `api_client.py`, and `commands.py`.
- Fixed ruff lint errors (E501, W293, I001).
- Restored blank line between docstring and `__future__` import.
- Fixed `st.autorefresh` compatibility issue (removed in Streamlit 1.57) by replacing with a refresh button.

## [0.1.0] — 2026-05-04

### Added
- **CLI interface** with Click: `price`, `list-coins`, and `search` commands.
- **Price service** with dependency injection via Protocol (`CoinGeckoClientProtocol`).
- **Symbol-to-ID resolution**: local map + API fallback.
- **Color-coded terminal output** (green for gains, red for losses).
- **Friendly error messages** for all domain exceptions (`CoinNotFoundError`, `RateLimitError`, `NetworkError`, etc.).
- **GitHub Actions CI** workflow with lint (Ruff), type check (mypy), and tests (pytest) for Python 3.10, 3.11, and 3.12.

### Changed
- Updated ROADMAP with completed phases 2–5.

### Fixed
- Resolved 7 issues from the first Judgment Day review (architecture, naming, edge cases).
- Resolved 5 additional issues from the second Judgment Day review.

## [0.0.1] — 2026-04-10

### Added
- Initial project structure with clean architecture (`src/core/`, `src/adapters/`, `src/cli/`, `src/config/`).
- `pyproject.toml` with project metadata, dependencies, dev tools, and entry points.
- Domain models: `Cryptocurrency`, `PriceData`, `CoinSearchResult`, `FavoriteCoin`, `PriceAlert`.
- Custom exception hierarchy: `CryptoTrackerError`, `APIError`, `RateLimitError`, `NetworkError`, `CoinNotFoundError`, `ValidationError`, `ConfigurationError`.
- CoinGecko API client with rate limiting, retry logic, and response validation.
- Environment-based settings with `python-dotenv` support.
- Unit tests for models, API client, and price service with mocked dependencies.
- Project documentation scaffolding (README, ROADMAP, CONTRIBUTING, AUTHORS).

[Unreleased]: https://github.com/LeandroBenjaminL/crypto-tracker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/LeandroBenjaminL/crypto-tracker/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/LeandroBenjaminL/crypto-tracker/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/LeandroBenjaminL/crypto-tracker/releases/tag/v0.0.1
