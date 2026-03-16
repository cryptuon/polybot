"""Root conftest.py with shared fixtures for all tests."""

import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset global singletons between tests."""
    from polybot.config import reload_settings

    yield

    # Reset settings after test
    reload_settings()


@pytest.fixture
def mock_settings(tmp_path: Path):
    """Create mock settings with temp paths."""
    from polybot.config import Settings

    # Create temp directories
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ipc_dir = tmp_path / "ipc"
    ipc_dir.mkdir()

    settings = Settings()
    settings.database.sqlite_path = data_dir / "test.db"
    settings.database.duckdb_path = data_dir / "test.duckdb"
    settings.database.strategy_logs_path = data_dir / "test_logs.duckdb"
    settings.nng.ipc_path = str(ipc_dir)

    return settings


@pytest.fixture
def sample_market_data() -> dict:
    """Sample market data for testing."""
    return {
        "id": "test_market_123",
        "question": "Will it rain tomorrow?",
        "slug": "rain-tomorrow",
        "description": "Test market description",
        "outcome_yes_token": "token_yes_123",
        "outcome_no_token": "token_no_123",
        "yes_price": 0.65,
        "no_price": 0.35,
        "volume": 10000.0,
        "volume_24h": 1000.0,
        "liquidity": 5000.0,
        "active": True,
        "closed": False,
        "resolved": False,
    }


@pytest.fixture
def sample_order_data() -> dict:
    """Sample order data for testing."""
    return {
        "id": "order_123",
        "market_id": "market_123",
        "token_id": "token_yes",
        "side": "BUY",
        "price": 0.65,
        "size": 100.0,
        "order_type": "GTC",
        "status": "OPEN",
        "strategy": "momentum",
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for API testing."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    return client
