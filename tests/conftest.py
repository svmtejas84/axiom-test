import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from api.main import app, AppState
from storage.models import Base

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
async def db_engine():
    """
    Creates a test database engine. 
    In a real scenario, this would point to a test PostgreSQL instance.
    For this mock suite, we'll use an in-memory SQLite if possible, 
    or mock the engine entirely.
    """
    try:
        # Attempt to use SQLite for real DB behavior in tests
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return engine
    except ImportError:
        # Fallback to a mock engine if aiosqlite is missing
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        return mock_engine

@pytest.fixture
async def db_session(db_engine):
    """Provides a clean database session for each test."""
    if isinstance(db_engine, AsyncMock):
        yield db_engine
        return

    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture(autouse=True)
async def setup_app_state(db_engine):
    """Mocks global AppState for tests."""
    # Mock Redis
    mock_redis = AsyncMock()
    
    # Patch AppState
    with patch("api.main.AppState.redis_client", mock_redis), \
         patch("api.main.AppState.postgres_engine", db_engine):
        yield

@pytest.fixture
async def client():
    """Provides an async HTTP client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_sheerid():
    with patch("api.routes.student.sheerid_service") as mock:
        yield mock

@pytest.fixture
def mock_llm():
    with patch("tasks.ml_worker.LLMRecommenderService") as mock:
        yield mock

@pytest.fixture
def mock_celery_task():
    with patch("api.routes.evaluate.run_evaluation_task.delay") as mock:
        mock.return_value = MagicMock(id="test_task_id")
        yield mock
