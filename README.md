# idealista-scraper

> Self-hosted backend that scrapes Italian real estate platforms, normalises
> listings into a unified schema, evaluates them against saved filter profiles,
> and delivers push notifications to any client that registers a device token.
> A React + Vite web frontend is included on this branch.

![License](https://img.shields.io/badge/license-Noncommercial%20Public%20v1.0-blue)
![Stack](https://img.shields.io/badge/stack-Python%203.11%20%2B%20FastAPI-informational)
![Frontend](https://img.shields.io/badge/frontend-React%2019%20%2B%20Vite-61dafb)
![Platforms](https://img.shields.io/badge/sources-Idealista%20%7C%20Immobiliare.it%20%7C%20Subito.it-green)

---

## Table of Contents

- [Overview](#overview)
- [Frontend Tutorial](#frontend-tutorial)
  - [Prerequisites](#prerequisites-1)
  - [Quick Start (Docker — full stack)](#quick-start-docker--full-stack)
  - [Quick Start (local dev)](#quick-start-local-dev)
  - [Pages & Features](#pages--features)
  - [Project Structure](#frontend-project-structure)
  - [Environment Variables](#frontend-environment-variables)
  - [Building for Production](#building-for-production)
  - [How Auth Works](#how-auth-works)
  - [Adding a New Page](#adding-a-new-page)
- [Architecture](#architecture)
- [API Contract](#api-contract)
  - [Canonical Listing Schema](#canonical-listing-schema)
  - [Filter Schema](#filter-schema)
  - [Platform Query Mapping](#platform-query-mapping)
  - [REST Endpoints](#rest-endpoints)
- [Supported Platforms](#supported-platforms)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started (Backend only)](#getting-started)
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

This branch adds a **React 19 + Vite** web frontend that consumes the API
and provides a full browser interface: listing feed, interactive map, saved
filters, and user profile management.

---

## Frontend Tutorial

### Prerequisites

- **Node.js 18+** and **npm 9+** (check with `node -v && npm -v`)
- A running backend (see [Getting Started](#getting-started)) **or** Docker

---

### Quick Start (Docker — full stack)

The fastest way to run everything is with Docker Compose:

```bash
# 1. Clone the repo and switch to this branch
git clone https://github.com/dianila68/idealista-scraper.git
cd idealista-scraper
git checkout claude/react-frontend

# 2. Create an .env file with a secret key
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env

# 3. Start all services (backend + DB + Redis + frontend)
docker compose up --build -d

# 4. Apply database migrations
docker compose exec backend alembic upgrade head
```

Services:

| Service    | URL                          |
|------------|------------------------------|
| Frontend   | http://localhost:5173         |
| Backend API| http://localhost:8000         |
| API docs   | http://localhost:8000/docs    |
| MailHog (dev email) | `docker compose --profile dev up` → http://localhost:8025 |

Open http://localhost:5173, register an account, verify your email via MailHog,
then log in to start browsing.

---

### Quick Start (local dev)

If the backend is already running at `http://localhost:8000`:

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Configure the API URL (optional — defaults to localhost:8000)
cp .env.example .env
# Edit VITE_API_URL if your backend is on a different host/port

# 3. Start the dev server with hot-module replacement
npm run dev
```

The app opens at **http://localhost:5173**. The Vite dev server proxies all
`/api/` requests to the backend automatically, so no CORS issues during
development.

---

### Pages & Features

#### `/register` — Create an account
Fill in email + password (min 8 characters). You will receive a verification
email. In local dev with MailHog, the email appears at http://localhost:8025.
Click the link in the email to verify your account before logging in.

#### `/login` — Sign in
Enter your verified email and password to receive a JWT token pair. Tokens are
stored in `localStorage`; the Axios client automatically attaches the bearer
token to every request and refreshes it transparently when it expires (401
→ refresh → retry).

#### `/forgot-password` and `/reset-password` — Password reset
Enter your email on the forgot-password page. A reset link is sent (check
MailHog in dev). Click the link — it lands on `/reset-password?token=…` where
you enter a new password.

#### `/listings` — Listing feed
Browse all scraped listings in a responsive card grid with infinite scroll.

Filter bar at the top lets you narrow by:
- **Città** — city name (e.g. `Milano`)
- **Tipo** — `affitto` (rent) or `vendita` (sale)
- **Fonte** — `idealista`, `immobiliare`, or `subito`
- **Prezzo min/max** — price range in EUR
- **Superficie min** — minimum surface in m²
- **Locali min** — minimum number of rooms

Hit **Filtra** to apply, **Reset** to clear. Scrolling to the bottom loads the
next page (cursor-based pagination, 24 items per page). Each card links
directly to the original listing on the source website.

#### `/map` — Interactive map
A full-screen Leaflet map centred on Italy showing all geocoded listings as
circle markers:

| Colour | Price |
|--------|-------|
| 🟢 Green  | < €800/month |
| 🟡 Yellow | €800–€1500 |
| 🔴 Red    | > €1500 |

**Hollow** circles indicate approximate locations (zone- or city-level
geocoding). **Filled** circles are street-precise. Click any marker for a
popup with title, price, location, and a link to the listing.

> **Note:** Listings only appear on the map after the geocoder has run. The
> geocoder calls Nominatim (OpenStreetMap) asynchronously after each scrape
> cycle. An empty map is normal until the first geocoding pass completes.

#### `/filters` — Saved filters
Create named filter profiles that the backend evaluates against every new
listing to trigger push notifications.

Click **+ Nuovo filtro** to open a form:

| Field | Description |
|-------|-------------|
| Nome | Required label for this filter |
| Città | Limit to a specific city |
| Tipo | `affitto` or `vendita` |
| Prezzo min/max | Price range |
| Superficie min | Minimum m² |
| Locali min | Minimum rooms |

Save the filter. The backend will send an FCM push notification to your
registered devices whenever a new listing matches this profile.

To delete a filter, click **Elimina** on its card.

#### `/profile` — User profile
- **Timezone** — change your display timezone from a dropdown.
- **Cambia password** — enter your current password, then the new one twice.
- **Elimina account** — permanently deletes your account and all associated
  data. Requires a confirmation click.
- **Esci** — logs you out and clears stored tokens.

---

### Frontend Project Structure

```
frontend/
├── src/
│   ├── api/               # Typed wrappers around the backend REST API
│   │   ├── client.ts      # Axios instance: base URL, JWT interceptor, auto-refresh
│   │   ├── auth.ts        # register, login, forgotPassword, resetPassword, me, updateMe
│   │   ├── listings.ts    # list (paginated), map (geocoded points)
│   │   └── filters.ts     # list, create, delete
│   ├── components/
│   │   ├── ListingCard.tsx   # Single listing card with image, price, tags
│   │   ├── Navbar.tsx        # Top navigation bar (auth-aware)
│   │   └── ProtectedRoute.tsx # Redirects to /login if not authenticated
│   ├── hooks/
│   │   └── useAuth.ts     # useMe(), useLogin(), useLogout() — TanStack Query wrappers
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Register.tsx
│   │   ├── ForgotPassword.tsx
│   │   ├── ResetPassword.tsx
│   │   ├── Listings.tsx   # Infinite-scroll feed + filter bar
│   │   ├── MapView.tsx    # Leaflet map with price-coloured markers
│   │   ├── Filters.tsx    # Saved filters list + create modal
│   │   └── Profile.tsx    # Timezone, password change, account deletion
│   ├── styles/
│   │   └── global.css     # Single global stylesheet (~170 lines, no framework)
│   ├── App.tsx            # React Router routes + QueryClient provider
│   ├── main.tsx           # Entry point
│   └── types.ts           # TypeScript interfaces matching backend schemas
├── Dockerfile             # Multi-stage build: Node (build) → nginx (serve)
├── nginx.conf             # SPA fallback + /api/ reverse proxy
├── .env.example           # VITE_API_URL
└── vite.config.ts         # Dev proxy + build config
```

---

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend base URL. In Docker, leave empty — nginx proxies `/api/` internally. |

Copy `.env.example` to `.env` and edit before running:

```bash
cp frontend/.env.example frontend/.env
```

---

### Building for Production

```bash
cd frontend
npm run build
# Output: frontend/dist/  — serve with any static host
```

Or use the included Dockerfile (built automatically by `docker compose`):

```bash
docker build -t idealista-frontend ./frontend
docker run -p 80:80 idealista-frontend
```

The nginx image serves the built SPA and proxies `/api/` to `http://backend:8000`
(the Docker Compose service name). For standalone deployment, override the proxy
target in `nginx.conf`.

---

### How Auth Works

1. **Login** posts credentials to `POST /api/v1/auth/token` and stores
   `access_token` + `refresh_token` in `localStorage`.
2. Every Axios request attaches `Authorization: Bearer <access_token>`.
3. On a **401 response**, the Axios interceptor (`src/api/client.ts`) silently:
   - Calls `POST /api/v1/auth/refresh` with the stored refresh token.
   - Stores the new token pair.
   - Retries the original request with the new access token.
4. If the refresh also fails (e.g. refresh token expired), `localStorage` is
   cleared and the user is redirected to `/login`.
5. **ProtectedRoute** reads the `useMe()` query — if the token is invalid or
   absent, the server returns 401, the query fails, and the component renders
   `<Navigate to="/login" />`.

---

### Adding a New Page

1. Create `frontend/src/pages/MyPage.tsx`.
2. Add a route in `frontend/src/App.tsx` inside the protected `<Routes>` block:
   ```tsx
   <Route path="/my-page" element={<div className="page-body"><MyPage /></div>} />
   ```
3. Add a link in `frontend/src/components/Navbar.tsx`:
   ```tsx
   <NavLink to="/my-page" className={...}>My Page</NavLink>
   ```
4. If you need to call the backend, add a typed function in the appropriate
   `src/api/*.ts` file and use it via `useQuery` / `useMutation` from
   `@tanstack/react-query`.

---
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

> This section covers **backend-only** setup. For the full stack (backend +
> frontend), see the [Frontend Tutorial](#frontend-tutorial) above.

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
