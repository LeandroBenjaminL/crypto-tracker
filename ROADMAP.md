# 🚀 Crypto Tracker - Roadmap

## Overview

This roadmap tracks the development phases of the Crypto Tracker CLI project. Each phase builds on the previous one, gradually adding features while maintaining clean architecture principles.

---

## Phase 1: Foundation ✅
**Status: Complete**

- [x] Project structure with clean architecture
- [x] `pyproject.toml` configuration
- [x] Virtual environment setup
- [x] Git repository initialized
- [x] README and documentation

---

## Phase 2: Core Models
**Goal: Define data structures** ✅

- [x] `src/core/models.py` - Cryptocurrency, Price data classes
- [x] `src/core/exceptions.py` - Custom exceptions
- [x] Unit tests for models

**Learning Objectives:**
- Python dataclasses
- Type hints
- Exception handling

---

## Phase 3: API Integration
**Goal: Connect to CoinGecko API** ✅

- [x] `src/adapters/api_client.py` - CoinGecko wrapper with rate limiting
- [x] `src/config/settings.py` - Environment-based configuration
- [x] Integration tests with mocked HTTP (16 tests)
- [x] Rate limiting handling (429, Retry-After)

**Learning Objectives:**
- HTTP requests with `requests`
- Environment variables with `python-dotenv`
- API error handling
- Mocking in tests

---

## Phase 4: Business Logic
**Goal: Implement price service** ✅

- [x] `src/core/price_service.py` - Core business logic
- [x] Dependency injection via Protocol (structural typing)
- [x] Symbol-to-ID resolution (local map + API fallback)
- [x] Unit tests with mocked API client (25 tests)

**Learning Objectives:**
- Separation of concerns
- Dependency injection
- Test-driven development

---

## Phase 5: CLI Interface
**Goal: Build command interface** ✅

- [x] `src/cli/commands.py` - Click-based CLI
- [x] `crypto-tracker price <symbol>` command (single + batch)
- [x] `crypto-tracker list-coins` command (top N by market cap)
- [x] `crypto-tracker search <query>` command
- [x] Color-coded output (green/red for gains/losses)
- [x] Friendly error messages for all exception types

**Learning Objectives:**
- Building CLIs with Click
- User input validation
- Exit codes and error handling

---

## Phase 6: Favorites System (Week 5-6)
**Goal: Save user preferences**

- [ ] JSON-based local storage
- [ ] `crypto-tracker favorites add/remove/list`
- [ ] Persistent configuration

**Learning Objectives:**
- File I/O in Python
- JSON handling
- Configuration management

---

## Phase 7: Testing & CI (Week 6-7)
**Goal: Production-ready quality**

- [ ] 80%+ test coverage
- [ ] GitHub Actions workflow
- [ ] Pre-commit hooks (ruff, mypy)
- [ ] Type checking passes

**Learning Objectives:**
- pytest advanced features
- Continuous Integration
- Code quality tools

---

## Phase 8: Documentation (Week 7-8)
**Goal: Portfolio-ready**

- [ ] Complete README with screenshots
- [ ] API documentation
- [ ] Contributing guidelines
- [ ] CHANGELOG

**Learning Objectives:**
- Technical writing
- Project documentation
- Open source best practices

---

## Future Enhancements (Post-Launch)

These features are planned but not scheduled:

- [ ] Price history charts
- [ ] Price alert notifications
- [ ] CSV/JSON export
- [ ] Multiple currency support
- [ ] Web UI (Flask/FastAPI)
- [ ] Docker deployment

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-05-04 | CLI complete: price, list, search commands |
| 0.0.1 | 2026-04-10 | Project structure + core models |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.
