import asyncio
import hashlib
import json
import random
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx
import structlog

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing

log = structlog.get_logger()

# Realistic pool: Chrome (Windows/Mac/Linux), Firefox, Safari, mobile Chrome/Safari.
# Rotated per request so repeated hits from the same IP look like different browsers.
_USER_AGENTS: list[str] = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Mobile Chrome (Android)
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    # Mobile Safari (iPhone)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
]

# Non-rotating base headers sent on every request (UA is injected per-request).
_BASE_HEADERS: dict[str, str] = {
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
}

# HTTP status codes that warrant a retry with back-off.
_RETRYABLE = frozenset({429, 500, 502, 503, 504})


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
        # Rotate proxy per scrape session. For per-request rotation, callers
        # would need separate clients; session-level rotation is a reasonable
        # trade-off that avoids the overhead of creating a client per request.
        proxy = random.choice(self._proxies) if self._proxies else None
        self._client = httpx.AsyncClient(
            headers=_BASE_HEADERS,
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

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET with jittered polite delay, UA rotation, and status-aware retry.

        - 429: respects Retry-After header; backs off 30 s × 2^attempt otherwise.
        - 502/503/504: backs off 10 s × 2^attempt.
        - Other 4xx: raises immediately (no retry).
        - Transport errors: backs off 2^(attempt+1) seconds.
        """
        max_attempts = 4
        for attempt in range(max_attempts):
            # Polite jittered delay (± 50% of configured delay).
            # Randomising the inter-request gap makes traffic patterns less
            # machine-like than a fixed 3-second interval.
            jitter = self._delay * random.uniform(0.5, 1.5)
            await asyncio.sleep(jitter)

            # Inject a randomly chosen UA so successive pages appear to come
            # from different browsers. Merge with any site-specific headers
            # passed by the adapter (Accept, Accept-Language overrides, etc.).
            req_headers: dict[str, str] = dict(kwargs.get("headers") or {})
            req_headers.setdefault("User-Agent", random.choice(_USER_AGENTS))
            all_kwargs = {k: v for k, v in kwargs.items() if k != "headers"}
            all_kwargs["headers"] = req_headers

            try:
                response = await self.client.get(url, **all_kwargs)  # type: ignore[arg-type]
            except httpx.TransportError as exc:
                if attempt >= max_attempts - 1:
                    raise
                wait = 2 ** (attempt + 1)
                log.warning("scraper._get.transport_error", attempt=attempt, wait=wait, exc=str(exc))
                await asyncio.sleep(wait)
                continue

            if response.status_code == 200:
                return response

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                wait = int(retry_after) if retry_after.isdigit() else 30 * (2 ** attempt)
                wait = min(wait, 300)  # cap at 5 minutes
                log.warning(
                    "scraper._get.rate_limited",
                    url=url,
                    wait=wait,
                    attempt=attempt,
                    retry_after=retry_after or None,
                )
                if attempt >= max_attempts - 1:
                    response.raise_for_status()
                await asyncio.sleep(wait)
                continue

            if response.status_code in (502, 503, 504):
                wait = 10 * (2 ** attempt)
                log.warning(
                    "scraper._get.server_error",
                    status=response.status_code,
                    url=url,
                    wait=wait,
                    attempt=attempt,
                )
                if attempt >= max_attempts - 1:
                    response.raise_for_status()
                await asyncio.sleep(wait)
                continue

            # All other non-2xx statuses (e.g. 403, 404): raise immediately.
            response.raise_for_status()

        # Unreachable — every path above either returns or raises.
        raise RuntimeError("_get exhausted retries without returning or raising")  # pragma: no cover

    @staticmethod
    def content_hash(raw: RawListing) -> str:
        """Stable SHA-256 fingerprint for deduplication."""
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
