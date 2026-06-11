"""Unit tests for the Subito.it scraper — no network calls."""
from pathlib import Path

from app.schemas.filter import FilterConfig, LocationFilter, PriceRange, RoomRange, SizeRange
from app.scrapers.subito import (
    SubitoScraper,
    _parse_floor,
    _parse_location,
    _parse_number,
    _parse_price,
    parse_search_page,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "subito"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


# ── Parser helpers ────────────────────────────────────────────────────────────

def test_parse_price():
    assert _parse_price("1.300 €") == 1300.0


def test_parse_price_empty():
    assert _parse_price("Trattabile") is None


def test_parse_number_int():
    assert _parse_number("3") == 3.0


def test_parse_number_sqm():
    assert _parse_number("70 m²") == 70.0


def test_parse_number_decimal():
    assert _parse_number("47,5") == 47.5


def test_parse_floor_ground():
    assert _parse_floor("Piano terra") == 0


def test_parse_floor_numbered():
    assert _parse_floor("4") == 4


def test_parse_floor_basement():
    assert _parse_floor("Seminterrato") == -1


def test_parse_location_full():
    city, zone = _parse_location("Navigli, Milano (MI)")
    assert city == "Milano"
    assert zone == "Navigli"


def test_parse_location_no_province():
    city, zone = _parse_location("Trastevere, Roma")
    assert city == "Roma"
    assert zone == "Trastevere"


def test_parse_location_single():
    city, zone = _parse_location("Milano")
    assert city == "Milano"
    assert zone is None


# ── Full page parse ───────────────────────────────────────────────────────────

def test_parse_page_count():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert len(listings) == 3


def test_parse_page_source():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert all(item.source == "subito" for item in listings)


def test_parse_page_listing_type():
    listings = parse_search_page(_fixture("search_rent.html"), listing_type="rent")
    assert all(item.listing_type == "rent" for item in listings)


def test_parse_page_prices():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert [item.price for item in listings] == [1300.0, 950.0, 800.0]


def test_parse_page_sizes():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert [item.size_sqm for item in listings] == [70.0, 35.0, 50.0]


def test_parse_page_rooms():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].rooms == 3
    assert listings[1].rooms == 1
    assert listings[2].rooms == 2


def test_parse_page_bathrooms():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert all(item.bathrooms == 1 for item in listings)


def test_parse_page_floors():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].floor == 2
    assert listings[1].floor == 0   # Piano terra
    assert listings[2].floor == 4


def test_parse_page_cities():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].city == "Milano"
    assert listings[1].city == "Roma"
    assert listings[2].city == "Napoli"


def test_parse_page_zones():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].zone == "Navigli"
    assert listings[1].zone == "Trastevere"
    assert listings[2].zone == "Chiaia"


def test_parse_page_images():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].images[0].startswith("https://")
    assert listings[1].images == []
    assert listings[2].images[0].startswith("https://")


def test_parse_page_url_absolute():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert all(item.url.startswith("https://www.subito.it/") for item in listings)


def test_parse_page_source_ids():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].source_id == "300111111"
    assert listings[1].source_id == "300222222"
    assert listings[2].source_id == "300333333"


# ── map_filter ────────────────────────────────────────────────────────────────

def test_map_filter_price():
    scraper = SubitoScraper()
    fc = FilterConfig(price=PriceRange(min=600, max=1400))
    params = scraper.map_filter(fc)
    assert params["ps"] == "600"
    assert params["pe"] == "1400"


def test_map_filter_size():
    scraper = SubitoScraper()
    fc = FilterConfig(size_sqm=SizeRange(min=40, max=100))
    params = scraper.map_filter(fc)
    assert params["sqs"] == "40"
    assert params["sqe"] == "100"


def test_map_filter_rooms():
    scraper = SubitoScraper()
    fc = FilterConfig(rooms=RoomRange(min=2))
    params = scraper.map_filter(fc)
    assert params["rms"] == "2"


def test_map_filter_empty():
    scraper = SubitoScraper()
    assert scraper.map_filter(FilterConfig()) == {}


# ── _build_search_url ─────────────────────────────────────────────────────────

def test_build_url_rent_milan():
    scraper = SubitoScraper()
    fc = FilterConfig(
        listing_type="rent",
        locations=[LocationFilter(city="Milano")],
    )
    url, lt = scraper._build_search_url(fc)
    assert "affitto" in url
    assert "milano" in url
    assert lt == "rent"


def test_build_url_sale():
    scraper = SubitoScraper()
    url, lt = scraper._build_search_url(FilterConfig(listing_type="sale"))
    assert "vendita" in url
    assert lt == "sale"


def test_build_url_page_2():
    scraper = SubitoScraper()
    url, _ = scraper._build_search_url(FilterConfig(), page=2)
    assert "o=2" in url
