import asyncio
from typing import Any

from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
from vertexai.preview.language_models import TextGenerationModel

from src.config.settings import settings


class VertexAIClient:
    """Client for interacting with Vertex AI models."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "us-central1",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the Vertex AI client.

        Args:
            project_id: GCP project ID
            location: GCP location
            max_retries: Maximum number of retries on failure
            retry_delay: Delay between retries in seconds
        """
        self.project_id = project_id or settings.project_id
        self.location = location
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._models: dict[str, Any] = {}

        # Initialize Vertex AI
        aiplatform.init(project=self.project_id, location=self.location)

    def get_model(self, model_name: str = "gemini-pro") -> Any:
        """
        Get or create a model instance.

        Args:
            model_name: Name of the model to use

        Returns:
            Model instance
        """
        if model_name not in self._models:
            if model_name.startswith("gemini"):
                self._models[model_name] = GenerativeModel(model_name)
            else:
                self._models[model_name] = TextGenerationModel.from_pretrained(model_name)

        return self._models[model_name]

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model_name: str = "gemini-pro",
        temperature: float = 0.1,
        max_output_tokens: int = 2048,
        top_p: float = 0.95,
        top_k: int = 40,
    ) -> str:
        """
        Generate text using Vertex AI with retry logic.

        Args:
            prompt: Input prompt
            system_prompt: Optional system prompt
            model_name: Model to use
            temperature: Sampling temperature
            max_output_tokens: Maximum output tokens
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter

        Returns:
            Generated text

        Raises:
            Exception: If all retries fail
        """
        model = self.get_model(model_name)

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                if model_name.startswith("gemini"):
                    # Gemini model
                    generation_config = {
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                        "top_p": top_p,
                        "top_k": top_k,
                    }

                    if system_prompt:
                        response = model.generate_content(
                            [system_prompt, prompt], generation_config=generation_config
                        )
                    else:
                        response = model.generate_content(
                            prompt, generation_config=generation_config
                        )

                    return response.text

                else:
                    # PaLM model
                    parameters = {
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                        "top_p": top_p,
                        "top_k": top_k,
                    }

                    response = model.predict(prompt, **parameters)
                    return response.text

            except ResourceExhausted as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    continue

            except GoogleAPICallError as e:
                last_error = e
                if attempt < self.max_retries - 1 and e.code is not None and e.code >= 500:
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise

        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model_name: str = "gemini-pro",
        **kwargs,
    ) -> dict[str, Any]:
        """
        Generate and parse JSON response.

        Args:
            prompt: Input prompt
            system_prompt: Optional system prompt
            model_name: Model to use
            **kwargs: Additional generation parameters

        Returns:
            Parsed JSON response
        """
        import json

        # Add JSON instruction to prompt
        json_prompt = f"""{prompt}

You must respond with valid JSON only. Do not include markdown formatting, explanations, or any text outside the JSON.
"""

        response = await self.generate(
            prompt=json_prompt, system_prompt=system_prompt, model_name=model_name, **kwargs
        )

        # Try to extract JSON from response
        try:
            # Look for JSON array or object
            json_match = None
            for pattern in [r"\[.*\]", r"\{.*\}"]:
                import re

                match = re.search(pattern, response, re.DOTALL)
                if match:
                    json_match = match.group()
                    break

            if json_match:
                return json.loads(json_match)
            else:
                return json.loads(response)

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {e}\nResponse: {response[:500]}") from e

    def count_tokens(self, text: str, model_name: str = "gemini-pro") -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to count tokens for
            model_name: Model name

        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token
        return len(text) // 4
