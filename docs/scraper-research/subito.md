# Subito.it — Scraper Research

## Approach Selected
HTML parsing via httpx + BeautifulSoup. Subito.it renders listings server-side.

## Search URL Structure
```
https://www.subito.it/annunci/immobili/{op}/{city_slug}-citta/
```
- `op` = `affitto` (rent) | `vendita` (sale)
- City slug: lowercase, spaces → hyphens + `-citta` suffix (e.g. `milano-citta`)
- Pagination: `?o={n}` (offset-based, starts at 2 for page 2)

**Examples:**
```
https://www.subito.it/annunci/immobili/affitto/milano-citta/?ps=600&pe=1400
https://www.subito.it/annunci/immobili/vendita/roma-citta/?sqs=50
```

## Query Parameters
| Platonic field | Subito param | Notes |
|---|---|---|
| `price.min` | `ps` | Integer EUR (price start) |
| `price.max` | `pe` | Integer EUR (price end) |
| `size_sqm.min` | `sqs` | Integer m² (size start) |
| `size_sqm.max` | `sqe` | Integer m² (size end) |
| `rooms.min` | `rms` | Integer (rooms min start) |

## HTML Card Structure
Listings are in `<div class="item-card">` divs with `data-item-id` attribute:
```html
<div class="item-card" data-item-id="300111111">
  <a class="item-card__body" href="/annunci/immobili/affitto/milano-citta/300111111-appartamento-navigli.htm">
    <h2 class="item-card__title">Appartamento 3 locali in affitto - Navigli, Milano</h2>
    <span class="item-card__price">1.300 €</span>
    <ul class="item-card__info-list">
      <li class="item-card__info-item">
        <span class="item-card__info-label">Superficie</span>
        <span class="item-card__info-value">70 m²</span>
      </li>
      <li class="item-card__info-item">
        <span class="item-card__info-label">Locali</span>
        <span class="item-card__info-value">3</span>
      </li>
      <li class="item-card__info-item">
        <span class="item-card__info-label">Piano</span>
        <span class="item-card__info-value">2</span>
      </li>
      <li class="item-card__info-item">
        <span class="item-card__info-label">Bagni</span>
        <span class="item-card__info-value">1</span>
      </li>
    </ul>
    <span class="item-card__location">Navigli, Milano (MI)</span>
    <img src="..." class="item-card__img" />
  </a>
</div>
```

## Pagination Detection
Next page exists if `<a class="pagination__next">` is present.

## Rate Limiting & Headers
- Mobile Safari User-Agent avoids some detection
- Minimum 3s delay between requests
- No authentication required for search results
- Subito is a Classifieds platform (Subito = "immediately" in Italian) — also lists non-property items

## Data Quality Notes
- **Noise**: Subito mixes all classified categories; the `/annunci/immobili/` path filters to real estate only
- **Deduplication**: same property often re-posted multiple times with different IDs; content_hash deduplication handles this
- **Price format**: Subito shows price as `1.300 €` without `/mese` suffix (price is per month for rentals)
- **Bathrooms**: Subito exposes bathroom count unlike Idealista

## Field Mapping
| Subito HTML | RawListing field | Parser |
|---|---|---|
| `data-item-id` | `source_id` | div attribute |
| `item-card__body[href]` | `url` | prefix `https://www.subito.it` |
| `item-card__title` text | `title` | element text |
| `item-card__price` text | `price` | `_parse_price()` strips `.` thousands |
| `info-label="Superficie"` value | `size_sqm` | `_parse_number()` |
| `info-label="Locali"` value | `rooms` | `_parse_number()` cast to int |
| `info-label="Piano"` value | `floor` | `_parse_floor()` |
| `info-label="Bagni"` value | `bathrooms` | `_parse_number()` cast to int |
| `item-card__location` text | `city`, `zone` | `_parse_location()`: "Zone, City (Prov)" |
| `item-card__img[src]` | `images[0]` | absolute URL |

## Location Parsing
Subito uses format: `{Zone}, {City} ({Province code})`.
`_parse_location()` strips the province code `(MI)` and splits into `(city, zone)`.

## Notes
- Subito doesn't expose features/amenities list in search results — only in listing detail pages
- Price is always shown as total monthly amount, not per m²
- Province code (MI, RM, NA, etc.) is always present and can be used for province-level filtering in future
