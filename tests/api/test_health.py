"""Tests for API health endpoints."""

import sys
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient

from api.health import HealthStatus, ReadyStatus, router


class TestHealthStatusModel:
    """Test HealthStatus Pydantic model."""

    def test_health_status_creation(self):
        """Test creating a HealthStatus instance."""
        status = HealthStatus(status="healthy")
        assert status.status == "healthy"
        assert status.version == "1.0.0"

    def test_health_status_custom_version(self):
        """Test HealthStatus with custom version."""
        status = HealthStatus(status="healthy", version="2.0.0")
        assert status.version == "2.0.0"

    def test_health_status_serialization(self):
        """Test HealthStatus JSON serialization."""
        status = HealthStatus(status="healthy")
        data = status.model_dump()
        assert data == {"status": "healthy", "version": "1.0.0"}


class TestReadyStatusModel:
    """Test ReadyStatus Pydantic model."""

    def test_ready_status_creation(self):
        """Test creating a ReadyStatus instance."""
        status = ReadyStatus(
            status="ready",
            services={"firestore": "connected", "pubsub": "connected"},
        )
        assert status.status == "ready"
        assert status.services["firestore"] == "connected"
        assert status.version == "1.0.0"

    def test_ready_status_not_ready(self):
        """Test ReadyStatus when services are disconnected."""
        status = ReadyStatus(
            status="not_ready",
            services={"firestore": "disconnected", "pubsub": "connected"},
        )
        assert status.status == "not_ready"
        assert status.services["firestore"] == "disconnected"

    def test_ready_status_serialization(self):
        """Test ReadyStatus JSON serialization."""
        status = ReadyStatus(
            status="ready",
            services={"firestore": "connected"},
        )
        data = status.model_dump()
        assert data["status"] == "ready"
        assert data["services"] == {"firestore": "connected"}
        assert data["version"] == "1.0.0"


