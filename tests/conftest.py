"""Pytest configuration and async fixtures for ComplaintIQ."""

import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

import complaintiq.core.database as db_module
from complaintiq.core.database import get_database
from complaintiq.serving.app import app


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-wide event loop for running async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    """Ensure every test uses a clean in-memory mock database."""
    # Use isolated mock client
    mock_client = AsyncMongoMockClient()
    db_module._mongo_client = mock_client
    db_module._database = mock_client["complaintiq_test"]
    db_module._is_mock = True

    db = await get_database()
    # Clear collections before test
    await db["triage_requests"].delete_many({})
    await db["human_feedback"].delete_many({})

    yield db

    # Cleanup after test
    await db["triage_requests"].delete_many({})
    await db["human_feedback"].delete_many({})


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTPX AsyncClient configured for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
