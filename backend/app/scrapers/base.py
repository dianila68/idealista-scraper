"""Contract every platform scraper adapter must implement."""
from abc import ABC, abstractmethod

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing


class BaseScraper(ABC):
    """Base class for platform adapters (Idealista, Immobiliare, Subito).

    Concrete adapters translate the platform-agnostic ``FilterConfig`` into
    platform-native query parameters, fetch matching listings, and normalise
    them into ``RawListing`` objects.
    """

    source_name: str = ""

    @abstractmethod
    def map_filter(self, filter_config: FilterConfig) -> dict:
        """Translate the platonic filter into platform-native query params."""
        ...

    @abstractmethod
    async def fetch_listings(self, filter_config: FilterConfig) -> list[RawListing]:
        """Fetch all listings matching the filter from this platform."""
        ...

    @abstractmethod
    async def fetch_detail(self, listing_id: str) -> RawListing:
        """Fetch full detail for a single listing by its platform ID."""
        ...


SCRAPER_REGISTRY: dict[str, BaseScraper] = {}


def register_scraper(scraper: BaseScraper) -> BaseScraper:
    """Register an adapter instance for dynamic dispatch by source name."""
    name = scraper.source_name
    if not name:
        raise ValueError(f"{type(scraper).__name__} must define a non-empty source_name")
    if name in SCRAPER_REGISTRY:
        raise ValueError(f"A scraper for source '{name}' is already registered")
    SCRAPER_REGISTRY[name] = scraper
    return scraper


def get_scraper(source: str) -> BaseScraper:
    """Look up a registered adapter by source name."""
    try:
        return SCRAPER_REGISTRY[source]
    except KeyError:
        raise KeyError(
            f"No scraper registered for source '{source}'. "
            f"Available: {sorted(SCRAPER_REGISTRY)}"
        ) from None
