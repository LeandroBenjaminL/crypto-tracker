# 🚀 Crypto Tracker - Roadmap

## Overview

This roadmap tracks the development phases of the Crypto Tracker project. Each phase builds on the previous one, gradually adding features while maintaining clean architecture principles.

---

## Phase 1: Foundation ✅
**Status: Complete**

- [x] Project structure with clean architecture
- [x] `pyproject.toml` configuration
- [x] Virtual environment setup
- [x] Git repository initialized
- [x] README and documentation scaffolding

---

## Phase 2: Core Models ✅
**Goal: Define data structures**

- [x] `src/core/models.py` — Cryptocurrency, PriceData, CoinSearchResult, FavoriteCoin, PriceAlert
- [x] `src/core/exceptions.py` — Custom exception hierarchy
- [x] Unit tests for models (23 tests)

**Learning Objectives:**
- Python dataclasses
- Type hints
- Exception handling

---

## Phase 3: API Integration ✅
**Goal: Connect to CoinGecko API**

- [x] `src/adapters/api_client.py` — CoinGecko wrapper with TTL cache, rate limiting, retries
- [x] `src/config/settings.py` — Environment-based configuration
- [x] Integration tests with mocked HTTP (18 tests)
- [x] Rate limiting handling (429, Retry-After)
- [x] Resilience: HTTPAdapter with retry strategy for 5xx errors

**Learning Objectives:**
- HTTP requests with `requests`
- Environment variables with `python-dotenv`
- API error handling
- Mocking in tests

---

## Phase 4: Business Logic ✅
**Goal: Implement price service**

- [x] `src/core/price_service.py` — Core business logic
- [x] Dependency injection via Protocol (structural typing)
- [x] Symbol-to-ID resolution (local map + API fallback)
- [x] Historical price data support
- [x] Unit tests with mocked API client (30 tests)

**Learning Objectives:**
- Separation of concerns
- Dependency injection with Protocols
- Test-driven development

---

## Phase 5: CLI Interface ✅
**Goal: Build command interface**

- [x] `src/cli/commands.py` — Click-based CLI
- [x] `crypto-tracker price <symbol>` command (single + batch)
- [x] `crypto-tracker list-coins` command (top N by market cap)
- [x] `crypto-tracker search <query>` command
- [x] Color-coded output (green/red for gains/losses)
- [x] Friendly error messages for all exception types
- [x] CLI tests with Click's CliRunner (17 tests)

**Learning Objectives:**
- Building CLIs with Click
- User input validation
- Exit codes and error handling

---

## Phase 6: Favorites System ✅
**Goal: Save user preferences**

- [x] JSON-based local storage (`~/.crypto_tracker.json`)
- [x] `FavoritesManager` in `src/core/favorites.py`
- [x] Favorites support in Streamlit dashboard
- [x] Tests for favorites operations (16 tests)

**Learning Objectives:**
- File I/O in Python
- JSON handling
- Configuration management

---

## Phase 7: Testing & CI ✅
**Goal: Production-ready quality**

- [x] ~104 tests across 5 test files
- [x] GitHub Actions workflow (Python 3.10, 3.11, 3.12)
- [x] Linting with Ruff
- [x] Type checking with mypy
- [x] Coverage reporting with pytest-cov

**Learning Objectives:**
- pytest advanced features
- Continuous Integration
- Code quality tools

---

## Phase 8: Documentation ✅
**Goal: Portfolio-ready**

- [x] Complete README with features, quick start, architecture
- [x] ARCHITECTURE.md with clean architecture diagrams
- [x] CHANGELOG.md in Keep a Changelog format
- [x] CONTRIBUTING.md with development guidelines
- [x] ROADMAP.md updated with all completed phases

**Learning Objectives:**
- Technical writing
- Project documentation
- Open source best practices

---

## Phase 9: Streamlit Dashboard ✅
**Goal: Dual UI — web interface**

- [x] `app.py` with 4 pages: Favoritos, Precio, Top Monedas, Buscar
- [x] Interactive Plotly charts for price history
- [x] Styled DataFrames with dark theme
- [x] Market cap treemap visualization
- [x] Currency selector (USD, EUR, ARS, GBP, BRL, JPY, CNY)
- [x] Cache management and refresh controls

