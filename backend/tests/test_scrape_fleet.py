"""Unit tests for the distributed scraping fleet — no DB or network required."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scrape_fleet import WorkerSlot, build_workers, pick_worker, run_filter_fleet

_PLATFORM = "idealista"


def _slot(proxy: str | None = None, cookies: dict | None = None) -> WorkerSlot:
    return WorkerSlot(
        user_id=uuid.uuid4(),
        platform=_PLATFORM,
        cookies=cookies or {"sid": "abc"},
        proxy=proxy,
    )


# ── WorkerSlot budget tracking ────────────────────────────────────────────────

def test_slot_starts_under_budget():
    slot = _slot()
    assert slot.is_under_budget(30)


def test_slot_records_requests():
    slot = _slot()
    for _ in range(5):
        slot.record_request()
    assert slot.request_count_last_hour == 5


def test_slot_over_budget():
    slot = _slot()
    for _ in range(10):
        slot.record_request()
    assert not slot.is_under_budget(10)
    assert slot.is_under_budget(11)


# ── pick_worker round-robin ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pick_worker_round_robin():
    """Each successive call picks the next worker in sequence."""
    # Clear global rotator state
    import app.services.scrape_fleet as fleet_mod
    fleet_mod._rotator_index.clear()

    workers = [_slot() for _ in range(3)]
    picked = []
    for _ in range(3):
        w = await pick_worker(workers, "test-source-rr")
        picked.append(w)
    assert picked[0] is workers[0]
    assert picked[1] is workers[1]
    assert picked[2] is workers[2]


@pytest.mark.asyncio
async def test_pick_worker_skips_over_budget():
    """Budget-exceeded worker is skipped; next available worker is picked."""
    import app.services.scrape_fleet as fleet_mod
    fleet_mod._rotator_index.clear()

    over = _slot()
    for _ in range(30):
        over.record_request()

    fresh = _slot()
    workers = [over, fresh]

    with patch("app.services.scrape_fleet.settings") as mock_cfg:
        mock_cfg.fleet_requests_per_account_per_hour = 30
        w = await pick_worker(workers, "test-source-skip")

    assert w is fresh


@pytest.mark.asyncio
async def test_pick_worker_all_over_budget_returns_none():
    import app.services.scrape_fleet as fleet_mod
    fleet_mod._rotator_index.clear()

    workers = [_slot() for _ in range(2)]
    for s in workers:
        for _ in range(30):
            s.record_request()

    with patch("app.services.scrape_fleet.settings") as mock_cfg:
        mock_cfg.fleet_requests_per_account_per_hour = 30
        result = await pick_worker(workers, "test-source-all-over")

    assert result is None


# ── build_workers ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_workers_assigns_proxies():
    """Proxies are assigned round-robin across workers."""
    mock_cred_1 = MagicMock()
    mock_cred_1.user_id = uuid.uuid4()
    mock_cred_1.cookies_enc = None

    mock_cred_2 = MagicMock()
    mock_cred_2.user_id = uuid.uuid4()
    mock_cred_2.cookies_enc = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_cred_1, mock_cred_2]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False
    mock_session_factory = MagicMock(return_value=mock_session_cm)

    with patch("app.services.scrape_fleet.settings") as mock_cfg:
        mock_cfg.proxies = ["proxy1:8080", "proxy2:8080"]
        workers = await build_workers(mock_session_factory, _PLATFORM)

    assert len(workers) == 2
    assert workers[0].proxy == "proxy1:8080"
    assert workers[1].proxy == "proxy2:8080"


@pytest.mark.asyncio
async def test_build_workers_empty_when_no_credentials():
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False
    mock_session_factory = MagicMock(return_value=mock_session_cm)

    with patch("app.services.scrape_fleet.settings") as mock_cfg:
        mock_cfg.proxies = []
        workers = await build_workers(mock_session_factory, _PLATFORM)

    assert workers == []


# ── run_filter_fleet ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_filter_fleet_calls_scraper():
    """Fleet runner fetches listings and upserts results."""
    from app.schemas.filter import FilterConfig
    from app.schemas.listing import RawListing

    dummy = RawListing(source=_PLATFORM, source_id="x1", url="https://example.com")

    mock_scraper = AsyncMock()
    mock_scraper.fetch_listings.return_value = [dummy]
    mock_scraper.content_hash = MagicMock(return_value="aa" * 32)
    mock_scraper.__aenter__.return_value = mock_scraper
    mock_scraper.__aexit__.return_value = False

    mock_listing = MagicMock()
    mock_listing.lat = 1.0
    mock_listing.lng = 2.0

    mock_session = AsyncMock()
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = False
    mock_session_factory = MagicMock(return_value=mock_session_cm)

    fc = FilterConfig(sources=[_PLATFORM])

    import app.services.scrape_fleet as fleet_mod
    fleet_mod._rotator_index.clear()

    with (
        patch("app.services.scrape_fleet.build_workers", new=AsyncMock(return_value=[_slot()])),
        patch("app.services.scrape_fleet.get_scraper", return_value=mock_scraper),
        patch("app.services.scrape_fleet.upsert_listing", new_callable=AsyncMock) as mock_upsert,
        patch("app.services.scrape_fleet.dispatch_new_listing", new_callable=AsyncMock),
        patch("app.services.scrape_fleet.geocode", new=AsyncMock(return_value=None)),
        patch("app.services.scrape_fleet.settings") as mock_cfg,
    ):
        mock_cfg.fleet_requests_per_account_per_hour = 30
        mock_cfg.fleet_jitter_seconds = 0
        mock_cfg.request_delay_seconds = 0
        mock_cfg.proxies = []
        mock_upsert.return_value = (mock_listing, True)
        await run_filter_fleet(mock_session_factory, "filter-1", fc)

    mock_scraper.fetch_listings.assert_awaited_once_with(fc)
    mock_upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_filter_fleet_anonymous_fallback():
    """When no accounts exist, fleet falls back to an anonymous slot."""
    from app.schemas.filter import FilterConfig

    mock_scraper = AsyncMock()
    mock_scraper.fetch_listings.return_value = []
    mock_scraper.__aenter__.return_value = mock_scraper
    mock_scraper.__aexit__.return_value = False

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = AsyncMock()
    mock_session_cm.__aexit__.return_value = False
    mock_session_factory = MagicMock(return_value=mock_session_cm)

    fc = FilterConfig(sources=[_PLATFORM])

    import app.services.scrape_fleet as fleet_mod
    fleet_mod._rotator_index.clear()

    with (
        patch("app.services.scrape_fleet.build_workers", new=AsyncMock(return_value=[])),
        patch("app.services.scrape_fleet.get_scraper", return_value=mock_scraper),
        patch("app.services.scrape_fleet.settings") as mock_cfg,
    ):
        mock_cfg.fleet_requests_per_account_per_hour = 30
        mock_cfg.fleet_jitter_seconds = 0
        mock_cfg.request_delay_seconds = 0
        mock_cfg.proxies = [None]
        # Should not raise even with no accounts
        await run_filter_fleet(mock_session_factory, "filter-anon", fc)

    mock_scraper.fetch_listings.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_filter_fleet_skips_over_budget():
    """When all workers are over-budget, no scraper call is made."""
    from app.schemas.filter import FilterConfig

    over_slot = _slot()
    for _ in range(30):
        over_slot.record_request()

    fc = FilterConfig(sources=[_PLATFORM])

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = AsyncMock()
    mock_session_cm.__aexit__.return_value = False
    mock_session_factory = MagicMock(return_value=mock_session_cm)

    import app.services.scrape_fleet as fleet_mod
    fleet_mod._rotator_index.clear()

    with (
        patch("app.services.scrape_fleet.build_workers", new=AsyncMock(return_value=[over_slot])),
        patch("app.services.scrape_fleet.get_scraper") as mock_get_scraper,
        patch("app.services.scrape_fleet.settings") as mock_cfg,
    ):
        mock_cfg.fleet_requests_per_account_per_hour = 30
        mock_cfg.fleet_jitter_seconds = 0
        mock_cfg.proxies = [None]
        await run_filter_fleet(mock_session_factory, "filter-over", fc)

    mock_get_scraper.assert_not_called()
