"""Unit tests for notification dispatch — no Firebase, no database required."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notifications import _send_fcm, dispatch_new_listing


def _make_listing(**kwargs):
    """Build a minimal mock Listing ORM object."""
    listing = MagicMock()
    listing.id = uuid.uuid4()
    listing.source = kwargs.get("source", "idealista")
    listing.source_id = kwargs.get("source_id", "abc123")
    listing.url = kwargs.get("url", "https://example.com/1")
    listing.title = kwargs.get("title", "Appartamento in affitto")
    listing.price = kwargs.get("price", 1200.0)
    listing.currency = kwargs.get("currency", "EUR")
    listing.listing_type = kwargs.get("listing_type", "rent")
    listing.property_type = kwargs.get("property_type", "apartment")
    listing.city = kwargs.get("city", "Milano")
    listing.zone = kwargs.get("zone", "Navigli")
    listing.size_sqm = kwargs.get("size_sqm", 65.0)
    listing.rooms = kwargs.get("rooms", 2)
    listing.bathrooms = kwargs.get("bathrooms", 1)
    listing.floor = kwargs.get("floor", 2)
    listing.features = kwargs.get("features", ["ascensore"])
    listing.images = kwargs.get("images", [])
    listing.raw = kwargs.get("raw", {})
    return listing


def _make_filter_row(filter_id: str, config: dict, notify: bool = True):
    row = MagicMock()
    row.id = uuid.UUID(filter_id)
    row.config = config
    row.notify = notify
    row.user_id = uuid.uuid4()
    return row


def _make_device(user_id, token: str = "fake-fcm-token-123"):
    device = MagicMock()
    device.fcm_token = token
    device.user_id = user_id
    return device


# ── _send_fcm ─────────────────────────────────────────────────────────────────

def test_send_fcm_success():
    with (
        patch("app.services.notifications._get_fcm_app"),
        patch("app.services.notifications.messaging") as mock_messaging,
    ):
        mock_messaging.Message.return_value = MagicMock()
        mock_messaging.Notification.return_value = MagicMock()
        mock_messaging.AndroidConfig.return_value = MagicMock()
        mock_messaging.send.return_value = "projects/x/messages/1"
        result = _send_fcm("token", "Title", "Body")
    assert result is True


def test_send_fcm_failure_returns_false():
    with (
        patch("app.services.notifications._get_fcm_app"),
        patch("app.services.notifications.messaging") as mock_messaging,
    ):
        mock_messaging.Message.return_value = MagicMock()
        mock_messaging.Notification.return_value = MagicMock()
        mock_messaging.AndroidConfig.return_value = MagicMock()
        mock_messaging.send.side_effect = Exception("FCM error")
        result = _send_fcm("token", "Title", "Body")
    assert result is False


# ── dispatch_new_listing ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_sends_to_matching_filter():
    filter_id = "00000000-0000-0000-0000-000000000001"
    user_id = uuid.uuid4()
    filter_row = _make_filter_row(
        filter_id,
        {"price": {"min": 800, "max": 1500}},
        notify=True,
    )
    device = _make_device(user_id)
    filter_row.user_id = user_id

    db = AsyncMock()
    db.execute = AsyncMock()

    # First execute() returns filters, second returns devices
    filter_result = MagicMock()
    filter_result.scalars.return_value.all.return_value = [filter_row]
    device_result = MagicMock()
    device_result.scalars.return_value.all.return_value = [device]
    db.execute.side_effect = [filter_result, device_result]

    listing = _make_listing(price=1200.0)

    with patch("app.services.notifications._send_fcm", return_value=True) as mock_send:
        count = await dispatch_new_listing(db, listing)

    assert count == 1
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_no_filters_returns_zero():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    listing = _make_listing()
    count = await dispatch_new_listing(db, listing)
    assert count == 0


@pytest.mark.asyncio
async def test_dispatch_notify_false_skipped():
    filter_id = "00000000-0000-0000-0000-000000000002"
    filter_row = _make_filter_row(
        filter_id,
        {"price": {"min": 800, "max": 1500}},
        notify=False,
    )

    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [filter_row]
    db.execute = AsyncMock(return_value=result)

    listing = _make_listing()
    with patch("app.services.notifications._send_fcm") as mock_send:
        count = await dispatch_new_listing(db, listing)

    assert count == 0
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_no_devices_returns_zero():
    filter_id = "00000000-0000-0000-0000-000000000003"
    user_id = uuid.uuid4()
    filter_row = _make_filter_row(filter_id, {}, notify=True)
    filter_row.user_id = user_id

    db = AsyncMock()
    filter_result = MagicMock()
    filter_result.scalars.return_value.all.return_value = [filter_row]
    device_result = MagicMock()
    device_result.scalars.return_value.all.return_value = []
    db.execute.side_effect = [filter_result, device_result]

    listing = _make_listing()
    count = await dispatch_new_listing(db, listing)
    assert count == 0


@pytest.mark.asyncio
async def test_dispatch_price_above_max_not_matched():
    """Listing price exceeds filter max → no notification."""
    filter_id = "00000000-0000-0000-0000-000000000004"
    user_id = uuid.uuid4()
    filter_row = _make_filter_row(
        filter_id,
        {"price": {"max": 1000}},
        notify=True,
    )
    filter_row.user_id = user_id

    db = AsyncMock()
    filter_result = MagicMock()
    filter_result.scalars.return_value.all.return_value = [filter_row]
    db.execute = AsyncMock(return_value=filter_result)

    listing = _make_listing(price=1500.0)
    with patch("app.services.notifications._send_fcm") as mock_send:
        count = await dispatch_new_listing(db, listing)

    assert count == 0
    mock_send.assert_not_called()
