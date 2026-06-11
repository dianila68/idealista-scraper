"""Unit tests for the map API endpoint — DB fully mocked."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app
from app.models.listing import Listing


def _make_listing(lat: float | None = 45.46, lng: float | None = 9.19) -> MagicMock:
    row = MagicMock(spec=Listing)
    row.id = uuid.uuid4()
    row.title = "Appartamento Navigli"
    row.price = 1200.0
    row.city = "Milano"
    row.zone = "Navigli"
    row.lat = lat
    row.lng = lng
    row.url = "https://example.com/listing/1"
    return row


def _stub_db(rows: list):
    async def _override():
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        db.execute = AsyncMock(return_value=result)
        db.get = AsyncMock(return_value=None)
        yield db

    return _override


@pytest.mark.asyncio
async def test_map_no_listings():
    app.dependency_overrides[get_db] = _stub_db([])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/listings/map")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == {"listings": []}


@pytest.mark.asyncio
async def test_map_returns_geocoded_listings():
    listing = _make_listing(lat=45.46, lng=9.19)
    app.dependency_overrides[get_db] = _stub_db([listing])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/listings/map")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["listings"]) == 1
    point = data["listings"][0]
    assert point["lat"] == 45.46
    assert point["lng"] == 9.19
    assert point["city"] == "Milano"
    assert point["price"] == 1200.0
    assert point["url"] == "https://example.com/listing/1"


@pytest.mark.asyncio
async def test_map_filter_id_param():
    """filter_id query param is accepted; unknown filter returns empty list."""
    filter_id = str(uuid.uuid4())
    app.dependency_overrides[get_db] = _stub_db([])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/api/v1/listings/map?filter_id={filter_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    assert resp.json() == {"listings": []}


@pytest.mark.asyncio
async def test_map_route_returns_html():
    """GET /map returns an HTML page containing the Leaflet map div."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/map")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert b'id="map"' in resp.content
