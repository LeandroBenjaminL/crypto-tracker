# 🏗️ Arquitectura de Crypto Tracker

> Este documento explica las decisiones de arquitectura del proyecto, cómo se organiza el código y por qué se eligió cada patrón.

## Índice

1. [Visión general](#visión-general)
2. [Estructura de directorios](#estructura-de-directorios)
3. [Capas de la arquitectura](#capas-de-la-arquitectura)
4. [Flujo de datos](#flujo-de-datos)
5. [Decisiones clave](#decisiones-clave)
6. [Testing](#testing)
7. [Dual UI: CLI + Streamlit](#dual-ui-cli--streamlit)

---

## Visión general

Crypto Tracker sigue una **arquitectura limpia (Clean Architecture)** con separación de responsabilidades en cuatro capas:

| Capa | Responsabilidad | Independencia |
|------|-----------------|---------------|
| **CLI** | Recibir input del usuario, mostrar output | Solo conoce `core` |
| **Core** | Reglas de negocio, modelos de dominio | Sin dependencias externas |
| **Adapters** | Integrar con APIs y servicios externos | Solo implementa lo que `core` espera |
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
│   │   └── favorites.py       # Persistencia local de favoritos
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── api_client.py      # Cliente HTTP de CoinGecko
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py        # Comandos de Click
│   └── config/
│       ├── __init__.py
│       └── settings.py        # Configuración desde env
├── tests/
│   ├── test_models.py         # 23 tests — modelos de dominio
│   ├── test_price_service.py  # 30 tests — lógica de negocio
│   ├── test_api_client.py     # 18 tests — cliente HTTP con mocks
│   ├── test_cli.py            # 17 tests — CLI con CliRunner
│   └── test_favorites.py      # 16 tests — persistencia JSON
├── app.py                     # Dashboard Streamlit
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

Persistencia simple en JSON en el home del usuario (`~/.crypto_tracker.json`). Diseño intencionalmente minimalista: no necesitamos una base de datos para una lista de símbolos.

```python
class FavoritesManager:
    def add(self, symbol: str) -> None      # idempotente (sin duplicados)
    def remove(self, symbol: str) -> None
    def list_all(self) -> list[FavoriteCoin]
    def is_favorite(self, symbol: str) -> bool
```

---

### 2. Adapters — Integraciones externas

**Archivo:** `src/adapters/api_client.py`

Esta es la **única** parte del código que sabe de HTTP. Si CoinGecko cambia su API, solo se modifica este archivo.

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

## Flujo de datos

### Escenario: "El usuario quiere el precio de Bitcoin"

```
┌─────────────┐
│   Usuario   │
│  "btc"      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  CLI / Streamlit                                            │
│  - Valida input (no vacío)                                  │
│  - Llama a service.get_price("btc")                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PriceService (core)                                        │
│  1. Normaliza "btc" → "btc"                                 │
│  2. Busca en SYMBOL_TO_ID → "bitcoin"                       │
│  3. Llama a client.get_price(["bitcoin"], "usd")            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  CoinGeckoClient (adapter)                                  │
│  1. Chequea TTL cache → ¿ya tenemos este request?           │
│  2. Rate limiter → ¿podemos hacer la llamada?               │
│  3. HTTP GET /simple/price                                  │
│  4. Parsea JSON, valida, cachea, devuelve dict              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PriceService (core, de vuelta)                             │
│  1. Convierte dict → PriceData                              │
│  2. Arma CoinSearchResult(coin, price_data)                 │
│  3. Lo devuelve al CLI/Streamlit                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  CLI / Streamlit                                            │
│  - Formatea precio, cambio, market cap                      │
│  - Muestra al usuario con colores/gráficos                  │
└─────────────────────────────────────────────────────────────┘
```

**Nota clave:** El `core` nunca ve un `requests.Response`. Solo ve dicts de Python. El `adapter` es el único que habla HTTP.

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

---

## Testing

**Filosofía:** testear cada capa en aislamiento, con mocks para las dependencias.

| Suite | Archivo | Casos | Qué testea |
|-------|---------|-------|------------|
| Models | `test_models.py` | 23 | Creación, igualdad, formateo, timestamps |
| Price Service | `test_price_service.py` | 30 | Lógica de negocio, resolución de símbolos, validaciones |
| API Client | `test_api_client.py` | 18 | HTTP mocks, rate limit, errores 429/404/500, cache |
| CLI | `test_cli.py` | 17 | Click CliRunner, argumentos, opciones, errores |
| Favorites | `test_favorites.py` | 16 | CRUD JSON, persistencia, corrupción de archivo |

**Total: ~104 tests.**

### Ejemplo: test de integración aislada

```python
def test_get_price_by_symbol(service: PriceService, mock_client: MagicMock):
    mock_client.get_price.return_value = {"bitcoin": {"usd": 45000}}
    result = service.get_price("btc")
    assert result.coin.symbol == "btc"
    assert result.price_data.price == 45000
```

El `mock_client` cumple el `CoinGeckoClientProtocol` por duck typing. No necesitamos herencia ni librerías de mocking complejas.

---

## Dual UI: CLI + Streamlit

Una decisión de diseño interesante de este proyecto es que **la misma lógica de negocio alimenta dos interfaces completamente diferentes**:

```
                         ┌─────────────────┐
                         │   PriceService   │
                         │   (core)         │
                         └────────┬────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
              ▼                                       ▼
    ┌─────────────────┐                     ┌─────────────────┐
    │   CLI (Click)   │                     │  Streamlit App  │
    │   commands.py   │                     │   app.py        │
    │                 │                     │                 │
    │  • Terminal     │                     │  • Web browser  │
    │  • Texto plano  │                     │  • Plotly charts│
    │  • Color cód.   │                     │  • CSV export   │
    └─────────────────┘                     └─────────────────┘
```

Ambas UIs:
- Usan el mismo `PriceService` inyectado con el mismo `CoinGeckoClient`.
- Manejan las mismas excepciones del dominio.
- Comparten el `FavoritesManager` para persistencia.

Esto demuestra el poder de la arquitectura limpia: **la interfaz es un detalle de implementación**, reemplazable sin tocar el negocio.

---

## Diagrama de dependencias

```
                    ┌─────────────┐
                    │   Config    │
                    │  settings   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │    CLI     │  │ Streamlit  │  │   Tests    │
    │  commands  │  │   app.py   │  │   mocks    │
    └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
          │               │               │
          └───────────────┼───────────────┘
                          │
                          ▼
                   ┌────────────┐
                   │    Core    │
                   │  service   │
                   │  models    │
                   │ favorites  │
                   └─────┬──────┘
                         │
                         ▼
                   ┌────────────┐
                   │  Adapters  │
                   │ api_client │
                   │  (HTTP)    │
                   └─────┬──────┘
                         │
                         ▼
                   ┌────────────┐
                   │  External  │
                   │ CoinGecko  │
                   └────────────┘
```

**Regla visual:** las flechas apuntan hacia abajo. Ninguna flecha apunta hacia arriba. El `core` no conoce al CLI, ni al Streamlit, ni a los tests.

---

*Documento vivo: si la arquitectura cambia, este archivo se actualiza.*
