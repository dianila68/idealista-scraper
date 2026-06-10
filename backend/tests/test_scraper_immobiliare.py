"""Unit tests for the Immobiliare.it scraper — no network calls."""
from pathlib import Path

from app.schemas.filter import FilterConfig, LocationFilter, PriceRange, RoomRange, SizeRange
from app.scrapers.immobiliare import (
    ImmobiliareScraper,
    _parse_floor,
    _parse_price,
    _parse_rooms,
    _parse_sqm,
    _split_location,
    parse_search_page,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "immobiliare"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


# ── Parser helpers ────────────────────────────────────────────────────────────

def test_parse_price_monthly():
    assert _parse_price("1.400 €/mese") == 1400.0


def test_parse_price_sale():
    assert _parse_price("320.000 €") == 320000.0


def test_parse_price_empty():
    assert _parse_price("Prezzo su richiesta") is None


def test_parse_sqm():
    assert _parse_sqm("75 m²") == 75.0


def test_parse_sqm_decimal():
    assert _parse_sqm("47,5 m²") == 47.5


def test_parse_rooms():
    assert _parse_rooms("3 locali") == 3


def test_parse_floor_ground():
    assert _parse_floor("Piano terra") == 0


def test_parse_floor_numbered():
    assert _parse_floor("2° piano") == 2


def test_parse_floor_basement():
    assert _parse_floor("Seminterrato") == -1


def test_split_location_full():
    addr, zone, city = _split_location("Via Vigevano 10, Navigli, Milano")
    assert addr == "Via Vigevano 10"
    assert zone == "Navigli"
    assert city == "Milano"


def test_split_location_two_parts():
    _, zone, city = _split_location("Navigli, Milano")
    assert city == "Milano"
    assert zone is None


def test_split_location_single():
    addr, zone, city = _split_location("Milano")
    assert addr == "Milano"
    assert zone is None
    assert city is None


# ── Full page parse ───────────────────────────────────────────────────────────

def test_parse_page_count():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert len(listings) == 3


def test_parse_page_source():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert all(item.source == "immobiliare" for item in listings)


def test_parse_page_listing_type():
    listings = parse_search_page(_fixture("search_rent.html"), listing_type="rent")
    assert all(item.listing_type == "rent" for item in listings)


def test_parse_page_prices():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert [item.price for item in listings] == [1400.0, 1100.0, 850.0]


def test_parse_page_sizes():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert [item.size_sqm for item in listings] == [75.0, 55.0, 80.0]


def test_parse_page_rooms():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].rooms == 3
    assert listings[1].rooms == 2
    assert listings[2].rooms == 3


def test_parse_page_floors():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].floor == 3
    assert listings[1].floor == 0   # Piano terra
    assert listings[2].floor == 1


def test_parse_page_cities():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].city == "Milano"
    assert listings[1].city == "Roma"
    assert listings[2].city == "Torino"


def test_parse_page_zones():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].zone == "Navigli"
    assert listings[1].zone == "Prati"
    assert listings[2].zone == "Centro"


def test_parse_page_features():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert "ascensore" in listings[0].features
    assert "balcone" in listings[1].features
    assert "giardino" in listings[2].features


def test_parse_page_images():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].images[0].startswith("https://")
    assert listings[1].images == []
    assert listings[2].images[0].startswith("https://")


def test_parse_page_url_absolute():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert all(item.url.startswith("https://www.immobiliare.it/") for item in listings)


def test_parse_page_source_ids():
    listings = parse_search_page(_fixture("search_rent.html"))
    assert listings[0].source_id == "200111111"
    assert listings[1].source_id == "200222222"
    assert listings[2].source_id == "200333333"


# ── map_filter ────────────────────────────────────────────────────────────────

def test_map_filter_price():
    scraper = ImmobiliareScraper()
    fc = FilterConfig(price=PriceRange(min=700, max=1500))
    params = scraper.map_filter(fc)
    assert params["prezzoMinimo"] == "700"
    assert params["prezzoMassimo"] == "1500"


def test_map_filter_size():
    scraper = ImmobiliareScraper()
    fc = FilterConfig(size_sqm=SizeRange(min=50))
    params = scraper.map_filter(fc)
    assert params["superficieMinima"] == "50"
    assert "superficieMassima" not in params


def test_map_filter_rooms():
    scraper = ImmobiliareScraper()
    fc = FilterConfig(rooms=RoomRange(min=2, max=4))
    params = scraper.map_filter(fc)
    assert params["localiMinimo"] == "2"
    assert params["localiMassimo"] == "4"


def test_map_filter_empty():
    scraper = ImmobiliareScraper()
    assert scraper.map_filter(FilterConfig()) == {}


# ── _build_search_url ─────────────────────────────────────────────────────────

def test_build_url_rent_milan():
    scraper = ImmobiliareScraper()
    fc = FilterConfig(
        listing_type="rent",
        locations=[LocationFilter(city="Milano")],
    )
    url, lt = scraper._build_search_url(fc)
    assert "affitto" in url
    assert "milano" in url
    assert lt == "rent"


def test_build_url_sale():
    scraper = ImmobiliareScraper()
    url, lt = scraper._build_search_url(FilterConfig(listing_type="sale"))
    assert "vendita" in url
    assert lt == "sale"


def test_build_url_page_2():
    scraper = ImmobiliareScraper()
    url, _ = scraper._build_search_url(FilterConfig(), page=2)
    assert "pag=2" in url
