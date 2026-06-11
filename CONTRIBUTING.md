# 🤝 Contributing to Crypto Tracker

Thank you for your interest in contributing! This is a learning project, so contributions that help others learn are especially welcome.

## Development Setup

```bash
# Clone and enter
git clone https://github.com/LeandroBenjaminL/crypto-tracker.git
cd crypto-tracker

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Development Tools

We use a `Makefile` to standardize common development tasks.

| Command | Description |
|---------|-------------|
| `make install` | Install the package with dev dependencies |
| `make test` | Run the test suite |
| `make lint` | Run ruff linter on `src/`, `app.py`, and `tests/` |
| `make fmt` | Run ruff formatter on `src/`, `app.py`, and `tests/` |
| `make typecheck` | Run mypy type checker on `src/` and `app.py` |
| `make coverage` | Run tests with HTML and terminal coverage reports |
| `make pre-commit` | Run all pre-commit hooks on all files |
| `make clean` | Remove `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.coverage`, and `htmlcov` |

## Pre-commit Checks

Before every commit, run:

```bash
make pre-commit
```

This runs:
- `ruff check --fix` — linting with auto-fixes
- `ruff format` — code formatting
- `mypy src/ app.py` — static type checking
- `pytest --no-header -q` — quick test run

## Code Style

We use `ruff` for linting and `mypy` for type checking:

```bash
# Lint
ruff check src/ app.py tests/

# Format
ruff format src/ app.py tests/

# Type check
mypy src/ app.py
```

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add price history command
fix: handle API rate limit errors
docs: update README with new screenshots
test: add tests for price service
chore: update dependencies
```

## Testing

- Write tests BEFORE implementing features (TDD)
- All tests must pass before merging

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Single file
pytest tests/test_portfolio_repository.py -v

# Edge cases only
pytest -v -k "error or edge or not_found or empty or unknown"

# View coverage report
open htmlcov/index.html
```

## Frontend (Astro)

```bash
cd frontend
npm install
npm run dev      # local dev server at localhost:4321
npm run build    # build for production
```

The frontend build (`astro build`) also runs in CI. Make sure it passes before pushing frontend changes.

## Project Architecture

Remember the golden rule:

```
src/core/       = Pure Python, no external dependencies
src/adapters/   = External integrations (API calls, DB)
src/cli/        = CLI interface
src/api/        = REST API layer
src/telegram/   = Telegram bot
```

### Project Structure

| Directory | Purpose |
|-----------|---------|
| `src/core/` | Domain models, business logic, pipeline ETL |
| `src/adapters/` | CoinGecko client, PostgreSQL repositories |
| `src/api/` | FastAPI server + HTTP client |
| `src/cli/` | Click commands |
| `src/telegram/` | Telegram bot |
| `src/ui/` | Streamlit formatters, theme |
| `src/config/` | Settings from environment |
| `frontend/` | Astro 6 SPA |
| `tests/` | 9 test files, 312 tests |
| `migrations/` | Alembic (5 versions) |

## PR Guidelines

- Keep PRs under **400 lines** of diff. If larger, split into chained PRs.
- Before pushing: `ruff check src/ app.py tests/`, `mypy src/ app.py`, `pytest`, and `cd frontend && npm run build` if frontend changes.
- All PRs go against `main`. No direct pushes to main.

## Questions?

Open an issue for discussion before submitting PRs.
