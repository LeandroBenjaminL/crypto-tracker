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

We use a `Makefile` to standardize common development tasks. All targets work on Linux, macOS, and WSL.

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

## Pre-commit Hooks

We use [pre-commit](https://pre-commit.com/) to run checks automatically before each commit. Install it separately if you haven't already:

```bash
pip install pre-commit
```

Install the git hooks (one-time setup):

```bash
pre-commit install
```

Run manually on all files:

```bash
make pre-commit
```

The following checks run automatically on every commit:

- `ruff check --fix` — linting with auto-fixes
- `ruff format` — code formatting
- `mypy src/` — static type checking
- `pytest --no-header -q` — quick test run

## Code Style

We use `ruff` for linting and `mypy` for type checking:

```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy src/
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
- Aim for 80%+ coverage
- All tests must pass before merging

```bash
# Run with coverage
pytest --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Project Architecture

Remember the golden rule:

```
core/  = Pure Python, no external dependencies
adapters/ = External integrations (API calls)
cli/ = User interface
```

## Questions?

Open an issue for discussion before submitting PRs.
