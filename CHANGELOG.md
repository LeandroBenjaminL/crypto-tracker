# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ETL Pipeline (`src/core/pipeline.py`) que extrae top 100 monedas de CoinGecko cada 30min y carga en PostgreSQL.
- Tabla `price_snapshots` con snapshots periódicos de precios (Alembic migration 0002).
- Tabla `price_history` con histórico cacheado 7d/30d/90d (Alembic migration 0003).
- Pipeline también refresca histórico cada 6h para las top 20 monedas.
- Comando CLI `crypto-tracker pipeline` para ejecutar el ETL manualmente.
- API ahora lee de PostgreSQL primero en `/api/price`, `/api/prices`, `/api/top`, `/api/history`.
- Fallback a CoinGecko cuando la DB no tiene datos (Opción B).
- Migraciones automáticas de Alembic al arrancar la API y al ejecutar el pipeline.
- Health endpoint ahora expone `price_source` ("db" o "coingecko").
- GitHub Actions workflow para pipeline ETL cada 30 minutos (`pipeline.yml`).
- Soporte multi-entrypoint en Dockerfile: `ENTRYPOINT=api|streamlit|pipeline`.
- Badges de CI y deploy en README.

### Changed
- README.md completamente actualizado con arquitectura, API, pipeline, Docker y deploy.
- Precarga al arranque reducida de ~15 calls a solo 3 (BTC, ETH, top 10).
- `pipeline.run()` ahora devuelve `dict` con stats en vez de `int`.
- `line-length` de ruff aumentado de 100 a 120.
- Mypy configurado con plugin de SQLAlchemy y overrides para archivos problemáticos.

### Fixed
- CI ahora pasa sin errores: ruff 0, mypy 0, 256 tests verdes.
- Unused imports eliminados en tests y source.
- Variable `Session_factory` renombrada a `session_factory` (PEP8).
- Tests actualizados para incluir `price_source` en health check.

## [0.2.0] — 2026-05-05

### Added
- **Streamlit dashboard** (`app.py`) con 4 páginas: Favoritos, Precio, Top Monedas, Buscar.
- **Interactive historical charts** usando Plotly (7d, 30d, 90d, 1y).
- **Favorites system** con persistencia JSON (`~/.crypto_tracker.json`).
- **CSV export** desde la página Top Monedas.
- **Auto-refresh toggle** y botón de refresh manual con limpieza de cache.
- **Mapa de símbolos** con 50+ criptos populares para resolución local rápida.
- **Indicador de API key** en la sidebar de Streamlit.
- **Treemap de market cap** en la página Top Monedas.
- **Rate limiter** y **TTL cache** en el API client.

### Changed
- Switched de `st.cache_data` a `st.cache_resource` para evitar pickle errors.
- Rate limit reducido a 5 requests/minute para el tier gratis de CoinGecko.
- Errores más amigables en el dashboard con botones de reintento.

### Fixed
- `AttributeError` en página de precio por shadowing de variable pandas.
- 13 errores de mypy en `app.py`, `api_client.py`, `commands.py`.
- Errores de ruff (E501, W293, I001).
- Línea en blanco entre docstring e import de `__future__`.
- Compatibilidad con Streamlit 1.57 (reemplazo de `st.autorefresh`).

## [0.1.0] — 2026-05-04

### Added
- **CLI interface** con Click: `price`, `list-coins`, `search`.
- **Price service** con dependency injection via Protocol.
- **Symbol-to-ID resolution**: mapa local + fallback API.
- **Output colorido** en terminal (verde para ganancias, rojo para pérdidas).
- **Mensajes de error amigables** para todas las excepciones de dominio.
- **GitHub Actions CI** con Ruff, mypy, pytest (Python 3.10, 3.11, 3.12).

### Fixed
- 7 issues del primer Judgment Day review.
- 5 issues del segundo Judgment Day review.

## [0.0.1] — 2026-04-10

### Added
- Estructura inicial con clean architecture (`src/core/`, `src/adapters/`, `src/cli/`, `src/config/`).
- `pyproject.toml` con metadata, dependencias, dev tools y entry points.
- Modelos de dominio: `Cryptocurrency`, `PriceData`, `CoinSearchResult`, `FavoriteCoin`, `PriceAlert`.
- Jerarquía de excepciones: `CryptoTrackerError`, `APIError`, `RateLimitError`, `NetworkError`, `CoinNotFoundError`, `ValidationError`, `ConfigurationError`.
- CoinGecko API client con rate limiting, retry y validación.
- Settings basadas en environment variables con `python-dotenv`.
- Tests unitarios para modelos, API client y price service con mocks.
- Documentación inicial (README, ROADMAP, CONTRIBUTING, AUTHORS).

[Unreleased]: https://github.com/LeandroBenjaminL/crypto-tracker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/LeandroBenjaminL/crypto-tracker/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/LeandroBenjaminL/crypto-tracker/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/LeandroBenjaminL/crypto-tracker/releases/tag/v0.0.1
