.PHONY: install test lint fmt typecheck coverage pre-commit clean

# Install the package with all dev dependencies
install:
	pip install -e ".[dev]"

# Run the test suite
test:
	pytest

# Run linter (ruff)
lint:
	ruff check src/ app.py tests/

# Run formatter (ruff)
fmt:
	ruff format src/ app.py tests/

# Run static type checker (mypy)
typecheck:
	mypy src/ app.py

# Run tests with HTML and terminal coverage report
coverage:
	pytest --cov=src --cov-report=html --cov-report=term

# Run all pre-commit hooks on all files
pre-commit:
	pre-commit run --all-files

# Remove cache files and coverage artifacts
clean:
	@find . -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' \) -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage
	@rm -rf htmlcov
