# 🪙 Crypto Tracker

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-256%20cases-green.svg)](./tests)
[![CI](https://github.com/LeandroBenjaminL/crypto-tracker/actions/workflows/test.yml/badge.svg)](https://github.com/LeandroBenjaminL/crypto-tracker/actions)
[![Deploy](https://github.com/LeandroBenjaminL/crypto-tracker/actions/workflows/pipeline.yml/badge.svg)](https://github.com/LeandroBenjaminL/crypto-tracker/actions)

Trackea precios de criptomonedas desde la terminal, un dashboard web o una API REST. Con pipeline ETL que cachea datos en PostgreSQL para respuestas en milisegundos.

**Live demo:** [crypto-tracker-api-trwx.onrender.com/docs](https://crypto-tracker-api-trwx.onrender.com/docs)

---

## 📖 Sobre el proyecto

Proyecto de aprendizaje con **arquitectura limpia**, **pipeline de datos** y **deploy en producción**. Trenzas tres interfaces (CLI, Streamlit, API REST) con la misma lógica de negocio.

### Lo que hace

```
crypto-tracker price btc          → $64,321 ▲ +2.34%
crypto-tracker pipeline           → 100 snapshots, 20 históricos actualizados
http://localhost:8000/api/health   → {"status": "ok", "price_source": "db"}
```

---

## ✨ Features

| Capa | Features |
|------|----------|
| **💻 CLI** | Precio de monedas, top por market cap, búsqueda, pipeline ETL |
| **📊 Dashboard** | Streamlit con gráficos interactivos, favoritos, CSV export |
| **🌐 API REST** | FastAPI con Swagger docs, health check, cache en PostgreSQL |
| **🗄️ Pipeline ETL** | Cada 30min extrae top 100 de CoinGecko y carga en DB |
| **⚡ Cache inteligente** | API lee de PostgreSQL (10ms), fallback a CoinGecko si no hay datos |
| **🐳 Docker** | Una imagen, tres entrypoints: api, streamlit, pipeline |
| **🗃️ PostgreSQL** | Favoritos + snapshots de precios + histórico con migraciones Alembic |
| **🔁 CI/CD** | Ruff + mypy + pytest en GitHub Actions, deploy automático a Render |

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
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENTES                                 │
│  ┌────────┐  ┌──────────────┐  ┌──────────┐                      │
│  │  CLI   │  │  Streamlit   │  │  API     │  ← también es server │
│  └────┬───┘  └──────┬───────┘  └─────┬────┘                      │
│       │             │               │                            │
├───────┴─────────────┴───────────────┴────────────────────────────┤
│                      ┌──────────────┐                            │
│                      │  CORE        │  ← lógica de negocio pura  │
│                      │  price_      │    sin imports externos     │
│                      │  service.py  │                            │
│                      └──────┬───────┘                            │
│                             │                                     │
│               ┌─────────────┼─────────────┐                       │
│               ▼             ▼             ▼                       │
│  ┌──────────────────┐ ┌──────────┐ ┌──────────┐                  │
│  │  CoinGeckoClient │ │PostgreSQL│ │ Favorites│                  │
│  │  (adapters)      │ │(adapters)│ │ (json)   │                  │
│  └──────────────────┘ └──────────┘ └──────────┘                  │
├──────────────────────────────────────────────────────────────────┤
│                      PIPELINE ETL (cada 30min)                    │
│                                                                  │
│  CoinGecko ──Extrae──▶ Transforma ──Carga──▶ PostgreSQL          │
│     │                                       │                    │
│     └── Histórico (7d, 30d, 90d) cada 6h ───┘                    │
│                                                                  │
│  La API lee de PostgreSQL. CoinGecko es SOLO el fallback.        │
└──────────────────────────────────────────────────────────────────┘
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

**URLs:**
- Producción: `https://crypto-tracker-api-trwx.onrender.com`
- Docs: `https://crypto-tracker-api-trwx.onrender.com/docs`

---

## 🗄️ Pipeline ETL

El pipeline se ejecuta automáticamente:

| Frecuencia | Qué hace | Cómo |
|------------|----------|------|
| **Cada 30 min** | Snapshots de precios (top 100) | GitHub Actions |
| **Cada 6h** | Histórico (7d, 30d, 90d) para top 20 | Pipeline + CoinGecko |
| **Al arrancar** | Migraciones Alembic | `run_migrations()` |

```bash
# Manualmente
crypto-tracker pipeline --top 100
```

---

## 🧪 Tests

```bash
# Todos
pytest

# Con coverage
pytest --cov=src --cov-report=term

# 256 tests, 73% coverage
```

### CI/CD

| Check | Qué verifica | Estado |
|-------|-------------|--------|
| Ruff | Formato e imports | ✅ |
| Mypy | Tipado estático | ✅ |
| Pytest | Tests (3 versiones de Python) | ✅ |
| Pipeline ETL | Cron cada 30 min | ✅ |

---

## 🐳 Docker

```bash
# Build
docker build -t crypto-tracker .

# API (default)
docker run -p 8000:8000 crypto-tracker

# Streamlit
docker run -e ENTRYPOINT=streamlit -p 8501:8501 crypto-tracker

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

- CLI + Streamlit + API REST
- Pipeline ETL con PostgreSQL
- Cache inteligente (DB first, CoinGecko fallback)
- Migraciones automáticas (Alembic)
- Deploy a Render + GitHub Actions
- CI verde (ruff, mypy, 256 tests)

### Próximo 🔜

- Alertas de precios (notificaciones)
- Autenticación básica
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
| Migraciones DB | `migrations/` con Alembic |
| Docker multi-entrypoint | `Dockerfile` con `case` + `$ENTRYPOINT` |
| CI/CD | `.github/workflows/` |
| Deploy cloud | Render + GitHub Actions |

---

## 📄 Más docs

| Archivo | Qué cubre |
|---------|-----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Decisiones de arquitectura a fondo |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones |
| [ROADMAP.md](ROADMAP.md) | Plan de desarrollo |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Guía para contribuir |

---

## 📝 Licencia

MIT — usalo libremente para aprender y portafolio.
