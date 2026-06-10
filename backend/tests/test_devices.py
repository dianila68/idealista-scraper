import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_register_device(client: AsyncClient):
    token = await register_and_login(client, "device_reg@example.com")
    resp = await client.post(
        "/api/v1/devices/register",
        json={"fcm_token": "TOKEN-ABCDEF", "platform": "android"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["fcm_token"] == "TOKEN-ABCDEF"
    assert body["platform"] == "android"


@pytest.mark.asyncio
async def test_register_device_idempotent(client: AsyncClient):
    """Registering the same token twice returns 201 both times without duplicating."""
    token = await register_and_login(client, "device_idem@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"fcm_token": "TOKEN-IDEMPOTENT", "platform": "android"}

    r1 = await client.post("/api/v1/devices/register", json=payload, headers=headers)
    r2 = await client.post("/api/v1/devices/register", json=payload, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_unregister_device(client: AsyncClient):
    token = await register_and_login(client, "device_del@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/devices/register",
        json={"fcm_token": "TOKEN-DEL", "platform": "android"},
        headers=headers,
    )
    resp = await client.delete("/api/v1/devices/TOKEN-DEL", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_unregister_not_found(client: AsyncClient):
    token = await register_and_login(client, "device_404@example.com")
    resp = await client.delete(
        "/api/v1/devices/nonexistent-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
