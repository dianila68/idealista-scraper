# Immobiliare.it — Scraper Research

## Approach Selected
HTML parsing via httpx + BeautifulSoup. Immobiliare.it renders search results server-side with structured HTML classes.

## Search URL Structure
```
https://www.immobiliare.it/{op}/appartamenti/{city_slug}/
```
- `op` = `affitto` (rent) | `vendita` (sale)
- City slug: lowercase, spaces → hyphens (e.g. `milano`)
- Pagination: `?pag={n}`

**Examples:**
```
https://www.immobiliare.it/affitto/appartamenti/milano/?prezzoMassimo=1500
https://www.immobiliare.it/vendita/appartamenti/roma/?superficieMinima=50
```

## Query Parameters
| Platonic field | Immobiliare param | Notes |
|---|---|---|
| `price.min` | `prezzoMinimo` | Integer EUR |
| `price.max` | `prezzoMassimo` | Integer EUR |
| `size_sqm.min` | `superficieMinima` | Integer m² |
| `size_sqm.max` | `superficieMassima` | Integer m² |
| `rooms.min` | `localiMinimo` | Integer |
| `rooms.max` | `localiMassimo` | Integer |
| `floor.exclude_ground` | `pianoMinimo=1` | Excludes ground floor |

## HTML Card Structure
Listings are in `<li class="nd-list__item in-searchLayoutItem">` tags with `data-listing-id` attribute:
```html
<li class="nd-list__item in-searchLayoutItem" data-listing-id="200111111">
  <div class="in-card__title">
    <a class="in-card__title-link" href="/annunci/affitto/appartamenti/milano/navigli/200111111-annuncio.htm">
      Appartamento in affitto, Milano - Navigli
    </a>
  </div>
  <div class="in-realEstateListCard__price">1.400 €/mese</div>
  <ul class="in-realEstateListCard__details">
    <li><span aria-label="superficie" class="in-icon--surface">75 m²</span></li>
    <li><span aria-label="locali" class="in-icon--rooms">3 locali</span></li>
    <li><span aria-label="piano" class="in-icon--floor">3° piano</span></li>
  </ul>
  <div class="in-card__location">Via Vigevano 10, Navigli, Milano</div>
  <ul class="in-features__list">
    <li class="in-features__item">Ascensore</li>
  </ul>
  <img class="in-card__gallery-image" src="..." />
</li>
```

## Pagination Detection
Next page exists if `<a class="in-pagination__item nd-button--ghost">` is present.

## Rate Limiting & Headers
- Standard browser User-Agent (desktop Chrome)
- Minimum 3s delay between requests
- No authentication required for search results
- Immobiliare has historically been more scraping-friendly than Idealista

## Field Mapping
| Immobiliare HTML | RawListing field | Parser |
|---|---|---|
| `data-listing-id` | `source_id` | li attribute |
| `in-card__title-link[href]` | `url` | prefix `https://www.immobiliare.it` |
| `in-card__title-link` text | `title` | element text |
| `in-realEstateListCard__price` text | `price` | `_parse_price()` |
| `span[aria-label="superficie"]` text | `size_sqm` | `_parse_sqm()` |
| `span[aria-label="locali"]` text | `rooms` | `_parse_rooms()` |
| `span[aria-label="piano"]` text | `floor` | `_parse_floor()` |
| `in-card__location` text | `city`, `zone` | `_split_location()`: "street, zone, city" |
| `in-card__gallery-image[src]` | `images[0]` | absolute URL |
| `in-features__list li` | `features` | lowercase list |

## Location Parsing
Immobiliare uses a comma-separated format: `{street}, {zone}, {city}`.
The last element is always the city; the second-to-last is the zone when 3+ parts are present.

## Notes
- Immobiliare.it has a public JSON API at `api.immobiliare.it` — worth investigating for v2 as it would be more stable than HTML scraping
- aria-label attributes on detail spans make parsing robust against CSS class changes
- `in-card__gallery-image` may be absent for listings without photos
