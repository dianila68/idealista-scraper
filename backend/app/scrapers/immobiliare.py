from __future__ import annotations

import re

import structlog
from bs4 import BeautifulSoup

from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing
from app.scrapers.base import BaseScraper, register

log = structlog.get_logger()

_BASE_URL = "https://www.immobiliare.it"

_OP_MAP = {
    "rent": "affitto",
    "sale": "vendita",
}

_FLOOR_MAP: dict[str, int] = {
    "piano terra": 0,
    "seminterrato": -1,
    "interrato": -2,
    "rialzato": 0,
    "ammezzato": 0,
}


def _parse_price(text: str) -> float | None:
    cleaned = re.sub(r"[^\d]", "", text.replace(".", "").split(",")[0])
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_sqm(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(".", "").replace(",", "."))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_rooms(text: str) -> int | None:
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def _parse_floor(text: str) -> int | None:
    lower = text.strip().lower()
    if lower in _FLOOR_MAP:
        return _FLOOR_MAP[lower]
    m = re.search(r"(\d+)", lower)
    return int(m.group(1)) if m else None


def _split_location(location_text: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse 'Via Vigevano 10, Navigli, Milano' → (address, zone, city).
    Immobiliare.it cards list: street, zone, city (last element is city).
    """
    parts = [p.strip() for p in location_text.split(",")]
    if len(parts) >= 3:
        return parts[0], parts[-2], parts[-1]
    if len(parts) == 2:
        return parts[0], None, parts[1]
    return location_text, None, None


def _parse_features(ul_tag: object) -> list[str]:
    if ul_tag is None:
        return []
    from bs4 import Tag

    if not isinstance(ul_tag, Tag):
        return []
    return [li.get_text(strip=True).lower() for li in ul_tag.find_all("li")]


def parse_search_page(html: str, listing_type: str = "rent") -> list[RawListing]:
    """Parse an Immobiliare.it search-results HTML page into RawListings."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[RawListing] = []

    for card in soup.find_all("li", class_="in-searchLayoutItem"):
        source_id: str | None = card.get("data-listing-id")  # type: ignore[assignment]
        if not source_id:
            continue

        title_tag = card.find("a", class_="in-card__title-link")
        if title_tag is None:
            continue

        href: str = title_tag.get("href", "")  # type: ignore[assignment]
        url = _BASE_URL + href if href.startswith("/") else href
        title: str = title_tag.get_text(strip=True)

        price_tag = card.find(class_="in-realEstateListCard__price")
        price = _parse_price(price_tag.get_text()) if price_tag else None

        size_sqm: float | None = None
        rooms: int | None = None
        floor: int | None = None

        for detail in card.find_all("span", class_=re.compile(r"in-icon--")):
            aria: str = detail.get("aria-label", "")  # type: ignore[assignment]
            text = detail.get_text(strip=True)
            if aria == "superficie":
                size_sqm = _parse_sqm(text)
            elif aria == "locali":
                rooms = _parse_rooms(text)
            elif aria == "piano":
                floor = _parse_floor(text)

        location_tag = card.find(class_="in-card__location")
        city: str | None = None
        zone: str | None = None
        if location_tag:
            _, zone, city = _split_location(location_tag.get_text(strip=True))

        img_tag = card.find("img", class_="in-card__gallery-image")
        images: list[str] = []
        if img_tag:
            src: str = img_tag.get("src", "")  # type: ignore[assignment]
            if src:
                images = [src]

        features = _parse_features(card.find("ul", class_="in-features__list"))

        results.append(
            RawListing(
                source="immobiliare",
                source_id=source_id,
                url=url,
                title=title,
                price=price,
                currency="EUR",
                listing_type=listing_type,
                property_type="apartment",
                city=city,
                zone=zone,
                size_sqm=size_sqm,
                rooms=rooms,
                floor=floor,
                features=features,
                images=images,
                raw={"title": title},
            )
        )

    return results


@register
class ImmobiliareScraper(BaseScraper):
    source = "immobiliare"

    _HEADERS = {
        "Accept-Language": "it-IT,it;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def map_filter(self, fc: FilterConfig) -> dict[str, str]:
        params: dict[str, str] = {}
        if fc.price.min is not None:
            params["prezzoMinimo"] = str(int(fc.price.min))
        if fc.price.max is not None:
            params["prezzoMassimo"] = str(int(fc.price.max))
        if fc.size_sqm.min is not None:
            params["superficieMinima"] = str(int(fc.size_sqm.min))
        if fc.size_sqm.max is not None:
            params["superficieMassima"] = str(int(fc.size_sqm.max))
        if fc.rooms.min is not None:
            params["localiMinimo"] = str(fc.rooms.min)
        if fc.rooms.max is not None:
            params["localiMassimo"] = str(fc.rooms.max)
        if fc.floor and fc.floor.exclude_ground:
            params["pianoMinimo"] = "1"
        return params

    def _build_search_url(self, fc: FilterConfig, page: int = 1) -> tuple[str, str]:
        listing_type = fc.listing_type or "rent"
        op = _OP_MAP.get(listing_type, "affitto")

        location_slug = "italia"
        if fc.locations:
            loc = fc.locations[0]
            city_slug = loc.city.lower().replace(" ", "-")
            location_slug = city_slug

        path = f"/{op}/appartamenti/{location_slug}/"
        if page > 1:
            path = path.rstrip("/") + f"/?pag={page}"

        return _BASE_URL + path, listing_type

    async def fetch_listings(self, fc: FilterConfig) -> list[RawListing]:
        results: list[RawListing] = []
        params = self.map_filter(fc)

        for page in range(1, 4):
            url, listing_type = self._build_search_url(fc, page)
            try:
                resp = await self._get(url, params=params, headers=self._HEADERS)
            except Exception:
                log.warning("immobiliare.fetch_failed", url=url, page=page)
                break

            page_listings = parse_search_page(resp.text, listing_type)
            log.debug("immobiliare.page_fetched", page=page, count=len(page_listings))

            if not page_listings:
                break

            results.extend(page_listings)

            soup = BeautifulSoup(resp.text, "html.parser")
            if not soup.find("a", class_="in-pagination__item"):
                break

        return results
