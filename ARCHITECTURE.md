# 🏗️ Arquitectura de Crypto Tracker

> Este documento explica las decisiones de arquitectura del proyecto, cómo se organiza el código y por qué se eligió cada patrón.

## Índice

1. [Visión general](#visión-general)
2. [Estructura de directorios](#estructura-de-directorios)
3. [Capas de la arquitectura](#capas-de-la-arquitectura)
4. [Flujo de datos](#flujo-de-datos)
5. [Decisiones clave](#decisiones-clave)
6. [Testing](#testing)
7. [Triple UI: CLI + Streamlit + API](#triple-ui-cli--streamlit--api)
8. [Docker y deployment](#docker-y-deployment)

---

## Visión general

Crypto Tracker sigue una **arquitectura limpia (Clean Architecture)** con separación de responsabilidades en seis zonas:

| Capa | Responsabilidad | Independencia |
|------|-----------------|---------------|
| **CLI** | Recibir input del usuario, mostrar output | Solo conoce `core` |
| **API (FastAPI)** | Exponer lógica como REST endpoints | Conoce `core` y `adapters/database` |
| **Streamlit** | Dashboard web interactivo | **Consume la API vía HTTP** — no importa `core` directo |
| **Core** | Reglas de negocio, modelos de dominio | Sin dependencias externas |
| **Adapters** | Integrar con APIs externas y DB | Solo implementa lo que `core` espera |
| **Config** | Leer variables de entorno y settings | Utilitario, usado por todos |

La regla de oro: **el `core` no sabe de HTTP, ni de terminal, ni de web**. Es Python puro.

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
│   │   └── favorites.py       # Persistencia local de favoritos
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── api_client.py      # Cliente HTTP de CoinGecko
│   │   └── database.py        # Repositorio PostgreSQL via SQLAlchemy
│   ├── api/                   # 🆕 Capa REST
│   │   ├── __init__.py
│   │   ├── server.py           # FastAPI — 8 endpoints + OpenAPI docs
│   │   └── client.py           # Cliente HTTP para consumir la API
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py        # Comandos de Click
│   └── config/
│       ├── __init__.py
│       └── settings.py        # Configuración desde env
├── tests/
│   ├── test_models.py              # 23 tests — modelos de dominio
│   ├── test_price_service.py       # 30 tests — lógica de negocio
│   ├── test_api_client.py          # 18 tests — CoinGecko HTTP mocks
│   ├── test_cli.py                 # 17 tests — CLI con CliRunner
│   ├── test_favorites.py           # 16 tests — persistencia JSON
│   ├── test_database.py            # 14 tests — 🆕 SQLAlchemy + SQLite
│   ├── test_api_server.py          # 🆕 FastAPI con TestClient
│   └── test_api_client_http.py     # 🆕 HTTP client contra la API
├── app.py                     # Dashboard Streamlit
├── run.py                     # 🆕 Launcher: arranca API + Streamlit juntos
├── Dockerfile                 # 🆕 Imagen Docker multi-entrypoint
├── docker-compose.yml         # 🆕 3 servicios: API + Streamlit + PostgreSQL
├── pyproject.toml
└── .github/workflows/test.yml # CI con Python 3.10/3.11/3.12
```

---

## Capas de la arquitectura

### 1. Core — El dominio

**Archivos:** `src/core/models.py`, `src/core/exceptions.py`, `src/core/price_service.py`, `src/core/favorites.py`

Esta capa contiene todo lo que el negocio "sabe" sobre criptomonedas, precios y favoritos. No importa `requests`, `click`, ni `streamlit`.

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

Cada capa superior (CLI, Streamlit) mapea estas excepciones a mensajes amigables para el usuario.

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

El servicio mantiene un mapa local `SYMBOL_TO_ID` con 50+ monedas populares (btc → bitcoin, eth → ethereum, etc.). Esto permite:

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

#### Favorites (`favorites.py`)

Persistencia de favoritos con **dos backends intercambiables**:

| Backend | Clase | Cuándo se usa |
|---------|-------|---------------|
| **JSON file** | `FavoritesManager` | Default — sin configuración extra |
| **PostgreSQL** | `FavoritesRepository` | Cuando `DATABASE_URL` está configurada |

Ambos implementan la misma interfaz pública. El server elige uno al arrancar con **graceful degradation**: si hay `DATABASE_URL` pero la DB no responde, cae silenciosamente a JSON y loguea un warning.

```python
if settings.database_url:
    try:
        _favorites = FavoritesRepository(settings.database_url)
    except Exception:
        _favorites = FavoritesManager()  # fallback
else:
    _favorites = FavoritesManager()
```

#### JSON file (`FavoritesManager`)

Persistencia simple en el home del usuario (`~/.crypto_tracker.json`). Intencionalmente minimalista: no necesitamos una base de datos para una lista de símbolos.

```python
class FavoritesManager:
    def add(self, symbol: str) -> None      # idempotente (sin duplicados)
    def remove(self, symbol: str) -> None
    def list_all(self) -> list[FavoriteCoin]
    def is_favorite(self, symbol: str) -> bool
```

#### PostgreSQL (`FavoritesRepository`)

Cuando hay `DATABASE_URL` configurada, reemplaza al JSON file. Usa SQLAlchemy 2.0 con el pattern **Repository**:

```python
class FavoritesRepository:
    def list_all(self) -> list[FavoriteCoin]
    def add(self, symbol: str) -> None       # idempotente (IntegrityError → silencioso)
    def remove(self, symbol: str) -> None
    def is_favorite(self, symbol: str) -> bool
```

La tabla `favorites` tiene dos columnas: `symbol` (PK) y `added_at` (timestamptz).
Se crea automáticamente con `Base.metadata.create_all()` al iniciar el repositorio — no requiere migraciones manuales (aunque para producción recomendamos Alembic).

---

### 2. Adapters — Integraciones externas

**Archivos:** `src/adapters/api_client.py`, `src/adapters/database.py`

Los adapters son la **única** parte del código que sabe de HTTP y bases de datos. Si CoinGecko cambia su API o migramos de PostgreSQL a otra DB, solo se modifican estos archivos.

#### CoinGeckoClient (`api_client.py`)

#### CoinGeckoClient

```python
class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"

    def get_price(self, coin_ids, currency): ...
    def get_top_coins(self, limit, currency): ...
    def search_coin(self, query): ...
    def get_coin_history(self, coin_id, days, currency): ...
```

#### Resiliencia incorporada

| Mecanismo | Implementación | Por qué |
|-----------|----------------|---------|
| **Retry** | `urllib3.Retry` con backoff en 500/502/503/504 | Transient errors |
| **Rate limiter** | `RateLimiter` con ventana de 60s y 5 calls/min | Evitar 429 en tier gratuito |
| **TTL Cache** | `TTLCache` con 30s de vida y max 128 entries | No golpear la API por los mismos datos |
| **Timeout** | 10s en todas las requests | No quedar colgado |

#### Manejo de 429 (Rate Limit)

```python
if response.status_code == 429:
    retry_after = response.headers.get("Retry-After")
    raise RateLimitError(retry_after=int(retry_after) if retry_after else None)
```

El CLI y el dashboard traducen esto a: *"Límite de API alcanzado. Esperá X segundos o usá una API key gratuita."*

#### Database Adapter (`database.py`)

Repositorio SQLAlchemy 2.0 para favoritos. Usa el pattern **Repository** para abstraer la DB del core.

**Características:**
- **Auto-creación de tablas** con `Base.metadata.create_all()` al instanciar.
- **Idempotencia**: `add()` con `IntegrityError` se traga el error si el favorito ya existe.
- **SQLite en testing**: los tests usan `sqlite://` (in-memory), que comparte la misma API que PostgreSQL para CRUD básico.
- **Graceful degradation**: el server intenta PostgreSQL, y si falla, cae a JSON sin romper la app.

```python
class FavoritesRepository:
    def __init__(self, database_url: str):
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)  # tablas auto
```

---

### 3. CLI — Interfaz de terminal

**Archivo:** `src/cli/commands.py`

Construido con [Click](https://click.palletsprojects.com/). Es un grupo de comandos con tres subcomandos:

```bash
crypto-tracker price btc eth sol       # precios actuales
crypto-tracker list-coins --limit 20   # top por market cap
crypto-tracker search cardano          # búsqueda por nombre/símbolo
```

**Principio:** el CLI no llama a la API directamente. Solo conoce `PriceService`. Si mañana cambiamos de CoinGecko a otra fuente, el CLI no se entera.

#### Formato de salida

- Precios con decimales adaptativos: `$45,000.00`, `$0.0042`, `$0.00000042`
- Cambio 24h con color: `▲ +2.50%` en verde, `▼ -1.20%` en rojo
- Market cap humanizado: `$900.50B`, `$1.20T`

---

### 4. Config — Settings

**Archivo:** `src/config/settings.py`

Carga configuración desde variables de entorno, con soporte para archivo `.env`:

```python
@dataclass(frozen=True)
class Settings:
    coingecko_api_key: str = ""                # opcional, para más rate limit
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    default_currency: str = "usd"
    cache_ttl: int = 60                        # segundos
    favorites_file: Path = Path.home() / ".crypto_tracker.json"
```

Usamos un dataclass `frozen=True` para que la configuración no se mute accidentalmente en runtime.

---

### 5. API Layer — REST endpoints

**Archivos:** `src/api/server.py`, `src/api/client.py`

Esta capa **no existía en el diseño original**. Se agregó para desacoplar Streamlit del core: en vez de importar `PriceService` directo, el dashboard ahora habla HTTP con FastAPI.

#### Server (`server.py`)

FastAPI con 8 endpoints, OpenAPI docs automáticas en `/docs`, y precarga de datos al arrancar.

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/health` | GET | Health check con versión y fuente de favoritos |
| `/api/price/{query}` | GET | Precio de una moneda |
| `/api/prices` | GET | Precios batch (vía query string `?q=btc,eth,sol`) |
| `/api/top` | GET | Top N por market cap |
| `/api/history/{query}` | GET | Histórico para gráficos |
| `/api/search/{query}` | GET | Búsqueda por nombre/símbolo |
| `/api/favorites` | GET | Listar favoritos |
| `/api/favorites/{symbol}` | POST | Agregar favorito |
| `/api/favorites/{symbol}` | DELETE | Quitar favorito |

**Manejo de errores:** cada excepción del dominio se mapea a un código HTTP:

| Excepción | HTTP | Mensaje |
|-----------|------|---------|
| `CoinNotFoundError` | 404 | "Moneda no encontrada" |
| `RateLimitError` | 429 | "Límite de API alcanzado" |
| `NetworkError` | 502 | "Error de conexión externa" |
| `ValidationError` | 422 | Detail con el error |
| `APIError` | 502 | Detail del error |
| `CryptoTrackerError` (genérico) | 500 | "Error interno" |

**Precarga:** al arrancar, un thread en background precarga datos populares (top 20, precios de 10 monedas, histórico de BTC) usando su propio rate limiter para no interferir con requests de usuarios.

#### Client (`client.py`)

Cliente HTTP que Streamlit usa para consumir la API. Traduce respuestas HTTP y errores de red a las excepciones del dominio (`CoinNotFoundError`, `RateLimitError`, `NetworkError`).

```python
# Antes: Streamlit importaba PriceService directo
from src.core.price_service import PriceService
service = PriceService(api_client=client)
data = service.get_price("btc")

# Ahora: Streamlit llama a la API vía HTTP
from src.api import client as api
data = api.get_price("btc")  # GET → http://localhost:8000/api/price/btc
```

**¿Por qué este cambio?**
- **Cache compartido**: la API cachea respuestas de CoinGecko y todas las sesiones de Streamlit se benefician.
- **Rerenders más livianos**: Streamlit no carga todo el dominio, solo recibe JSON.
- **API sirve a cualquier frontend**: React, mobile, curl — todos pueden usar los mismos endpoints.

---

## Flujo de datos

Hay **dos caminos posibles** según la interfaz que use el usuario. Ambos terminan en el mismo `PriceService` y `CoinGeckoClient`.

### Camino A — CLI (llamada directa al core)

```
┌─────────────┐
│   Usuario   │
│  "btc"      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  CLI (commands.py)                                          │
│  - Valida input                                              │
│  - Llama a service.get_price("btc")                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PriceService (core)                                        │
│  1. Normaliza "btc"                                         │
│  2. SYMBOL_TO_ID → "bitcoin"                                │
│  3. client.get_price(["bitcoin"], "usd")                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  CoinGeckoClient (adapter)                                  │
│  TTL cache → Rate limiter → HTTP GET → parse → cache        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PriceService → CLI                                         │
│  dict → PriceData → CoinSearchResult → formateo → pantalla  │
└─────────────────────────────────────────────────────────────┘
```

### Camino B — Streamlit (vía API REST)

```
┌─────────────┐
│   Usuario   │
│  "btc"      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Streamlit (app.py)                                         │
│  api.get_price("btc")  →  HTTP GET                          │
└──────────────────────────┬──────────────────────────────────┘
                           │  GET http://localhost:8000/api/price/btc
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI (server.py)                                        │
│  1. Parsea params                                           │
│  2. _service.get_price("btc")                               │
│  3. CoinSearchResult → CoinOut (Pydantic)                   │
│  4. JSON response                                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PriceService → CoinGeckoClient (mismo que Camino A)        │
└─────────────────────────────────────────────────────────────┘
```

**¿Por qué dos caminos?** Porque Streamlit rerenderiza CONSTANTEMENTE. Si cada rerender importara todo el dominio, sería lento. La API corre separada (otro proceso o container), cachea respuestas en memoria, y sirve datos a múltiples sesiones.

**Nota clave:** El `core` nunca ve un `requests.Response`. Solo ve dicts de Python. Los adapters son los únicos que hablan con el mundo exterior.

---

## Decisiones clave

### ¿Por qué Protocol en vez de ABC?

```python
class CoinGeckoClientProtocol(Protocol):
    ...
```

Usamos `typing.Protocol` (structural typing) porque:
- No necesitamos que `CoinGeckoClient` herede de nada.
- Cualquier objeto con los mismos métodos sirve (mocks, stubs, clientes alternativos).
- Es más flexible que una ABC para proyectos pequeños.

### ¿Por qué dataclasses en vez de Pydantic?

Las dataclasses de la stdlib son suficientes para este dominio. No necesitamos validación de schema en runtime ni serialización JSON automática. Las dataclasses son más livianas y no añaden dependencias.

### ¿Por qué JSON en vez de SQLite para favoritos?

Intencionalmente simple. Una lista de símbolos no justifica una base de datos. El archivo JSON es legible, portable, y se puede versionar si el usuario lo desea.

### ¿Por qué `st.cache_resource` en vez de `st.cache_data`?

Los objetos del dominio (`Cryptocurrency`, `PriceData`) no son pickle-serializables de forma trivial (algunos tienen `__eq__` custom). `st.cache_resource` mantiene la referencia en memoria con TTL, sin intentar serializar.

### ¿Por qué TTL cache propio en vez de `functools.lru_cache`?

`lru_cache` no soporta TTL ni argumentos mutables (como `list`). Nuestro `TTLCache` es simple, con eviction por antigüedad, y usa tuplas como clave.

### ¿Por qué FastAPI en vez de Flask?

FastAPI tiene **OpenAPI docs automáticas** (`/docs`, `/redoc`), validación con Pydantic, y type hints nativos. Para un proyecto de datos donde querés que otros puedan explorar la API fácilmente, es muy superior. Flask requiere configurar todo eso manualmente.

### ¿Por qué Streamlit consume la API vía HTTP en vez de importar el core directo?

Es una decisión que cambiamos a mitad del proyecto. Originalmente Streamlit importaba `PriceService` directo. El problema: cada rerender de Streamlit reinicia el script, y aunque `st.cache_resource` ayuda, el caché es por-sesión. Con la API:

1. **Cache compartido**: una sola instancia de `CoinGeckoClient` sirve a todas las sesiones.
2. **Rerenders livianos**: Streamlit solo recibe JSON, no carga todo el dominio.
3. **La API es independiente**: puede servir a cualquier frontend (React, mobile, curl).

El costo: un proceso extra que gestionar y latencia de red local (~1ms, imperceptible).

### ¿Por qué PostgreSQL + JSON en vez de solo JSON?

El JSON file es simple y funciona siempre. PostgreSQL se suma como opción para entornos donde:

- **Múltiples usuarios** comparten la misma instalación (Docker Compose).
- **Persistencia confiable** sin riesgo de corrupción de archivo.
- **Operaciones concurrentes** sin race conditions.

La clave: **graceful degradation**. Si configuraste DB pero no funciona, el sistema cae a JSON sin que el usuario se entere. Esto permite desarrollo local sin PostgreSQL y producción con DB.

### ¿Por qué SQLAlchemy 2.0 para la DB?

SQLAlchemy 2.0 con `DeclarativeBase` y `sessionmaker` es el estándar actual. Usamos SQLite in-memory para tests (misma API que PostgreSQL para CRUD), sin necesidad de mockear.

---

## Testing

**Filosofía:** testear cada capa en aislamiento, con mocks para las dependencias. Cada adaptador/interfaz tiene su propia suite.

| Suite | Archivo | Casos | Qué testea |
|-------|---------|-------|------------|
| Models | `test_models.py` | 23 | Creación, igualdad, formateo, timestamps |
| Price Service | `test_price_service.py` | 30 | Lógica de negocio, resolución de símbolos, validaciones |
| CoinGecko Client | `test_api_client.py` | 18 | HTTP mocks, rate limit, errores 429/404/500, cache |
| CLI | `test_cli.py` | 17 | Click CliRunner, argumentos, opciones, errores |
| JSON Favorites | `test_favorites.py` | 16 | CRUD JSON, persistencia, corrupción de archivo |
| DB Repository | `test_database.py` | 14 | 🆕 SQLAlchemy con SQLite in-memory |
| API Server | `test_api_server.py` | ~20 | 🆕 FastAPI con TestClient + mocks |
| API HTTP Client | `test_api_client_http.py` | ~16 | 🆕 Cliente HTTP con mocks de requests |

**Total: ~154 tests.**

### Patrones de test por capa

| Capa | Cómo se testea | Herramienta |
|------|----------------|-------------|
| **Core** | Mock del API client | `MagicMock` + Protocol |
| **Adapters** | Mock de `requests.Session` | `create_autospec` |
| **CLI** | Mock del service | Click `CliRunner` |
| **DB** | SQLite in-memory | `sqlite://` + fixtures |
| **API Server** | Mock de service + favorites | FastAPI `TestClient` |
| **API HTTP Client** | Mock de `requests.get/post/delete` | `unittest.mock.patch` |

### Ejemplo: test del API Server con TestClient

```python
def test_get_price_by_symbol(client: TestClient, mock_service: MagicMock):
    mock_service.get_price.return_value = _coin_search_result()
    resp = client.get("/api/price/btc")
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "btc"
    assert resp.json()["price"] == 45000.50
    mock_service.get_price.assert_called_once_with("btc", currency="usd")
```

El `TestClient` de Starlette permite testear endpoints sin levantar un servidor HTTP. Mockeamos `_service` y `_favorites` en el módulo server, y desactivamos la precarga para los tests.

---

## Triple UI: CLI + Streamlit + API

El proyecto empezó con dos interfaces (CLI + Streamlit) compartiendo el mismo `PriceService`. Después agregamos una tercera: la **API REST**, que a su vez es consumida por el Streamlit modernizado.

```
                         ┌─────────────────┐
                         │   PriceService   │
                         │   (core)         │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
    ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐
    │   CLI (Click)   │  │  FastAPI     │  │  Streamlit App  │
    │   commands.py   │  │  server.py   │  │   app.py        │
    │                 │  │              │  │       │         │
    │  • Terminal     │  │  • REST API  │  │  ❌ No llama   │
    │  • Texto plano  │  │  • /docs     │  │  directo a core │
    │  • Color cód.   │  │  • Precarga  │  │       │         │
    └─────────────────┘  └──────┬───────┘  │  ✅ Consume API │
                               │           │  vía HTTP       │
                               └───────────┴─────────────────┘
```

### Relaciones entre interfaces

| Interfaz | ¿Importa core directo? | ¿Consume API? | Ideal para |
|----------|----------------------|---------------|------------|
| **CLI** | ✅ Sí | ❌ No | Terminal, scripts, automatización |
| **FastAPI** | ✅ Sí | ❌ No | Otros frontends, integraciones |
| **Streamlit** | ❌ No | ✅ Sí | Usuarios finales, dashboards |

### ¿Por qué Streamlit no importa core directo?

Originalmente sí lo hacía. Pero Streamlit rerenderiza CONSTANTEMENTE (cada click, cada input). Si cada rerender importara todo el dominio — `PriceService`, `CoinGeckoClient`, models, excepciones, etc. — la experiencia se degradaba. La API resuelve esto:

1. **Cache compartido**: una sola instancia de `CoinGeckoClient` en la API sirve a todas las sesiones de Streamlit.
2. **Rerenders livianos**: Streamlit solo recibe JSON, no carga módulos de Python.
3. **La API es independiente**: puede servir a cualquier frontend (React, mobile, curl).

Este es un buen ejemplo de cómo la arquitectura limpia permite evolucionar: el core no cambió, solo reorganizamos cómo las interfaces se conectan a él.

---

## Diagrama de dependencias

```
                    ┌─────────────────────┐
                    │      Config         │
                    │     settings        │
                    └──────────┬──────────┘
                               │
           ┌───────────────────┼───────────────────────┐
           │                   │                       │
           ▼                   ▼                       ▼
    ┌────────────┐    ┌──────────────┐        ┌────────────┐
    │    CLI     │    │   FastAPI    │        │   Tests    │
    │  commands  │    │  server.py   │        │   mocks    │
    └─────┬──────┘    └──────┬───────┘        └─────┬──────┘
          │                  │                       │
          │                  ▼                       │
          │           ┌──────────────┐               │
          │           │  Streamlit   │               │
          │           │   app.py     │               │
          │           │  (via HTTP)  │               │
          │           └──────┬───────┘               │
          │                  │                       │
          └──────────────────┼───────────────────────┘
                             │
                             ▼
                      ┌────────────┐
                      │    Core    │
                      │  service   │
                      │  models    │
                      │ favorites  │
                      └─────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
    ┌────────────┐  ┌──────────────┐  ┌──────────────┐
    │ CoinGecko  │  │  Database   │  │   JSON File  │
    │  Client    │  │ Repository  │  │ Favorites    │
    │  (HTTP)    │  │ (PostgreSQL)│  │ (fallback)   │
    └─────┬──────┘  └──────────────┘  └──────────────┘
          │
          ▼
    ┌────────────┐
    │  External  │
    │ CoinGecko  │
    └────────────┘
```

**Regla visual:** las flechas apuntan hacia abajo. Ninguna flecha apunta hacia arriba. El `core` no conoce a ninguna interfaz, solo define contratos (Protocol) que los adapters implementan.

---

## Docker y deployment

El proyecto incluye Docker multi-etapa para levantar todo el stack:

### Docker Compose (3 servicios)

```yaml
services:
  db:            # PostgreSQL 16 Alpine — datos persistentes
  api:           # FastAPI — depende de db (healthcheck)
  streamlit:     # Dashboard — depende de api (healthcheck)
```

**Flujo de arranque:**
1. PostgreSQL levanta y pasa su healthcheck (`pg_isready`).
2. FastAPI arranca, conecta a la DB, y expone el health endpoint.
3. Streamlit arranca y apunta a `http://api:8000` (DNS interno de Docker).

**Variables de entorno:**
| Variable | Dónde se usa | Default |
|----------|-------------|---------|
| `COINGECKO_API_KEY` | API + precarga | (vacío — free tier) |
| `DATABASE_URL` | API → FavoritesRepository | (vacío — usa JSON) |
| `API_BASE_URL` | Streamlit → api client | `http://api:8000` |

### Dockerfile

Una sola imagen con dos entrypoints:

```dockerfile
# Default: API
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0"]

# Override: Streamlit
# docker run crypto-tracker streamlit run app.py
```

### Makefile

Comandos útiles para el día a día:

```bash
make docker-build    # build imagen
make docker-up       # docker compose up -d
make docker-logs     # logs en vivo
make docker-rebuild  # rebuild + restart
make docker-down     # stop todo
```

### Launcher local (`run.py`)

Para desarrollo sin Docker:

```bash
python run.py
# Arranca FastAPI + Streamlit como subprocessos
# Hace polling al health endpoint hasta que la API responda
# Cleanup automático con atexit
```

---

*Documento vivo: si la arquitectura cambia, este archivo se actualiza.*
