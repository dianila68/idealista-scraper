# Idealista.it — Scraper Research

## Approach Selected
HTML parsing via httpx + BeautifulSoup (no Playwright required for search pages).

## Search URL Structure
```
https://www.idealista.it/{op}/{city_slug}-{city_slug}/
```
- `op` = `affitto-case` (rent) | `vendita-case` (sale)
- City slug: lowercase, spaces → hyphens (e.g. `milano-milano`)
- Pagination: `?pagina={n}` appended to base path

**Examples:**
```
https://www.idealista.it/affitto-case/milano-milano/?precioMin=800&precioMax=1500
https://www.idealista.it/vendita-case/roma-roma/?superficieMin=50
```

## Query Parameters
| Platonic field | Idealista param | Notes |
|---|---|---|
| `price.min` | `precioMin` | Integer EUR |
| `price.max` | `precioMax` | Integer EUR |
| `size_sqm.min` | `superficieMin` | Integer m² |
| `size_sqm.max` | `superficieMax` | Integer m² |
| `rooms.min` | `habitacionesMin` | Integer |
| `rooms.max` | `habitacionesMax` | Integer |
| `floor.exclude_ground` | `plantaBaja=false` | String boolean |

## HTML Card Structure
Listings are rendered as `<article class="item">` tags:
```html
<article class="item" data-element-id="100123456">
  <a class="item-link" href="/immobile/100123456/">
    <span class="item-price">1.200 €/mese</span>
    <span class="item-rooms">2 locali</span>
    <span class="item-size">65 m²</span>
    <span class="item-floor">2° piano</span>
    <span class="item-address">Via Torino, Milano</span>
    <h3 class="item-title">Appartamento in affitto a Milano, Navigli</h3>
    <img class="item-image" src="..." />
  </a>
  <ul class="item-features">
    <li>Ascensore</li>
    ...
  </ul>
</article>
```

## Pagination Detection
Next page exists if `<a class="icon-arrow-right-after">` is present in the page.

## Rate Limiting & Headers
- User-Agent: mobile browser string avoids some bot detection
- Minimum 3s delay between requests (configurable via `REQUEST_DELAY_SECONDS`)
- No authentication required for search results
- robots.txt: review periodically; scraping for personal use only

## Field Mapping
| Idealista HTML | RawListing field | Parser |
|---|---|---|
| `data-element-id` | `source_id` | article attribute |
| `item-link[href]` | `url` | prefix `https://www.idealista.it` |
| `item-price` text | `price` | `_parse_price()` strips `€/mese`, `.` thousands |
| `item-size` text | `size_sqm` | `_parse_size()` extracts numeric |
| `item-rooms` text | `rooms` | `_parse_rooms()` extracts first int |
| `item-floor` text | `floor` | `_parse_floor()` maps "Piano terra"→0 |
| `item-address` text | `city` | last comma-separated part |
| `item-title` text | `zone` | text after "a {City}, " |
| `item-image[src]` | `images[0]` | absolute URL |
| `ul.item-features li` | `features` | lowercase list |

## Notes
- Idealista is Spanish-owned; param names are in Spanish (precio, superficie, habitaciones)
- City slug format: `{city}-{city}` (city name repeated, e.g. `roma-roma`)
- Zone is extracted from the listing title, not a structured field
- M9 Playwright option: if search pages become fully JS-rendered, upgrade to Playwright
