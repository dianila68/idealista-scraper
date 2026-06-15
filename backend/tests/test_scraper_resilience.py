"""Tests for BaseScraper._get retry logic, UA rotation, and jitter — no network."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing
from app.scrapers.base import _USER_AGENTS, BaseScraper


class _StubScraper(BaseScraper):
    source = "_resilience_stub_"

    async def fetch_listings(self, fc: FilterConfig) -> list[RawListing]:
        return []

    def map_filter(self, fc: FilterConfig) -> dict[str, str]:
        return {}


_DUMMY_REQUEST = httpx.Request("GET", "http://example.com")


def _make_response(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers=headers or {},
        content=b"",
        request=_DUMMY_REQUEST,
    )


def _mock_client(fake_get) -> AsyncMock:
    """Return an AsyncMock whose .get calls fake_get and .aclose is a no-op."""
    client = AsyncMock()
    client.get = AsyncMock(side_effect=fake_get)
    return client


# ── UA rotation ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_injects_user_agent():
    """_get must always add a User-Agent even when caller passes no headers."""
    captured: list[str] = []

    async def fake_get(url, **kwargs):
        captured.append(kwargs["headers"].get("User-Agent", ""))
        return _make_response(200)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(fake_get)
        with patch("asyncio.sleep", AsyncMock()):
            await scraper._get("http://example.com")

    assert captured[0] in _USER_AGENTS


@pytest.mark.asyncio
async def test_get_preserves_caller_headers():
    """Site-specific Accept/Accept-Language passed by adapters must be kept."""
    captured: list[dict] = []

    async def fake_get(url, **kwargs):
        captured.append(dict(kwargs["headers"]))
        return _make_response(200)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(fake_get)
        with patch("asyncio.sleep", AsyncMock()):
            await scraper._get("http://example.com", headers={"Accept": "text/html"})

    assert captured[0]["Accept"] == "text/html"
    assert "User-Agent" in captured[0]


@pytest.mark.asyncio
async def test_get_does_not_override_caller_ua():
    """If the caller already supplies a UA, _get must not replace it."""
    captured: list[dict] = []

    async def fake_get(url, **kwargs):
        captured.append(dict(kwargs["headers"]))
        return _make_response(200)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(fake_get)
        with patch("asyncio.sleep", AsyncMock()):
            await scraper._get("http://example.com", headers={"User-Agent": "MyBot/1.0"})

    assert captured[0]["User-Agent"] == "MyBot/1.0"


# ── 429 handling ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_retries_on_429():
    """429 must trigger a retry, not an immediate raise."""
    calls = 0

    async def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return _make_response(200 if calls >= 3 else 429)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(fake_get)
        with patch("asyncio.sleep", AsyncMock()):
            resp = await scraper._get("http://example.com")

    assert resp.status_code == 200
    assert calls == 3


@pytest.mark.asyncio
async def test_get_respects_retry_after_header():
    """When 429 includes Retry-After: N, the wait should be N seconds."""
    waited: list[float] = []
    calls = 0

    async def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _make_response(429, headers={"Retry-After": "45"})
        return _make_response(200)

    async def fake_sleep(secs: float) -> None:
        waited.append(secs)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(fake_get)
        with patch("asyncio.sleep", AsyncMock(side_effect=fake_sleep)):
            await scraper._get("http://example.com")

    assert any(s == 45 for s in waited)


@pytest.mark.asyncio
async def test_get_raises_after_max_429_retries():
    """Exhausting all retries on 429 must eventually raise HTTPStatusError."""
    async def always_429(url, **kwargs):
        return _make_response(429)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(always_429)
        with patch("asyncio.sleep", AsyncMock()), pytest.raises(httpx.HTTPStatusError):
            await scraper._get("http://example.com")


# ── 503 handling ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_retries_on_503():
    """503 must be retried with back-off."""
    calls = 0

    async def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return _make_response(200 if calls >= 2 else 503)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(fake_get)
        with patch("asyncio.sleep", AsyncMock()):
            resp = await scraper._get("http://example.com")

    assert resp.status_code == 200
    assert calls == 2


# ── 4xx raises immediately ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_raises_immediately_on_403():
    """403 Forbidden must not be retried — raise on first occurrence."""
    calls = 0

    async def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return _make_response(403)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(fake_get)
        with patch("asyncio.sleep", AsyncMock()), pytest.raises(httpx.HTTPStatusError):
            await scraper._get("http://example.com")

    assert calls == 1


# ── Transport error retry ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_retries_on_transport_error():
    """Network-level errors must be retried with exponential back-off."""
    calls = 0

    async def flaky(url, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.TransportError("connection reset")
        return _make_response(200)

    scraper = _StubScraper(request_delay=0)
    async with scraper:
        scraper._client = _mock_client(flaky)
        with patch("asyncio.sleep", AsyncMock()):
            resp = await scraper._get("http://example.com")

    assert resp.status_code == 200
    assert calls == 2
