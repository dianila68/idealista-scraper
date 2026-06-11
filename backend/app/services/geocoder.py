from __future__ import annotations

import asyncio
from functools import lru_cache

import httpx
import structlog

log = structlog.get_logger()

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "idealista-scraper/1.0 (luigidelle05@gmail.com)"}
_RATE_LIMIT = asyncio.Semaphore(1)
_DELAY_SECONDS = 1.0


@lru_cache(maxsize=2048)
def _cached_result(query: str) -> tuple[float, float] | None:
    # Populated via _set_cache below; lru_cache used as a registry
    return None


_cache: dict[str, tuple[float, float] | None] = {}


async def _nominatim_search(query: str) -> tuple[float, float] | None:
    async with _RATE_LIMIT:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
                resp = await client.get(
                    _NOMINATIM_URL,
                    params={"q": query, "format": "json", "limit": 1},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("geocoder.nominatim_error", query=query, exc=str(exc))
            return None
        finally:
            await asyncio.sleep(_DELAY_SECONDS)

    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


async def geocode(city: str | None, zone: str | None) -> tuple[float, float] | None:
    """Return (lat, lng) for a city/zone or None if not resolvable.

    Tries '{zone}, {city}, Italy' first, falls back to '{city}, Italy'.
    Results are in-process cached to avoid redundant API calls.
    """
    if not city:
        return None

    primary_key = f"{zone or ''},{city},Italy"
    if primary_key in _cache:
        return _cache[primary_key]

    coords: tuple[float, float] | None = None

    if zone:
        coords = await _nominatim_search(f"{zone}, {city}, Italy")

    if coords is None:
        fallback_key = f",{city},Italy"
        if fallback_key in _cache:
            coords = _cache[fallback_key]
        else:
            coords = await _nominatim_search(f"{city}, Italy")
            _cache[fallback_key] = coords

    _cache[primary_key] = coords
    if coords:
        log.debug("geocoder.resolved", city=city, zone=zone, lat=coords[0], lng=coords[1])
    return coords


def clear_cache() -> None:
    _cache.clear()
