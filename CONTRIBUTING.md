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
