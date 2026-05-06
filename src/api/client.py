"""
Cliente HTTP para consumir nuestra propia API desde Streamlit.

En vez de importar PriceService y CoinGeckoClient directo, Streamlit
le pega a FastAPI que corre aparte. Esto da:
  - Cache compartido entre sesiones
  - Rerenders más livianos (no carga todo el dominio)
  - La API sirve para cualquier frontend (React, mobile, etc.)
"""

from __future__ import annotations

import os
from typing import Any

import requests

from src.core.exceptions import APIError, CoinNotFoundError, NetworkError, RateLimitError

# La URL base se configura vía variable de entorno.
# En local: http://127.0.0.1:8000
# En Docker: http://api:8000 (el nombre del servicio en docker-compose)
_API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _handle_response(response: requests.Response) -> Any:
    """Traduce errores HTTP de la API a nuestras excepciones del dominio."""
    if response.ok:
        return response.json() if response.content else None

    detail = _safe_detail(response)

    if response.status_code == 404:
        raise CoinNotFoundError(detail)
    if response.status_code == 429:
        raise RateLimitError(retry_after=5)
    if response.status_code == 502:
        raise APIError(detail, status_code=502)
    if response.status_code == 422:
        from src.core.exceptions import ValidationError
        raise ValidationError("api", "", detail)

    raise APIError(detail, status_code=response.status_code)


def _safe_detail(response: requests.Response) -> str:
    """Saca el detail del JSON de error, o manda el status."""
    try:
        body = response.json()
        return body.get("detail", str(response.status_code))
    except Exception:
        return str(response.status_code)


# ---------------------------------------------------------------------------
# Precios
# ---------------------------------------------------------------------------


def get_price(query: str, currency: str = "usd") -> dict[str, Any]:
    """Precio de una moneda."""
    try:
        resp = requests.get(f"{_API_BASE}/api/price/{query}", params={"currency": currency})
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    except requests.Timeout:
        raise NetworkError()
    return _handle_response(resp)


def get_prices(queries: list[str], currency: str = "usd") -> list[dict[str, Any]]:
    """Precios de varias monedas."""
    q = ",".join(queries)
    try:
        resp = requests.get(f"{_API_BASE}/api/prices", params={"q": q, "currency": currency})
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    except requests.Timeout:
        raise NetworkError()
    return _handle_response(resp)


def get_top(limit: int = 10, currency: str = "usd") -> list[dict[str, Any]]:
    """Top N monedas por market cap."""
    try:
        resp = requests.get(f"{_API_BASE}/api/top", params={"limit": limit, "currency": currency})
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    return _handle_response(resp)


def get_history(query: str, days: int = 7, currency: str = "usd") -> list[dict[str, float]]:
    """Precio histórico."""
    try:
        resp = requests.get(
            f"{_API_BASE}/api/history/{query}",
            params={"days": days, "currency": currency},
        )
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    return _handle_response(resp)


# ---------------------------------------------------------------------------
# Búsqueda
# ---------------------------------------------------------------------------


def search(query: str) -> list[dict[str, Any]]:
    """Buscar monedas por nombre o símbolo."""
    try:
        resp = requests.get(f"{_API_BASE}/api/search/{query}")
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    return _handle_response(resp)


# ---------------------------------------------------------------------------
# Favoritos
# ---------------------------------------------------------------------------


def list_favorites() -> list[dict[str, Any]]:
    """Listar favoritos."""
    try:
        resp = requests.get(f"{_API_BASE}/api/favorites")
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    return _handle_response(resp)


def add_favorite(symbol: str) -> dict[str, Any]:
    """Agregar favorito."""
    try:
        resp = requests.post(f"{_API_BASE}/api/favorites/{symbol}")
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    return _handle_response(resp)


def remove_favorite(symbol: str) -> None:
    """Quitar favorito."""
    try:
        resp = requests.delete(f"{_API_BASE}/api/favorites/{symbol}")
    except (requests.ConnectionError, requests.Timeout):
        raise NetworkError()
    if not resp.ok:
        _handle_response(resp)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def health() -> dict[str, Any]:
    """Ver si la API está viva."""
    try:
        resp = requests.get(f"{_API_BASE}/api/health")
        resp.raise_for_status()
        return resp.json()
    except (requests.ConnectionError, requests.Timeout):
        return {"status": "down", "api_key_configured": False, "version": "?"}
