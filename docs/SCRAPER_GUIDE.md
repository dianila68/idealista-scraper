# Adding a New Scraper Source

This guide explains how to add a new Italian real-estate platform to the aggregator in 5 steps.
All scraper adapters live in `backend/app/scrapers/`.

---

## Step 1 — Create the adapter module

Create `backend/app/scrapers/<source_name>.py`.

```python
from app.scrapers.base import BaseScraper, register
from app.schemas.filter import FilterConfig
from app.schemas.listing import RawListing

@register
class MySiteScraper(BaseScraper):
    source = "mysite"          # must be unique across all adapters
    ...
```

The `@register` decorator adds the class to the global registry so the scheduler and API
can find it by name.

---

## Step 2 — Implement `map_filter()`

Translate a `FilterConfig` into the platform's native query parameters (a plain `dict[str, str]`).

```python
def map_filter(self, fc: FilterConfig) -> dict[str, str]:
    params: dict[str, str] = {}
    if fc.price.min is not None:
        params["price_from"] = str(int(fc.price.min))
    if fc.price.max is not None:
        params["price_to"] = str(int(fc.price.max))
    # ... size_sqm, rooms, floor, etc.
    return params
```

**FilterConfig platonic fields** (all optional):

| Field | Type | Meaning |
|---|---|---|
| `price.min` / `price.max` | `float \| None` | EUR price bounds |
| `size_sqm.min` / `size_sqm.max` | `float \| None` | m² bounds |
| `rooms.min` / `rooms.max` | `int \| None` | room count bounds |
| `floor.min` | `int \| None` | minimum floor |
| `floor.exclude_ground` | `bool` | skip ground-floor listings |
| `listing_type` | `"rent" \| "sale" \| None` | operation type |
| `locations` | `list[LocationFilter]` | each has `.city` and optional `.zone` |
| `features_required` | `list[str]` | e.g. `["ascensore", "giardino"]` |
| `sources` | `list[str] \| None` | restrict to named sources |

---

## Step 3 — Implement `normalize()`

Convert a **single** platform-native record (a `dict` of raw parsed fields) into a `RawListing`.
This is the explicit schema boundary: all platform-specific knowledge lives here.

```python
def normalize(self, raw_data: dict) -> RawListing:
    return RawListing(
        source="mysite",
        source_id=str(raw_data["id"]),
        url=raw_data["url"],
        title=raw_data.get("title"),
        price=_parse_price(raw_data.get("price_text", "")),
        listing_type=raw_data.get("listing_type"),
        property_type="apartment",
        city=raw_data.get("city"),
        zone=raw_data.get("zone"),
        location_precision="zone",   # see below
        province=raw_data.get("province"),
        size_sqm=raw_data.get("size_sqm"),
        rooms=raw_data.get("rooms"),
        floor=raw_data.get("floor"),
        features=raw_data.get("features", []),
        images=raw_data.get("images", []),
        raw=raw_data,
    )
```

### `location_precision` values

| Value | Use when | Geocoder behaviour |
|---|---|---|
| `"street"` | Full street address available (e.g. Immobiliare.it) | Uses city-level geocode directly |
| `"zone"` | Neighbourhood / district available (e.g. Idealista, Subito) | Tries `{zone}, {city}, Italy` → falls back to `{city}, Italy` |
| `"city"` | Only city name available | Skips zone query, goes straight to `{city}, Italy` |

On the map, `"zone"` and `"city"` listings appear as **hollow markers**; `"street"` listings appear as **filled markers**.

### `province`

Set to the two-letter ISO province code (`"MI"`, `"RM"`, `"NA"` …) when the source provides it.
Used for future province-level map clustering. Leave `None` if the source doesn't expose it.

---

## Step 4 — Implement `fetch_listings()`

Orchestrate HTTP calls using `self._get(url, ...)` (retrying, rate-limited), then call
`parse_search_page()` (or inline HTML parsing) to produce a list of `RawListing` objects.

```python
async def fetch_listings(self, fc: FilterConfig) -> list[RawListing]:
    results: list[RawListing] = []
    params = self.map_filter(fc)

    for page in range(1, 4):      # cap at 3 pages
        url = self._build_search_url(fc, page)
        try:
            resp = await self._get(url, params=params)
        except Exception:
            break

        page_listings = parse_search_page(resp.text, fc.listing_type or "rent")
        if not page_listings:
            break
        results.extend(page_listings)

        if not _has_next_page(resp.text):
            break

    return results
```

`_get()` from `BaseScraper` handles:
- Tenacity retry (3 attempts, exponential back-off)
- `asyncio.sleep(self._delay)` before every request (default 3 s)
- Optional proxy rotation (pass `proxies=[...]` to the constructor)

---

## Step 5 — Add HTML fixture + unit tests

1. Save a sample search-results HTML page to `backend/tests/fixtures/<source>/search_rent.html`.
2. Create `backend/tests/test_scraper_<source>.py` — test every parser function in isolation,
   plus a full page-parse test using the fixture.

**Minimum test coverage checklist:**
- `_parse_price()` — monthly, sale, empty/invalid
- `_parse_floor()` — Piano terra → 0, numbered, basement/interrato
- `_parse_location()` / `_split_location()` — full, partial, no zone
- `normalize()` — verify `location_precision` and `province` are set
- `map_filter()` — price range, size range, rooms, empty filter
- `_build_search_url()` — rent/sale, page 2, city slug

No network calls in tests — use the HTML fixture and mock `self._get()` if needed.

---

## Platonic schema (`RawListing`) — full field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `source` | `str` | yes | Registry key, e.g. `"idealista"` |
| `source_id` | `str` | yes | Platform-native listing ID |
| `url` | `str` | yes | Canonical listing URL |
| `title` | `str \| None` | — | Listing title |
| `price` | `float \| None` | — | EUR; monthly for rent, total for sale |
| `currency` | `str` | — | Default `"EUR"` |
| `listing_type` | `"rent" \| "sale" \| None` | — | |
| `property_type` | `str \| None` | — | `"apartment"`, `"house"`, etc. |
| `city` | `str \| None` | — | City name (Italian) |
| `zone` | `str \| None` | — | Neighbourhood / district |
| `location_precision` | `str` | — | `"street"`, `"zone"` (default), or `"city"` |
| `province` | `str \| None` | — | Two-letter ISO code, e.g. `"MI"` |
| `size_sqm` | `float \| None` | — | Surface area in m² |
| `rooms` | `int \| None` | — | Number of rooms (locali) |
| `bathrooms` | `int \| None` | — | Number of bathrooms |
| `floor` | `int \| None` | — | Floor number; 0 = ground, −1 = basement |
| `total_floors` | `int \| None` | — | Total floors in building |
| `features` | `list[str]` | — | Lowercase amenities list |
| `images` | `list[str]` | — | Absolute image URLs |
| `raw` | `dict` | — | Original parsed data for debugging |
| `published_at` | `datetime \| None` | — | Platform-reported publish date |

The `dedup` service converts `RawListing` → ORM `Listing` via `upsert_listing()`.
`filter_eval.matches()` evaluates a stored `Listing` against a `FilterConfig` — no DB required.
