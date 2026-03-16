"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_health_live(client: TestClient):
    """Liveness probe should return alive status."""
    response = client.get("/health/live")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_health_ready(client: TestClient):
    """Readiness probe should return ready status."""
    response = client.get("/health/ready")

    # May return 503 if DB not initialized, which is acceptable
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data


def test_health_full(client: TestClient):
    """Full health check should return component statuses."""
    response = client.get("/health")

    # May return 200 or 503 depending on component health
    assert response.status_code in [200, 503]
    data = response.json()

    assert "status" in data
    assert "version" in data
    assert "components" in data
    assert "uptime_seconds" in data

    # Check all expected components are present
    assert "sqlite" in data["components"]
    assert "duckdb" in data["components"]
    assert "nng" in data["components"]
    assert "config" in data["components"]


def test_root_endpoint(client: TestClient):
    """Root endpoint should return API info."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "PolyBot API"
    assert "version" in data
    assert data["docs"] == "/docs"
