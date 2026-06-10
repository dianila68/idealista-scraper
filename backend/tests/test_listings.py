from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from tests.conftest import register_and_login


def _make_listing(**kwargs) -> Listing:
    defaults = dict(
        source="idealista",
        source_id="TEST-001",
        content_hash="abc123",
        url="https://idealista.it/1",
        title="Test apartment",
        price=1200.0,
        city="Milano",
        zone="Navigli",
        listing_type="rent",
        property_type="apartment",
        rooms=2,
        size_sqm=65.0,
        features=[],
        images=[],
        raw={},
        scraped_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return Listing(**defaults)


@pytest.mark.asyncio
async def test_listings_empty(client: AsyncClient):
    token = await register_and_login(client, "listings_empty@example.com")
    resp = await client.get("/api/v1/listings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_listings_returns_data(client: AsyncClient, db_session: AsyncSession):
    token = await register_and_login(client, "listings_data@example.com")

    listing = _make_listing(source_id="L-FEED-001", content_hash="hash001")
    db_session.add(listing)
    await db_session.commit()

    resp = await client.get("/api/v1/listings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    ids = [r["source_id"] for r in resp.json()["results"]]
    assert "L-FEED-001" in ids


@pytest.mark.asyncio
async def test_listings_filter_by_source(client: AsyncClient, db_session: AsyncSession):
    token = await register_and_login(client, "listings_src@example.com")

    db_session.add(_make_listing(source="idealista", source_id="SRC-ID-001", content_hash="h-id-001"))
    db_session.add(_make_listing(source="subito", source_id="SRC-SB-001", content_hash="h-sb-001"))
    await db_session.commit()

    resp = await client.get(
        "/api/v1/listings?source=idealista",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    sources = {r["source"] for r in resp.json()["results"]}
    assert "subito" not in sources


@pytest.mark.asyncio
async def test_listings_invalid_source(client: AsyncClient):
    token = await register_and_login(client, "listings_badsrc@example.com")
    resp = await client.get(
        "/api/v1/listings?source=unknown",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_listing_detail(client: AsyncClient, db_session: AsyncSession):
    token = await register_and_login(client, "listings_detail@example.com")

    listing = _make_listing(source_id="DETAIL-001", content_hash="h-detail-001", raw={"x": 1})
    db_session.add(listing)
    await db_session.commit()
    await db_session.refresh(listing)

    resp = await client.get(
        f"/api/v1/listings/{listing.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["raw"] == {"x": 1}


@pytest.mark.asyncio
async def test_listing_not_found(client: AsyncClient):
    import uuid
    token = await register_and_login(client, "listings_404@example.com")
    resp = await client.get(
        f"/api/v1/listings/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sources_endpoint(client: AsyncClient):
    token = await register_and_login(client, "listings_sources@example.com")
    resp = await client.get("/api/v1/listings/sources", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    sources = {s["source"] for s in resp.json()}
    assert sources == {"idealista", "immobiliare", "subito"}
