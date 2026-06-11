# 🪙 Crypto Tracker

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-488%20cases-green.svg)](./tests)
[![CI](https://github.com/LeandroBenjaminL/crypto-tracker/actions/workflows/test.yml/badge.svg)](https://github.com/LeandroBenjaminL/crypto-tracker/actions)
[![ETL](https://github.com/LeandroBenjaminL/crypto-tracker/actions/workflows/pipeline-etl.yml/badge.svg)](https://github.com/LeandroBenjaminL/crypto-tracker/actions)
[![Frontend](https://github.com/LeandroBenjaminL/crypto-tracker/actions/workflows/frontend.yml/badge.svg)](https://github.com/LeandroBenjaminL/crypto-tracker/actions)
[![Pages](https://img.shields.io/badge/frontend-github.io-blueviolet.svg)](https://leandrobenjaminl.github.io/crypto-tracker/)

Trackea precios de criptomonedas desde la terminal, Telegram, un dashboard web o una API REST. Con pipeline ETL que cachea datos en PostgreSQL para respuestas en milisegundos.

**Live demo (API):** [crypto-tracker-api-trwx.onrender.com/docs](https://crypto-tracker-api-trwx.onrender.com/docs)
**Frontend (Astro):** [leandrobenjaminl.github.io/crypto-tracker](https://leandrobenjaminl.github.io/crypto-tracker/)

---

## 📖 Sobre el proyecto

Proyecto de aprendizaje con **arquitectura limpia**, **pipeline de datos**, **frontend Astro** y **deploy en producción**. Trenzas múltiples interfaces (CLI, Telegram, API REST, frontend web, Streamlit) con la misma lógica de negocio.

### Lo que hace

```bash
crypto-tracker price btc          → $64,321 ▲ +2.34%
crypto-tracker pipeline           → 100 snapshots, 20 históricos actualizados
/price btc en Telegram            → 🤖 Bitcoin (BTC): $64,321 ▲ +2.34%
http://localhost:8000/api/health   → {"status": "ok", "price_source": "db"}
```

---

## ✨ Features

| Capa | Features |
|------|----------|
| **💻 CLI** | Precio de monedas, top por market cap, búsqueda, pipeline ETL, Telegram bot |
| **🤖 Telegram** | Bot con `/price`, `/top`, `/alert`, `/help` — autorización por lista blanca |
| **📊 Dashboard (Streamlit)** | Streamlit con gráficos interactivos, favoritos, CSV export, portfolio |
| **🌐 Frontend (Astro)** | SPA estática con GitHub Pages — precios, top, búsqueda, favoritos, count-up animations, stagger scroll-reveal, 404 |
| **🌐 API REST** | FastAPI con Swagger docs, health check, cache en PostgreSQL |
| **🗄️ Pipeline ETL** | Cada 30min extrae top 100 de CoinGecko, alertas de precio, histórico |
| **💼 Portfolio** | Tracking de holdings con P&L, cost basis, valor actual |
| **⚡ Cache inteligente** | API lee de PostgreSQL (10ms), fallback a CoinGecko si no hay datos |
| **🐳 Docker** | Una imagen, cuatro entrypoints: api, streamlit, pipeline, telegram |
| **🗃️ PostgreSQL** | Favoritos + snapshots + histórico + pipeline runs + alertas + portfolio |
| **🔁 CI/CD** | Ruff + mypy + pytest + Astro build en GitHub Actions, deploy a Render y Pages |

---

## 🚀 Getting Started

### Sin Docker (rápido)

```bash
git clone https://github.com/LeandroBenjaminL/crypto-tracker.git
cd crypto-tracker
pip install -e ".[dev]"

# CLI
crypto-tracker price btc

# Dashboard
streamlit run app.py

# Tests
pytest
```

### Con Docker

```bash
# Build y arrancar todo (API + DB + Streamlit)
docker compose up -d

# Solo la API
docker build -t crypto-tracker .
docker run -p 8000:8000 crypto-tracker

# El pipeline (ETL una vez)
docker run -e DATABASE_URL=... crypto-tracker pipeline

# Telegram bot
docker run -e TELEGRAM_BOT_TOKEN=... crypto-tracker telegram
```

### Con PostgreSQL (recomendado)

```bash
pip install -e ".[dev,postgres]"
export DATABASE_URL=postgresql://user:pass@localhost:5432/cryptotracker

# Las migraciones corren solas al arrancar
crypto-tracker pipeline   # <- corre migrations + ETL
```

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENTES                                      │
│  ┌────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  CLI   │  │  Telegram    │  │  API     │  │ Streamlit│  │  Astro  │ │
│  │ Click  │  │  Bot         │  │  REST    │  │ Dashboard│  │ Frontend│ │
│  └────┬───┘  └──────┬───────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │             │               │              │              │      │
├───────┴─────────────┴───────────────┴──────────────┴──────────────┴──────┤
│                                ┌──────────────┐                         │
│                                │   CORE       │ ← lógica de negocio     │
│                                │  price_      │   pura, sin imports     │
│                                │  service.py  │   externos              │
│                                │  pipeline.py │                         │
│                                └──────┬───────┘                         │
│                                       │                                  │
│                         ┌─────────────┼─────────────┐                    │
│                         ▼             ▼             ▼                    │
│  ┌──────────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐          │
│  │  CoinGeckoClient │ │PostgreSQL│ │ Favorites│ │ Telegram  │          │
│  │  (adapters)      │ │(adapters)│ │ (json)   │ │ Bot (own) │          │
│  └──────────────────┘ └──────────┘ └──────────┘ └───────────┘          │
├─────────────────────────────────────────────────────────────────────────┤
│                      PIPELINE ETL (cada 30min)                          │
│                                                                         │
│  CoinGecko ──Extrae──▶ Transforma ──Carga──▶ PostgreSQL                │
│     │                                       │                           │
│     └── Histórico (7d, 30d, 90d) cada 6h ───┘                           │
│     └── Alertas de precio ──▶ check_alerts() ──▶ triggered              │
│                                                                         │
│  La API lee de PostgreSQL. CoinGecko es SOLO el fallback.               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Flujo de datos

```
Request: GET /api/price/bitcoin

  1. ¿Hay snapshot en PostgreSQL? ──Sí──▶ Responde en 10ms 🚀
  2. No ──▶ ¿Hay DATABASE_URL? ──Sí──▶ Responde 404
  3. No ──▶ CoinGecko (fallback) ──▶ 1-3s
```

---

## 📡 API REST

La API corre en **Render** y en local con Docker:

| Endpoint | Descripción | Cache |
|----------|-------------|-------|
| `GET /api/health` | Health check con fuente de datos | — |
| `GET /api/price/{query}` | Precio de una moneda | DB |
| `GET /api/prices?q=btc,eth` | Precios de varias | DB |
| `GET /api/top?limit=10` | Top por market cap | DB |
| `GET /api/history/{query}?days=30` | Histórico para gráficos | DB |
| `GET /api/search/{query}` | Buscar monedas | CoinGecko |
| `POST /api/favorites/{symbol}` | Agregar favorito | DB |
| `GET /api/favorites` | Listar favoritos | DB |
| `DELETE /api/favorites/{symbol}` | Quitar favorito | DB |
| `GET /api/portfolio` | Listar holdings | DB |
| `POST /api/portfolio` | Crear holding | DB |
| `PUT /api/portfolio/{id}` | Actualizar holding | DB |
| `DELETE /api/portfolio/{id}` | Eliminar holding | DB |
| `GET /api/portfolio/summary` | Resumen P&L | DB |

**URLs:**
- Producción: `https://crypto-tracker-api-trwx.onrender.com`
- Docs: `https://crypto-tracker-api-trwx.onrender.com/docs`

---

## 🗄️ Pipeline ETL

El pipeline se ejecuta automáticamente:

| Frecuencia | Qué hace | Cómo |
|------------|----------|------|
| **Cada 30 min** | Snapshots de precios (top 100) | GitHub Actions (schedule + manual dispatch) |
| **Cada 6h** | Histórico (7d, 30d, 90d) para top 20 | Pipeline + CoinGecko |
| **Al arrancar** | Migraciones Alembic | `run_migrations()` |
| **Post-pipeline** | Check de alertas de precio | `check_alerts()` |

```bash
# Manualmente
crypto-tracker pipeline --top 100
```

---

## 🧪 Tests

```bash
# Todos
pytest

# Solo un archivo
pytest tests/test_portfolio_repository.py -v

# Tests de error/edge cases
pytest -v -k "error or edge or not_found or empty or unknown"

# Con coverage
pytest --cov=src --cov-report=term

# 488 tests — 17 test files
```

| Suite | Archivo | Tests | Qué cubre |
|-------|---------|-------|-----------|
| Models | `test_models.py` | 66 | Creación, igualdad, formateo, P&L, excepciones |
| Price Service | `test_price_service.py` | 23 | Lógica de negocio, resolución de símbolos |
| CoinGecko Client | `test_api_client.py` | 18 | HTTP mocks, rate limit, errores, cache |
| API Server | `test_api_server.py` | 61 | FastAPI TestClient, endpoints, errores |
| HTTP Client | `test_api_client_http.py` | 42 | Cliente HTTP mocks |
| CLI | `test_cli.py` | 17 | Click CliRunner, argumentos |
| CLI Commands | `test_commands.py` | 34 | Alertas, pipeline, formatos, errores CLI |
| Favorites (JSON) | `test_favorites.py` | 25 | CRUD JSON, persistencia, edge cases |
| DB Repository | `test_database.py` | 15 | SQLAlchemy FavoritesRepository |
| Portfolio | `test_portfolio_repository.py` | 37 | CRUD + P&L summary |
| Pipeline ETL | `test_pipeline.py` | 44 | Run, alertas, histórico, snapshots |
| Settings | `test_settings.py` | 20 | Config, env vars, defaults, errores |
| Telegram Bot | `test_bot.py` | 11 | Comandos, autorización, inicio |
| Exceptions | `test_exceptions.py` | 31 | Jerarquía de errores, mensajes |
| API Cache | `test_api_cache.py` | 10 | TTL, fetch, cache management |
| Formatters | `test_formatters.py` | 21 | fmtPrice, fmtChange, fmtCap, colores |
| Navigation | `test_navigation.py` | 8 | Páginas, sidebar, opciones |

### CI/CD

| Check | Qué verifica | Estado |
|-------|-------------|--------|
| Ruff | Formato e imports | ✅ |
| Mypy | Tipado estático (25 archivos) | ✅ |
| Pytest | Tests (3 versiones de Python) | ✅ (488 passed) |
| Astro Build | Build del frontend | ✅ |
| Frontend Tests | Placeholder npm test | ✅ |
| Pipeline ETL | Cron cada 30min | ✅ |
| GitHub Pages | Deploy automático | ✅ |

---

## 🐳 Docker

```bash
# Build
docker build -t crypto-tracker .

# API (default)
docker run -p 8000:8000 crypto-tracker

# Streamlit
docker run -e ENTRYPOINT=streamlit -p 8501:8501 crypto-tracker

# Telegram
docker run -e ENTRYPOINT=telegram -e TELEGRAM_BOT_TOKEN=... crypto-tracker

# Pipeline
docker run -e DATABASE_URL=... crypto-tracker pipeline

# Todo junto
docker compose up -d
```

### Render (producción)

La imagen Docker se deploya automáticamente a [Render](https://render.com) desde la rama `main`. Render asigna el puerto via `$PORT` y provee PostgreSQL.

---

## 🗺️ Roadmap

Ver [ROADMAP.md](ROADMAP.md) para el plan completo.

### Completado ✅

- CLI + Telegram + Streamlit + API REST
- Frontend Astro con GitHub Pages (count-up animations, scroll-reveal)
- Pipeline ETL con PostgreSQL + alertas de precio (cada 30min)
- Portfolio tracking con P&L
- Cache inteligente (DB first, CoinGecko fallback)
- Migraciones automáticas (Alembic, 5 migrations)
- Deploy a Render + GitHub Actions + GitHub Pages
- CI verde (ruff, mypy, 488 tests)

### Próximo 🔜

- Notificaciones de alertas (email/push)
- Autenticación básica en API
- Dashboard de métricas del pipeline

---

## 🧠 Conceptos que aprendés acá

| Concepto | Dónde está |
|----------|-----------|
| Clean Architecture | `src/core/` sin imports externos |
| Dependency Injection | `PriceService` recibe cliente por constructor |
| Protocol / Structural Typing | `CoinGeckoClientProtocol` |
| ETL Pipeline | `src/core/pipeline.py` |
| API REST | `src/api/server.py` con FastAPI |
| Migraciones DB | `migrations/` con Alembic (5 versiones) |
| Telegram Bot | `src/telegram/bot.py` con python-telegram-bot |
| Portfolio & P&L | `src/adapters/database.py` — PortfolioRepository |
| Price Alerts | `src/core/pipeline.py` — `check_alerts()` |
| Docker multi-entrypoint | `Dockerfile` con `case` + `$ENTRYPOINT` |
| Frontend SSG | `frontend/` con Astro 6 |
| CI/CD | `.github/workflows/` (3 workflows) |
| Deploy cloud | Render + GitHub Pages |

---

## 📄 Más docs

| Archivo | Qué cubre |
|---------|-----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Decisiones de arquitectura a fondo |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones |
| [ROADMAP.md](ROADMAP.md) | Plan de desarrollo |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Guía para contribuir |
| [frontend/README.md](frontend/README.md) | Documentación del frontend Astro |

---

## 📝 Licencia

MIT — usalo libremente para aprender y portafolio.
