# 🪙 Crypto Tracker CLI

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-104%20cases-green.svg)](./tests)

A command-line tool to track cryptocurrency prices, manage favorites, and view historical data — all powered by the CoinGecko public API.

## 📖 About This Project

This is a **learning project** built with clean architecture principles. The goal is to demonstrate:

- **Clean Architecture**: Separation of concerns between CLI, business logic, and external services
- **Test-Driven Development**: Core logic is fully tested with mocks (~104 tests)
- **Dual UI**: Same engine powers both a terminal CLI and a web dashboard
- **Production-ready structure**: Real project organization with `pyproject.toml`, CI/CD, and type checking

> 🧠 **Learning Focus**: This project prioritizes understanding over speed. Each component is designed to be explained and understood, not just "made to work."

## ✨ Features

- ✅ Search cryptocurrency prices by symbol or name
- ✅ List top cryptocurrencies by market cap
- ✅ Save favorite coins for quick access
- ✅ View price history (7d, 30d, 90d, 1y)
- ✅ Streamlit web dashboard with interactive charts
- ✅ CSV export from the dashboard
- ✅ Multi-currency support (USD, EUR, ARS, GBP, BRL, JPY, CNY)
- ✅ Rate limiting and caching for API efficiency
- ✅ Friendly error messages for all network and API issues

## 🏗️ Architecture Overview

```
crypto-tracker/
├── src/                    # Source code
│   ├── core/              # Business logic (pure, no dependencies)
│   │   ├── models.py      # Domain entities (Cryptocurrency, PriceData, ...)
│   │   ├── exceptions.py  # Custom exception hierarchy
│   │   ├── price_service.py  # Business rules + symbol resolution
│   │   └── favorites.py   # Persistent local storage
│   ├── adapters/          # External integrations
│   │   └── api_client.py  # CoinGecko API with caching, retries, rate limiting
│   ├── cli/               # CLI interface
│   │   └── commands.py    # Click commands (price, list-coins, search)
│   └── config/            # Configuration
│       └── settings.py    # Environment-based settings
├── tests/                  # pytest suite with mocked dependencies
├── app.py                  # Streamlit dashboard (dual UI)
├── pyproject.toml          # Project metadata and tooling config
└── README.md
```

### The Core Idea: Separation of Concerns

```
┌────────────────────────────────────────────────────────────┐
│                      CLI (commands.py)                     │
│         "El usuario escribió: crypto-tracker price btc"   │
└──────────────────────────┬─────────────────────────────────┘
                           │ calls
                           ▼
┌────────────────────────────────────────────────────────────┐
│               CORE (price_service.py)                       │
│   "Sé CÓMO buscar un precio, pero no sé DE DÓNDE"         │
│   Python puro: sin imports de requests, httpx, etc.        │
└──────────────────────────┬─────────────────────────────────┘
                           │ uses
                           ▼
┌────────────────────────────────────────────────────────────┐
│             ADAPTERS (api_client.py)                       │
│   "Sé CÓMO llamar a la API de CoinGecko"                  │
│   Este es el ÚNICO lugar que sabe de HTTP requests         │
└────────────────────────────────────────────────────────────┘
```

**Why this matters:**
- If CoinGecko API changes → only `adapters/api_client.py` changes
- If you want to add a GUI later → only `cli/commands.py` changes
- If you want to test the logic → mock the adapter, no network needed

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- pip or pipx

### Installation

```bash
# Clone the repository
git clone https://github.com/LeandroBenjaminL/crypto-tracker.git
cd crypto-tracker

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

### CLI Quick Start

```bash
# Check the current price of Bitcoin
crypto-tracker price btc

# Check multiple coins
crypto-tracker price btc eth sol

# List top 10 by market cap
crypto-tracker list --limit 10

# Add to favorites (from the dashboard)
# View favorites
crypto-tracker favorites list

# Search by name or symbol
crypto-tracker search cardano
```

### Streamlit Dashboard

```bash
# Launch the web interface
streamlit run app.py
```

The dashboard includes:
- **⭐ Favoritos** — quick view of saved coins with live prices
- **🔍 Precio** — search any coin with interactive historical charts
- **🏆 Top Monedas** — ranked table with CSV export and market cap treemap
- **🔎 Buscar** — discover coins by name or symbol

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_price_service.py

# Run with verbose output
pytest -v
```

## 📚 Learning Resources

This project teaches these concepts through real code:

| Concept | Where to Learn |
|---------|----------------|
| Clean Architecture | `src/core/` + `src/adapters/` structure |
| Dependency Injection | How `price_service.py` receives `api_client` via Protocol |
| Abstract Interfaces | `CoinGeckoClientProtocol` in `price_service.py` |
| Mocking in Tests | `tests/test_price_service.py`, `tests/test_api_client.py` |
| Python Packaging | `pyproject.toml` |
| CLI Design | `src/cli/commands.py` with Click |
| Streamlit Dashboard | `app.py` with caching and Plotly charts |
| Rate Limiting | `RateLimiter` in `api_client.py` |
| Caching | `TTLCache` in `api_client.py` + `st.cache_resource` in `app.py` |

## 🔜 Roadmap

See [ROADMAP.md](ROADMAP.md) for the detailed development timeline.

## 📄 Documentation

| File | What it covers |
|------|----------------|
| [ROADMAP.md](ROADMAP.md) | Development phases and future plans |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Deep dive into clean architecture decisions |
| [CHANGELOG.md](CHANGELOG.md) | Version history and release notes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development guidelines |

## 📝 License

MIT License — feel free to use this for learning and portfolio.

---

Built with 💚 as a learning project
