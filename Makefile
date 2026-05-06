.PHONY: install test lint fmt typecheck coverage pre-commit clean db-migrate db-revision db-upgrade db-downgrade

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

# Build Docker image
docker-build:
	docker build -t crypto-tracker .

# Start all services in background
docker-up:
	docker compose up -d

# Stop all services
docker-down:
	docker compose down

# View logs in real-time
docker-logs:
	docker compose logs -f

# Rebuild and restart
docker-rebuild:
	docker compose up -d --build

# Remove cache files and coverage artifacts
clean:
	@find . -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' \) -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage
	@rm -rf htmlcov

# ──────────────────────────────────────────────────────────
# Database migrations (Alembic)
# ──────────────────────────────────────────────────────────

# Up: DATABASE_URL=sqlite:///crypto_tracker.db alembic upgrade head
db-upgrade:
	alembic upgrade head

# Down one step
db-downgrade:
	alembic downgrade -1

# Show current version and history
db-history:
	alembic history

# Autogenerate a new migration (after model changes)
# Usage: make db-revision msg="add email column to users"
db-revision:
	alembic revision --autogenerate -m "$(msg)"

# Run initial migration (create all tables)
db-init:
	alembic upgrade head
