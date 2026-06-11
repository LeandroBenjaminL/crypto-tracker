# 🏗️ Arquitectura de Crypto Tracker

> Este documento explica las decisiones de arquitectura del proyecto, cómo se organiza el código y por qué se eligió cada patrón.

## Índice

1. [Visión general](#visión-general)
2. [Estructura de directorios](#estructura-de-directorios)
3. [Capas de la arquitectura](#capas-de-la-arquitectura)
4. [Flujo de datos](#flujo-de-datos)
5. [Decisiones clave](#decisiones-clave)
6. [Testing](#testing)
7. [Triple UI: CLI + API + Streamlit](#triple-ui-cli--api--streamlit)
8. [Frontend Astro](#frontend-astro)
9. [Telegram Bot](#telegram-bot)
10. [Portfolio y Alertas](#portfolio-y-alertas)
11. [Docker y deployment](#docker-y-deployment)

---

## Visión general

Crypto Tracker sigue una **arquitectura limpia (Clean Architecture)** con separación de responsabilidades en seis zonas:

| Capa | Responsabilidad | Independencia |
|------|-----------------|---------------|
| **CLI** | Recibir input del usuario, mostrar output | Solo conoce `core` |
| **API (FastAPI)** | Exponer lógica como REST endpoints | Conoce `core` y `adapters/database` |
| **Telegram Bot** | Interfaz conversacional | Solo conoce `core` y `adapters` |
| **Streamlit** | Dashboard web interactivo | **Consume la API vía HTTP** |
| **Frontend Astro** | SPA estática en GitHub Pages | **Consume la API vía HTTP** |
| **Core** | Reglas de negocio, modelos de dominio | Sin dependencias externas |
| **Adapters** | Integrar con APIs externas y DB | Solo implementa lo que `core` espera |
| **Config** | Leer variables de entorno y settings | Utilitario, usado por todos |

La regla de oro: **el `core` no sabe de HTTP, ni de terminal, ni de web**. Es Python puro.

---

## Estructura de directorios

```
crypto-tracker/
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py          # Entidades de dominio
│   │   ├── exceptions.py      # Jerarquía de excepciones
│   │   ├── price_service.py   # Lógica de negocio
│   │   ├── pipeline.py        # ETL: CoinGecko → PostgreSQL + alertas
│   │   └── favorites.py       # Persistencia local de favoritos (JSON)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── api_client.py      # Cliente HTTP de CoinGecko
│   │   └── database.py        # SQLAlchemy: 6 tablas + migraciones
│   ├── api/                   # Capa REST
│   │   ├── __init__.py
│   │   ├── server.py           # FastAPI — 14 endpoints + OpenAPI docs
│   │   └── client.py           # Cliente HTTP para consumir la API
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py        # Click: price, list, search, pipeline, telegram
│   ├── telegram/
│   │   ├── __init__.py
│   │   └── bot.py             # Bot de Telegram con python-telegram-bot
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── api_cache.py       # Cache para llamadas a la API
│   │   ├── formatters.py      # Formateo de precios y monedas
│   │   ├── navigation.py      # Navegación del dashboard
│   │   └── theme.py           # Tema y CSS del dashboard
│   └── config/
│       ├── __init__.py
│       └── settings.py        # Configuración desde env
├── frontend/                  # Astro 6 — SPA estática
│   └── src/
│       ├── components/        # CoinsTable, PriceCard, ThemeToggle
│       ├── layouts/           # BaseLayout (Header + footer + theme)
│       ├── lib/               # api.ts, render.ts
│       ├── pages/             # index, price/[slug], top, search, favorites, 404
│       └── styles/            # global.css
├── migrations/              # Alembic migrations (5)
│   ├── versions/
│   │   ├── 0001_create_favorites_table.py
│   │   ├── 0002_create_price_snapshots_table.py
│   │   ├── 0003_create_price_history_table.py
│   │   ├── 0004_create_pipeline_runs_table.py
│   │   └── 0005_create_price_alerts_table.py
│   ├── env.py
│   ├── script.py.mako
│   └── alembic.ini
├── tests/
│   ├── test_models.py              # ~50 tests — modelos de dominio
│   ├── test_price_service.py       # ~30 tests — lógica de negocio
│   ├── test_api_client.py          # ~18 tests — CoinGecko HTTP mocks
│   ├── test_cli.py                 # ~17 tests — CLI con CliRunner
│   ├── test_favorites.py           # ~16 tests — persistencia JSON
│   ├── test_database.py            # ~14 tests — SQLAlchemy FavoritesRepository
│   ├── test_api_server.py          # ~50 tests — FastAPI con TestClient
│   ├── test_api_client_http.py     # ~44 tests — HTTP client mocks
│   └── test_portfolio_repository.py # 37 tests — PortfolioRepository CRUD + P&L
├── app.py                     # Dashboard Streamlit
├── run.py                     # Launcher local (API + Streamlit)
├── Dockerfile                 # 4 entrypoints: api | streamlit | pipeline | telegram
├── docker-compose.yml         # 3 servicios: API + Streamlit + PostgreSQL
├── pyproject.toml
├── alembic.ini
├── Makefile                   # Comandos de desarrollo
└── .github/workflows/
    ├── test.yml               # CI: Ruff + mypy + pytest
    ├── pipeline.yml           # Pipeline ETL (manual dispatch)
    └── frontend.yml           # Deploy frontend Astro a GitHub Pages
```

---

## Capas de la arquitectura

### 1. Core — El dominio

**Archivos:** `src/core/models.py`, `src/core/exceptions.py`, `src/core/price_service.py`, `src/core/favorites.py`, `src/core/pipeline.py`

Esta capa contiene todo lo que el negocio "sabe" sobre criptomonedas, precios, favoritos, pipeline ETL y alertas. No importa `requests`, `click`, `telegram`, ni `streamlit`.

#### Modelos (`models.py`)

```python
@dataclass(eq=False)
class Cryptocurrency:
    id: str          # "bitcoin"
    symbol: str      # "btc"
    name: str        # "Bitcoin"
    rank: int = 0

@dataclass
class PriceData:
    coin_id: str
    price: float
    change_24h: float
    volume_24h: float
    market_cap: float
    timestamp: datetime

@dataclass
class CoinSearchResult:
    coin: Cryptocurrency
    price_data: Optional[PriceData] = None

@dataclass
class PortfolioHolding:
    id: int
    coin_id: str
    symbol: str
    quantity: float
    purchase_price: float
    current_price: float = 0.0
    created_at: datetime = ...
    updated_at: Optional[datetime] = None

    @property
    def cost_basis(self) -> float: ...
    @property
    def current_value(self) -> float: ...
    @property
    def pnl(self) -> float: ...
```

Son **value objects**: inmutables, sin identidad más allá de sus datos. `Cryptocurrency` se compara por `id`, no por instancia.

#### Excepciones (`exceptions.py`)

Jerarquía propia para diferenciar errores del dominio:

```
CryptoTrackerError (base)
├── CoinNotFoundError
├── APIError
│   └── RateLimitError
├── NetworkError
├── ValidationError
├── ConfigurationError
└── CacheError
```

Cada capa superior (CLI, Telegram, API, Streamlit) mapea estas excepciones a mensajes amigables.

#### PriceService (`price_service.py`)

El corazón del negocio. Recibe un `api_client` por constructor (**dependency injection**) y define qué operaciones son válidas:

- `get_price(query)` — resuelve símbolo → ID → precio
- `get_prices(queries)` — batch de precios en una sola llamada API
- `search(query)` — busca monedas por nombre o símbolo
- `list_top(limit)` — top N por market cap
- `get_history(query, days)` — datos históricos para graficar

**Protocolo (`CoinGeckoClientProtocol`):**

```python
class CoinGeckoClientProtocol(Protocol):
    def get_price(self, coin_ids: list[str], currency: str = "usd") -> dict[str, Any]: ...
    def get_top_coins(self, limit: int = 10, currency: str = "usd") -> list[dict[str, Any]]: ...
    def search_coin(self, query: str) -> list[dict[str, Any]]: ...
    def get_coin_history(self, coin_id: str, days: int = 7, currency: str = "usd") -> dict[str, Any]: ...
```

Usamos **structural typing** (duck typing) en vez de herencia: cualquier objeto que tenga esos métodos sirve. Esto hace que los tests sean triviales: pasamos un `MagicMock` y listo.

#### Resolución de símbolos

El servicio mantiene un mapa local `SYMBOL_TO_ID` con 50+ monedas populares. Esto permite:

1. **Resolución rápida** sin llamada a la API.
2. **Fallback a búsqueda API** si el símbolo no está en el mapa.
3. **Uso directo del ID** si el usuario ya pasa el ID de CoinGecko.

```python
def _resolve_to_id(self, query: str) -> str:
    # 1. Mapa local
    resolved = _try_resolve_id(normalized)
    if resolved: return resolved
    # 2. Búsqueda API
    results = self._client.search_coin(normalized)
    if results: return results[0]["id"]
    # 3. Usar tal cual (la API dirá si es válido)
    return normalized
```

#### Pipeline ETL (`pipeline.py`)

El pipeline es un **ETL** (Extract, Transform, Load) que mantiene la base de datos actualizada. Ver sección [Pipeline ETL](#pipeline-etl) más abajo.

#### Favorites (`favorites.py`)

Persistencia de favoritos con **dos backends intercambiables**:

| Backend | Clase | Cuándo se usa |
|---------|-------|---------------|
| **JSON file** | `FavoritesManager` | Default — sin configuración extra |
| **PostgreSQL** | `FavoritesRepository` | Cuando `DATABASE_URL` está configurada |

Ambos implementan la misma interfaz pública. El server elige uno al arrancar con **graceful degradation**: si hay `DATABASE_URL` pero la DB no responde, cae silenciosamente a JSON y loguea un warning.

---

### 2. Adapters — Integraciones externas

**Archivos:** `src/adapters/api_client.py`, `src/adapters/database.py`

Los adapters son la **única** parte del código que sabe de HTTP y bases de datos.

#### CoinGeckoClient (`api_client.py`)

```python
class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"
    def get_price(self, coin_ids, currency): ...
    def get_top_coins(self, limit, currency): ...
    def search_coin(self, query): ...
    def get_coin_history(self, coin_id, days, currency): ...
```

**Resiliencia incorporada:**

| Mecanismo | Implementación | Por qué |
|-----------|----------------|---------|
| **Retry** | `urllib3.Retry` con backoff en 500/502/503/504 | Transient errors |
| **Rate limiter** | `RateLimiter` con ventana de 60s y 5 calls/min | Evitar 429 en tier gratuito |
| **TTL Cache** | `TTLCache` con 30s de vida y max 128 entries | No golpear la API por los mismos datos |
| **Timeout** | 10s en todas las requests | No quedar colgado |

#### Database Adapter (`database.py`)

Repositorio SQLAlchemy 2.0 con 6 tablas:

| Tabla | Clase Row | Propósito |
|-------|-----------|-----------|
| `favorites` | `FavoriteRow` | Favoritos del usuario |
| `price_snapshots` | `PriceSnapshotRow` | Snapshots periódicos de precios |
| `price_history` | `PriceHistoryRow` | Histórico cacheado (7d, 30d, 90d) |
| `pipeline_runs` | `PipelineRunRow` | Registro de ejecuciones del pipeline |
| `price_alerts` | `PriceAlertRow` | Alertas de precio configurables |
| `portfolio_holdings` | `PortfolioHoldingRow` | Holdings del portfolio |

**Repositorios:**

| Clase | Tabla | Métodos |
|-------|-------|---------|
| `FavoritesRepository` | `favorites` | CRUD + idempotencia |
| `PortfolioRepository` | `portfolio_holdings` | CRUD + `get_summary()` con P&L |

---

### 3. Pipeline ETL — Cache de datos en PostgreSQL

**Archivo:** `src/core/pipeline.py`

El pipeline es un **ETL** (Extract, Transform, Load) que mantiene la base de datos actualizada para que la API nunca tenga que llamar a CoinGecko directamente.

#### Frecuencia

| Datos | Frecuencia | Tabla |
|-------|-----------|-------|
| Precios top 100 monedas | Cada 30 min (manual dispatch) | `price_snapshots` |
| Histórico (7d, 30d, 90d) | Cada 6h | `price_history` |
| Migraciones DB | Al arrancar | `alembic_version` |
| Alertas de precio | Post-pipeline | `check_alerts()` |

#### Cómo funciona

```python
def run(database_url, top_n=100):
    run_migrations(database_url)
    raw_coins = client.get_top_coins(limit=top_n)
    rows = [PriceSnapshotRow(...) for raw in raw_coins]
    session.add_all(rows)
    _refresh_history_if_stale(client, engine)
    triggered = check_alerts(engine)
```

#### Cache-first (Opción B)

```
Request → ¿Hay datos en DB? → Sí → 10ms 🚀
                           → No → CoinGecko (fallback) → 1-3s
```

#### Alertas de precio

Después de cada corrida del pipeline, `check_alerts()` revisa las alertas activas. Cada alerta tiene `coin_id`, `condition` ("above" | "below"), `target_price`. Cuando se dispara → `is_active = 0`.

---

### 4. Telegram Bot

**Archivo:** `src/telegram/bot.py`

Bot de Telegram construido con [python-telegram-bot](https://python-telegram-bot.org/) (v20+). Corre como un proceso standalone.

#### Comandos

| Comando | Descripción |
|---------|-------------|
| `/start` | Mensaje de bienvenida |
| `/price COIN` | Precio actual (ej: `/price btc`) |
| `/top [N]` | Top N monedas (default 10) |
| `/alert COIN above\|below PRECIO` | Crear alerta de precio |
| `/help` | Ayuda |

#### Autorización

Soporta una **lista blanca** opcional via `TELEGRAM_ALLOWED_USERS`. Si no está configurada, responde a todos.

```python
def _is_allowed(user_id: int) -> bool:
    return not _ALLOWED_USERS or user_id in _ALLOWED_USERS
```

---

### 5. Portfolio y Alertas

#### PortfolioRepository

**Archivo:** `src/adapters/database.py` (clase `PortfolioRepository`, línea 323)

Repositorio para tracking de holdings con **cálculo de P&L**.

**CRUD completo:**
- `create(coin_id, symbol, quantity, purchase_price)` — validaciones: quantity > 0, price >= 0
- `get_by_id(holding_id)` — lookup individual
- `list_all()` — ordenado por `created_at` descendente
- `update(holding_id, quantity?, purchase_price?)` — actualización parcial
- `delete(holding_id)` — returns True si existía

**P&L Summary:**

```python
def get_summary(self, current_prices: dict[str, float]) -> dict:
    """
    Calcula:
    - total_value: valor actual de todos los holdings
    - total_cost: costo total de compra
    - total_pnl: ganancia/pérdida neta
    - pnl_percent: porcentaje sobre el costo
    - holdings_count: cantidad de posiciones

    Si un coin_id no está en current_prices, usa purchase_price como fallback
    (P&L neutro para esa moneda).
    """
```

---

## Flujo de datos

Hay **tres caminos posibles** según la interfaz que use el usuario. Todos terminan en el mismo `PriceService` y `CoinGeckoClient`.

### Camino A — CLI (llamada directa al core)

```
Usuario → CLI (commands.py) → PriceService → CoinGeckoClient → HTTP → CoinGecko
```

### Camino B — Streamlit / Frontend (vía API REST)

```
Usuario → Streamlit/Astro → HTTP GET → FastAPI → DB (cache-first) → CoinGecko (fallback)
```

### Camino C — Telegram Bot

```
Usuario → Telegram Bot → PriceService → CoinGeckoClient → HTTP → CoinGecko
```

---

## Frontend Astro

**Directorio:** `frontend/`

Frontend estático construido con [Astro 6](https://astro.build/). Se deploya a **GitHub Pages** automáticamente.

### Estructura

```
frontend/
├── src/
│   ├── components/     # CoinsTable, PriceCard, ThemeToggle
│   ├── layouts/        # BaseLayout (header + footer + theme)
│   ├── lib/            # api.ts, render.ts
│   ├── pages/          # index, price/[slug], top, search, favorites, 404
│   └── styles/         # global.css
├── astro.config.mjs
└── package.json
```

---

## Testing

**Filosofía:** testear cada capa en aislamiento, con mocks para las dependencias.

| Suite | Archivo | Tests | Qué testea |
|-------|---------|-------|------------|
| Models | `test_models.py` | ~50 | Creación, igualdad, formateo |
| Price Service | `test_price_service.py` | ~30 | Lógica de negocio, símbolos |
| CoinGecko Client | `test_api_client.py` | ~18 | HTTP mocks, rate limit |
| CLI | `test_cli.py` | ~17 | Click CliRunner |
| JSON Favorites | `test_favorites.py` | ~16 | CRUD JSON |
| DB FavoritesRepo | `test_database.py` | ~14 | SQLAlchemy + SQLite |
| API Server | `test_api_server.py` | ~50 | FastAPI TestClient |
| API HTTP Client | `test_api_client_http.py` | ~44 | HTTP client mocks |
| PortfolioRepo | `test_portfolio_repository.py` | 37 | CRUD + P&L |

**Total: 312 tests — 9 test files.**

---

## Docker y deployment

### Docker multi-entrypoint

```dockerfile
CMD ["sh", "-c", "case ${ENTRYPOINT:-api} in \
  pipeline) crypto-tracker pipeline ;; \
  streamlit) streamlit run app.py ;; \
  telegram) crypto-tracker-telegram ;; \
  *) uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT:-8000} ;; \
esac"]
```

### Docker Compose (3 servicios)

```yaml
services:
  db:            # PostgreSQL 16 Alpine
  api:           # FastAPI
  streamlit:     # Dashboard
```

### GitHub Actions (3 workflows)

| Workflow | Disparador | Qué hace |
|----------|-----------|----------|
| `test.yml` | Push/PR a main | Ruff + mypy + pytest |
| `pipeline.yml` | Manual dispatch | ETL en producción |
| `frontend.yml` | Push a main (frontend/) | Astro build + Pages deploy |

### Variables de entorno

| Variable | Default | Uso |
|----------|---------|-----|
| `COINGECKO_API_KEY` | (vacío) | API + precarga |
| `DATABASE_URL` | (vacío) | Repositorios DB |
| `API_BASE_URL` | `http://api:8000` | Streamlit → API |
| `TELEGRAM_BOT_TOKEN` | (vacío) | Bot de Telegram |
| `TELEGRAM_ALLOWED_USERS` | (vacío) | Lista blanca del bot |

---

*Documento vivo: si la arquitectura cambia, este archivo se actualiza.*
