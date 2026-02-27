from enum import Enum
from typing import Any

from src.llm.client import VertexAIClient


class ModelTier(str, Enum):
    """Model tiers for different use cases."""

    FAST = "fast"  # Quick, cheaper models
    BALANCED = "balanced"  # Good balance of speed and quality
    HIGH_QUALITY = "high_quality"  # Best quality, slower


class ModelRouter:
    """Routes requests to appropriate model based on requirements."""

    # Model configuration
    MODELS = {
        ModelTier.FAST: {
            "model_name": "gemini-1.5-flash",
            "max_tokens": 2048,
            "temperature": 0.1,
        },
        ModelTier.BALANCED: {
            "model_name": "gemini-1.5-pro",
            "max_tokens": 4096,
            "temperature": 0.1,
        },
        ModelTier.HIGH_QUALITY: {
            "model_name": "gemini-1.5-pro",
            "max_tokens": 8192,
            "temperature": 0.0,
        },
    }

    def __init__(self):
        self.client = VertexAIClient()

    async def route(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.BALANCED,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        """
        Route request to appropriate model.

        Args:
            prompt: Input prompt
            tier: Model tier to use
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Generated response
        """
        model_config = self.MODELS[tier].copy()
        model_config.update(kwargs)

        return await self.client.generate(
            prompt=prompt, system_prompt=system_prompt, **model_config
        )

    async def route_json(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.BALANCED,
        system_prompt: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Route request and parse JSON response.

        Args:
            prompt: Input prompt
            tier: Model tier to use
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Parsed JSON response
        """
        model_config = self.MODELS[tier].copy()
        model_config.update(kwargs)

        return await self.client.generate_json(
            prompt=prompt, system_prompt=system_prompt, **model_config
        )

    def select_tier(
        self, task_type: str, complexity: str = "medium", priority: str = "normal"
    ) -> ModelTier:
        """
        Select appropriate model tier based on task characteristics.

        Args:
            task_type: Type of task (security, style, logic, pattern, summary)
            complexity: Task complexity (low, medium, high)
            priority: Priority level (low, normal, high)

        Returns:
            Selected model tier
        """
        # Security issues need high quality
        if task_type == "security":
            return ModelTier.HIGH_QUALITY

        # Simple tasks can use fast tier
        if complexity == "low" and priority == "low":
            return ModelTier.FAST

        # High priority or complex tasks need better quality
        if complexity == "high" or priority == "high":
            return ModelTier.HIGH_QUALITY

        # Default to balanced
        return ModelTier.BALANCED

    async def batch_route(
        self,
        prompts: list[str],
        tier: ModelTier = ModelTier.BALANCED,
        system_prompt: str | None = None,
        **kwargs,
    ) -> list[str]:
        """
        Route multiple prompts concurrently.

        Args:
            prompts: List of prompts
            tier: Model tier to use
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            List of responses
        """
        import asyncio

        tasks = [self.route(prompt, tier, system_prompt, **kwargs) for prompt in prompts]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Filter out exceptions, return only successful responses
        return [r for r in results if not isinstance(r, BaseException)]
