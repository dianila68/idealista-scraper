"""Distributed scraping fleet — account rotation with per-proxy isolation.

In fleet mode the scheduler distributes each filter across *all* connected
platform accounts rather than only the filter owner's account.  Each worker
slot holds an independent (account, proxy, browser-profile) triple so
requests arrive from different IPs and session fingerprints, making
per-IP and per-account rate-detection thresholds harder to trigger.

Architecture
------------
- BROWSER_PROFILES  — pool of realistic Accept-Language / viewport header
                       combinations; one profile is assigned per WorkerSlot.
- WorkerSlot        — one (account, proxy, profile) identity with a sliding-
                       window request counter for per-account rate enforcement.
- build_workers     — load all healthy credentials for a platform, pair them
                       with proxies and assign browser profiles round-robin.
- pick_worker       — round-robin selector that skips over-budget workers.
- run_filter_fleet  — top-level entry point called by the scheduler when
                       fleet_enabled=True; replaces _run_scrape_for_filter.
- scrape_source_for_all_filters — per-source entry point used by the
                       staggered per-source APScheduler jobs.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.credential import PlatformCredential
from app.schemas.filter import FilterConfig
from app.schemas.filter import FilterConfig as _FC  # noqa: F401 (re-export for scheduler)
from app.scrapers.base import available_sources, get_scraper
from app.services.credential_crypto import decrypt_cookies
from app.services.dedup import upsert_listing
from app.services.geocoder import geocode
from app.services.notifications import dispatch_new_listing

log = structlog.get_logger()

# Per-source round-robin counters.  Shared across all asyncio tasks in one
# process (single-worker FastAPI/uvicorn deployment).
_rotator_index: dict[str, int] = {}
_rotator_lock = asyncio.Lock()

# Browser profile pool — each profile is a set of HTTP headers that together
# simulate a distinct browser instance.  Profiles differ in Accept-Language
# (Italian region/dialect, plus varying secondary languages), Sec-CH-UA hints,
# and DNT preference.  They are assigned round-robin to WorkerSlots so that
# requests from different accounts also appear to come from different browser
# installations.
#
# All profiles stay Chrome-only (matching curl_cffi's "chrome124" TLS
# impersonation) — mixing browser families would create a UA/TLS contradiction
# that anti-bot vendors detect immediately.
BROWSER_PROFILES: list[dict[str, str]] = [
    {
        # Milan / Northern Italy, Chrome 124, Windows — primary profile
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "DNT": "1",
    },
    {
        # Rome / Central Italy, Chrome 123, macOS
        "Accept-Language": "it-IT,it;q=0.9,en-GB;q=0.8,en;q=0.6",
        "Sec-CH-UA": '"Chromium";v="123", "Google Chrome";v="123", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
    },
    {
        # Naples / Southern Italy, Chrome 124, Linux
        "Accept-Language": "it-IT,it;q=1.0,de;q=0.5",
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Linux"',
        "DNT": "0",
    },
    {
        # Turin / Northwest Italy, Chrome 122, Windows — slightly older build
        "Accept-Language": "it-IT,it;q=0.9,fr;q=0.6,en;q=0.4",
        "Sec-CH-UA": '"Chromium";v="122", "Google Chrome";v="122", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    {
        # Bologna / Emilia-Romagna, Chrome 124, Android (mobile)
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.7",
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?1",
        "Sec-CH-UA-Platform": '"Android"',
    },
]


@dataclass
class WorkerSlot:
    """One scraper identity: a platform account paired with a proxy and browser profile."""

    user_id: uuid.UUID
    platform: str
    cookies: dict[str, str]
    proxy: str | None
    # Browser fingerprint headers for this slot (Accept-Language, Sec-CH-UA, etc.)
    profile: dict[str, str] = field(default_factory=dict)

    # Sliding window: timestamps of requests made in the last hour.
    _request_times: deque[datetime] = field(default_factory=deque, repr=False)

    def _prune(self) -> None:
        now = datetime.now(UTC)
        while self._request_times and (now - self._request_times[0]).total_seconds() > 3600:
            self._request_times.popleft()

    def is_under_budget(self, budget: int) -> bool:
        self._prune()
        return len(self._request_times) < budget

    def record_request(self) -> None:
        self._request_times.append(datetime.now(UTC))

    @property
    def request_count_last_hour(self) -> int:
        self._prune()
        return len(self._request_times)


async def build_workers(
    session_factory: async_sessionmaker[AsyncSession],
    platform: str,
) -> list[WorkerSlot]:
    """Return WorkerSlots for every healthy account on *platform*.

    Proxies and browser profiles are both assigned in round-robin order so that
    each account appears to be a distinct browser installation at a distinct IP.
    If no proxies are configured all workers share the host's IP — fleet mode
    still provides account and fingerprint diversity even without a proxy pool.
    """
    proxy_pool: list[str | None] = settings.proxies or [None]  # type: ignore[list-item]

    async with session_factory() as session:
        result = await session.execute(
            select(PlatformCredential).where(
                PlatformCredential.platform == platform,
                PlatformCredential.login_status == "ok",
            )
        )
        rows = result.scalars().all()

    slots: list[WorkerSlot] = []
    for i, row in enumerate(rows):
        uid_str = str(row.user_id)
        try:
            cookies = decrypt_cookies(row.cookies_enc, uid_str, platform) if row.cookies_enc else {}
        except Exception as exc:
            log.warning("fleet.cookie_decrypt_failed", platform=platform, user_id=uid_str, exc=str(exc))
            cookies = {}
        proxy = proxy_pool[i % len(proxy_pool)]
        profile = BROWSER_PROFILES[i % len(BROWSER_PROFILES)]
        slots.append(
            WorkerSlot(
                user_id=row.user_id,
                platform=platform,
                cookies=cookies,
                proxy=proxy,
                profile=profile,
            )
        )

    log.info("fleet.workers_built", platform=platform, count=len(slots))
    return slots


async def pick_worker(workers: list[WorkerSlot], source: str) -> WorkerSlot | None:
    """Round-robin over *workers*, skipping those that exceeded their hourly budget.

    Returns None only when every worker is over-budget.
    """
    budget = settings.fleet_requests_per_account_per_hour
    n = len(workers)

    async with _rotator_lock:
        start = _rotator_index.get(source, 0)
        for offset in range(n):
            slot = workers[(start + offset) % n]
            if slot.is_under_budget(budget):
                _rotator_index[source] = (start + offset + 1) % n
                return slot

    log.warning("fleet.all_workers_over_budget", source=source, workers=n)
    return None


async def _run_worker(
    session_factory: async_sessionmaker[AsyncSession],
    filter_id: str,
    fc: FilterConfig,
    slot: WorkerSlot,
) -> int:
    """Scrape *fc* using *slot*'s identity and upsert results.  Returns new-listing count."""
    jitter = settings.fleet_jitter_seconds
    if jitter > 0:
        await asyncio.sleep(random.uniform(0, jitter))

    try:
        scraper = get_scraper(
            slot.platform,
            request_delay=settings.request_delay_seconds,
            proxies=[slot.proxy] if slot.proxy else None,
            cookies=slot.cookies or None,
            extra_headers=slot.profile or None,
        )
    except ValueError:
        log.warning("fleet.unknown_source", source=slot.platform)
        return 0

    slot.record_request()

    try:
        async with scraper:
            raw_listings = await scraper.fetch_listings(fc)
    except Exception as exc:
        log.error(
            "fleet.scrape_error",
            source=slot.platform,
            filter_id=filter_id,
            user_id=str(slot.user_id),
            exc=str(exc),
        )
        return 0

    if not raw_listings:
        return 0

    new_count = 0
    for raw in raw_listings:
        content_hash = scraper.content_hash(raw)
        async with session_factory() as session:
            listing_row, is_new = await upsert_listing(session, raw, content_hash)
            if listing_row.lat is None:
                coords = await geocode(listing_row.city, listing_row.zone)
                if coords is not None:
                    listing_row.lat, listing_row.lng = coords
                    await session.flush()
            if is_new:
                new_count += 1
                await dispatch_new_listing(session, listing_row)

    log.info(
        "fleet.worker_done",
        source=slot.platform,
        filter_id=filter_id,
        user_id=str(slot.user_id),
        proxy=slot.proxy,
        new=new_count,
    )
    return new_count


