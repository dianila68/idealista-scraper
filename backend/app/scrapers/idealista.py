from __future__ import annotations

import re

import structlog
from bs4 import BeautifulSoup

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing
from app.scrapers.base import BaseScraper, register

log = structlog.get_logger()

_BASE_URL = "https://www.idealista.it"

# Maps listing_type → URL path prefix
_OP_MAP = {
    "rent": "affitto-case",
    "sale": "vendita-case",
}

# Floor name → int
_FLOOR_MAP: dict[str, int] = {
    "piano terra": 0,
    "seminterrato": -1,
    "interrato": -2,
    "rialzato": 0,
}


def _parse_price(text: str) -> float | None:
    """Extract numeric price from text like '1.200 €/mese' or '250.000 €'."""
    cleaned = re.sub(r"[^\d,.]", "", text.replace(".", "").replace(",", "."))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_size(text: str) -> float | None:
    """Extract numeric m² from text like '65 m²'."""
    m = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(".", "").replace(",", "."))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_rooms(text: str) -> int | None:
    """Extract room count from text like '2 locali' or '1 locale'."""
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def _parse_floor(text: str) -> int | None:
    """Parse floor text to int: 'Piano terra'→0, '2° piano'→2, etc."""
    lower = text.strip().lower()
    if lower in _FLOOR_MAP:
        return _FLOOR_MAP[lower]
    m = re.search(r"(\d+)", lower)
    return int(m.group(1)) if m else None


def _parse_city_zone(address: str) -> tuple[str | None, str | None]:
    """
    Best-effort city/zone split from Idealista address strings.

    Idealista address format: 'Via Torino, Milano' or 'Zona Navigli, Milano'
    The h3 title often includes zone: 'Appartamento in affitto a Milano, Navigli'
    """
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        return parts[-1], None
    return parts[0] if parts else None, None


