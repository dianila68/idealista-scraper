from __future__ import annotations

import re

import structlog
from bs4 import BeautifulSoup

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing
from app.scrapers.base import BaseScraper, register

log = structlog.get_logger()

_BASE_URL = "https://www.subito.it"

_OP_MAP = {
    "rent": "affitto",
    "sale": "vendita",
}

_FLOOR_MAP: dict[str, int] = {
    "piano terra": 0,
    "seminterrato": -1,
    "interrato": -2,
    "rialzato": 0,
}


def _parse_price(text: str) -> float | None:
    cleaned = re.sub(r"[^\d]", "", text.replace(".", "").split(",")[0])
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_number(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(".", "").replace(",", "."))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_floor(text: str) -> int | None:
    lower = text.strip().lower()
    if lower in _FLOOR_MAP:
        return _FLOOR_MAP[lower]
    m = re.search(r"(\d+)", lower)
    return int(m.group(1)) if m else None


def _parse_location(text: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse 'Navigli, Milano (MI)' → (city='Milano', zone='Navigli', province='MI').
    Subito location format: 'Zone, City (Province)'.
    Returns (city, zone, province).
    """
    province: str | None = None
    m = re.search(r"\(([A-Z]{2})\)\s*$", text.strip())
    if m:
        province = m.group(1)
    clean = re.sub(r"\s*\([A-Z]{2}\)\s*$", "", text.strip())
    parts = [p.strip() for p in clean.split(",")]
    if len(parts) >= 2:
        return parts[-1], parts[0], province
    return clean, None, province


def _extract_info(card: object) -> dict[str, str]:
    """Extract label→value pairs from item-card__info-list items."""
    from bs4 import Tag

    if not isinstance(card, Tag):
        return {}
    info: dict[str, str] = {}
    for item in card.find_all("li", class_="item-card__info-item"):
        label_tag = item.find(class_="item-card__info-label")
        value_tag = item.find(class_="item-card__info-value")
        if label_tag and value_tag:
            info[label_tag.get_text(strip=True).lower()] = value_tag.get_text(strip=True)
    return info


def parse_search_page(html: str, listing_type: str = "rent") -> list[RawListing]:
    """Parse a Subito.it search-results HTML page into RawListings."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[RawListing] = []

    for card in soup.find_all("div", class_="item-card"):
        source_id: str | None = card.get("data-item-id")  # type: ignore[assignment]
        if not source_id:
            continue

        body = card.find("a", class_="item-card__body")
        if body is None:
            continue

        href: str = body.get("href", "")  # type: ignore[assignment]
        url = _BASE_URL + href if href.startswith("/") else href

        title_tag = body.find(class_="item-card__title")
        title: str = title_tag.get_text(strip=True) if title_tag else ""

        price_tag = body.find(class_="item-card__price")
        price = _parse_price(price_tag.get_text()) if price_tag else None

        info = _extract_info(card)
        size_val = info.get("superficie", "")
        _size = _parse_number(size_val)
        size_sqm: float | None = _size if _size is not None else None

        rooms_val = info.get("locali", "")
        rooms_num = _parse_number(rooms_val)
        rooms = int(rooms_num) if rooms_num is not None else None

        floor_val = info.get("piano", "")
        floor = _parse_floor(floor_val) if floor_val else None

        baths_val = info.get("bagni", "")
        baths_num = _parse_number(baths_val)
        bathrooms = int(baths_num) if baths_num is not None else None

        loc_tag = body.find(class_="item-card__location")
        city: str | None = None
        zone: str | None = None
        province: str | None = None
        if loc_tag:
            city, zone, province = _parse_location(loc_tag.get_text(strip=True))

        img_tag = body.find("img", class_="item-card__img")
        images: list[str] = []
        if img_tag:
            src: str = img_tag.get("src", "")  # type: ignore[assignment]
            if src:
                images = [src]

        results.append(
            RawListing(
                source="subito",
                source_id=source_id,
                url=url,
                title=title,
                price=price,
                currency="EUR",
                listing_type=listing_type,
                property_type="apartment",
                city=city,
                zone=zone,
                location_precision="zone",  # Subito gives zone+city but no street
                province=province,
                size_sqm=size_sqm,
                rooms=rooms,
                bathrooms=bathrooms,
                floor=floor,
                images=images,
                raw={"title": title},
            )
        )

    return results


@register
class SubitoScraper(BaseScraper):
    source = "subito"

    _HEADERS = {
        "Accept-Language": "it-IT,it;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    }

    def map_filter(self, fc: FilterConfig) -> dict[str, str]:
        params: dict[str, str] = {}
        if fc.price.min is not None:
            params["ps"] = str(int(fc.price.min))
        if fc.price.max is not None:
            params["pe"] = str(int(fc.price.max))
        if fc.size_sqm.min is not None:
            params["sqs"] = str(int(fc.size_sqm.min))
        if fc.size_sqm.max is not None:
            params["sqe"] = str(int(fc.size_sqm.max))
        if fc.rooms.min is not None:
            params["rms"] = str(fc.rooms.min)
        return params

    def _build_search_url(self, fc: FilterConfig, page: int = 1) -> tuple[str, str]:
        listing_type = fc.listing_type or "rent"
        op = _OP_MAP.get(listing_type, "affitto")

        location_slug = ""
        if fc.locations:
            loc = fc.locations[0]
            city_slug = loc.city.lower().replace(" ", "-") + "-citta"
            location_slug = f"{city_slug}/"

        path = f"/annunci/immobili/{op}/{location_slug}"
        if page > 1:
            path = path.rstrip("/") + f"/?o={page}"

        return _BASE_URL + path, listing_type

    def normalize(self, raw_data: dict) -> RawListing:
        """Convert a parsed Subito card dict into a RawListing."""
        city, zone, province = _parse_location(raw_data.get("location_text", ""))
        return RawListing(
            source="subito",
            source_id=str(raw_data.get("source_id", "")),
            url=raw_data.get("url", ""),
            title=raw_data.get("title"),
            price=_parse_price(raw_data.get("price_text", "")) if raw_data.get("price_text") else None,
            listing_type=raw_data.get("listing_type"),
            property_type="apartment",
            city=city,
            zone=zone,
            location_precision="zone",
            province=province,
            size_sqm=raw_data.get("size_sqm"),
            rooms=raw_data.get("rooms"),
            bathrooms=raw_data.get("bathrooms"),
            floor=raw_data.get("floor"),
            images=raw_data.get("images", []),
            raw=raw_data,
        )

    async def fetch_listings(self, fc: FilterConfig) -> list[RawListing]:
        results: list[RawListing] = []
        params = self.map_filter(fc)

        for page in range(1, 4):
            url, listing_type = self._build_search_url(fc, page)
            try:
                resp = await self._get(url, params=params, headers=self._HEADERS)
            except Exception:
                log.warning("subito.fetch_failed", url=url, page=page)
                break

            page_listings = parse_search_page(resp.text, listing_type)
            log.debug("subito.page_fetched", page=page, count=len(page_listings))

            if not page_listings:
                break

            results.extend(page_listings)

            soup = BeautifulSoup(resp.text, "html.parser")
            if not soup.find("a", class_="pagination__next"):
                break

        return results