class TestHealthEndpoint:
    """Test /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_200(self, async_client: AsyncClient):
        """Test that /health returns 200 OK."""
        response = await async_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_check_response_body(self, async_client: AsyncClient):
        """Test that /health returns correct response body."""
        response = await async_client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_check_content_type(self, async_client: AsyncClient):
        """Test that /health returns JSON content type."""
        response = await async_client.get("/health")
        assert "application/json" in response.headers["content-type"]


def _setup_mock_firestore_module(client_instance=None, side_effect=None):
    """Create a mock google.cloud.firestore module and register it in sys.modules.

    Args:
        client_instance: Mock instance to return when Client() is called.
        side_effect: Exception to raise when Client() is called.

    Returns:
        The mock module.
    """
    mock_mod = ModuleType("google.cloud.firestore")
    if side_effect:
        mock_mod.Client = Mock(side_effect=side_effect)
    else:
        mock_mod.Client = Mock(return_value=client_instance or Mock())
    return mock_mod


def _setup_mock_pubsub_module(client_instance=None, side_effect=None):
    """Create a mock google.cloud.pubsub_v1 module and register it in sys.modules.

    Args:
        client_instance: Mock instance to return when PublisherClient() is called.
        side_effect: Exception to raise when PublisherClient() is called.

    Returns:
        The mock module.
    """
    mock_mod = ModuleType("google.cloud.pubsub_v1")
    if side_effect:
        mock_mod.PublisherClient = Mock(side_effect=side_effect)
    else:
        mock_mod.PublisherClient = Mock(return_value=client_instance or Mock())
    return mock_mod


class TestReadyEndpoint:
    """Test /ready endpoint.

    The ready endpoint imports google.cloud.firestore and google.cloud.pubsub_v1
    dynamically inside the function body. Since these packages may not be installed
    in the test environment, we mock them via sys.modules injection.
    """

    @pytest.mark.asyncio
    async def test_ready_check_all_services_connected(self, async_client: AsyncClient):
        """Test /ready when all services are connected."""
        mock_fs_client = Mock()
        mock_fs_client.collection.return_value.document.return_value.get.return_value = Mock()

        fs_mod = _setup_mock_firestore_module(client_instance=mock_fs_client)
        ps_mod = _setup_mock_pubsub_module()

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["services"]["firestore"] == "connected"
        assert data["services"]["pubsub"] == "connected"

    @pytest.mark.asyncio
    async def test_ready_check_firestore_disconnected(self, async_client: AsyncClient):
        """Test /ready when Firestore is disconnected."""
        fs_mod = _setup_mock_firestore_module(side_effect=Exception("Firestore unavailable"))
        ps_mod = _setup_mock_pubsub_module()

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["services"]["firestore"] == "disconnected"
        assert data["services"]["pubsub"] == "connected"

    @pytest.mark.asyncio
    async def test_ready_check_pubsub_disconnected(self, async_client: AsyncClient):
        """Test /ready when Pub/Sub is disconnected."""
        mock_fs_client = Mock()
        mock_fs_client.collection.return_value.document.return_value.get.return_value = Mock()

        fs_mod = _setup_mock_firestore_module(client_instance=mock_fs_client)
        ps_mod = _setup_mock_pubsub_module(side_effect=Exception("PubSub unavailable"))

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["services"]["firestore"] == "connected"
        assert data["services"]["pubsub"] == "disconnected"

    @pytest.mark.asyncio
    async def test_ready_check_all_services_disconnected(self, async_client: AsyncClient):
        """Test /ready when all services are disconnected."""
        fs_mod = _setup_mock_firestore_module(side_effect=Exception("Firestore error"))
        ps_mod = _setup_mock_pubsub_module(side_effect=Exception("PubSub error"))

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["services"]["firestore"] == "disconnected"
        assert data["services"]["pubsub"] == "disconnected"

    @pytest.mark.asyncio
    async def test_ready_check_version(self, async_client: AsyncClient):
        """Test that /ready includes version info."""
        fs_mod = _setup_mock_firestore_module(side_effect=Exception("skip"))
        ps_mod = _setup_mock_pubsub_module(side_effect=Exception("skip"))

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        data = response.json()
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_ready_check_firestore_get_fails(self, async_client: AsyncClient):
        """Test /ready when Firestore client creates but .get() fails."""
        mock_fs_client = Mock()
        mock_fs_client.collection.return_value.document.return_value.get.side_effect = Exception(
            "Firestore read error"
        )

        fs_mod = _setup_mock_firestore_module(client_instance=mock_fs_client)
        ps_mod = _setup_mock_pubsub_module()

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        data = response.json()
        assert data["status"] == "not_ready"
        assert data["services"]["firestore"] == "disconnected"
        assert data["services"]["pubsub"] == "connected"

    @pytest.mark.asyncio
    async def test_ready_check_response_structure(self, async_client: AsyncClient):
        """Test that /ready response has the correct structure."""
        fs_mod = _setup_mock_firestore_module(side_effect=Exception("skip"))
        ps_mod = _setup_mock_pubsub_module(side_effect=Exception("skip"))

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        data = response.json()
        assert "status" in data
        assert "services" in data
        assert "version" in data
        assert "firestore" in data["services"]
        assert "pubsub" in data["services"]

    @pytest.mark.asyncio
    async def test_ready_check_content_type(self, async_client: AsyncClient):
        """Test that /ready returns JSON content type."""
        fs_mod = _setup_mock_firestore_module(side_effect=Exception("skip"))
        ps_mod = _setup_mock_pubsub_module(side_effect=Exception("skip"))

        with patch.dict(
            sys.modules,
            {
                "google.cloud.firestore": fs_mod,
                "google.cloud.pubsub_v1": ps_mod,
            },
        ):
            response = await async_client.get("/ready")

        assert "application/json" in response.headers["content-type"]


class TestRouterConfiguration:
    """Test router configuration."""

    def test_router_has_health_tag(self):
        """Test that router is tagged with 'health'."""
        assert "health" in router.tags

    def test_router_has_health_route(self):
        """Test that router has /health route."""
        routes = [r.path for r in router.routes]
        assert "/health" in routes

    def test_router_has_ready_route(self):
        """Test that router has /ready route."""
        routes = [r.path for r in router.routes]
        assert "/ready" in routes