def _parse_zone_from_title(title: str) -> str | None:
    """Extract zone from title like '... a Milano, Navigli'."""
    m = re.search(r"a\s+\w+,\s+(.+)$", title, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_features(ul_tag: object) -> list[str]:
    if ul_tag is None:
        return []
    from bs4 import Tag

    if not isinstance(ul_tag, Tag):
        return []
    return [li.get_text(strip=True).lower() for li in ul_tag.find_all("li")]


def parse_search_page(html: str, listing_type: str = "rent") -> list[RawListing]:
    """Parse an Idealista search-results HTML page into RawListings."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[RawListing] = []

    for article in soup.find_all("article", class_="item"):
        source_id: str | None = article.get("data-element-id")  # type: ignore[assignment]
        if not source_id:
            continue

        link = article.find("a", class_="item-link")
        if link is None:
            continue

        href: str = link.get("href", "")  # type: ignore[assignment]
        url = _BASE_URL + href if href.startswith("/") else href

        raw_price = link.find(class_="item-price")
        price = _parse_price(raw_price.get_text()) if raw_price else None

        raw_size = link.find(class_="item-size")
        size_sqm = _parse_size(raw_size.get_text()) if raw_size else None

        raw_rooms = link.find(class_="item-rooms")
        rooms = _parse_rooms(raw_rooms.get_text()) if raw_rooms else None

        raw_floor = link.find(class_="item-floor")
        floor = _parse_floor(raw_floor.get_text()) if raw_floor else None

        raw_title = link.find(class_="item-title")
        title: str = raw_title.get_text(strip=True) if raw_title else ""

        raw_addr = link.find(class_="item-address")
        address_text: str = raw_addr.get_text(strip=True) if raw_addr else ""
        city, _ = _parse_city_zone(address_text)
        zone = _parse_zone_from_title(title)

        raw_img = link.find("img", class_="item-image")
        images: list[str] = []
        if raw_img:
            src: str = raw_img.get("src", "")  # type: ignore[assignment]
            if src:
                images = [src]

        features = _parse_features(article.find("ul", class_="item-features"))

        results.append(
            RawListing(
                source="idealista",
                source_id=source_id,
                url=url,
                title=title,
                price=price,
                currency="EUR",
                listing_type=listing_type,
                property_type="apartment",
                city=city,
                zone=zone,
                location_precision="zone",  # Idealista shows neighbourhood, not street
                size_sqm=size_sqm,
                rooms=rooms,
                floor=floor,
                features=features,
                images=images,
                raw={"address": address_text},
            )
        )

    return results


@register
class IdealistaScraper(BaseScraper):
    source = "idealista"

    _HEADERS = {
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
    }

    def map_filter(self, fc: FilterConfig) -> dict[str, str]:
        """Map FilterConfig to Idealista URL query parameters."""
        params: dict[str, str] = {}
        if fc.price.min is not None:
            params["precioMin"] = str(int(fc.price.min))
        if fc.price.max is not None:
            params["precioMax"] = str(int(fc.price.max))
        if fc.size_sqm.min is not None:
            params["superficieMin"] = str(int(fc.size_sqm.min))
        if fc.size_sqm.max is not None:
            params["superficieMax"] = str(int(fc.size_sqm.max))
        if fc.rooms.min is not None:
            params["habitacionesMin"] = str(fc.rooms.min)
        if fc.rooms.max is not None:
            params["habitacionesMax"] = str(fc.rooms.max)
        if fc.floor and fc.floor.exclude_ground:
            params["plantaBaja"] = "false"
        return params

    def _build_search_url(self, fc: FilterConfig, page: int = 1) -> tuple[str, str]:
        """Return (url, listing_type) for a FilterConfig."""
        listing_type = fc.listing_type or "rent"
        op = _OP_MAP.get(listing_type, "affitto-case")

        # Use first location if provided, else default to all Italy
        location_slug = "tutta-italia"
        if fc.locations:
            loc = fc.locations[0]
            city_slug = loc.city.lower().replace(" ", "-")
            location_slug = f"{city_slug}-{city_slug}"

        path = f"/{op}/{location_slug}/"
        if page > 1:
            path = path.rstrip("/") + f"/?pagina={page}"

        return _BASE_URL + path, listing_type

    def normalize(self, raw_data: dict) -> RawListing:
        """Convert a parsed Idealista card dict into a RawListing.

        Delegates to the module-level parser functions so normalization is
        testable without instantiating the adapter or making HTTP calls.
        """
        return RawListing(
            source="idealista",
            source_id=str(raw_data.get("source_id", "")),
            url=raw_data.get("url", ""),
            title=raw_data.get("title"),
            price=_parse_price(raw_data.get("price_text", "")) if raw_data.get("price_text") else None,
            listing_type=raw_data.get("listing_type"),
            property_type="apartment",
            city=raw_data.get("city"),
            zone=raw_data.get("zone"),
            location_precision="zone",
            size_sqm=_parse_size(raw_data.get("size_text", "")) if raw_data.get("size_text") else None,
            rooms=_parse_rooms(raw_data.get("rooms_text", "")) if raw_data.get("rooms_text") else None,
            floor=_parse_floor(raw_data.get("floor_text", "")) if raw_data.get("floor_text") else None,
            features=raw_data.get("features", []),
            images=raw_data.get("images", []),
            raw=raw_data,
        )

    async def fetch_listings(self, fc: FilterConfig) -> list[RawListing]:
        """Fetch up to 3 pages of Idealista search results for the given filter."""
        results: list[RawListing] = []
        params = self.map_filter(fc)

        for page in range(1, 4):
            url, listing_type = self._build_search_url(fc, page)
            try:
                resp = await self._get(url, params=params, headers=self._HEADERS)
            except Exception:
                log.warning("idealista.fetch_failed", url=url, page=page)
                break

            page_listings = parse_search_page(resp.text, listing_type)
            log.debug("idealista.page_fetched", page=page, count=len(page_listings))

            if not page_listings:
                break

            results.extend(page_listings)

            # Check whether there's a next-page link
            soup = BeautifulSoup(resp.text, "html.parser")
            if not soup.find("a", class_="icon-arrow-right-after"):
                break

        return results
