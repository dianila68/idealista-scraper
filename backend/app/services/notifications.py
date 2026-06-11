from __future__ import annotations

import structlog
from firebase_admin import messaging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.filter import Filter
from app.models.listing import Listing
from app.schemas.filter import FilterConfig
from app.services.filter_eval import matching_filter_ids

log = structlog.get_logger()

_fcm_app: object | None = None


def _get_fcm_app() -> object:
    """Lazily initialise Firebase Admin SDK. Returns the app object."""
    global _fcm_app  # noqa: PLW0603
    if _fcm_app is not None:
        return _fcm_app

    import os

    import firebase_admin
    from firebase_admin import credentials

    cred_path = os.getenv("FIREBASE_CREDENTIALS", "")
    if cred_path and os.path.isfile(cred_path):
        cred = credentials.Certificate(cred_path)
        _fcm_app = firebase_admin.initialize_app(cred)
    else:
        # Fallback: use Application Default Credentials (useful in GCP/Cloud Run)
        _fcm_app = firebase_admin.initialize_app()

    return _fcm_app


def _send_fcm(token: str, title: str, body: str, data: dict[str, str] | None = None) -> bool:
    """Send a single FCM push notification. Returns True on success."""
    try:
        _get_fcm_app()
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            android=messaging.AndroidConfig(priority="high"),
        )
        messaging.send(message)
        return True
    except Exception as exc:
        log.warning("fcm.send_failed", token=token[:12] + "...", exc=str(exc))
        return False


async def dispatch_new_listing(db: AsyncSession, listing: Listing) -> int:
    """
    Evaluate *listing* against all active filters and push FCM notifications
    to the devices of matching users. Returns the number of notifications sent.
    """
    # Load all filters
    result = await db.execute(select(Filter))
    all_filters = result.scalars().all()
    if not all_filters:
        return 0

    filter_pairs = [
        (str(row.id), FilterConfig.model_validate(row.config))
        for row in all_filters
        if row.notify
    ]
    if not filter_pairs:
        return 0

    # Build a RawListing-compatible object from the ORM Listing for filter_eval
    from app.schemas.listing import RawListing

    raw = RawListing(
        source=listing.source,
        source_id=listing.source_id,
        url=listing.url,
        title=listing.title or "",
        price=listing.price,
        currency=listing.currency or "EUR",
        listing_type=listing.listing_type,
        property_type=listing.property_type,
        city=listing.city,
        zone=listing.zone,
        size_sqm=listing.size_sqm,
        rooms=listing.rooms,
        bathrooms=listing.bathrooms,
        floor=listing.floor,
        features=listing.features or [],
        images=listing.images or [],
        raw=listing.raw or {},
    )

    matched_ids = matching_filter_ids(raw, filter_pairs)
    if not matched_ids:
        return 0

    # Collect user IDs for matched filters
    matched_user_ids = {
        row.user_id
        for row in all_filters
        if str(row.id) in matched_ids
    }

    # Fetch FCM tokens for those users
    device_result = await db.execute(
        select(Device).where(Device.user_id.in_(matched_user_ids))
    )
    devices = device_result.scalars().all()
    if not devices:
        return 0

    sent = 0
    notif_title = "Nuovo annuncio trovato"
    price_str = f"{int(listing.price):,} €" if listing.price else ""
    notif_body = listing.title or "Clicca per vedere l'annuncio"
    if price_str:
        notif_body = f"{price_str} — {notif_body}"

    for device in devices:
        ok = _send_fcm(
            token=device.fcm_token,
            title=notif_title,
            body=notif_body,
            data={
                "listing_id": str(listing.id),
                "listing_url": listing.url or "",
            },
        )
        if ok:
            sent += 1

    log.info(
        "notifications.dispatched",
        listing_id=str(listing.id),
        matched_filters=len(matched_ids),
        devices=len(devices),
        sent=sent,
    )
    return sent


async def dispatch_batch(db: AsyncSession, listings: list[Listing]) -> int:
    """Dispatch notifications for a batch of new listings. Returns total sent."""
    total = 0
    for listing in listings:
        total += await dispatch_new_listing(db, listing)
    return total
