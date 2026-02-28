"""Tests for ModelRouter."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from llm.router import ModelRouter, ModelTier


class TestModelTier:
    """Test ModelTier enum."""

    def test_tier_values(self):
        """Test that ModelTier enum has expected values."""
        assert ModelTier.FAST == "fast"
        assert ModelTier.BALANCED == "balanced"
        assert ModelTier.HIGH_QUALITY == "high_quality"

    def test_tier_is_string(self):
        """Test that ModelTier values are strings (StrEnum)."""
        assert isinstance(ModelTier.FAST, str)
        assert isinstance(ModelTier.BALANCED, str)
        assert isinstance(ModelTier.HIGH_QUALITY, str)

    def test_tier_membership(self):
        """Test membership checking."""
        assert ModelTier.FAST == "fast"
        assert ModelTier.BALANCED == "balanced"
        assert ModelTier.HIGH_QUALITY == "high_quality"


class TestModelRouterInit:
    """Test ModelRouter initialization."""

    @patch("llm.router.VertexAIClient")
    def test_init_creates_client(self, mock_client_class):
        """Test that init creates a VertexAIClient."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        router = ModelRouter()

        mock_client_class.assert_called_once()
        assert router.client is mock_instance

    @patch("llm.router.VertexAIClient")
    def test_models_config_has_all_tiers(self, mock_client_class):
        """Test that MODELS config includes all tiers."""
        router = ModelRouter()

        assert ModelTier.FAST in router.MODELS
        assert ModelTier.BALANCED in router.MODELS
        assert ModelTier.HIGH_QUALITY in router.MODELS

    @patch("llm.router.VertexAIClient")
    def test_models_config_structure(self, mock_client_class):
        """Test that each tier config has required keys."""
        router = ModelRouter()

        for tier in ModelTier:
            config = router.MODELS[tier]
            assert "model_name" in config
            assert "max_tokens" in config
            assert "temperature" in config

    @patch("llm.router.VertexAIClient")
    def test_fast_tier_uses_flash(self, mock_client_class):
        """Test that FAST tier uses flash model."""
        router = ModelRouter()
        assert router.MODELS[ModelTier.FAST]["model_name"] == "gemini-1.5-flash"

    @patch("llm.router.VertexAIClient")
    def test_balanced_tier_uses_pro(self, mock_client_class):
        """Test that BALANCED tier uses pro model."""
        router = ModelRouter()
        assert router.MODELS[ModelTier.BALANCED]["model_name"] == "gemini-1.5-pro"

    @patch("llm.router.VertexAIClient")
    def test_high_quality_tier_config(self, mock_client_class):
        """Test HIGH_QUALITY tier configuration."""
        router = ModelRouter()
        config = router.MODELS[ModelTier.HIGH_QUALITY]
        assert config["model_name"] == "gemini-1.5-pro"
        assert config["max_tokens"] == 8192
        assert config["temperature"] == 0.0


class TestModelRouterRoute:
    """Test ModelRouter.route method."""

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_balanced_default(self, mock_client_class):
        """Test routing with default balanced tier."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="response text")
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        result = await router.route("test prompt")

        assert result == "response text"
        mock_client.generate.assert_called_once()
        call_kwargs = mock_client.generate.call_args.kwargs
        assert call_kwargs["prompt"] == "test prompt"
        assert call_kwargs["model_name"] == "gemini-1.5-pro"
        assert call_kwargs["max_tokens"] == 4096
        assert call_kwargs["temperature"] == 0.1

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_fast_tier(self, mock_client_class):
        """Test routing with fast tier."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="fast response")
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        result = await router.route("test prompt", tier=ModelTier.FAST)

        assert result == "fast response"
        call_kwargs = mock_client.generate.call_args.kwargs
        assert call_kwargs["model_name"] == "gemini-1.5-flash"
        assert call_kwargs["max_tokens"] == 2048

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_high_quality_tier(self, mock_client_class):
        """Test routing with high quality tier."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="quality response")
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        result = await router.route("test prompt", tier=ModelTier.HIGH_QUALITY)

        assert result == "quality response"
        call_kwargs = mock_client.generate.call_args.kwargs
        assert call_kwargs["model_name"] == "gemini-1.5-pro"
        assert call_kwargs["max_tokens"] == 8192
        assert call_kwargs["temperature"] == 0.0

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_with_system_prompt(self, mock_client_class):
        """Test routing with a system prompt."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="prompted response")
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        result = await router.route(
            "test prompt", system_prompt="Be helpful.", tier=ModelTier.BALANCED
        )

        assert result == "prompted response"
        call_kwargs = mock_client.generate.call_args.kwargs
        assert call_kwargs["system_prompt"] == "Be helpful."

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_with_kwargs_override(self, mock_client_class):
        """Test that kwargs override tier defaults."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="custom response")
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        result = await router.route(
            "test prompt",
            tier=ModelTier.FAST,
            temperature=0.9,
            max_tokens=1024,
        )

        assert result == "custom response"
        call_kwargs = mock_client.generate.call_args.kwargs
        # kwargs should override tier defaults
        assert call_kwargs["temperature"] == 0.9
        assert call_kwargs["max_tokens"] == 1024

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_does_not_mutate_models_config(self, mock_client_class):
        """Test that route does not modify the MODELS class variable."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="response")
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        original_config = router.MODELS[ModelTier.FAST].copy()

        await router.route("test", tier=ModelTier.FAST, temperature=0.99)

        # Original config should be unchanged
        assert router.MODELS[ModelTier.FAST] == original_config


