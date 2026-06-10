"""Unit tests for BaseScraper utilities — no network, no database."""
import pytest

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing
from app.scrapers.base import BaseScraper, available_sources, get_scraper, register


class _StubScraper(BaseScraper):
    source = "_stub_"

    async def fetch_listings(self, filter_config: FilterConfig) -> list[RawListing]:
        return []

    def map_filter(self, filter_config: FilterConfig) -> dict[str, str]:
        return {}


def _raw(**kwargs) -> RawListing:
    defaults = dict(
        source="idealista",
        source_id="123",
        url="https://example.com/1",
        price=1000.0,
        size_sqm=50.0,
    )
    defaults.update(kwargs)
    return RawListing(**defaults)


def test_content_hash_stable():
    r = _raw()
    assert BaseScraper.content_hash(r) == BaseScraper.content_hash(r)


def test_content_hash_changes_on_price():
    r1 = _raw(price=1000)
    r2 = _raw(price=1200)
    assert BaseScraper.content_hash(r1) != BaseScraper.content_hash(r2)


def test_content_hash_changes_on_size():
    r1 = _raw(size_sqm=50)
    r2 = _raw(size_sqm=65)
    assert BaseScraper.content_hash(r1) != BaseScraper.content_hash(r2)


def test_content_hash_is_hex_string():
    h = BaseScraper.content_hash(_raw())
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_register_and_get_scraper():
    register(_StubScraper)
    scraper = get_scraper("_stub_")
    assert isinstance(scraper, _StubScraper)


def test_get_scraper_unknown_raises():
    with pytest.raises(ValueError, match="No scraper registered"):
        get_scraper("__nonexistent__")


def test_available_sources_includes_registered():
    register(_StubScraper)
    assert "_stub_" in available_sources()
