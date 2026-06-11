# 🚀 Crypto Tracker - Roadmap

## Overview

This roadmap tracks the development phases of the Crypto Tracker project. Each phase builds on the previous one, gradually adding features while maintaining clean architecture principles.

---

## Phase 1: Foundation ✅
- [x] Project structure with clean architecture
- [x] `pyproject.toml` configuration
- [x] Virtual environment setup
- [x] Git repository initialized
- [x] README and documentation scaffolding

## Phase 2: Core Models ✅
- [x] `src/core/models.py` — Cryptocurrency, PriceData, CoinSearchResult, FavoriteCoin, PriceAlert, PortfolioHolding
- [x] `src/core/exceptions.py` — Custom exception hierarchy
- [x] Unit tests for models

## Phase 3: API Integration ✅
- [x] `src/adapters/api_client.py` — CoinGecko wrapper with TTL cache, rate limiting, retries
- [x] `src/config/settings.py` — Environment-based configuration
- [x] Integration tests with mocked HTTP (~18 tests)
- [x] Rate limiting handling (429, Retry-After)
- [x] Resilience: HTTPAdapter with retry strategy for 5xx errors

## Phase 4: Business Logic ✅
- [x] `src/core/price_service.py` — Core business logic
- [x] Dependency injection via Protocol (structural typing)
- [x] Symbol-to-ID resolution (local map + API fallback)
- [x] Historical price data support
- [x] Unit tests with mocked API client (~30 tests)

## Phase 5: CLI Interface ✅
- [x] `src/cli/commands.py` — Click-based CLI
- [x] `crypto-tracker price <symbol>` command (single + batch)
- [x] `crypto-tracker list-coins` command (top N by market cap)
- [x] `crypto-tracker search <query>` command
- [x] Color-coded output (green/red for gains/losses)
- [x] Friendly error messages for all exception types
- [x] CLI tests with Click's CliRunner (~17 tests)

## Phase 6: Favorites System ✅
- [x] JSON-based local storage (`~/.crypto_tracker.json`)
- [x] `FavoritesManager` in `src/core/favorites.py`
- [x] Favorites support in Streamlit dashboard
- [x] Tests for favorites operations (~16 tests)

## Phase 7: Testing & CI ✅
- [x] ~100+ tests across 5 test files
- [x] GitHub Actions workflow (Python 3.10, 3.11, 3.12)
- [x] Linting with Ruff
- [x] Type checking with mypy
- [x] Coverage reporting with pytest-cov

## Phase 8: Documentation ✅
- [x] Complete README with features, quick start, architecture
- [x] ARCHITECTURE.md with clean architecture diagrams
- [x] CHANGELOG.md in Keep a Changelog format
- [x] CONTRIBUTING.md with development guidelines
- [x] ROADMAP.md updated with all completed phases

## Phase 9: Streamlit Dashboard ✅
- [x] `app.py` with 4 pages: Favoritos, Precio, Top Monedas, Buscar
- [x] Interactive Plotly charts for price history
- [x] Styled DataFrames with dark theme
- [x] Market cap treemap visualization
- [x] Currency selector (USD, EUR, ARS, GBP, BRL, JPY, CNY)
- [x] Cache management and refresh controls

## Phase 10: Polish & Resilience ✅
- [x] TTL cache in API client to reduce redundant calls
- [x] Rate limiter with configurable window (conservative 5/min for free tier)
- [x] API key support in `.env` for higher rate limits
- [x] CSV export from dashboard
- [x] Expanded coin symbol map (50+ popular coins)
- [x] Graceful handling of `st.autorefresh` deprecation
- [x] Type-safe mypy pass across all modules

## Phase 11: REST API + Docker ✅
- [x] FastAPI REST layer (`src/api/server.py`) with 8 endpoints
- [x] OpenAPI docs at `/docs` and `/redoc`
- [x] Pydantic response schemas (`CoinOut`, `HistoryPoint`, `FavoriteOut`)
- [x] Exception-to-HTTP mapping for all domain errors
- [x] Precarga de datos populares en background thread
- [x] HTTP client for Streamlit (`src/api/client.py`)
- [x] `run.py` launcher (arranca API + Streamlit juntos)
- [x] Tests with FastAPI TestClient (~50 tests)

## Phase 12: PostgreSQL + Docker Compose ✅
- [x] `FavoritesRepository` with SQLAlchemy 2.0
- [x] `PortfolioRepository` with CRUD + P&L summary
- [x] PostgreSQL via Docker Compose
- [x] Graceful degradation (DB fallback → JSON)
- [x] SQLite in-memory for testing
- [x] Dockerfile with multi-entrypoint (API / Streamlit / Pipeline / Telegram)
- [x] Docker Compose with 3 services (db + api + streamlit)
- [x] Healthchecks for all services
- [x] Makefile with docker commands

