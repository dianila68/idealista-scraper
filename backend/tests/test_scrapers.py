"""Unit tests for the BaseScraper contract and adapter registry."""
import pytest

from app.schemas.filter import FilterConfig, LocationFilter, PriceRange
from app.schemas.listing import RawListing
from app.scrapers.base import SCRAPER_REGISTRY, BaseScraper, get_scraper, register_scraper


class StubScraper(BaseScraper):
    source_name = "stub"

    def map_filter(self, filter_config: FilterConfig) -> dict:
        params: dict = {}
        if filter_config.listing_type:
            params["operation"] = filter_config.listing_type
        if filter_config.price.max is not None:
            params["maxPrice"] = filter_config.price.max
        if filter_config.locations:
            params["city"] = filter_config.locations[0].city
        return params

    async def fetch_listings(self, filter_config: FilterConfig) -> list[RawListing]:
        return [
            RawListing(source=self.source_name, source_id="42", url="https://stub.example/42")
        ]

    async def fetch_detail(self, listing_id: str) -> RawListing:
        return RawListing(
            source=self.source_name,
            source_id=listing_id,
            url=f"https://stub.example/{listing_id}",
        )


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(SCRAPER_REGISTRY)
    SCRAPER_REGISTRY.clear()
    yield
    SCRAPER_REGISTRY.clear()
    SCRAPER_REGISTRY.update(saved)


def test_base_scraper_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseScraper()  # type: ignore[abstract]


def test_incomplete_adapter_cannot_be_instantiated():
    class PartialScraper(BaseScraper):
        source_name = "partial"

        def map_filter(self, filter_config: FilterConfig) -> dict:
            return {}

    with pytest.raises(TypeError):
        PartialScraper()  # type: ignore[abstract]


async def test_stub_adapter_satisfies_interface():
    scraper = StubScraper()
    listings = await scraper.fetch_listings(FilterConfig())
    assert all(isinstance(item, RawListing) for item in listings)
    assert listings[0].source == "stub"

    detail = await scraper.fetch_detail("99")
    assert detail.source_id == "99"
    assert detail.url.endswith("/99")


def test_map_filter_translates_platonic_fields():
    config = FilterConfig(
        listing_type="rent",
        price=PriceRange(max=900),
        locations=[LocationFilter(city="Milano", zones=["Navigli"])],
    )
    params = StubScraper().map_filter(config)
    assert params == {"operation": "rent", "maxPrice": 900, "city": "Milano"}


def test_registry_dispatch():
    scraper = register_scraper(StubScraper())
    assert get_scraper("stub") is scraper
    assert list(SCRAPER_REGISTRY) == ["stub"]


def test_register_duplicate_source_rejected():
    register_scraper(StubScraper())
    with pytest.raises(ValueError, match="already registered"):
        register_scraper(StubScraper())


def test_register_without_source_name_rejected():
    class NamelessScraper(StubScraper):
        source_name = ""

    with pytest.raises(ValueError, match="source_name"):
        register_scraper(NamelessScraper())


def test_get_scraper_unknown_source():
    with pytest.raises(KeyError, match="No scraper registered"):
        get_scraper("idealista")
