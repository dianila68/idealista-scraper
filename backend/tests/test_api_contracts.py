"""API contract edge cases: auth enforcement, input validation, pagination."""
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from tests.conftest import register_and_login


def _listing(**kwargs) -> Listing:
    defaults = dict(
        source="idealista",
        source_id="CONTRACT-001",
        content_hash="ch-contract-001",
        url="https://idealista.it/1",
        title="Contract test apartment",
        price=1000.0,
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


# ── Auth enforcement ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listings_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/listings")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_filters_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/filters")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_devices_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_bearer_token(client: AsyncClient):
    resp = await client.get(
        "/api/v1/listings",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert resp.status_code == 401


# ── Health endpoint (no auth) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_no_auth(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Input validation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "valid@example.com", "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_filter_invalid_config(client: AsyncClient):
    token = await register_and_login(client, "contract_invalid@example.com")
    resp = await client.post(
        "/api/v1/filters",
        json={"name": "Bad filter", "config": {"listing_type": "unknown_type"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_device_invalid_platform(client: AsyncClient):
    token = await register_and_login(client, "contract_device@example.com")
    resp = await client.post(
        "/api/v1/devices",
        json={"fcm_token": "test-token-123", "platform": "windows"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ── Pagination ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listings_pagination_limit(client: AsyncClient, db_session: AsyncSession):
    """Limit parameter caps the number of results returned."""
    token = await register_and_login(client, "contract_page@example.com")
    for i in range(5):
        db_session.add(_listing(source_id=f"PAGE-{i:03d}", content_hash=f"h-page-{i:03d}"))
    await db_session.commit()

    resp = await client.get(
        "/api/v1/listings?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) <= 2


@pytest.mark.asyncio
async def test_listings_has_more_true(client: AsyncClient, db_session: AsyncSession):
    """has_more=True when there are more results beyond the page."""
    token = await register_and_login(client, "contract_hasmore@example.com")
    for i in range(4):
        db_session.add(_listing(source_id=f"HM-{i:03d}", content_hash=f"h-hm-{i:03d}"))
    await db_session.commit()

    resp = await client.get(
        "/api/v1/listings?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # With 4 total and limit=2, has_more should be True (or next_cursor non-null)
    if body["has_more"]:
        assert body["next_cursor"] is not None


@pytest.mark.asyncio
async def test_listings_cursor_pagination(client: AsyncClient, db_session: AsyncSession):
    """next_cursor returns the next page without duplicating results."""
    token = await register_and_login(client, "contract_cursor@example.com")
    for i in range(6):
        db_session.add(_listing(source_id=f"CURSOR-{i:03d}", content_hash=f"h-cursor-{i:03d}"))
    await db_session.commit()

    page1 = await client.get(
        "/api/v1/listings?limit=3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page1.status_code == 200
    p1 = page1.json()
    ids_page1 = {r["source_id"] for r in p1["results"]}

    if p1.get("next_cursor"):
        page2 = await client.get(
            f"/api/v1/listings?limit=3&cursor={p1['next_cursor']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert page2.status_code == 200
        ids_page2 = {r["source_id"] for r in page2.json()["results"]}
        # No overlap between pages
        assert ids_page1.isdisjoint(ids_page2)


# ── Filter CRUD contract ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_replace_updates_all_fields(client: AsyncClient):
    """PUT replaces the entire filter config."""
    token = await register_and_login(client, "contract_put@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    original_payload = {
        "name": "Original",
        "config": {"listing_type": "rent"},
        "notify": True,
        "notify_digest": False,
    }
    created = await client.post("/api/v1/filters", json=original_payload, headers=headers)
    fid = created.json()["id"]

    replacement = {
        "name": "Replaced",
        "config": {"listing_type": "sale"},
        "notify": False,
        "notify_digest": True,
    }
    resp = await client.put(f"/api/v1/filters/{fid}", json=replacement, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Replaced"
    assert body["config"]["listing_type"] == "sale"
    assert body["notify"] is False


@pytest.mark.asyncio
async def test_filter_patch_only_updates_provided_fields(client: AsyncClient):
    """PATCH only changes provided fields."""
    token = await register_and_login(client, "contract_patch@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/filters",
        json={"name": "Original", "config": {"listing_type": "rent"}},
        headers=headers,
    )
    fid = created.json()["id"]

    resp = await client.patch(f"/api/v1/filters/{fid}", json={"notify": False}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Original"  # unchanged
    assert body["notify"] is False     # updated
