"""Unit tests for filter evaluation — no database required."""
from app.schemas.filter import (
    FilterConfig,
    FloorFilter,
    LocationFilter,
    PriceRange,
    RoomRange,
    SizeRange,
)
from app.schemas.listing import RawListing
from app.services.filter_eval import matches, matching_filter_ids


def listing(**kwargs) -> RawListing:
    defaults = dict(
        source="idealista",
        source_id="1",
        url="https://example.com/1",
        listing_type="rent",
        property_type="apartment",
        city="Milano",
        zone="Navigli",
        price=1200.0,
        size_sqm=65.0,
        rooms=2,
        bathrooms=1,
        floor=2,
        features=["elevator"],
    )
    defaults.update(kwargs)
    return RawListing(**defaults)


def fc(**kwargs) -> FilterConfig:
    return FilterConfig(**kwargs)


# ── Price ────────────────────────────────────────────────────────────────────

def test_price_within_range():
    assert matches(listing(price=1000), fc(price=PriceRange(min=500, max=1500)))


def test_price_above_max():
    assert not matches(listing(price=2000), fc(price=PriceRange(max=1500)))


def test_price_below_min():
    assert not matches(listing(price=300), fc(price=PriceRange(min=500)))


def test_null_price_passes_any_constraint():
    assert matches(listing(price=None), fc(price=PriceRange(min=500, max=1500)))


# ── Rooms ────────────────────────────────────────────────────────────────────

def test_rooms_min_satisfied():
    assert matches(listing(rooms=3), fc(rooms=RoomRange(min=2)))


def test_rooms_min_not_satisfied():
    assert not matches(listing(rooms=1), fc(rooms=RoomRange(min=2)))


def test_rooms_null_passes():
    assert matches(listing(rooms=None), fc(rooms=RoomRange(min=2)))


# ── Size ─────────────────────────────────────────────────────────────────────

def test_size_within_range():
    assert matches(listing(size_sqm=70), fc(size_sqm=SizeRange(min=50, max=100)))


def test_size_too_small():
    assert not matches(listing(size_sqm=40), fc(size_sqm=SizeRange(min=50)))


# ── Location ─────────────────────────────────────────────────────────────────

def test_city_match():
    assert matches(listing(city="Milano"), fc(locations=[LocationFilter(city="Milano")]))


def test_city_no_match():
    assert not matches(listing(city="Roma"), fc(locations=[LocationFilter(city="Milano")]))


def test_zone_match():
    locs = [LocationFilter(city="Milano", zones=["Navigli", "Isola"])]
    assert matches(listing(city="Milano", zone="Navigli"), fc(locations=locs))


def test_zone_no_match():
    locs = [LocationFilter(city="Milano", zones=["Isola"])]
    assert not matches(listing(city="Milano", zone="Navigli"), fc(locations=locs))


def test_zone_null_passes_zone_constraint():
    locs = [LocationFilter(city="Milano", zones=["Isola"])]
    assert matches(listing(city="Milano", zone=None), fc(locations=locs))


# ── Floor ────────────────────────────────────────────────────────────────────

def test_floor_min():
    assert matches(listing(floor=3), fc(floor=FloorFilter(min=2)))
    assert not matches(listing(floor=1), fc(floor=FloorFilter(min=2)))


def test_exclude_ground():
    assert not matches(listing(floor=0), fc(floor=FloorFilter(exclude_ground=True)))
    assert matches(listing(floor=1), fc(floor=FloorFilter(exclude_ground=True)))


# ── Features ─────────────────────────────────────────────────────────────────

def test_required_feature_present():
    assert matches(listing(features=["elevator", "parking"]), fc(features=["elevator"]))


def test_required_feature_missing():
    assert not matches(listing(features=["parking"]), fc(features=["elevator"]))


def test_feature_case_insensitive():
    assert matches(listing(features=["Elevator"]), fc(features=["elevator"]))


# ── Source filter ─────────────────────────────────────────────────────────────

def test_source_included():
    assert matches(listing(source="idealista"), fc(sources=["idealista", "immobiliare"]))


def test_source_excluded():
    assert not matches(listing(source="subito"), fc(sources=["idealista", "immobiliare"]))


# ── Listing type ──────────────────────────────────────────────────────────────

def test_listing_type_match():
    assert matches(listing(listing_type="rent"), fc(listing_type="rent"))


def test_listing_type_no_match():
    assert not matches(listing(listing_type="sale"), fc(listing_type="rent"))


# ── matching_filter_ids ───────────────────────────────────────────────────────

def test_matching_filter_ids():
    filters = [
        ("filter-1", fc(price=PriceRange(max=1500))),
        ("filter-2", fc(price=PriceRange(max=1000))),
    ]
    ids = matching_filter_ids(listing(price=1200), filters)
    assert ids == ["filter-1"]


def test_matching_filter_ids_multiple():
    filters = [
        ("filter-1", fc(price=PriceRange(max=1500))),
        ("filter-2", fc(price=PriceRange(max=1300))),
    ]
    ids = matching_filter_ids(listing(price=1200), filters)
    assert set(ids) == {"filter-1", "filter-2"}