**Learning Objectives:**
- Streamlit app structure
- Plotly visualizations
- Caching strategies (`cache_resource` for non-serializable objects)
- Custom CSS injection

---

## Phase 10: Polish & Resilience ✅
**Goal: Production-grade robustness**

- [x] TTL cache in API client to reduce redundant calls
- [x] Rate limiter with configurable window (conservative 5/min for free tier)
- [x] API key support in `.env` for higher rate limits
- [x] CSV export from dashboard
- [x] Expanded coin symbol map (50+ popular coins)
- [x] Graceful handling of `st.autorefresh` deprecation (manual refresh button)
- [x] Type-safe mypy pass across all modules

**Learning Objectives:**
- Caching strategies and TTL eviction
- Rate limiting patterns
- Export functionality
- Long-term maintenance (deprecation handling)

---

## Phase 11: REST API + Docker ✅
**Goal: Multi-layer architecture with API gateway**

- [x] FastAPI REST layer (`src/api/server.py`) with 8 endpoints
- [x] OpenAPI docs at `/docs` and `/redoc`
- [x] Pydantic response schemas (`CoinOut`, `HistoryPoint`, `FavoriteOut`)
- [x] Exception-to-HTTP mapping for all domain errors
- [x] Precarga de datos populares en background thread
- [x] HTTP client for Streamlit (`src/api/client.py`)
- [x] `run.py` launcher (arranca API + Streamlit juntos)
- [x] Tests with FastAPI TestClient

**Learning Objectives:**
- FastAPI patterns and dependency injection
- OpenAPI automatic documentation
- Background task management with threading
- HTTP client architecture

---

## Phase 12: PostgreSQL + Docker Compose ✅
**Goal: Production-ready infrastructure**

- [x] `FavoritesRepository` with SQLAlchemy 2.0
- [x] PostgreSQL via Docker Compose
- [x] Graceful degradation (DB fallback → JSON)
- [x] SQLite in-memory for testing
- [x] Dockerfile with multi-entrypoint (API / Streamlit)
- [x] Docker Compose with 3 services (db + api + streamlit)
- [x] Healthchecks for all services
- [x] Makefile with docker commands

**Learning Objectives:**
- SQLAlchemy 2.0 ORM
- Repository pattern
- Docker multi-stage builds
- Docker Compose orchestration

---

## Phase 13: API & DB Tests ✅
**Goal: Full coverage across all layers**

- [x] `test_api_server.py` — FastAPI TestClient (20+ tests)
- [x] `test_api_client_http.py` — HTTP client mocks (16+ tests)
- [x] `test_database.py` — SQLAlchemy repository (14 tests)
- [x] Error mapping tests (all domain → HTTP translations)
- [x] ARCHITECTURE.md synced with all new layers

**Learning Objectives:**
- FastAPI TestClient patterns
- Patching module globals for testing
- Parameterized test cases with pytest

---

## Future Enhancements (Post-Launch)

### Near Term
- [ ] Price alert notifications (email/webhook desktop)
- [ ] Portfolio tracking (quantity × price, P&L calculation)
- [ ] CLI favorites commands (`crypto-tracker favorites add/remove/list`)
- [ ] Alembic migrations for schema versioning

### Medium Term
- [ ] Multiple currency support in CLI (`--currency` already works, expand defaults)
- [ ] JSON export alongside CSV
- [ ] Configurable watchlist refresh interval
- [ ] User authentication for multi-user dashboard (JWT)

### Long Term
- [ ] Advanced charting (candlestick, volume, moving averages)
- [ ] Mobile-responsive Streamlit improvements
- [ ] Deployment to Streamlit Cloud / Railway / Fly.io
- [ ] Export to PDF reports

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.4.0 | 2026-05-05 | API + DB tests, ARCHITECTURE.md sync, full test coverage |
| 0.3.0 | 2026-05-05 | FastAPI REST layer, PostgreSQL, Docker Compose |
| 0.2.0 | 2026-05-05 | Dashboard: charts, favorites, CSV export, caching, resilience |
| 0.1.0 | 2026-05-04 | CLI complete: price, list, search commands + Streamlit dashboard |
| 0.0.1 | 2026-04-10 | Project structure + core models |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.
