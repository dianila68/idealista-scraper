from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing
from app.schemas.listing import RawListing

log = structlog.get_logger()


async def upsert_listing(db: AsyncSession, raw: RawListing, content_hash: str) -> tuple[Listing, bool]:
    """Insert or update a listing. Returns (listing, is_new).

    - New listing: inserted and returned.
    - Changed listing (price/size drift): updated in-place.
    - Unchanged listing: skipped (no DB write).
    """
    result = await db.execute(
        select(Listing).where(
            Listing.source == raw.source,
            Listing.source_id == raw.source_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        listing = Listing(
            source=raw.source,
            source_id=raw.source_id,
            content_hash=content_hash,
            url=raw.url,
            title=raw.title,
            price=raw.price,
            currency=raw.currency,
            listing_type=raw.listing_type,
            property_type=raw.property_type,
            city=raw.city,
            zone=raw.zone,
            size_sqm=raw.size_sqm,
            rooms=raw.rooms,
            bathrooms=raw.bathrooms,
            floor=raw.floor,
            total_floors=raw.total_floors,
            features=raw.features,
            images=raw.images,
            raw=raw.raw,
            published_at=raw.published_at,
            scraped_at=datetime.now(UTC),
            contact_phone=raw.contact_phone,
            contact_email=raw.contact_email,
        )
        db.add(listing)
        await db.flush()
        log.debug("listing.new", source=raw.source, source_id=raw.source_id)
        return listing, True

    if existing.content_hash == content_hash:
        # Even on unchanged content, update contact info if newly available
        if raw.contact_phone and not existing.contact_phone:
            existing.contact_phone = raw.contact_phone
            await db.flush()
        if raw.contact_email and not existing.contact_email:
            existing.contact_email = raw.contact_email
            await db.flush()
        return existing, False

    # Listing changed — update mutable fields
    existing.content_hash = content_hash
    existing.price = raw.price
    existing.size_sqm = raw.size_sqm
    existing.title = raw.title
    existing.features = raw.features
    existing.images = raw.images
    existing.raw = raw.raw
    existing.scraped_at = datetime.now(UTC)
    if raw.contact_phone:
        existing.contact_phone = raw.contact_phone
    if raw.contact_email:
        existing.contact_email = raw.contact_email
    await db.flush()
    log.debug("listing.updated", source=raw.source, source_id=raw.source_id)
    return existing, False


async def bulk_upsert(
    db: AsyncSession, listings: list[tuple[RawListing, str]]
) -> tuple[int, int]:
    """Upsert a batch of (RawListing, content_hash) pairs.

    Returns (new_count, updated_count).
    """
    new_count = 0
    updated_count = 0
    for raw, h in listings:
        _, is_new = await upsert_listing(db, raw, h)
        if is_new:
            new_count += 1
        else:
            updated_count += 1
    await db.commit()
    return new_count, updated_count
