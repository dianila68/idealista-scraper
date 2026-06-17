"""Authenticate with Idealista / Immobiliare / Subito using stored credentials.

Each `login_*` coroutine returns a cookie jar dict on success and raises on failure.
The caller is responsible for persisting cookies back to the DB.

Idealista note: the login page is DataDome-protected, so the first login
requires a Playwright session. Subsequent scrapes reuse the stored cookie jar
(handled by BaseScraper) and only re-login here when cookies expire.
"""
from __future__ import annotations

from typing import Any

import structlog
from curl_cffi.requests import AsyncSession
from playwright.async_api import async_playwright

log = structlog.get_logger()

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def login_subito(username: str, password: str) -> dict[str, str]:
    """Authenticate with Subito.it and return session cookies.

    Subito uses a JSON REST login endpoint that returns a JWT and session cookie.
    The session cookie is what matters for subsequent page requests.
    """
    login_url = "https://api.subito.it/srt/api/v1/user/authentication/login"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _CHROME_UA,
        "Accept": "application/json",
        "Origin": "https://www.subito.it",
        "Referer": "https://www.subito.it/",
    }
    payload = {"username": username, "password": password}

    async with AsyncSession(impersonate="chrome124", timeout=30) as session:
        resp = await session.post(login_url, json=payload, headers=headers)

    if resp.status_code not in (200, 201):
        log.warning("platform_auth.subito.login_failed", status=resp.status_code)
        raise ValueError(f"Subito login failed: HTTP {resp.status_code}")

    # Collect all cookies from the response
    cookies: dict[str, str] = {}
    for name, value in resp.cookies.items():
        cookies[name] = value

    # Also parse the token from JSON body to store in cookies for API calls
    try:
        body: dict[str, Any] = resp.json()
        if token := body.get("token") or body.get("access_token"):
            cookies["_subito_token"] = token
    except Exception:
        pass

    if not cookies:
        raise ValueError("Subito login returned no session cookies")

    log.info("platform_auth.subito.login_ok", cookie_count=len(cookies))
    return cookies


async def login_immobiliare(username: str, password: str) -> dict[str, str]:
    """Authenticate with Immobiliare.it via form POST and return cookies."""
    login_url = "https://www.immobiliare.it/account/accesso/"
    headers = {
        "User-Agent": _CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.immobiliare.it/account/accesso/",
        "Origin": "https://www.immobiliare.it",
    }

    async with AsyncSession(impersonate="chrome124", timeout=30) as session:
        # Load login page first to pick up CSRF tokens
        get_resp = await session.get(login_url, headers=headers)

        form_data = {
            "email": username,
            "password": password,
        }
        # Try to extract hidden CSRF field from page
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(get_resp.text, "html.parser")
            csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"}) or \
                         soup.find("input", {"name": "_token"})
            if csrf_input and csrf_input.get("value"):
                field_name = csrf_input.get("name")
                form_data[field_name] = csrf_input.get("value")
        except Exception:
            pass

        resp = await session.post(login_url, data=form_data, headers=headers)

    if resp.status_code not in (200, 302):
        log.warning("platform_auth.immobiliare.login_failed", status=resp.status_code)
        raise ValueError(f"Immobiliare login failed: HTTP {resp.status_code}")

    cookies: dict[str, str] = {name: value for name, value in resp.cookies.items()}
    # Also carry over session cookies from the GET step
    for name, value in get_resp.cookies.items():
        cookies.setdefault(name, value)

    # Verify we have a session cookie (not just returned to login page)
    session_indicators = {"imm_session", "_session", "sessionid", "PHPSESSID"}
    if not any(k in cookies for k in session_indicators):
        raise ValueError("Immobiliare login did not produce a session cookie — check credentials")

    log.info("platform_auth.immobiliare.login_ok", cookie_count=len(cookies))
    return cookies


async def login_idealista(username: str, password: str) -> dict[str, str]:
    """Authenticate with Idealista.it using Playwright (DataDome bypassed in browser).

    This is the one-time login cost. After successful login the cookie jar is
    persisted and subsequent scrapes reuse it via curl_cffi (no Playwright needed).
    """
    cookies: dict[str, str] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=_CHROME_UA,
            locale="it-IT",
            timezone_id="Europe/Rome",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            await page.goto("https://www.idealista.it/", timeout=30_000)
            await page.goto("https://www.idealista.it/acceder/", timeout=30_000)
            await page.wait_for_load_state("networkidle", timeout=15_000)

            # Fill login form
            await page.fill('input[name="email"], input[type="email"]', username)
            await page.fill('input[name="password"], input[type="password"]', password)
            await page.click('button[type="submit"], input[type="submit"]')
            await page.wait_for_load_state("networkidle", timeout=20_000)

            # Check login success (redirect away from login page)
            if "acceder" in page.url:
                raise ValueError("Idealista login failed — still on login page (wrong credentials or CAPTCHA)")

            # Harvest all cookies from the browser context
            raw_cookies = await context.cookies()
            for c in raw_cookies:
                cookies[c["name"]] = c["value"]

        finally:
            await browser.close()

    if not cookies:
        raise ValueError("Idealista login returned no cookies")

    log.info("platform_auth.idealista.login_ok", cookie_count=len(cookies))
    return cookies


_LOGIN_HANDLERS = {
    "subito": login_subito,
    "immobiliare": login_immobiliare,
    "idealista": login_idealista,
}


async def platform_login(platform: str, username: str, password: str) -> dict[str, str]:
    """Dispatch to the correct platform login handler."""
    handler = _LOGIN_HANDLERS.get(platform)
    if handler is None:
        raise ValueError(f"Unknown platform: {platform}")
    return await handler(username, password)