## Phase 13: API & DB Tests ✅
- [x] `test_api_server.py` — FastAPI TestClient (~50 tests)
- [x] `test_api_client_http.py` — HTTP client mocks (~44 tests)
- [x] `test_database.py` — SQLAlchemy FavoritesRepository (~14 tests)
- [x] `test_portfolio_repository.py` — PortfolioRepository CRUD + P&L (37 tests)
- [x] Error mapping tests (all domain → HTTP translations)
- [x] 312 tests total across 9 test files

## Phase 14: Pipeline ETL + Price Alerts ✅
- [x] ETL Pipeline (`src/core/pipeline.py`) — CoinGecko → PostgreSQL
- [x] `price_snapshots` table for periodic price caching
- [x] `price_history` table for cached historical data
- [x] `pipeline_runs` table for run tracking
- [x] `price_alerts` table with above/below conditions
- [x] `check_alerts()` — post-pipeline alert evaluation
- [x] Alembic migrations (0004, 0005)
- [x] Cache-first API endpoints (DB → CoinGecko fallback)
- [x] GitHub Actions workflow for manual pipeline dispatch

## Phase 15: Telegram Bot ✅
- [x] `src/telegram/bot.py` with python-telegram-bot v20+
- [x] `/price`, `/top`, `/alert`, `/start`, `/help` commands
- [x] Optional allowlist (`TELEGRAM_ALLOWED_USERS`)
- [x] Markdown-formatted responses with emoji indicators
- [x] Docker entrypoint for Telegram bot
- [x] CLI entrypoint: `crypto-tracker-telegram`

## Phase 16: Portfolio Tracking ✅
- [x] `PortfolioHolding` dataclass with properties (`cost_basis`, `current_value`, `pnl`)
- [x] `PortfolioRepository` with full CRUD
- [x] `get_summary()` — aggregated P&L across all holdings
- [x] Fallback to purchase_price when current price unavailable
- [x] API endpoints: GET/POST/PUT/DELETE `/api/portfolio`
- [x] 37 tests covering CRUD, validation, edge cases

## Phase 17: Frontend Astro + GitHub Pages ✅
- [x] Astro 6 project in `frontend/`
- [x] Pages: index, price/[slug], top, search, favorites, 404
- [x] Components: CoinsTable, PriceCard, ThemeToggle
- [x] Base layout with header, footer, dark/light theme
- [x] Client-side API consumption via `api.ts`
- [x] Shared render helpers in `render.ts`
- [x] Global CSS with Google Fonts
- [x] GitHub Actions deploy to GitHub Pages
- [x] Live at `leandrobenjaminl.github.io/crypto-tracker/`

## Phase 18: Docker 4-Entrypoint ✅
- [x] 4 entrypoints: api, streamlit, pipeline, telegram
- [x] Dynamic PORT support for Render
- [x] All dependency groups in one image
- [x] Docker Compose with healthchecks

## Future Enhancements

### Near Term
- [ ] Price alert notifications (email/push/webhook)
- [ ] CLI favorites commands (`crypto-tracker favorites add/remove/list`)
- [ ] CLI portfolio commands
- [ ] Multiple currency support in CLI defaults
- [ ] Tests for Telegram bot
- [ ] Tests for Pipeline ETL (run, check_alerts)
- [ ] Mypy — remove overrides from telegram.bot, cli.commands

### Medium Term
- [ ] User authentication for multi-user API (JWT)
- [ ] JSON export alongside CSV
- [ ] Configurable watchlist refresh interval
- [ ] Pipeline dashboard with run metrics
- [ ] Portfolio chart (value over time)

### Long Term
- [ ] Advanced charting (candlestick, volume, moving averages)
- [ ] Mobile-responsive improvements
- [ ] Deployment to additional platforms
- [ ] Export to PDF reports

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.4.0 | 2026-06-11 | Frontend Astro + GitHub Pages, CI/CD fixes, Portfolio repo tests |
| 0.3.0 | 2026-06-11 | Pipeline ETL, PostgreSQL, price alerts, portfolio, Telegram bot |
| 0.2.0 | 2026-05-05 | FastAPI REST layer, PostgreSQL, Docker Compose, Streamlit dashboard |
| 0.1.0 | 2026-05-04 | CLI complete: price, list, search commands |
| 0.0.1 | 2026-04-10 | Project structure + core models |