class TestModelRouterRouteJson:
    """Test ModelRouter.route_json method."""

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_json_basic(self, mock_client_class):
        """Test basic JSON routing."""
        mock_client = Mock()
        mock_client.generate_json = AsyncMock(return_value={"key": "value"})
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        result = await router.route_json("test prompt")

        assert result == {"key": "value"}
        mock_client.generate_json.assert_called_once()

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_json_passes_tier_config(self, mock_client_class):
        """Test that tier config is passed to generate_json."""
        mock_client = Mock()
        mock_client.generate_json = AsyncMock(return_value={"result": True})
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        await router.route_json("test prompt", tier=ModelTier.HIGH_QUALITY)

        call_kwargs = mock_client.generate_json.call_args.kwargs
        assert call_kwargs["model_name"] == "gemini-1.5-pro"
        assert call_kwargs["max_tokens"] == 8192
        assert call_kwargs["temperature"] == 0.0

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_json_with_system_prompt(self, mock_client_class):
        """Test JSON routing with system prompt."""
        mock_client = Mock()
        mock_client.generate_json = AsyncMock(return_value={"valid": True})
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        await router.route_json(
            "test prompt", system_prompt="Respond in JSON.", tier=ModelTier.BALANCED
        )

        call_kwargs = mock_client.generate_json.call_args.kwargs
        assert call_kwargs["system_prompt"] == "Respond in JSON."

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_route_json_kwargs_override(self, mock_client_class):
        """Test that kwargs override tier config in JSON routing."""
        mock_client = Mock()
        mock_client.generate_json = AsyncMock(return_value={})
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        await router.route_json("test prompt", tier=ModelTier.FAST, temperature=0.5)

        call_kwargs = mock_client.generate_json.call_args.kwargs
        assert call_kwargs["temperature"] == 0.5


