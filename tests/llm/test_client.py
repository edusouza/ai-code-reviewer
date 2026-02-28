"""Tests for VertexAIClient."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted


class TestVertexAIClientInit:
    """Test VertexAIClient initialization."""

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_init_with_defaults(self, mock_settings, mock_init):
        """Test initialization with default settings."""
        mock_settings.project_id = "default-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        assert client.project_id == "default-project"
        assert client.location == "us-central1"
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        assert client._models == {}
        mock_init.assert_called_once_with(project="default-project", location="us-central1")

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_init_with_custom_params(self, mock_settings, mock_init):
        """Test initialization with custom parameters."""
        mock_settings.project_id = "default-project"
        from llm.client import VertexAIClient

        client = VertexAIClient(
            project_id="custom-project",
            location="europe-west1",
            max_retries=5,
            retry_delay=2.0,
        )

        assert client.project_id == "custom-project"
        assert client.location == "europe-west1"
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
        mock_init.assert_called_once_with(project="custom-project", location="europe-west1")

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_init_project_id_from_settings_when_none(self, mock_settings, mock_init):
        """Test that project_id falls back to settings when None."""
        mock_settings.project_id = "settings-project"
        from llm.client import VertexAIClient

        client = VertexAIClient(project_id=None)

        assert client.project_id == "settings-project"


class TestVertexAIClientGetModel:
    """Test VertexAIClient.get_model method."""

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_get_gemini_model(self, mock_settings, mock_init):
        """Test getting a Gemini model creates GenerativeModel."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        with patch("llm.client.GenerativeModel") as mock_gen:
            mock_model = Mock()
            mock_gen.return_value = mock_model

            model = client.get_model("gemini-pro")

            mock_gen.assert_called_once_with("gemini-pro")
            assert model is mock_model

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_get_gemini_flash_model(self, mock_settings, mock_init):
        """Test getting a Gemini Flash model."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        with patch("llm.client.GenerativeModel") as mock_gen:
            mock_model = Mock()
            mock_gen.return_value = mock_model

            model = client.get_model("gemini-1.5-flash")

            mock_gen.assert_called_once_with("gemini-1.5-flash")
            assert model is mock_model

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_get_palm_model(self, mock_settings, mock_init):
        """Test getting a PaLM model creates TextGenerationModel."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        with patch("llm.client.TextGenerationModel") as mock_text_gen:
            mock_model = Mock()
            mock_text_gen.from_pretrained.return_value = mock_model

            model = client.get_model("text-bison")

            mock_text_gen.from_pretrained.assert_called_once_with("text-bison")
            assert model is mock_model

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_get_model_caching(self, mock_settings, mock_init):
        """Test that models are cached after first retrieval."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        with patch("llm.client.GenerativeModel") as mock_gen:
            mock_model = Mock()
            mock_gen.return_value = mock_model

            model1 = client.get_model("gemini-pro")
            model2 = client.get_model("gemini-pro")

            # Should only be called once due to caching
            mock_gen.assert_called_once_with("gemini-pro")
            assert model1 is model2

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_get_model_default_name(self, mock_settings, mock_init):
        """Test that default model name is gemini-pro."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        with patch("llm.client.GenerativeModel") as mock_gen:
            mock_model = Mock()
            mock_gen.return_value = mock_model

            client.get_model()

            mock_gen.assert_called_once_with("gemini-pro")


