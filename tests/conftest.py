"""
Test fixtures.

Uses an in-memory SQLite database (via aiosqlite) instead of PostgreSQL.
Tables are created once per test session; each test gets a fresh session
that is rolled back after the test completes.

Redis calls are mocked to avoid needing a running Redis server.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.db.init_models  # noqa: F401 — ensures all ORM models are registered
from app.dependencies.database import get_db

# ── Test database (SQLite in-memory, shared pool so all connections see the same data) ──

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Schema setup — runs once for the entire test session ─────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Clear all table data between tests (autouse) ──────────────────────────────

@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def clear_tables(setup_database) -> AsyncGenerator[None, None]:
    yield
    # After each test, wipe all rows so state doesn't leak across tests.
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ── Per-test DB session ───────────────────────────────────────────────────────

@pytest_asyncio.fixture(loop_scope="function")
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


# ── Mock Redis ────────────────────────────────────────────────────────────────

def _make_mock_redis() -> AsyncMock:
    mock = AsyncMock()
    mock.setex = AsyncMock()
    mock.delete = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.keys = AsyncMock(return_value=[])
    mock.mget = AsyncMock(return_value=[])
    mock.publish = AsyncMock(return_value=0)
    mock.exists = AsyncMock(return_value=False)
    mock.aclose = AsyncMock()
    return mock


# ── HTTP test client ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture(loop_scope="function")
async def client(db_session: AsyncSession, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    from main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Patch Redis so no real connection is needed
    mock_redis = _make_mock_redis()
    import app.managers.redis_manager as rm
    monkeypatch.setattr(rm, "_redis", mock_redis)

    # Prevent the Redis subscriber background task from starting
    import app.events.redis_subscriber as rs
    monkeypatch.setattr(rs, "run_subscriber", AsyncMock())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(loop_scope="function")
async def registered_user(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "securepassword123",
        "display_name": "Test User",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture(loop_scope="function")
async def auth_headers(client: AsyncClient, registered_user: dict) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "securepassword123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture(loop_scope="function")
async def auth_tokens(client: AsyncClient, registered_user: dict) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "securepassword123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()
