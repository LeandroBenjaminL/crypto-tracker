# 🪙 Crypto Tracker CLI

A command-line tool to track cryptocurrency prices, manage favorites, and view historical data — all powered by the CoinGecko public API.

## 📖 About This Project

This is a **learning project** built with clean architecture principles. The goal is to demonstrate:

- **Clean Architecture**: Separation of concerns between CLI, business logic, and external services
- **Test-Driven Development**: Core logic is fully tested with mocks
- **Production-ready structure**: Real project organization with `pyproject.toml`, proper packaging, and CI

> 🧠 **Learning Focus**: This project prioritizes understanding over speed. Each component is designed to be explained and understood, not just "made to work."

## ✨ Features

- [ ] Search cryptocurrency prices by symbol or name
- [ ] List top cryptocurrencies by market cap
- [ ] Save favorite coins for quick access
- [ ] View price history (7d, 30d)
- [ ] Set price alerts (future)
- [ ] Export data to CSV (future)

## 🏗️ Architecture Overview

```
crypto-tracker/
├── src/                    # Source code
│   ├── core/              # Business logic (pure, no dependencies)
│   │   ├── models.py      # Data structures
│   │   └── price_service.py
│   ├── adapters/          # External integrations
│   │   └── api_client.py  # CoinGecko API wrapper
│   └── cli/               # CLI interface
│       └── commands.py
├── tests/                  # Unit and integration tests
├── config/                # Configuration
│   └── settings.py
├── pyproject.toml         # Project metadata
└── README.md
```

### The Core Idea: Separation of Concerns

```
┌────────────────────────────────────────────────────────────┐
│                      CLI (commands.py)                     │
│         "User typed: crypto-tracker price btc"            │
└──────────────────────────┬─────────────────────────────────┘
                           │ calls
                           ▼
┌────────────────────────────────────────────────────────────┐
│               CORE (price_service.py)                       │
│   "I know HOW to find a price, but I don't know FROM WHERE"│
│   Pure Python: no imports from requests, httpx, etc.       │
└──────────────────────────┬─────────────────────────────────┘
                           │ uses
                           ▼
┌────────────────────────────────────────────────────────────┐
│             ADAPTERS (api_client.py)                       │
│   "I know HOW to call CoinGecko API"                        │
│   This is the ONLY place that knows about HTTP requests    │
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
git clone https://github.com/yourusername/crypto-tracker.git
cd crypto-tracker

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run the CLI
crypto-tracker --help
```

### Quick Start

```bash
# Check the current price of Bitcoin
crypto-tracker price btc

# Check multiple coins
crypto-tracker price btc eth sol

# List top 10 by market cap
crypto-tracker list --limit 10

# Add to favorites
crypto-tracker favorites add btc

# View favorites
crypto-tracker favorites list
```

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
| Dependency Injection | How `price_service.py` receives `api_client` |
| Abstract Interfaces | Define in `core`, implement in `adapters` |
| Mocking in Tests | `tests/test_price_service.py` |
| Python Packaging | `pyproject.toml` |
| CLI Design | `src/cli/commands.py` |

## 🔜 Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed development timeline.

## 📝 License

MIT License - feel free to use this for learning and portfolio.

---

Built with 💚 as a learning project
