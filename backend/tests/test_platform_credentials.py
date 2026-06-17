"""Tests for credential encryption and the /credentials API endpoints."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.credential_crypto import decrypt, decrypt_cookies, encrypt, encrypt_cookies


# ── Crypto round-trips ────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    uid, platform = str(uuid.uuid4()), "subito"
    assert decrypt(encrypt("secret", uid, platform), uid, platform) == "secret"


def test_different_keys_per_platform():
    uid = str(uuid.uuid4())
    tok_a = encrypt("x", uid, "subito")
    tok_b = encrypt("x", uid, "idealista")
    assert tok_a != tok_b  # different derived keys produce different ciphertexts


def test_different_keys_per_user():
    uid_a, uid_b = str(uuid.uuid4()), str(uuid.uuid4())
    tok_a = encrypt("x", uid_a, "subito")
    tok_b = encrypt("x", uid_b, "subito")
    assert tok_a != tok_b


def test_decrypt_wrong_user_raises():
    uid_a, uid_b = str(uuid.uuid4()), str(uuid.uuid4())
    tok = encrypt("secret", uid_a, "subito")
    with pytest.raises(Exception):
        decrypt(tok, uid_b, "subito")


def test_cookies_roundtrip():
    uid, platform = str(uuid.uuid4()), "immobiliare"
    cookies = {"session": "abc123", "token": "xyz"}
    assert decrypt_cookies(encrypt_cookies(cookies, uid, platform), uid, platform) == cookies


# ── API endpoints ─────────────────────────────────────────────────────────────

@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_upsert_and_list_credentials(client: AsyncClient, auth_headers: dict):
    resp = await client.put(
        "/api/v1/credentials/subito",
        json={"username": "user@example.com", "password": "pass123"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "subito" in resp.json()["message"]

    resp = await client.get("/api/v1/credentials", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["platform"] == "subito" for i in items)
    # Must never expose raw credentials
    for item in items:
        assert "username" not in item
        assert "password" not in item


@pytest.mark.asyncio
async def test_update_credentials_resets_status(client: AsyncClient, auth_headers: dict):
    await client.put(
        "/api/v1/credentials/subito",
        json={"username": "a@b.com", "password": "old"},
        headers=auth_headers,
    )
    await client.put(
        "/api/v1/credentials/subito",
        json={"username": "a@b.com", "password": "new"},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/credentials", headers=auth_headers)
    row = next(i for i in resp.json() if i["platform"] == "subito")
    assert row["login_status"] == "pending"


@pytest.mark.asyncio
async def test_delete_credentials(client: AsyncClient, auth_headers: dict):
    await client.put(
        "/api/v1/credentials/immobiliare",
        json={"username": "x@y.com", "password": "pw"},
        headers=auth_headers,
    )
    resp = await client.delete("/api/v1/credentials/immobiliare", headers=auth_headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/credentials", headers=auth_headers)
    assert not any(i["platform"] == "immobiliare" for i in resp.json())


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(client: AsyncClient, auth_headers: dict):
    resp = await client.delete("/api/v1/credentials/idealista", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verify_stores_cookies_on_success(client: AsyncClient, auth_headers: dict):
    await client.put(
        "/api/v1/credentials/subito",
        json={"username": "u@s.com", "password": "pw"},
        headers=auth_headers,
    )
    fake_cookies = {"SUB_SESSION": "tok123"}
    with patch(
        "app.api.v1.credentials.platform_login",
        new=AsyncMock(return_value=fake_cookies),
    ):
        resp = await client.post("/api/v1/credentials/subito/verify", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["login_status"] == "ok"
    assert "1 cookies" in body["message"]

    # Status reflected in list
    resp = await client.get("/api/v1/credentials", headers=auth_headers)
    row = next(i for i in resp.json() if i["platform"] == "subito")
    assert row["login_status"] == "ok"


@pytest.mark.asyncio
async def test_verify_marks_failed_on_bad_credentials(client: AsyncClient, auth_headers: dict):
    await client.put(
        "/api/v1/credentials/subito",
        json={"username": "u@s.com", "password": "wrong"},
        headers=auth_headers,
    )
    with patch(
        "app.api.v1.credentials.platform_login",
        new=AsyncMock(side_effect=ValueError("Subito login failed: HTTP 401")),
    ):
        resp = await client.post("/api/v1/credentials/subito/verify", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["login_status"] == "failed"


@pytest.mark.asyncio
async def test_credentials_require_auth(client: AsyncClient):
    resp = await client.get("/api/v1/credentials")
    assert resp.status_code == 403
