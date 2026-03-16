"""API test fixtures."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from polybot.api.app import create_app


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)
