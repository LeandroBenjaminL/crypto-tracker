# Testing Skill — Crypto Tracker

## 🔴 REGLA DE ORO — PRE-PUSH

**NUNCA pushear sin verificar que los tests pasan y ruff + mypy están limpios.**

Antes de `git push`, ejecutar:

```bash
ruff check src/ app.py tests/
mypy src/ app.py
pytest -v --tb=short
```

Si algo falla, arreglarlo ANTES de pushear.
Un push con CI rojo = fix prioritario inmediato. No hay excepciones.

---

## Filosofía

> Los tests son la **malla de seguridad** que detecta regresiones y valida
> que la lógica de negocio (precios, cálculos de P&L, pipeline ETL) funciona
> correctamente antes de llegar a producción.

Principios operativos:

1. **Testeá los errores primero.** El camino feliz es fácil; los edge cases
   (moneda no encontrada, rate limit, DB caída, snapshot vacío) rompen en prod.

2. **Mocks en capas.** El `PriceService` se mockea en tests de API/CLI. El
   `CoinGeckoClient` se mockea en tests de `PriceService`. La DB se prueba
   con SQLite in-memory. Nunca mockear dos capas en el mismo test.

3. **Tests de integración real > unitarios con mocks pesados.** Los tests de
   API con `TestClient` de FastAPI prueban el ruteo real. Los tests de DB
   con SQLite in-memory prueban queries reales.

4. **Coverage no es el objetivo.** 256 tests con asserts débiles valen menos
   que 50 tests con asserts concretos. Un test de `test_get_price_unknown_coin`
   protege más que 10 tests de camino feliz.

---

## Tipos de tests en crypto-tracker

### Unitarios (test_price_service.py, test_models.py)
Testean lógica de negocio pura con el API client mockeado.
- **Qué probar**: resolución de símbolos, formateo de precios, validaciones
- **Fixture**: `mock_client` (MagicMock), `service` (PriceService inyectado)
- **Regla**: cada método público debe tener al menos un test de éxito + un test de error

### Integración (test_api_server.py, test_api_client_http.py)
Testean la API HTTP con `TestClient` de FastAPI.
- **Qué probar**: todos los endpoints (éxito y error), mapeo de errores del dominio a HTTP
- **Fixture**: `client` (TestClient), `app` con servicios mockeados
- **Regla**: cubrir al menos un caso de error por endpoint (404, 422, 429, 502)

### DB (test_database.py)
Testean repositorios con SQLite in-memory.
- **Qué probar**: CRUD de favoritos, snapshots, histórico, portfolio, pipeline runs
- **Regla**: cada operación debe probarse con datos válidos Y con búsquedas que no existen

### CLI (test_cli.py)
Testean comandos con `CliRunner` de Click.
- **Qué probar**: output formateado, códigos de error, flags
- **Regla**: probar `--help`, `--version`, y al menos un comando exitoso + uno con error

---

## Edge case checklist para crypto

| Categoría | Casos |
|---|---|
| **Moneda inexistente** | Símbolo inválido, ID que no existe en CoinGecko |
| **Rate limit** | 429 sin Retry-After, 429 con Retry-After |
| **API caída** | 500, 502, 503, 504, timeout, conexión rechazada |
| **DB caída** | PostgreSQL no disponible, SQLite corrupto |
| **Datos vacíos** | Sin snapshots en DB, histórico vacío, sin favoritos |
| **Precios nulos** | Moneda listada sin precio, cambio nulo, market cap nulo |
| **Cálculos P&L** | Cantidad 0, precio de compra negativo, sin precio actual |
| **Pipeline** | Sin DB, sin datos de CoinGecko, error en medio del ETL |
| **SQLAlchemy** | IntegrityError, sesiones rotas, rollbacks |

---

## Comandos

```bash
# Todos los tests
pytest -v --tb=short

# Con coverage
pytest --cov=src --cov-report=term --cov-report=html

# Ruff + mypy + pytest (lo que corre en CI)
ruff check src/ app.py tests/ && mypy src/ app.py && pytest

# Solo un archivo
pytest tests/test_price_service.py -v

# Solo tests de error
pytest -v -k "error or edge or not_found or empty or unknown"
```

---

## Anti-patrones

```python
# ❌ MAL: mockear dos capas en el mismo test
mock_client.get_price.return_value = {}
service = PriceService(api_client=mock_client)
# El test ya no prueba nada real

# ✅ BIEN: mockear solo la capa inmediata
mock_client.get_price.return_value = {"bitcoin": {"usd": 45000}}
result = service.get_price("bitcoin")
assert result.price_data.price == 45000

# ❌ MAL: assert estructural sin validar valor
assert "price" in result

# ✅ BIEN: verificá el valor concreto
assert result.price_data.price == 45000.50

# ❌ MAL: solo camino feliz
def test_get_price(client):
    r = client.get("/api/price/bitcoin")
    assert r.status_code == 200

# ✅ BIEN: cubrí también el error
def test_get_price_not_found(client):
    r = client.get("/api/price/nonexistent")
    assert r.status_code == 404
```
