"""Unit tests for the geocoder service — Nominatim HTTP calls mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.geocoder import clear_cache, geocode


def _nominatim_response(lat: str = "45.464664", lon: str = "9.188540") -> list[dict]:
    return [{"lat": lat, "lon": lon, "display_name": "Milano, Lombardia, Italy"}]


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.mark.asyncio
async def test_geocode_returns_coords():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _nominatim_response("45.46", "9.19")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with (
        patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.geocoder.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await geocode("Milano", "Navigli")

    assert result == (45.46, 9.19)


@pytest.mark.asyncio
async def test_geocode_returns_none_on_empty():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = []

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with (
        patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.geocoder.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await geocode("CittàInesistente", "ZonaNulla")

    assert result is None


@pytest.mark.asyncio
async def test_geocode_cache_hit():
    """Second call with same city/zone should not make another HTTP request."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _nominatim_response("41.9", "12.5")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with (
        patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.geocoder.asyncio.sleep", new_callable=AsyncMock),
    ):
        r1 = await geocode("Roma", "Trastevere")
        r2 = await geocode("Roma", "Trastevere")

    assert r1 == r2 == (41.9, 12.5)
    # First call: 1 HTTP request (zone+city); second call: 0 (cached)
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_geocode_fallback_to_city():
    """Zone query returns empty; fallback city-only query succeeds."""
    empty_resp = MagicMock()
    empty_resp.raise_for_status = MagicMock()
    empty_resp.json.return_value = []

    city_resp = MagicMock()
    city_resp.raise_for_status = MagicMock()
    city_resp.json.return_value = _nominatim_response("40.85", "14.27")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[empty_resp, city_resp])

    with (
        patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.geocoder.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await geocode("Napoli", "ZonaXYZ")

    assert result == (40.85, 14.27)
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_geocode_no_city_returns_none():
    result = await geocode(None, "Navigli")
    assert result is None


@pytest.mark.asyncio
async def test_geocode_nominatim_error_returns_none():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("network error"))

    with (
        patch("app.services.geocoder.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.geocoder.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await geocode("Milano", "Navigli")

    assert result is None
