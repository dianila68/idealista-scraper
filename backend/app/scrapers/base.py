import hashlib
import json
import random
from abc import ABC, abstractmethod
from typing import ClassVar

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing

log = structlog.get_logger()

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
    "Accept": "application/json, text/html, */*",
}


class BaseScraper(ABC):
    """All platform adapters extend this class."""

    source: ClassVar[str]

    def __init__(
        self,
        request_delay: float = 3.0,
        proxies: list[str] | None = None,
    ) -> None:
        self._delay = request_delay
        self._proxies = proxies or []
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseScraper":
        proxy = random.choice(self._proxies) if self._proxies else None
        self._client = httpx.AsyncClient(
            headers=_BROWSER_HEADERS,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            proxy=proxy,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use scraper as an async context manager")
        return self._client

    @abstractmethod
    async def fetch_listings(self, filter_config: FilterConfig) -> list[RawListing]:
        """Fetch listings matching filter_config from the platform."""

    @abstractmethod
    def map_filter(self, filter_config: FilterConfig) -> dict[str, str]:
        """Translate a FilterConfig into platform-native query parameters."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get(self, url: str, **kwargs: object) -> httpx.Response:
        import asyncio
        await asyncio.sleep(self._delay)
        response = await self.client.get(url, **kwargs)  # type: ignore[arg-type]
        response.raise_for_status()
        return response

    @staticmethod
    def content_hash(raw: RawListing) -> str:
        """Stable SHA-256 fingerprint for deduplication.

        Encodes the fields most likely to change when a listing is updated.
        """
        key = json.dumps(
            {
                "source": raw.source,
                "source_id": raw.source_id,
                "price": raw.price,
                "size_sqm": raw.size_sqm,
                "url": raw.url,
            },
            sort_keys=True,
        )
        return hashlib.sha256(key.encode()).hexdigest()


# Registry populated by each adapter module on import
_REGISTRY: dict[str, type[BaseScraper]] = {}


def register(cls: type[BaseScraper]) -> type[BaseScraper]:
    """Decorator: add an adapter class to the global registry."""
    _REGISTRY[cls.source] = cls
    return cls


def get_scraper(source: str, **kwargs: object) -> BaseScraper:
    """Return an instantiated adapter for *source*."""
    try:
        return _REGISTRY[source](**kwargs)  # type: ignore[arg-type]
    except KeyError as exc:
        raise ValueError(f"No scraper registered for source '{source}'") from exc


def available_sources() -> list[str]:
    return list(_REGISTRY.keys())
