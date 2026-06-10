"""Unit tests for the dedup service — DB mocked with AsyncMock."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.listing import RawListing
from app.services.dedup import bulk_upsert, upsert_listing


def _raw(**kwargs) -> RawListing:
    defaults = dict(
        source="idealista",
        source_id="D-001",
        url="https://example.com/d1",
        price=1200.0,
        size_sqm=60.0,
    )
    defaults.update(kwargs)
    return RawListing(**defaults)


def _orm_listing(content_hash: str = "oldhash"):
    row = MagicMock()
    row.source = "idealista"
    row.source_id = "D-001"
    row.content_hash = content_hash
    row.scraped_at = datetime.now(UTC)
    return row


def _mock_db(existing=None):
    """Build a minimal async DB session mock."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


# ── upsert_listing ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_new_listing():
    db = _mock_db(existing=None)
    raw = _raw()
    listing, is_new = await upsert_listing(db, raw, "newhash")
    assert is_new is True
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_unchanged_listing():
    existing = _orm_listing(content_hash="samehash")
    db = _mock_db(existing=existing)
    raw = _raw()
    listing, is_new = await upsert_listing(db, raw, "samehash")
    assert is_new is False
    # No add or flush for unchanged
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_changed_listing_updates_fields():
    existing = _orm_listing(content_hash="oldhash")
    db = _mock_db(existing=existing)
    raw = _raw(price=1500.0)
    listing, is_new = await upsert_listing(db, raw, "newhash")
    assert is_new is False
    assert existing.price == 1500.0
    assert existing.content_hash == "newhash"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_sets_scraped_at_for_new():
    db = _mock_db(existing=None)
    raw = _raw()
    before = datetime.now(UTC)
    listing, _ = await upsert_listing(db, raw, "hash")
    # The listing was passed to db.add(); check it has a scraped_at via
    # inspecting the Listing() constructor call via db.add
    call_arg = db.add.call_args[0][0]
    assert call_arg.scraped_at >= before


# ── bulk_upsert ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_upsert_counts():
    """3 items: 2 new, 1 unchanged."""
    existing = _orm_listing(content_hash="same")
    calls = [None, None, existing]  # first two are new

    call_iter = iter(calls)

    async def _fake_upsert(db, raw, h):
        ex = next(call_iter)
        if ex is None:
            row = MagicMock()
            return row, True
        if ex.content_hash == h:
            return ex, False
        ex.content_hash = h
        return ex, False

    with patch("app.services.dedup.upsert_listing", side_effect=_fake_upsert):
        db = _mock_db()
        pairs = [
            (_raw(source_id="X1"), "hash1"),
            (_raw(source_id="X2"), "hash2"),
            (_raw(source_id="X3"), "same"),
        ]
        new_count, updated_count = await bulk_upsert(db, pairs)

    assert new_count == 2
    assert updated_count == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_upsert_empty():
    db = _mock_db()
    new_count, updated_count = await bulk_upsert(db, [])
    assert new_count == 0
    assert updated_count == 0
    db.commit.assert_awaited_once()