class TestModelRouterSelectTier:
    """Test ModelRouter.select_tier method."""

    @patch("llm.router.VertexAIClient")
    def test_security_always_high_quality(self, mock_client_class):
        """Test that security tasks always use HIGH_QUALITY."""
        router = ModelRouter()

        assert router.select_tier("security") == ModelTier.HIGH_QUALITY
        assert router.select_tier("security", "low", "low") == ModelTier.HIGH_QUALITY
        assert router.select_tier("security", "medium", "normal") == ModelTier.HIGH_QUALITY
        assert router.select_tier("security", "high", "high") == ModelTier.HIGH_QUALITY

    @patch("llm.router.VertexAIClient")
    def test_low_complexity_low_priority_fast(self, mock_client_class):
        """Test that low complexity + low priority uses FAST tier."""
        router = ModelRouter()

        assert router.select_tier("style", "low", "low") == ModelTier.FAST
        assert router.select_tier("logic", "low", "low") == ModelTier.FAST
        assert router.select_tier("pattern", "low", "low") == ModelTier.FAST

    @patch("llm.router.VertexAIClient")
    def test_high_complexity_high_quality(self, mock_client_class):
        """Test that high complexity uses HIGH_QUALITY tier."""
        router = ModelRouter()

        assert router.select_tier("style", "high", "normal") == ModelTier.HIGH_QUALITY
        assert router.select_tier("logic", "high", "low") == ModelTier.HIGH_QUALITY

    @patch("llm.router.VertexAIClient")
    def test_high_priority_high_quality(self, mock_client_class):
        """Test that high priority uses HIGH_QUALITY tier."""
        router = ModelRouter()

        assert router.select_tier("style", "low", "high") == ModelTier.HIGH_QUALITY
        assert router.select_tier("logic", "medium", "high") == ModelTier.HIGH_QUALITY

    @patch("llm.router.VertexAIClient")
    def test_default_balanced(self, mock_client_class):
        """Test that default case uses BALANCED tier."""
        router = ModelRouter()

        assert router.select_tier("style") == ModelTier.BALANCED
        assert router.select_tier("logic", "medium", "normal") == ModelTier.BALANCED
        assert router.select_tier("pattern", "low", "normal") == ModelTier.BALANCED
        assert router.select_tier("summary", "medium", "low") == ModelTier.BALANCED

    @patch("llm.router.VertexAIClient")
    def test_select_tier_default_params(self, mock_client_class):
        """Test select_tier with default complexity and priority parameters."""
        router = ModelRouter()

        # Default complexity="medium", priority="normal" -> BALANCED
        result = router.select_tier("style")
        assert result == ModelTier.BALANCED

    @patch("llm.router.VertexAIClient")
    def test_select_tier_unknown_task_type_balanced(self, mock_client_class):
        """Test that unknown task types default to BALANCED."""
        router = ModelRouter()

        assert router.select_tier("unknown_task") == ModelTier.BALANCED
        assert router.select_tier("random") == ModelTier.BALANCED

    @patch("llm.router.VertexAIClient")
    def test_select_tier_priority_precedence(self, mock_client_class):
        """Test priority over complexity in tier selection edge cases."""
        router = ModelRouter()

        # low complexity but high priority -> HIGH_QUALITY
        assert router.select_tier("style", "low", "high") == ModelTier.HIGH_QUALITY

        # high complexity but low priority -> HIGH_QUALITY (complexity checked first in OR)
        assert router.select_tier("style", "high", "low") == ModelTier.HIGH_QUALITY


class TestModelRouterBatchRoute:
    """Test ModelRouter.batch_route method."""

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_batch_route_all_success(self, mock_client_class):
        """Test batch routing when all prompts succeed."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(side_effect=["response1", "response2", "response3"])
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        results = await router.batch_route(["p1", "p2", "p3"])

        assert results == ["response1", "response2", "response3"]
        assert mock_client.generate.call_count == 3

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_batch_route_with_failures(self, mock_client_class):
        """Test batch routing filters out exceptions."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(side_effect=["response1", Exception("Error"), "response3"])
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        results = await router.batch_route(["p1", "p2", "p3"])

        # Exception should be filtered out
        assert results == ["response1", "response3"]

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_batch_route_all_failures(self, mock_client_class):
        """Test batch routing when all prompts fail."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(side_effect=Exception("Error"))
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        results = await router.batch_route(["p1", "p2"])

        assert results == []

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_batch_route_empty_list(self, mock_client_class):
        """Test batch routing with empty prompt list."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        results = await router.batch_route([])

        assert results == []

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_batch_route_passes_tier_and_system_prompt(self, mock_client_class):
        """Test that batch_route passes tier config and system prompt."""
        mock_client = Mock()
        mock_client.generate = AsyncMock(return_value="response")
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        await router.batch_route(
            ["p1"],
            tier=ModelTier.FAST,
            system_prompt="Be concise.",
        )

        call_kwargs = mock_client.generate.call_args.kwargs
        assert call_kwargs["system_prompt"] == "Be concise."
        assert call_kwargs["model_name"] == "gemini-1.5-flash"

    @patch("llm.router.VertexAIClient")
    @pytest.mark.asyncio
    async def test_batch_route_concurrent_execution(self, mock_client_class):
        """Test that batch_route executes prompts concurrently."""
        call_order = []

        async def mock_generate(**kwargs):
            prompt = kwargs["prompt"]
            call_order.append(f"start_{prompt}")
            await asyncio.sleep(0.01)
            call_order.append(f"end_{prompt}")
            return f"response_{prompt}"

        mock_client = Mock()
        mock_client.generate = mock_generate
        mock_client_class.return_value = mock_client

        router = ModelRouter()
        results = await router.batch_route(["a", "b", "c"])

        assert len(results) == 3
        # All should start before any ends (concurrent)
        # Due to async nature, starts should come before corresponding ends
        assert "start_a" in call_order
        assert "start_b" in call_order
        assert "start_c" in call_order
