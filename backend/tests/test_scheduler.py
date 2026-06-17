"""Unit tests for the scheduler service — no database or network required."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.filter import FilterConfig
from app.services.scheduler import (
    _interval_minutes,
    _run_scrape_for_filter,
    get_scheduler,
    start_scheduler,
    stop_scheduler,
)

_TEST_USER_ID = uuid.uuid4()

# ── _interval_minutes ─────────────────────────────────────────────────────────

def test_interval_default():
    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.scrape_interval_minutes = 30
        mock_settings.idealista_interval = None
        mock_settings.immobiliare_interval = None
        mock_settings.subito_interval = None
        assert _interval_minutes() == 30


def test_interval_per_source_idealista():
    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.idealista_interval = 60
        assert _interval_minutes("idealista") == 60


def test_interval_per_source_immobiliare():
    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.immobiliare_interval = 45
        assert _interval_minutes("immobiliare") == 45


def test_interval_per_source_subito():
    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.subito_interval = 20
        assert _interval_minutes("subito") == 20


def test_interval_fallback_when_none():
    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.scrape_interval_minutes = 15
        mock_settings.idealista_interval = None
        assert _interval_minutes("idealista") == 15


# ── _run_scrape_for_filter ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_scrape_calls_scraper():
    """Scraper is called once and upsert is called with results."""
    from app.schemas.listing import RawListing

    dummy_listing = RawListing(
        source="idealista",
        source_id="abc",
        url="https://example.com",
        price=1000.0,
        size_sqm=60.0,
    )
    mock_scraper = AsyncMock()
    mock_scraper.fetch_listings.return_value = [dummy_listing]
    mock_scraper.content_hash = MagicMock(return_value="deadbeef" * 8)
    mock_scraper.__aenter__.return_value = mock_scraper
    mock_scraper.__aexit__.return_value = False

    mock_session = AsyncMock()
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False
    mock_session_factory = MagicMock(return_value=mock_session_cm)

    fc = FilterConfig(sources=["idealista"])

    mock_listing = MagicMock()
    with (
        patch("app.services.scheduler.get_scraper", return_value=mock_scraper),
        patch("app.services.scheduler.upsert_listing", new_callable=AsyncMock) as mock_upsert,
        patch("app.services.scheduler.dispatch_new_listing", new_callable=AsyncMock),
        patch("app.services.scheduler._load_cookies", new=AsyncMock(return_value={})),
    ):
        mock_upsert.return_value = (mock_listing, True)
        await _run_scrape_for_filter(mock_session_factory, "filter-1", fc, _TEST_USER_ID)

    mock_scraper.fetch_listings.assert_awaited_once_with(fc)
    mock_upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_scrape_skips_unknown_source():
    """Unknown source (returned by available_sources) is skipped without raising."""
    fc = FilterConfig()  # no sources → uses available_sources()

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = AsyncMock()
    mock_session_cm.__aexit__.return_value = False
    mock_session_factory = MagicMock(return_value=mock_session_cm)

    with (
        patch("app.services.scheduler.available_sources", return_value=["__phantom__"]),
        patch("app.services.scheduler.get_scraper", side_effect=ValueError("No scraper")),
        patch("app.services.scheduler._load_cookies", new=AsyncMock(return_value={})),
    ):
        # Should not raise
        await _run_scrape_for_filter(mock_session_factory, "filter-1", fc, _TEST_USER_ID)


@pytest.mark.asyncio
async def test_run_scrape_handles_fetch_error():
    """Scraper fetch error is caught and does not propagate."""
    mock_scraper = AsyncMock()
    mock_scraper.fetch_listings.side_effect = RuntimeError("network error")
    mock_scraper.__aenter__.return_value = mock_scraper
    mock_scraper.__aexit__.return_value = False

    fc = FilterConfig(sources=["idealista"])
    mock_session_factory = MagicMock()

    with (
        patch("app.services.scheduler.get_scraper", return_value=mock_scraper),
        patch("app.services.scheduler._load_cookies", new=AsyncMock(return_value={})),
    ):
        # Should not raise
        await _run_scrape_for_filter(mock_session_factory, "filter-1", fc, _TEST_USER_ID)


@pytest.mark.asyncio
async def test_run_scrape_empty_results_skips_upsert():
    """No upsert call when scraper returns empty list."""
    mock_scraper = AsyncMock()
    mock_scraper.fetch_listings.return_value = []
    mock_scraper.__aenter__.return_value = mock_scraper
    mock_scraper.__aexit__.return_value = False

    fc = FilterConfig(sources=["idealista"])
    mock_session_factory = MagicMock()

    with (
        patch("app.services.scheduler.get_scraper", return_value=mock_scraper),
        patch("app.services.scheduler.upsert_listing", new_callable=AsyncMock) as mock_upsert,
        patch("app.services.scheduler._load_cookies", new=AsyncMock(return_value={})),
    ):
        await _run_scrape_for_filter(mock_session_factory, "filter-1", fc, _TEST_USER_ID)
        mock_upsert.assert_not_called()


# ── start / stop ──────────────────────────────────────────────────────────────

def test_start_stop_scheduler():
    mock_session_factory = MagicMock()

    with patch("app.services.scheduler.settings") as mock_settings:
        mock_settings.scrape_interval_minutes = 30
        mock_settings.idealista_interval = None
        mock_settings.immobiliare_interval = None
        mock_settings.subito_interval = None

        scheduler = start_scheduler(mock_session_factory)
        assert scheduler.running
        assert get_scheduler() is scheduler

        stop_scheduler()
        assert get_scheduler() is None


def test_stop_when_not_started():
    """stop_scheduler is a no-op when scheduler is None."""
    stop_scheduler()  # should not raise
