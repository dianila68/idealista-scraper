# idealista-scraper

> Self-hosted backend that scrapes Italian real estate platforms, normalises
> listings into a unified schema, evaluates them against saved filter profiles,
> and delivers push notifications to any client that registers a device token.

[![Backend CI](https://github.com/dianila68/idealista-scraper/actions/workflows/backend.yml/badge.svg?branch=main)](https://github.com/dianila68/idealista-scraper/actions/workflows/backend.yml)
![License](https://img.shields.io/badge/license-Noncommercial%20Public%20v1.0-blue)
![Stack](https://img.shields.io/badge/stack-Python%203.11%20%2B%20FastAPI-informational)
![Platforms](https://img.shields.io/badge/sources-Idealista%20%7C%20Immobiliare.it%20%7C%20Subito.it-green)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [API Contract](#api-contract)
  - [Canonical Listing Schema](#canonical-listing-schema)
  - [Filter Schema](#filter-schema)
  - [Platform Query Mapping](#platform-query-mapping)
  - [REST Endpoints](#rest-endpoints)
- [Supported Platforms](#supported-platforms)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**idealista-scraper** is a backend service. It exposes a versioned REST API
that any client (mobile app, web dashboard, CLI) can consume. The backend:

1. Periodically scrapes Idealista.it, Immobiliare.it, and Subito.it.
2. Normalises every listing into a canonical JSON schema.
3. Deduplicates listings across platforms.
4. Evaluates listings against user-defined filter profiles.
5. Dispatches FCM push notifications for new matches.
6. Exposes all data via a documented REST API (`/api/v1/`).

All client concerns (UI, offline cache, notification rendering) live in
separate client repositories that consume this API.

---

## Architecture

```
  External Clients
  (Android app, web dashboard, CLI tools)
         │
         │  Bearer JWT · REST/JSON
         ▼
┌──────────────────────────────────────────────────┐
│                  FastAPI Backend                  │
│                                                  │
│  ┌────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  /filters  │  │  /listings  │  │  /devices │ │
│  │  /auth     │  │  /sources   │  │  /users   │ │
│  └─────┬──────┘  └──────┬──────┘  └─────┬─────┘ │
│        └────────────────┼───────────────┘        │
│                         │                        │
│              ┌──────────▼──────────┐             │
│              │   Scraper Engine    │             │
│              │                     │             │
│   ┌──────────┴──┐ ┌────────────┐ ┌─┴──────────┐ │
│   │ Idealista   │ │Immobiliare │ │  Subito.it  │ │
│   │  Adapter    │ │  Adapter   │ │  Adapter   │ │
│   └─────────────┘ └────────────┘ └────────────┘ │
│              │                                   │
│   ┌──────────▼──────────────────────────────┐   │
│   │         Deduplication Service            │   │
│   └──────────┬──────────────────────────────┘   │
│              │                                   │
│   ┌──────────▼──────────────────────────────┐   │
│   │      Notification Dispatcher (FCM)       │   │
│   └─────────────────────────────────────────┘   │
└──────────────────────┬───────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
   ┌─────▼──────┐              ┌──────▼──────┐
   │ PostgreSQL │              │    Redis     │
   │ (listings, │              │ (job queue,  │
   │  filters,  │              │  dedup cache)│
   │  users)    │              └─────────────┘
   └────────────┘
         │  (outbound only)
   ┌─────▼──────────────┐
   │ Firebase Cloud     │
   │ Messaging (FCM)    │
   └────────────────────┘
```

---

## API Contract

The API contract is the authoritative interface between this backend and any
client. Clients must implement against these schemas — not against internal
implementation details.

### Canonical Listing Schema

Every listing, regardless of source platform, is normalised into this shape:

```json
{
  "id": "uuid",
  "source": "idealista | immobiliare | subito",
  "source_id": "platform-native-id",
  "url": "https://...",
  "title": "string",
  "price": 1200.00,
  "currency": "EUR",
  "listing_type": "rent | sale",
  "property_type": "apartment | house | room | studio | ...",
  "city": "Milano",
  "zone": "Navigli",
  "size_sqm": 65,
  "rooms": 2,
  "bathrooms": 1,
  "floor": 3,
  "total_floors": 5,
  "features": ["elevator", "parking", "balcony"],
  "images": ["https://cdn.example.com/img1.jpg"],
  "published_at": "2024-01-15T10:30:00Z",
  "scraped_at": "2024-01-15T12:00:00Z",
  "content_hash": "sha256hex"
}
```

Fields absent in the source platform are `null`. The `raw` field (source
platform's original payload) is available at `GET /listings/{id}` for
authenticated users only.

### Filter Schema

A filter profile is the core user-defined query. All fields are optional;
omitting a field means no constraint on that dimension.

```json
{
  "id": "uuid",
  "name": "Milan 2BR under 1500",
  "listing_type": "rent",
  "property_type": ["apartment"],
  "locations": [
    { "city": "Milano", "zones": ["Navigli", "Isola", "Porta Romana"] }
  ],
  "price": { "min": null, "max": 1500 },
  "size_sqm": { "min": 50, "max": null },
  "rooms": { "min": 2, "max": null },
  "bathrooms": { "min": 1, "max": null },
  "floor": { "min": 1, "exclude_ground": true },
  "features": ["elevator"],
  "sources": ["idealista", "immobiliare", "subito"],
  "notify": true,
  "notify_digest": false,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Platform Query Mapping

The abstract filter is translated to each platform's native query parameters
by its adapter. This table is the canonical reference for adapter contributors.

| Abstract Field     | Idealista param(s)            | Immobiliare param(s)     | Subito param(s)          |
|--------------------|-------------------------------|--------------------------|--------------------------|
| `listing_type`     | `tipologia` (affitto/vendita) | `categoria`              | `tipo_annuncio`          |
| `property_type`    | `tipoPropiedad`               | `tipologia`              | `categoria`              |
| `city`             | `location` path segment       | `comune`                 | `c` (city code)          |
| `zones`            | `zone[]`                      | `zona`                   | `qk` (neighbourhood key) |
| `price.max`        | `precioMaximo`                | `prezzo_massimo`         | `max_price`              |
| `price.min`        | `precioMinimo`                | `prezzo_minimo`          | `min_price`              |
| `size_sqm.min`     | `superficieMin`               | `superficie_minima`      | `min_surface`            |
| `size_sqm.max`     | `superficieMax`               | `superficie_massima`     | `max_surface`            |
| `rooms.min`        | `habitacionesMin`             | `locali_minimi`          | `rooms_min`              |
| `floor.min`        | `pisoMin`                     | `piano_minimo`           | —                        |
| `exclude_ground`   | `conAscensor` (indirect)      | `escludi_piano_terra`    | —                        |
| `features`         | `caracteristicas[]`           | `caratteristiche[]`      | `features[]`             |

### REST Endpoints

Base path: `/api/v1/`. Authentication: `Authorization: Bearer <jwt>`.

Full interactive documentation at `/docs` (Swagger UI) and `/redoc`.

#### Auth

| Method | Path                      | Auth | Description                  |
|--------|---------------------------|------|------------------------------|
| POST   | `/auth/register`          | —    | Create account               |
| POST   | `/auth/token`             | —    | Login → JWT tokens           |
| POST   | `/auth/refresh`           | —    | Rotate refresh token         |
| POST   | `/auth/resend-verification` | — | Resend email verification    |
| GET    | `/auth/verify`            | —    | Verify email with token      |

#### Users

| Method | Path          | Auth | Description                    |
|--------|---------------|------|--------------------------------|
| GET    | `/users/me`   | Yes  | Get own profile                |
| DELETE | `/users/me`   | Yes  | Delete account + all data      |

#### Filters

| Method | Path              | Auth | Description                    |
|--------|-------------------|------|--------------------------------|
| GET    | `/filters`        | Yes  | List own filter profiles       |
| POST   | `/filters`        | Yes  | Create filter                  |
| GET    | `/filters/{id}`   | Yes  | Get one filter                 |
| PUT    | `/filters/{id}`   | Yes  | Replace filter                 |
| PATCH  | `/filters/{id}`   | Yes  | Partial update                 |
| DELETE | `/filters/{id}`   | Yes  | Delete filter                  |

#### Listings

| Method | Path                  | Auth | Description                              |
|--------|-----------------------|------|------------------------------------------|
| GET    | `/listings`           | Yes  | Paginated feed (cursor-based)            |
| GET    | `/listings/{id}`      | Yes  | Full listing detail (includes `raw`)     |
| GET    | `/listings/sources`   | Yes  | Platform status + last scrape time       |

Query params for `GET /listings`:
- `filter_id` — scope to a saved filter
- `source` — `idealista` / `immobiliare` / `subito`
- `cursor` / `per_page` (default 20, max 100)
- `sort` — `price_asc`, `price_desc`, `newest` (default)
- `suggest_roommate` — `true`: include apartment suggestions for single-room searches

#### Devices

| Method | Path                  | Auth | Description                         |
|--------|-----------------------|------|-------------------------------------|
| POST   | `/devices/register`   | Yes  | Register/refresh FCM device token   |
| DELETE | `/devices/{token}`    | Yes  | Unregister device token             |

---

## Supported Platforms

| Portal            | Rent | Sale | Scraping Method                         |
|-------------------|------|------|-----------------------------------------|
| Idealista.it      | Yes  | Yes  | Playwright (JS rendering required)      |
| Immobiliare.it    | Yes  | Yes  | httpx + JSON API                        |
| Subito.it         | Yes  | Yes  | httpx + HTML/JSON; extra noise filtering|

---

## Tech Stack

| Layer              | Technology                                        |
|--------------------|---------------------------------------------------|
| Language           | Python 3.11+                                      |
| Web framework      | FastAPI + Uvicorn                                 |
| Async ORM          | SQLAlchemy 2.x (async) + asyncpg                  |
| Migrations         | Alembic                                           |
| Validation         | Pydantic v2                                       |
| Auth               | python-jose (JWT) + passlib (bcrypt)              |
| Scraping           | httpx (Immobiliare, Subito) + Playwright (Idealista) |
| Scheduling         | APScheduler                                       |
| Cache / Queue      | Redis                                             |
| Push notifications | firebase-admin (FCM HTTP v1)                      |
| Testing            | pytest + pytest-asyncio + httpx (async test client)|
| Linting / Types    | ruff + mypy                                       |
| Containerisation   | Docker + Docker Compose                           |

---

## Repository Structure

```
idealista-scraper/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── filters.py
│   │   │       ├── listings.py
│   │   │       └── devices.py
│   │   ├── core/             # Config, DB session, security
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas (the API contract)
│   │   │   ├── listing.py
│   │   │   ├── filter.py
│   │   │   ├── user.py
│   │   │   └── device.py
│   │   ├── scrapers/         # Platform adapters
│   │   │   ├── base.py
│   │   │   ├── idealista.py
│   │   │   ├── immobiliare.py
│   │   │   └── subito.py
│   │   ├── services/         # Business logic
│   │   │   ├── dedup.py
│   │   │   ├── filter_eval.py
│   │   │   └── notifications.py
│   │   ├── scheduler/        # APScheduler job definitions
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   │   ├── fixtures/         # Recorded HTTP responses (no live network in CI)
│   │   │   ├── idealista/
│   │   │   ├── immobiliare/
│   │   │   └── subito/
│   │   ├── test_auth.py
│   │   ├── test_filters.py
│   │   ├── test_listings.py
│   │   └── test_scrapers.py
│   ├── Dockerfile
│   └── requirements.txt
├── docs/
│   ├── adr/                  # Architecture decision records
│   └── scraper-research/     # Per-platform research notes
├── .github/
│   └── workflows/
│       └── backend.yml
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## Getting Started

### Prerequisites
- Docker 24+ and Docker Compose v2
- Python 3.11+ (for local development without Docker)
- A Firebase project with Cloud Messaging enabled (free tier sufficient)

### Setup

```bash
git clone https://github.com/dianila68/idealista-scraper.git
cd idealista-scraper
cp .env.example .env          # fill in your values
# place firebase-service-account.json in backend/app/core/ (gitignored)
docker compose up -d
docker compose exec backend alembic upgrade head
```

API available at `http://localhost:8000` · Docs at `http://localhost:8000/docs`

---

## Configuration

| Variable                  | Default                | Description                                     |
|---------------------------|------------------------|-------------------------------------------------|
| `DATABASE_URL`            | —                      | PostgreSQL DSN (`postgresql+asyncpg://...`)     |
| `REDIS_URL`               | `redis://redis:6379/0` | Redis DSN                                       |
| `SECRET_KEY`              | —                      | JWT signing secret (min 32 chars)               |
| `SCRAPE_INTERVAL_MINUTES` | `30`                   | Global scrape interval                          |
| `IDEALISTA_INTERVAL`      | *(inherits)*           | Override for Idealista                          |
| `IMMOBILIARE_INTERVAL`    | *(inherits)*           | Override for Immobiliare                        |
| `SUBITO_INTERVAL`         | *(inherits)*           | Override for Subito                             |
| `REQUEST_DELAY_SECONDS`   | `3`                    | Minimum delay between requests per host         |
| `PROXY_LIST`              | —                      | Comma-separated `http://host:port` proxy URLs   |
| `FIREBASE_CREDENTIALS`    | `backend/app/core/firebase-service-account.json` | FCM service account path |
| `ROOMMATE_PRICE_MULTIPLIER` | `1.8`               | Budget multiplier for roommate suggestions      |
| `ALLOWED_ORIGINS`         | `*`                    | CORS allowed origins                            |
| `LOG_LEVEL`               | `INFO`                 | Python log level                                |

---

## Contributing

See open issues at [github.com/dianila68/idealista-scraper/issues](https://github.com/dianila68/idealista-scraper/issues).

To add a scraper adapter: extend `backend/app/scrapers/base.py:BaseScraper`,
implement `fetch_listings()` and `map_filter()`, add recorded HTTP fixtures
under `tests/fixtures/<platform>/`, and add the platform to the mapping table
in this README.

---

## License

Copyright (c) 2024 Luigi Delle — luigidelle05@gmail.com

**Noncommercial Public License v1.0** — free for non-commercial use.
Commercial use requires a paid license from the copyright holder.
See [LICENSE](./LICENSE) for full terms.