class TestVertexAIClientGenerate:
    """Test VertexAIClient.generate method."""

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def _make_client(self, mock_settings, mock_init, **kwargs):
        """Helper to create a VertexAIClient with mocked dependencies."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        return VertexAIClient(**kwargs)

    @pytest.mark.asyncio
    async def test_generate_gemini_without_system_prompt(self):
        """Test generating text with Gemini model without system prompt."""
        client = self._make_client()

        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Generated response"
        mock_model.generate_content = Mock(return_value=mock_response)
        client._models["gemini-pro"] = mock_model

        result = await client.generate("test prompt", model_name="gemini-pro")

        assert result == "Generated response"
        mock_model.generate_content.assert_called_once_with(
            "test prompt",
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 2048,
                "top_p": 0.95,
                "top_k": 40,
            },
        )

    @pytest.mark.asyncio
    async def test_generate_gemini_with_system_prompt(self):
        """Test generating text with Gemini model with system prompt."""
        client = self._make_client()

        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Generated with system prompt"
        mock_model.generate_content = Mock(return_value=mock_response)
        client._models["gemini-pro"] = mock_model

        result = await client.generate(
            "test prompt", system_prompt="You are helpful.", model_name="gemini-pro"
        )

        assert result == "Generated with system prompt"
        mock_model.generate_content.assert_called_once_with(
            ["You are helpful.", "test prompt"],
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 2048,
                "top_p": 0.95,
                "top_k": 40,
            },
        )

    @pytest.mark.asyncio
    async def test_generate_palm_model(self):
        """Test generating text with PaLM model."""
        client = self._make_client()

        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "PaLM response"
        mock_model.predict = Mock(return_value=mock_response)
        client._models["text-bison"] = mock_model

        result = await client.generate("test prompt", model_name="text-bison")

        assert result == "PaLM response"
        mock_model.predict.assert_called_once_with(
            "test prompt",
            temperature=0.1,
            max_output_tokens=2048,
            top_p=0.95,
            top_k=40,
        )

    @pytest.mark.asyncio
    async def test_generate_custom_parameters(self):
        """Test generating text with custom parameters."""
        client = self._make_client()

        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Custom response"
        mock_model.generate_content = Mock(return_value=mock_response)
        client._models["gemini-pro"] = mock_model

        result = await client.generate(
            "test prompt",
            model_name="gemini-pro",
            temperature=0.9,
            max_output_tokens=4096,
            top_p=0.8,
            top_k=50,
        )

        assert result == "Custom response"
        mock_model.generate_content.assert_called_once_with(
            "test prompt",
            generation_config={
                "temperature": 0.9,
                "max_output_tokens": 4096,
                "top_p": 0.8,
                "top_k": 50,
            },
        )

    @pytest.mark.asyncio
    async def test_generate_retry_on_resource_exhausted(self):
        """Test that ResourceExhausted triggers exponential backoff retries."""
        client = self._make_client(max_retries=3, retry_delay=0.01)

        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Success after retry"
        mock_model.generate_content = Mock(
            side_effect=[
                ResourceExhausted("Quota exceeded"),
                ResourceExhausted("Quota exceeded"),
                mock_response,
            ]
        )
        client._models["gemini-pro"] = mock_model

        with patch("llm.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client.generate("test prompt", model_name="gemini-pro")

        assert result == "Success after retry"
        assert mock_model.generate_content.call_count == 3
        # Exponential backoff: 0.01 * 2^0, 0.01 * 2^1
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_resource_exhausted_all_retries_fail(self):
        """Test that all retries failing raises an exception."""
        client = self._make_client(max_retries=2, retry_delay=0.01)

        mock_model = Mock()
        mock_model.generate_content = Mock(side_effect=ResourceExhausted("Quota exceeded"))
        client._models["gemini-pro"] = mock_model

        with patch("llm.client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="Failed after 2 attempts"):
                await client.generate("test prompt", model_name="gemini-pro")

        assert mock_model.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_retry_on_server_error(self):
        """Test that 5xx GoogleAPICallError triggers retry."""
        client = self._make_client(max_retries=2, retry_delay=0.01)

        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Success after server error"

        server_error = GoogleAPICallError("Internal Server Error")
        server_error._code = 500

        # We need to mock the code property
        error_mock = MagicMock(spec=GoogleAPICallError)
        error_mock.code = 500
        error_mock.__str__ = Mock(return_value="Internal Server Error")

        mock_model.generate_content = Mock(side_effect=[error_mock, mock_response])
        client._models["gemini-pro"] = mock_model

        # The code checks e.code, so we need a proper exception
        real_error = GoogleAPICallError("Internal Server Error")
        # GoogleAPICallError stores code differently, patch the property
        type(real_error).code = property(lambda self: 500)

        mock_model.generate_content = Mock(side_effect=[real_error, mock_response])

        with patch("llm.client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.generate("test prompt", model_name="gemini-pro")

        assert result == "Success after server error"

    @pytest.mark.asyncio
    async def test_generate_google_api_error_non_retryable(self):
        """Test that 4xx GoogleAPICallError raises immediately."""
        client = self._make_client(max_retries=3, retry_delay=0.01)

        mock_model = Mock()
        error = GoogleAPICallError("Bad Request")
        # 4xx error should not retry - code is None by default
        type(error).code = property(lambda self: 400)

        mock_model.generate_content = Mock(side_effect=error)
        client._models["gemini-pro"] = mock_model

        with pytest.raises(GoogleAPICallError):
            await client.generate("test prompt", model_name="gemini-pro")

        # Should only try once since it's a client error
        assert mock_model.generate_content.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_google_api_error_none_code_raises(self):
        """Test that GoogleAPICallError with code=None raises immediately."""
        client = self._make_client(max_retries=3, retry_delay=0.01)

        mock_model = Mock()
        error = GoogleAPICallError("Unknown error")
        # Default code is None

        mock_model.generate_content = Mock(side_effect=error)
        client._models["gemini-pro"] = mock_model

        with pytest.raises(GoogleAPICallError):
            await client.generate("test prompt", model_name="gemini-pro")

        assert mock_model.generate_content.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_generic_exception_retry(self):
        """Test that generic exceptions retry."""
        client = self._make_client(max_retries=2, retry_delay=0.01)

        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Success after generic error"
        mock_model.generate_content = Mock(
            side_effect=[ValueError("Unexpected error"), mock_response]
        )
        client._models["gemini-pro"] = mock_model

        with patch("llm.client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.generate("test prompt", model_name="gemini-pro")

        assert result == "Success after generic error"
        assert mock_model.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_generic_exception_all_retries_fail(self):
        """Test that generic exceptions raise after all retries."""
        client = self._make_client(max_retries=2, retry_delay=0.01)

        mock_model = Mock()
        mock_model.generate_content = Mock(side_effect=ValueError("Persistent error"))
        client._models["gemini-pro"] = mock_model

        with patch("llm.client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="Persistent error"):
                await client.generate("test prompt", model_name="gemini-pro")

    @pytest.mark.asyncio
    async def test_generate_exponential_backoff_timing(self):
        """Test that ResourceExhausted uses exponential backoff."""
        client = self._make_client(max_retries=4, retry_delay=1.0)

        mock_model = Mock()
        mock_model.generate_content = Mock(side_effect=ResourceExhausted("Quota exceeded"))
        client._models["gemini-pro"] = mock_model

        sleep_calls = []

        async def track_sleep(duration):
            sleep_calls.append(duration)

        with patch("llm.client.asyncio.sleep", side_effect=track_sleep):
            with pytest.raises(Exception, match="Failed after 4 attempts"):
                await client.generate("test prompt", model_name="gemini-pro")

        # Exponential backoff: 1.0*1, 1.0*2, 1.0*4
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == 1.0
        assert sleep_calls[1] == 2.0
        assert sleep_calls[2] == 4.0


class TestVertexAIClientGenerateJson:
    """Test VertexAIClient.generate_json method."""

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def _make_client(self, mock_settings, mock_init, **kwargs):
        """Helper to create a VertexAIClient."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        return VertexAIClient(**kwargs)

    @pytest.mark.asyncio
    async def test_generate_json_valid_object(self):
        """Test generating and parsing a valid JSON object."""
        client = self._make_client()

        json_response = '{"key": "value", "number": 42}'

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = json_response

            result = await client.generate_json("test prompt")

        assert result == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_generate_json_valid_array(self):
        """Test generating and parsing a valid JSON array."""
        client = self._make_client()

        json_response = "[1, 2, 3]"

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = json_response

            result = await client.generate_json("test prompt")

        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_generate_json_extracts_from_markdown(self):
        """Test that JSON is extracted from markdown-wrapped responses."""
        client = self._make_client()

        markdown_response = 'Here is the result:\n```json\n{"valid": true}\n```\nDone.'

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = markdown_response

            result = await client.generate_json("test prompt")

        assert result == {"valid": True}

    @pytest.mark.asyncio
    async def test_generate_json_extracts_array_from_text(self):
        """Test that JSON array is extracted from surrounding text."""
        client = self._make_client()

        text_response = "The indices are: [1, 3, 5] which are the top suggestions."

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = text_response

            result = await client.generate_json("test prompt")

        assert result == [1, 3, 5]

    @pytest.mark.asyncio
    async def test_generate_json_array_matched_before_object(self):
        """Test that array pattern is matched before object pattern."""
        client = self._make_client()

        # Contains both array and object patterns - array should be tried first
        response = '[{"a": 1}, {"b": 2}]'

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = response

            result = await client.generate_json("test prompt")

        assert result == [{"a": 1}, {"b": 2}]

    @pytest.mark.asyncio
    async def test_generate_json_invalid_json_raises(self):
        """Test that invalid JSON raises an exception."""
        client = self._make_client()

        invalid_response = "This is not JSON at all."

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = invalid_response

            with pytest.raises(Exception, match="Failed to parse JSON response"):
                await client.generate_json("test prompt")

    @pytest.mark.asyncio
    async def test_generate_json_broken_json_raises(self):
        """Test that broken JSON (looks like JSON but invalid) raises exception."""
        client = self._make_client()

        broken_response = '{"key": "value", invalid}'

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = broken_response

            with pytest.raises(Exception, match="Failed to parse JSON response"):
                await client.generate_json("test prompt")

    @pytest.mark.asyncio
    async def test_generate_json_appends_instruction(self):
        """Test that JSON instruction is appended to the prompt."""
        client = self._make_client()

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = '{"result": true}'

            await client.generate_json("test prompt")

        call_args = mock_gen.call_args
        prompt_arg = call_args.kwargs.get("prompt") or call_args[1].get("prompt")
        if prompt_arg is None:
            # Might be positional
            prompt_arg = call_args[0][0] if call_args[0] else ""

        assert "valid JSON only" in prompt_arg
        assert "test prompt" in prompt_arg

    @pytest.mark.asyncio
    async def test_generate_json_passes_kwargs(self):
        """Test that additional kwargs are passed to generate."""
        client = self._make_client()

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = '{"result": true}'

            await client.generate_json(
                "test prompt",
                system_prompt="Be JSON",
                model_name="gemini-1.5-pro",
                temperature=0.5,
            )

        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["system_prompt"] == "Be JSON"
        assert call_kwargs["model_name"] == "gemini-1.5-pro"
        assert call_kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_json_no_match_falls_back_to_full_parse(self):
        """Test fallback to full response parsing when no regex match found."""
        client = self._make_client()

        # Pure JSON with no surrounding text - regex will match, but test the path
        # where response itself is pure JSON without extra text
        pure_json = "42"  # valid JSON but not array/object - no regex match

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = pure_json

            result = await client.generate_json("test prompt")

        assert result == 42


class TestVertexAIClientCountTokens:
    """Test VertexAIClient.count_tokens method."""

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_count_tokens_basic(self, mock_settings, mock_init):
        """Test basic token counting (4 chars per token approximation)."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        assert client.count_tokens("") == 0
        assert client.count_tokens("abcd") == 1
        assert client.count_tokens("abcdefgh") == 2
        assert client.count_tokens("a" * 100) == 25

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_count_tokens_ignores_model_name(self, mock_settings, mock_init):
        """Test that model name does not affect token count (estimation only)."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        text = "Hello world, this is a test."
        count1 = client.count_tokens(text, model_name="gemini-pro")
        count2 = client.count_tokens(text, model_name="text-bison")

        assert count1 == count2
        assert count1 == len(text) // 4

    @patch("llm.client.aiplatform_init")
    @patch("llm.client.settings")
    def test_count_tokens_short_text(self, mock_settings, mock_init):
        """Test token counting for very short text."""
        mock_settings.project_id = "test-project"
        from llm.client import VertexAIClient

        client = VertexAIClient()

        # Less than 4 chars -> integer division yields 0
        assert client.count_tokens("ab") == 0
        assert client.count_tokens("abc") == 0
        assert client.count_tokens("abcd") == 1
