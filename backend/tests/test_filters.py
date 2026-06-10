import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login

FILTER_PAYLOAD = {
    "name": "Milan 2BR",
    "config": {
        "listing_type": "rent",
        "property_type": ["apartment"],
        "locations": [{"city": "Milano", "zones": ["Navigli"]}],
        "price": {"min": None, "max": 1500},
        "size_sqm": {"min": 50, "max": None},
        "rooms": {"min": 2, "max": None},
        "bathrooms": {"min": None, "max": None},
        "floor": {"min": 1, "exclude_ground": True},
        "features": ["elevator"],
        "sources": ["idealista", "immobiliare"],
    },
    "notify": True,
    "notify_digest": False,
}


@pytest.mark.asyncio
async def test_create_filter(client: AsyncClient):
    token = await register_and_login(client, "filter_create@example.com")
    resp = await client.post(
        "/api/v1/filters", json=FILTER_PAYLOAD, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Milan 2BR"
    assert body["config"]["listing_type"] == "rent"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_filters(client: AsyncClient):
    token = await register_and_login(client, "filter_list@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/v1/filters", json=FILTER_PAYLOAD, headers=headers)
    resp = await client.get("/api/v1/filters", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_filter(client: AsyncClient):
    token = await register_and_login(client, "filter_get@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/filters", json=FILTER_PAYLOAD, headers=headers)
    filter_id = created.json()["id"]

    resp = await client.get(f"/api/v1/filters/{filter_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == filter_id


@pytest.mark.asyncio
async def test_update_filter(client: AsyncClient):
    token = await register_and_login(client, "filter_update@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/filters", json=FILTER_PAYLOAD, headers=headers)
    filter_id = created.json()["id"]

    patch = {"name": "Updated name"}
    resp = await client.patch(f"/api/v1/filters/{filter_id}", json=patch, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated name"


@pytest.mark.asyncio
async def test_delete_filter(client: AsyncClient):
    token = await register_and_login(client, "filter_delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/filters", json=FILTER_PAYLOAD, headers=headers)
    filter_id = created.json()["id"]

    resp = await client.delete(f"/api/v1/filters/{filter_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/filters/{filter_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_row_isolation(client: AsyncClient):
    """A user cannot access another user's filter."""
    token_a = await register_and_login(client, "filter_iso_a@example.com")
    token_b = await register_and_login(client, "filter_iso_b@example.com")

    created = await client.post(
        "/api/v1/filters",
        json=FILTER_PAYLOAD,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    filter_id = created.json()["id"]

    resp = await client.get(
        f"/api/v1/filters/{filter_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404
