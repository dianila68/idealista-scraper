"""Shared test fixtures: async test client backed by a real test database."""
import os

# Provide defaults before any app module is imported so Settings() never raises
# at collection time when DATABASE_URL / SECRET_KEY are absent from the shell.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://scraper:scraper@localhost:5432/scraper_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

# passlib 1.7.4 + bcrypt 4.x+: detect_wrap_bug probes with a 255-byte password
# that bcrypt 4+ rejects with ValueError. Patch hashpw to silently truncate so
# the backend probe succeeds. Modern bcrypt does not have the wrap bug anyway.
import bcrypt as _bcrypt_mod  # noqa: E402

_bcrypt_orig_hashpw = _bcrypt_mod.hashpw


def _bcrypt_truncating_hashpw(password: bytes, salt: bytes) -> bytes:
    return _bcrypt_orig_hashpw(password[:72] if len(password) > 72 else password, salt)


_bcrypt_mod.hashpw = _bcrypt_truncating_hashpw  # type: ignore[assignment]

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402

TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://scraper:scraper@localhost:5432/scraper_test",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires a running Postgres instance")


def pytest_collection_modifyitems(config, items):
    """Skip only tests that use DB fixtures when Postgres is not reachable."""
    import asyncio

    import asyncpg

    # Only check DB if at least one item needs it
    db_fixtures = {"client", "db_session", "engine"}
    needs_db = [item for item in items if db_fixtures.intersection(item.fixturenames)]
    if not needs_db:
        return

    async def _check() -> bool:
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
        for item in needs_db:
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