async def run_filter_fleet(
    session_factory: async_sessionmaker[AsyncSession],
    filter_id: str,
    fc: FilterConfig,
) -> None:
    """Fleet-aware entry point: distribute *fc* across all connected accounts.

    For each source:
    - Load all healthy accounts → WorkerSlots.
    - If no accounts exist, fall back to anonymous scraping via a single slot
      with empty cookies (best-effort).
    - Pick one worker per source in round-robin order (rate-budget enforced).
    - Run the chosen worker; other workers are saved for later filters/cycles.

    The round-robin ensures that each successive filter cycle uses a different
    account, spreading the request load across the entire fleet over time.
    """
    sources = fc.sources if fc.sources else available_sources()

    for source in sources:
        workers = await build_workers(session_factory, source)

        if not workers:
            # No connected accounts — create a single anonymous slot
            proxy_pool: list[str | None] = settings.proxies or [None]  # type: ignore[list-item]
            workers = [
                WorkerSlot(
                    user_id=uuid.uuid4(),  # ephemeral, not persisted
                    platform=source,
                    cookies={},
                    proxy=proxy_pool[0],
                    profile=BROWSER_PROFILES[0],
                )
            ]
            log.info("fleet.anonymous_fallback", source=source, filter_id=filter_id)

        slot = await pick_worker(workers, source)
        if slot is None:
            log.warning("fleet.skipped_all_over_budget", source=source, filter_id=filter_id)
            continue

        await _run_worker(session_factory, filter_id, fc, slot)


async def scrape_source_for_all_filters(
    session_factory: async_sessionmaker[AsyncSession],
    source: str,
) -> None:
    """Per-source job target: load all filters and run fleet scraping for *source* only.

    This is the function registered as a separate APScheduler job per source when
    fleet_enabled=True with a non-zero fleet_source_offset_minutes.  Running one
    job per source (with staggered start times) means idealista, immobiliare, and
    subito fire at different clock offsets throughout the hour instead of all
    bursting simultaneously — traffic looks far more organic to rate-detection
    systems that analyse request patterns at the platform level.
    """
    from sqlalchemy import select as _select

    from app.models.filter import Filter
    from app.schemas.filter import FilterConfig

    async with session_factory() as session:
        result = await session.execute(_select(Filter))
        filters = result.scalars().all()

    if not filters:
        log.debug("fleet.no_filters", source=source)
        return

    tasks = []
    for row in filters:
        fc = FilterConfig.model_validate(row.config)
        # Only scrape sources this filter actually cares about
        if fc.sources and source not in fc.sources:
            continue
        # Create a scoped FilterConfig that targets exactly this source
        scoped_fc = fc.model_copy(update={"sources": [source]})
        tasks.append(run_filter_fleet(session_factory, str(row.id), scoped_fc))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("fleet.source_cycle_done", source=source, filters=len(tasks))
