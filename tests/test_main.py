"""Tests for main.py - FastAPI application creation and configuration."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestCreateApp:
    """Tests for the create_app function."""

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_returns_fastapi_instance(self, mock_settings, mock_router):
        """create_app returns a FastAPI application instance."""
        mock_settings.app_name = "Test App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_title_from_settings(self, mock_settings, mock_router):
        """App title comes from settings.app_name."""
        mock_settings.app_name = "My Reviewer"
        mock_settings.version = "2.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        assert app.title == "My Reviewer"

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_version_from_settings(self, mock_settings, mock_router):
        """App version comes from settings.version."""
        mock_settings.app_name = "App"
        mock_settings.version = "3.5.1"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        assert app.version == "3.5.1"

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_debug_mode_enables_docs(self, mock_settings, mock_router):
        """Debug mode enables /docs and /redoc endpoints."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = True

        from main import create_app

        app = create_app()
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_production_mode_disables_docs(self, mock_settings, mock_router):
        """Non-debug mode disables /docs and /redoc endpoints."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        assert app.docs_url is None
        assert app.redoc_url is None

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_includes_router(self, mock_settings, mock_router):
        """App includes the API router."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        # The app should have routes from the included router
        assert len(app.routes) > 0

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_has_cors_middleware(self, mock_settings, mock_router):
        """App has CORS middleware configured."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        # FastAPI stores user_middleware as Middleware objects
        assert len(app.user_middleware) > 0
        assert any("CORS" in str(m) for m in app.user_middleware)

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_debug_true_sets_app_debug(self, mock_settings, mock_router):
        """Debug flag is passed to FastAPI."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = True

        from main import create_app

        app = create_app()
        assert app.debug is True

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_debug_false_sets_app_debug(self, mock_settings, mock_router):
        """Non-debug flag is passed to FastAPI."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        assert app.debug is False

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_registers_exception_handler(self, mock_settings, mock_router):
        """create_app registers a global exception handler for Exception."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        # Check that an exception handler for Exception is registered
        assert Exception in app.exception_handlers

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_registers_startup_event(self, mock_settings, mock_router):
        """create_app registers a startup event handler."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        # on_event handlers are stored in router.on_startup
        assert len(app.router.on_startup) > 0

    @patch("main.api_router")
    @patch("main.settings")
    def test_create_app_registers_shutdown_event(self, mock_settings, mock_router):
        """create_app registers a shutdown event handler."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()
        assert len(app.router.on_shutdown) > 0


class TestExceptionHandler:
    """Tests for the global exception handler."""

    @patch("main.api_router")
    @patch("main.settings")
    def test_unhandled_exception_returns_500(self, mock_settings, mock_router):
        """Unhandled exception returns 500 with generic error message."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()

        # Add a route that raises an exception
        @app.get("/test-error")
        async def error_route():
            raise RuntimeError("Unexpected error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}

    @patch("main.api_router")
    @patch("main.settings")
    def test_exception_handler_does_not_leak_details(self, mock_settings, mock_router):
        """Exception handler does not expose internal error details."""
        mock_settings.app_name = "App"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()

        @app.get("/test-secret-error")
        async def secret_error():
            raise ValueError("secret database password is abc123")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-secret-error")
        body = response.json()
        assert "secret" not in str(body)
        assert "abc123" not in str(body)
        assert body["detail"] == "Internal server error"


class TestStartupShutdownEvents:
    """Tests for startup and shutdown lifecycle events."""

    @pytest.mark.asyncio
    @patch("main.api_router")
    @patch("main.settings")
    @patch("main.logger")
    async def test_startup_event_logs_message(self, mock_logger, mock_settings, mock_router):
        """Startup event logs the app name and version."""
        mock_settings.app_name = "TestApp"
        mock_settings.version = "1.2.3"
        mock_settings.debug = False

        from main import create_app

        app = create_app()

        # Invoke the startup handler directly
        for handler in app.router.on_startup:
            await handler()

        calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("TestApp" in c and "1.2.3" in c for c in calls)

    @pytest.mark.asyncio
    @patch("main.api_router")
    @patch("main.settings")
    @patch("main.logger")
    async def test_shutdown_event_logs_message(self, mock_logger, mock_settings, mock_router):
        """Shutdown event logs the app name."""
        mock_settings.app_name = "TestApp"
        mock_settings.version = "1.0.0"
        mock_settings.debug = False

        from main import create_app

        app = create_app()

        # Invoke the shutdown handler directly
        for handler in app.router.on_shutdown:
            await handler()

        calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("TestApp" in c for c in calls)


class TestAppModuleLevelInstance:
    """Tests for the module-level app instance."""

    def test_module_app_is_fastapi_instance(self):
        """The module-level 'app' is a FastAPI instance."""
        from main import app

        assert isinstance(app, FastAPI)

    def test_module_app_has_routes(self):
        """The module-level 'app' has registered routes."""
        from main import app

        assert len(app.routes) > 0
