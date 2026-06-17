from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.credential import PlatformCredential
from app.models.filter import Filter
from app.schemas.filter import FilterConfig
from app.scrapers.base import available_sources, get_scraper
from app.services.credential_crypto import decrypt_cookies
from app.services.dedup import upsert_listing
from app.services.geocoder import geocode
from app.services.notifications import dispatch_new_listing

log = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


async def _load_cookies(
    session: AsyncSession,
    user_id: uuid.UUID,
    platform: str,
) -> dict[str, str]:
    """Return the decrypted cookie jar for (user, platform), or {} if unavailable."""
    result = await session.execute(
        select(PlatformCredential).where(
            PlatformCredential.user_id == user_id,
            PlatformCredential.platform == platform,
            PlatformCredential.login_status == "ok",
        )
    )
    row = result.scalar_one_or_none()
    if row is None or row.cookies_enc is None:
        return {}
    # Treat cookies as expired if past their TTL
    if row.cookies_expire_at and row.cookies_expire_at < datetime.now(UTC):
        log.info("scheduler.cookies_expired", platform=platform, user_id=str(user_id))
        row.login_status = "expired"
        await session.commit()
        return {}
    try:
        return decrypt_cookies(row.cookies_enc, str(user_id), platform)
    except Exception as exc:
        log.warning("scheduler.cookies_decrypt_failed", platform=platform, exc=str(exc))
        return {}


async def _run_scrape_for_filter(
    session_factory: async_sessionmaker[AsyncSession],
    filter_id: str,
    fc: FilterConfig,
    user_id: uuid.UUID,
) -> None:
    """Fetch listings for one filter across all registered scrapers and upsert."""
    sources = fc.sources if fc.sources else available_sources()

    for source in sources:
        # Load user's authenticated cookies for this platform (empty dict = anonymous)
        async with session_factory() as cred_session:
            cookies = await _load_cookies(cred_session, user_id, source)

        try:
            scraper = get_scraper(
                source,
                request_delay=settings.request_delay_seconds,
                proxies=settings.proxies or None,
                cookies=cookies or None,
            )
        except ValueError:
            log.warning("scheduler.unknown_source", source=source)
            continue

        if cookies:
            log.info("scheduler.authenticated_scrape", source=source, filter_id=filter_id)
        try:
            async with scraper:
                raw_listings = await scraper.fetch_listings(fc)
        except Exception as exc:
            log.error("scheduler.scrape_error", source=source, filter_id=filter_id, exc=str(exc))
            continue

        if not raw_listings:
            continue

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
            "scheduler.upserted",
            source=source,
            filter_id=filter_id,
            new=new_count,
        )


async def _scrape_all_filters(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Load all active filters from DB and scrape each one."""
    async with session_factory() as session:
        result = await session.execute(select(Filter))
        filters = result.scalars().all()

    if not filters:
        log.debug("scheduler.no_filters")
        return

    tasks = []
    for row in filters:
        fc = FilterConfig.model_validate(row.config)
        tasks.append(_run_scrape_for_filter(session_factory, str(row.id), fc, row.user_id))

    await asyncio.gather(*tasks, return_exceptions=True)


def _interval_minutes(source: str | None = None) -> int:
    """Per-source interval with fallback to global setting."""
    if source == "idealista" and settings.idealista_interval is not None:
        return settings.idealista_interval
    if source == "immobiliare" and settings.immobiliare_interval is not None:
        return settings.immobiliare_interval
    if source == "subito" and settings.subito_interval is not None:
        return settings.subito_interval
    return settings.scrape_interval_minutes


def start_scheduler(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIOScheduler:
    """Create, configure, and start the APScheduler instance."""
    global _scheduler  # noqa: PLW0603

    scheduler = AsyncIOScheduler()

    interval = _interval_minutes()
    scheduler.add_job(
        _scrape_all_filters,
        trigger=IntervalTrigger(minutes=interval),
        args=[session_factory],
        id="scrape_all_filters",
        replace_existing=True,
        misfire_grace_time=60,
    )

    scheduler.start()
    _scheduler = scheduler
    log.info("scheduler.started", interval_minutes=interval)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler  # noqa: PLW0603
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
    _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
