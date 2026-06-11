# ADR 001: Android app lives in a separate repository

**Status:** Accepted
**Date:** 2026-06-11

## Context

Early planning documents described this project as a three-tier monorepo
containing the backend scraper, an Android app, and the notification
system. The backend has since stabilised around a versioned, documented
REST API (`/api/v1/`) with JWT auth, a canonical listing schema, and a
device-registration endpoint for FCM push delivery — everything a client
needs is already a public interface.

## Decision

The Android app will be developed in a **separate repository**, built
exclusively against the public interfaces this platform offers:

- the versioned REST API under `/api/v1/` (OpenAPI spec served at `/openapi.json`)
- JWT bearer authentication (`/auth/register`, `/auth/token`, `/auth/refresh`)
- FCM device registration (`/devices`) for push notifications

This repository remains backend-only. No `android/` directory, Gradle
tooling, or Android CI workflow will be added here.

## Consequences

- The Pydantic schemas in `backend/app/schemas/` and the OpenAPI document
  are the contract between the repos; breaking changes require a new API
  version (`/api/v2/`), not silent edits.
- Issues #1 and #3 are descoped: the Android scaffold and `android.yml`
  workflow acceptance criteria no longer apply to this repository.
- The same applies to any future client (web dashboard, CLI): clients
  consume the API, they do not live here.
