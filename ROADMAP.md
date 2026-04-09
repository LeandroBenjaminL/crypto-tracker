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

## Phase 2: Core Models (Week 1-2)
**Goal: Define data structures**

- [ ] `src/core/models.py` - Cryptocurrency, Price data classes
- [ ] `src/core/exceptions.py` - Custom exceptions
- [ ] Unit tests for models

**Learning Objectives:**
- Python dataclasses
- Type hints
- Exception handling

---

## Phase 3: API Integration (Week 2-3)
**Goal: Connect to CoinGecko API**

- [ ] `src/adapters/api_client.py` - CoinGecko wrapper
- [ ] `src/config/settings.py` - Configuration management
- [ ] Integration tests with `httpx`
- [ ] Rate limiting handling

**Learning Objectives:**
- HTTP requests with `requests`
- Environment variables with `python-dotenv`
- API error handling
- Mocking in tests

---

## Phase 4: Business Logic (Week 3-4)
**Goal: Implement price service**

- [ ] `src/core/price_service.py` - Core business logic
- [ ] Dependency injection pattern
- [ ] Unit tests with mocked API client

**Learning Objectives:**
- Separation of concerns
- Dependency injection
- Test-driven development

---

## Phase 5: CLI Interface (Week 4-5)
**Goal: Build command interface**

- [ ] `src/cli/commands.py` - Click-based CLI
- [ ] `crypto-tracker price <symbol>` command
- [ ] `crypto-tracker list` command
- [ ] Help and error messages

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
| 0.1.0 | TBD | Foundation complete |
| 0.0.1 | Current | Project structure |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.
