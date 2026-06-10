# idealista-scraper

> A self-hosted, three-tier real estate aggregator for the Italian property market.
> Scrapes Idealista.it, Immobiliare.it, and Subito.it, unifies listings through a
> platform-agnostic filter model, and delivers real-time push notifications to an
> Android companion app.

![License](https://img.shields.io/badge/license-Noncommercial%20Public%20v1.0-blue)
![Platform](https://img.shields.io/badge/platform-Android%20%7C%20Backend-green)
![Stack](https://img.shields.io/badge/stack-Python%20%2B%20FastAPI%20%7C%20Kotlin-informational)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Supported Platforms](#supported-platforms)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Android App Setup](#android-app-setup)
  - [Notification Setup](#notification-setup)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Filter Reference](#filter-reference)
  - [Platform Query Mapping](#platform-query-mapping)
- [API Reference](#api-reference)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**idealista-scraper** solves a common frustration: Italian property portals each have their
own search interface, alert systems, and result formats. This project provides a single,
unified layer that:

1. Periodically scrapes multiple portals on your behalf.
2. Normalises every listing into a common schema.
3. Evaluates each listing against your saved filter profiles.
4. Pushes a notification to your phone the moment a matching listing appears.

All components are self-hosted. No data leaves your infrastructure except for the FCM
push payload sent through Google's servers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER DEVICE (Android)                       │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                  idealista-scraper App                       │  │
│   │                                                              │  │
│   │  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐  │  │
│   │  │  Filter UI │  │ Listing Feed│  │  Notification Prefs  │  │  │
│   │  └─────┬──────┘  └──────┬──────┘  └──────────┬───────────┘  │  │
│   └────────┼────────────────┼─────────────────────┼─────────────┘  │
│            │  REST/JSON      │  REST/JSON           │ FCM Token Reg  │
└────────────┼────────────────┼─────────────────────┼────────────────┘
             │                │                      │
             ▼                ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND SERVER                               │
│                                                                     │
│  ┌──────────────┐   ┌───────────────┐   ┌────────────────────────┐ │
│  │  Filter API  │   │  Listings API │   │   Notification Service │ │
│  │  (CRUD)      │   │  (aggregated) │   │   (FCM dispatcher)     │ │
│  └──────┬───────┘   └───────┬───────┘   └──────────┬─────────────┘ │
│         │                   │                       │               │
│  ┌──────▼───────────────────▼───────────────────────▼─────────────┐ │
│  │                     Scraper Engine                              │ │
│  │                                                                 │ │
│  │  ┌──────────────┐ ┌────────────────────┐ ┌──────────────────┐  │ │
│  │  │ Idealista.it │ │  Immobiliare.it     │ │   Subito.it      │  │ │
│  │  │  Adapter     │ │  Adapter            │ │   Adapter        │  │ │
│  │  └──────┬───────┘ └─────────┬──────────┘ └────────┬─────────┘  │ │
│  └─────────┼───────────────────┼─────────────────────┼────────────┘ │
│            │                   │                      │              │
│  ┌─────────▼───────────────────▼──────────────────────▼────────────┐ │
│  │                  Unified Listing Store (PostgreSQL)              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
             │
             ▼  (outbound only)
┌────────────────────────┐
│  Firebase Cloud        │
│  Messaging (FCM)       │
└────────────────────────┘
```

---

## Features

### Scraper Engine
- Concurrent scraping of Idealista.it, Immobiliare.it, and Subito.it
- Configurable scrape interval per source (cron-based via APScheduler)
- Respectful request throttling and optional proxy rotation
- Deduplication across sources using a content-hash fingerprint
- Automatic retry with exponential back-off on HTTP errors
- Incremental scraping: only new or changed listings are stored

### Filter System
- Platform-agnostic filter model (see [Filter Reference](#filter-reference))
- Filters are stored server-side and keyed to a user profile
- Each filter profile is independently scheduled and evaluated
- Compound filters on any combination of fields

### Unified Listing Schema
- Canonical fields: `id`, `source`, `url`, `title`, `price`, `city`, `zone`,
  `size_sqm`, `rooms`, `bathrooms`, `floor`, `property_type`, `published_at`,
  `images[]`, `features[]`, `raw`
- The `raw` field preserves the original platform payload for debugging

### Android App
- Configure and manage filter profiles
- Browse the aggregated listing feed with infinite scroll
- Open original listing in-browser with one tap
- Manage notification subscriptions per filter profile
- Offline-capable: listings cached locally with Room

### Notification System
- Push notifications via Firebase Cloud Messaging (FCM)
- Payload includes: listing thumbnail URL, price, zone, size, direct link
- Per-filter notification toggle (mute without deleting a filter)
- Digest mode: batch notifications for high-frequency filters
- Notification history retained in-app for 30 days

---

## Supported Platforms

| Portal            | Rent | Sale | Notes                                            |
|-------------------|------|------|--------------------------------------------------|
| Idealista.it      | Yes  | Yes  | Primary target; requires JS rendering (Playwright) |
| Immobiliare.it    | Yes  | Yes  | REST-like API available; standard HTTP scraping  |
| Subito.it         | Yes  | Yes  | Classifieds; noisier data set; standard HTTP     |

---

## Tech Stack

### Backend
| Layer            | Technology                                      |
|------------------|-------------------------------------------------|
| Language         | Python 3.11+                                    |
| Web Framework    | FastAPI                                         |
| Scraping         | httpx + BeautifulSoup4 / Playwright             |
| Task Scheduling  | APScheduler                                     |
| Database         | PostgreSQL + Redis (job queue / dedup cache)    |
| ORM              | SQLAlchemy 2.x + Alembic                        |
| Push Dispatch    | firebase-admin (FCM HTTP v1 API)                |
| Containerisation | Docker + Docker Compose                         |

### Android App
| Layer            | Technology                                      |
|------------------|-------------------------------------------------|
| Language         | Kotlin                                          |
| UI               | Jetpack Compose                                 |
| Architecture     | MVVM + Unidirectional Data Flow                 |
| Networking       | Retrofit 2 + OkHttp                             |
| Local Storage    | Room (SQLite)                                   |
| Push             | Firebase Messaging SDK                          |
| Image Loading    | Coil                                            |
| DI               | Hilt                                            |

---

## Repository Structure

```
idealista-scraper/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (filters, listings, devices, auth)
│   │   ├── scrapers/       # Per-platform adapter implementations
│   │   │   ├── base.py         # Abstract BaseScraper interface
│   │   │   ├── idealista.py
│   │   │   ├── immobiliare.py
│   │   │   └── subito.py
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic (filter eval, dedup, FCM)
│   │   ├── scheduler/      # APScheduler job definitions
│   │   └── core/           # Config, DB session, logging
│   ├── alembic/            # Database migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── android/
│   ├── app/
│   │   └── src/main/
│   │       ├── java/com/idealista/scraper/
│   │       │   ├── ui/             # Composable screens and ViewModels
│   │       │   ├── data/           # Repository, Room DAOs, Retrofit service
│   │       │   ├── domain/         # Use cases and domain models
│   │       │   └── notifications/  # FCM service, notification builder
│   │       └── res/
│   └── build.gradle.kts
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
- Android Studio Hedgehog (2023.1.1) or newer
- A Firebase project with Cloud Messaging enabled (free tier is sufficient)
- Python 3.11+ (for local development without Docker)

### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/dianila68/idealista-scraper.git
   cd idealista-scraper
   ```

2. Copy and edit the environment file:
   ```bash
   cp .env.example .env
   # Edit .env — see Environment Variables section below
   ```

3. Place your Firebase service-account JSON at:
   ```
   backend/app/core/firebase-service-account.json
   ```
   This file is listed in `.gitignore` — never commit it.

4. Start all services:
   ```bash
   docker compose up -d
   ```

5. Run database migrations:
   ```bash
   docker compose exec backend alembic upgrade head
   ```

6. The API is now available at `http://localhost:8000`.
   Interactive docs: `http://localhost:8000/docs`

### Android App Setup

1. Open the `android/` directory in Android Studio.
2. In the Firebase Console, download `google-services.json` for your project
   and place it at `android/app/google-services.json`.
3. In `android/app/src/main/res/values/config.xml`, set your backend URL:
   ```xml
   <string name="backend_base_url">http://<your-server-ip>:8000</string>
   ```
4. Build and run on a device or emulator (API level 26+).

### Notification Setup

1. In the Firebase Console, enable **Cloud Messaging** for your project.
2. Download the server service-account JSON (Project Settings → Service Accounts
   → Generate new private key) and place it in the backend as described above.
3. The backend automatically registers device tokens when the Android app
   calls `POST /api/v1/devices/register`.
4. Notifications are dispatched after each scrape cycle whenever a new listing
   matches a saved filter.

---

## Configuration

### Environment Variables

All configuration is read from environment variables (`.env` file or host environment).

| Variable                   | Default                    | Description                                      |
|----------------------------|----------------------------|--------------------------------------------------|
| `DATABASE_URL`             | —                          | PostgreSQL DSN (`postgresql+asyncpg://...`)      |
| `REDIS_URL`                | `redis://redis:6379/0`     | Redis DSN for job queue and dedup cache          |
| `SCRAPE_INTERVAL_MINUTES`  | `30`                       | Global scrape interval in minutes                |
| `IDEALISTA_INTERVAL`       | *(inherits global)*        | Override interval for Idealista only             |
| `IMMOBILIARE_INTERVAL`     | *(inherits global)*        | Override interval for Immobiliare only           |
| `SUBITO_INTERVAL`          | *(inherits global)*        | Override interval for Subito only                |
| `REQUEST_DELAY_SECONDS`    | `3`                        | Minimum delay between requests to the same host  |
| `PROXY_LIST`               | —                          | Comma-separated `http://host:port` proxy URLs    |
| `FIREBASE_CREDENTIALS`     | `backend/app/core/firebase-service-account.json` | Path to FCM service account |
| `SECRET_KEY`               | —                          | JWT signing secret (min 32 chars)                |
| `LOG_LEVEL`                | `INFO`                     | Python log level                                 |

### Filter Reference

A filter profile is a JSON object stored server-side. All fields are optional;
omitting a field means "no constraint on this dimension".

```json
{
  "name": "Milan 2BR under 1500",
  "listing_type": "rent",
  "property_type": ["apartment"],
  "locations": [
    { "city": "Milano", "zones": ["Navigli", "Isola", "Porta Romana"] }
  ],
  "price": { "min": null, "max": 1500, "currency": "EUR" },
  "size_sqm": { "min": 50, "max": null },
  "rooms": { "min": 2, "max": null },
  "bathrooms": { "min": 1, "max": null },
  "floor": { "min": 1, "exclude_ground": true },
  "features": ["elevator", "parking"],
  "exclude_agencies": false,
  "sources": ["idealista", "immobiliare", "subito"],
  "notify": true,
  "notify_digest": false
}
```

### Platform Query Mapping

The abstract filter model is translated into each platform's native query parameters
by its adapter at scrape time.

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

---

## API Reference

All endpoints are prefixed with `/api/v1`. Authentication uses Bearer JWT tokens.

### Filters

| Method | Path              | Description                          |
|--------|-------------------|--------------------------------------|
| GET    | `/filters`        | List all filter profiles for caller  |
| POST   | `/filters`        | Create a new filter profile          |
| GET    | `/filters/{id}`   | Get a single filter profile          |
| PUT    | `/filters/{id}`   | Replace a filter profile             |
| PATCH  | `/filters/{id}`   | Update fields of a filter profile    |
| DELETE | `/filters/{id}`   | Delete a filter profile              |

### Listings

| Method | Path                  | Description                                              |
|--------|-----------------------|----------------------------------------------------------|
| GET    | `/listings`           | Paginated listing feed (optionally scoped to a filter)   |
| GET    | `/listings/{id}`      | Single listing detail                                    |
| GET    | `/listings/sources`   | Supported source platforms and their status              |

### Devices

| Method | Path                    | Description                               |
|--------|-------------------------|-------------------------------------------|
| POST   | `/devices/register`     | Register or refresh an FCM device token   |
| DELETE | `/devices/{token}`      | Unregister a device token                 |

### Auth

| Method | Path              | Description           |
|--------|-------------------|-----------------------|
| POST   | `/auth/register`  | Create a user account |
| POST   | `/auth/token`     | Obtain a JWT token    |
| POST   | `/auth/refresh`   | Refresh a JWT token   |

Full OpenAPI schema is served at `/docs` (Swagger UI) and `/redoc`.

---

## Contributing

Contributions are welcome under the terms of the project license.

1. Fork the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Follow the coding conventions of the component you are modifying
   (PEP 8 + type hints for Python; Kotlin official style guide for Android).
3. Write tests. Backend: pytest. Android: JUnit 4 + Robolectric.
4. Open a pull request against `main` with a clear description of the change
   and the motivation behind it.

**Adding a new scraper adapter:**
- Extend `backend/app/scrapers/base.py:BaseScraper`.
- Implement `fetch_listings(filter: FilterProfile) -> list[RawListing]`.
- Add the platform-to-abstract field mapping to the table in this README.
- Add integration tests using recorded HTTP fixtures (no live network in CI).

---

## License

Copyright (c) 2024 Luigi Delle (luigidelle05@gmail.com)

This project is released under the **Noncommercial Public License v1.0**.

You are free to use, study, modify, and redistribute this software for
**non-commercial purposes** at no charge.

**Any commercial use** — including but not limited to selling the software,
offering it as a hosted service, embedding it in a commercial product, or
using it to generate revenue — requires a separate commercial license obtained
from the copyright holder.

See the [LICENSE](./LICENSE) file for the complete terms.
For commercial licensing enquiries: luigidelle05@gmail.com
