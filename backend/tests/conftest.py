"""Shared test fixtures: async test client backed by a real test database."""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.main import app
from app.models.base import Base

TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://scraper:scraper@localhost:5432/scraper_test",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires a running Postgres instance")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when the test DB is not reachable."""
    import asyncio

    import asyncpg

    async def _check():
        try:
            conn = await asyncpg.connect(
                TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
                timeout=3,
            )
            await conn.close()
            return True
        except Exception:
            return False

    db_available = asyncio.run(_check())
    if not db_available:
        skip = pytest.mark.skip(reason="Test database not reachable — run via Docker Compose or CI")
        for item in items:
            item.add_marker(skip)


@pytest_asyncio.fixture
async def engine():
    # Function-scoped: pytest-asyncio gives each test its own event loop, and
    # asyncpg connections must not outlive the loop they were created on.
    # NullPool keeps no idle connections around between requests.
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine):
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session
            await session.rollback()

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def register_and_login(client: AsyncClient, email: str, password: str = "password123") -> str:
    """Helper: register a user and return a valid access token."""
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = await client.post("/api/v1/auth/token", json={"email": email, "password": password})
    return resp.json()["access_token"]
