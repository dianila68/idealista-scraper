"""Unit tests for the Idealista scraper — no network calls."""
from pathlib import Path

from app.schemas.filter import FilterConfig, LocationFilter, PriceRange, RoomRange, SizeRange
from app.scrapers.idealista import (
    IdealistaScraper,
    _parse_city_zone,
    _parse_floor,
    _parse_price,
    _parse_rooms,
    _parse_size,
    _parse_zone_from_title,
    parse_search_page,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "idealista"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


# ── Parser helpers ────────────────────────────────────────────────────────────

def test_parse_price_monthly():
    assert _parse_price("1.200 €/mese") == 1200.0


def test_parse_price_sale():
    assert _parse_price("250.000 €") == 250000.0


def test_parse_price_invalid():
    assert _parse_price("Prezzo su richiesta") is None


def test_parse_size():
    assert _parse_size("65 m²") == 65.0


def test_parse_size_decimal():
    assert _parse_size("47,5 m²") == 47.5


def test_parse_rooms_plural():
    assert _parse_rooms("3 locali") == 3


def test_parse_rooms_singular():
    assert _parse_rooms("1 locale") == 1


def test_parse_floor_ground():
    assert _parse_floor("Piano terra") == 0


def test_parse_floor_numbered():
    assert _parse_floor("3° piano") == 3


def test_parse_floor_basement():
    assert _parse_floor("Seminterrato") == -1


def test_parse_city_zone_two_parts():
    city, zone = _parse_city_zone("Via Torino, Milano")
    assert city == "Milano"
    assert zone is None


def test_parse_city_zone_single():
    city, _ = _parse_city_zone("Roma")
    assert city == "Roma"


def test_parse_zone_from_title():
    z = _parse_zone_from_title("Appartamento in affitto a Milano, Navigli")
    assert z == "Navigli"


def test_parse_zone_from_title_no_zone():
    assert _parse_zone_from_title("Casa in vendita") is None


# ── Full page parse ───────────────────────────────────────────────────────────

def test_parse_search_page_count():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert len(listings) == 3


def test_parse_search_page_source():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert all(item.source == "idealista" for item in listings)


def test_parse_search_page_listing_type():
    listings = parse_search_page(_fixture("search_rent.html"), listing_type="rent")
    assert all(item.listing_type == "rent" for item in listings)


def test_parse_search_page_prices():
    listings = parse_search_page(_fixture("search_rent.html"))
    prices = [item.price for item in listings]
    assert prices == [1200.0, 900.0, 2500.0]


def test_parse_search_page_sizes():
    listings = parse_search_page(_fixture("search_rent.html"))
    sizes = [item.size_sqm for item in listings]
    assert sizes == [65.0, 40.0, 120.0]


def test_parse_search_page_rooms():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].rooms == 2
    assert listings[1].rooms == 1
    assert listings[2].rooms == 4


def test_parse_search_page_floors():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].floor == 2
    assert listings[1].floor == 0    # Piano terra
    assert listings[2].floor == 5


def test_parse_search_page_zone():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].zone == "Navigli"
    assert listings[1].zone == "Loreto"


def test_parse_search_page_features():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert "ascensore" in listings[0].features
    assert "balcone" in listings[1].features
    assert "garage" in listings[2].features


def test_parse_search_page_url_absolute():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert all(item.url.startswith("https://www.idealista.it/") for item in listings)


def test_parse_search_page_images():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert len(listings[0].images) == 1
    assert listings[0].images[0].startswith("https://")
    # Third listing has no image in fixture
    assert listings[2].images == []


def test_parse_search_page_source_ids():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].source_id == "100111111"
    assert listings[1].source_id == "100222222"
    assert listings[2].source_id == "100333333"


# ── map_filter ────────────────────────────────────────────────────────────────

def test_map_filter_price_range():
    scraper = IdealistaScraper()
    fc = FilterConfig(price=PriceRange(min=800, max=1500))
    params = scraper.map_filter(fc)
    assert params["precioMin"] == "800"
    assert params["precioMax"] == "1500"


def test_map_filter_size_range():
    scraper = IdealistaScraper()
    fc = FilterConfig(size_sqm=SizeRange(min=50, max=120))
    params = scraper.map_filter(fc)
    assert params["superficieMin"] == "50"
    assert params["superficieMax"] == "120"


def test_map_filter_rooms():
    scraper = IdealistaScraper()
    fc = FilterConfig(rooms=RoomRange(min=2))
    params = scraper.map_filter(fc)
    assert params["habitacionesMin"] == "2"


def test_map_filter_empty():
    scraper = IdealistaScraper()
    params = scraper.map_filter(FilterConfig())
    assert params == {}


# ── _build_search_url ─────────────────────────────────────────────────────────

def test_build_url_rent_milan():
    scraper = IdealistaScraper()
    fc = FilterConfig(
        listing_type="rent",
        locations=[LocationFilter(city="Milano")],
    )
    url, lt = scraper._build_search_url(fc)
    assert "affitto-case" in url
    assert "milano" in url
    assert lt == "rent"


def test_build_url_sale():
    scraper = IdealistaScraper()
    fc = FilterConfig(listing_type="sale")
    url, lt = scraper._build_search_url(fc)
    assert "vendita-case" in url
    assert lt == "sale"


def test_build_url_page_2():
    scraper = IdealistaScraper()
    fc = FilterConfig(listing_type="rent")
    url, _ = scraper._build_search_url(fc, page=2)
    assert "pagina=2" in url


def test_build_url_default_listing_type():
    scraper = IdealistaScraper()
    url, lt = scraper._build_search_url(FilterConfig())
    assert "affitto-case" in url
    assert lt == "rent"
