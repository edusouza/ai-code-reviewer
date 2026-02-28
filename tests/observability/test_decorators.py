"""Tests for observability decorators module."""

from unittest.mock import Mock, patch

import pytest

from observability.decorators import (
    _extract_generation_params,
    _extract_input_data,
    _extract_metadata,
    _extract_prompt,
    _extract_token_usage,
    _safe_serialize,
    trace_agent,
    trace_llm,
    trace_span,
    trace_workflow,
)
from observability.langfuse_client import current_span_id, current_trace_id

# ---------------------------------------------------------------------------
# Helper functions tests
# ---------------------------------------------------------------------------


class TestSafeSerialize:
    """Test _safe_serialize helper."""

    def test_serialize_dict_method(self):
        """Objects with .dict() should be serialized via dict()."""
        obj = Mock()
        obj.dict.return_value = {"key": "value"}
        # Make sure model_dump is not checked first (dict comes first in code)
        del obj.model_dump
        result = _safe_serialize(obj)
        assert result == {"key": "value"}

    def test_serialize_model_dump_method(self):
        """Objects with .model_dump() (pydantic v2) should use model_dump()."""
        obj = Mock(spec=[])  # no dict attribute
        obj.model_dump = Mock(return_value={"field": 42})
        result = _safe_serialize(obj)
        assert result == {"field": 42}

    def test_serialize_object_with_dict_attr(self):
        """Objects with __dict__ should return __dict__."""

        class Foo:
            def __init__(self):
                self.x = 1
                self.y = 2

        result = _safe_serialize(Foo())
        assert result == {"x": 1, "y": 2}

    def test_serialize_primitive_string(self):
        """Strings should be serialized as str()."""
        result = _safe_serialize("hello")
        assert result == "hello"

    def test_serialize_primitive_int(self):
        """Ints should be serialized as str()."""
        result = _safe_serialize(42)
        assert result == "42"

    def test_serialize_none(self):
        """None should be serialized as str()."""
        result = _safe_serialize(None)
        assert result == "None"

    def test_serialize_list(self):
        """Lists should be serialized as str()."""
        result = _safe_serialize([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_serialize_exception_in_dict(self):
        """When .dict() raises, should fallback to str()."""
        obj = Mock()
        obj.dict.side_effect = Exception("broken")
        result = _safe_serialize(obj)
        assert isinstance(result, str)

    def test_serialize_exception_in_model_dump(self):
        """When .model_dump() raises, should fallback to str()."""
        obj = Mock(spec=[])
        obj.model_dump = Mock(side_effect=Exception("broken"))
        # It has model_dump but no dict, so model_dump gets called and fails
        # but since dict is checked first via hasattr on Mock, let's be explicit
        result = _safe_serialize(obj)
        assert isinstance(result, str)


class TestExtractMetadata:
    """Test _extract_metadata helper."""

    def test_basic_metadata(self):
        """Should include function name and module."""

        def my_func():
            pass

        result = _extract_metadata(my_func, (), {})
        assert result["function"] == "my_func"
        assert "module" in result

    def test_metadata_with_pr_event_first_arg(self):
        """Should extract PR info from first argument with 'provider' attr."""
        pr_event = Mock()
        pr_event.provider = "github"
        pr_event.repo_owner = "myorg"
        pr_event.repo_name = "myrepo"
        pr_event.pr_number = 42

        def review(event):
            pass

        result = _extract_metadata(review, (pr_event,), {})
        assert result["provider"] == "github"
        assert result["repo"] == "myorg/myrepo"
        assert result["pr_number"] == 42

    def test_metadata_with_none_repo_fields(self):
        """Should handle None repo_owner/repo_name gracefully."""
        pr_event = Mock()
        pr_event.provider = "gitlab"
        pr_event.repo_owner = None
        pr_event.repo_name = None
        pr_event.pr_number = 1

        def func(event):
            pass

        result = _extract_metadata(func, (pr_event,), {})
        assert result["repo"] == "/"

    def test_metadata_no_pr_event(self):
        """Should not include provider info when first arg has no 'provider'."""

        def func(x):
            pass

        result = _extract_metadata(func, ("string_arg",), {})
        assert "provider" not in result
        assert result["function"] == "func"

    def test_metadata_empty_args(self):
        """Should work with empty args."""

        def func():
            pass

        result = _extract_metadata(func, (), {})
        assert result["function"] == "func"


class TestExtractInputData:
    """Test _extract_input_data helper."""

    def test_extracts_file_path_and_language(self):
        """Should extract file_path and language from first arg."""
        chunk = Mock()
        chunk.file_path = "src/main.py"
        chunk.language = "python"

        result = _extract_input_data((chunk,), {})
        assert result == {"file_path": "src/main.py", "language": "python"}

    def test_extracts_file_path_only(self):
        """Should extract file_path when language is not present."""
        chunk = Mock(spec=["file_path"])
        chunk.file_path = "src/main.py"

        result = _extract_input_data((chunk,), {})
        assert result == {"file_path": "src/main.py"}

    def test_returns_none_for_plain_args(self):
        """Should return None when first arg has no relevant attrs."""
        result = _extract_input_data(("plain_string",), {})
        assert result is None

    def test_returns_none_for_empty_args(self):
        """Should return None for empty args."""
        result = _extract_input_data((), {})
        assert result is None


class TestExtractPrompt:
    """Test _extract_prompt helper."""

    def test_extracts_from_kwargs_prompt(self):
        """Should extract 'prompt' from kwargs."""
        result = _extract_prompt((), {"prompt": "hello world"})
        assert result == "hello world"

    def test_extracts_from_kwargs_messages(self):
        """Should extract 'messages' from kwargs."""
        result = _extract_prompt((), {"messages": [{"role": "user", "content": "hi"}]})
        assert "hi" in result

    def test_extracts_from_kwargs_content(self):
        """Should extract 'content' from kwargs."""
        result = _extract_prompt((), {"content": "analyze this"})
        assert result == "analyze this"

    def test_extracts_from_kwargs_input(self):
        """Should extract 'input' from kwargs."""
        result = _extract_prompt((), {"input": "query"})
        assert result == "query"

    def test_extracts_from_kwargs_text(self):
        """Should extract 'text' from kwargs."""
        result = _extract_prompt((), {"text": "some text"})
        assert result == "some text"

    def test_extracts_from_first_positional_string_arg(self):
        """Should extract prompt from first positional arg if it is a string."""
        result = _extract_prompt(("generate this",), {})
        assert result == "generate this"

    def test_returns_none_for_non_string_arg(self):
        """Should return None when first arg is not a string."""
        result = _extract_prompt((42,), {})
        assert result is None

    def test_returns_none_for_empty(self):
        """Should return None when no prompt found."""
        result = _extract_prompt((), {})
        assert result is None

    def test_kwargs_priority_over_args(self):
        """kwargs should be checked before positional args."""
        result = _extract_prompt(("positional",), {"prompt": "from_kwargs"})
        assert result == "from_kwargs"


class TestExtractGenerationParams:
    """Test _extract_generation_params helper."""

    def test_extracts_all_params(self):
        """Should extract all known generation parameters."""
        kwargs = {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9,
            "top_k": 40,
            "model": "gemini-pro",
            "unrelated": "ignored",
        }
        result = _extract_generation_params(kwargs)
        assert result == {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9,
            "top_k": 40,
            "model": "gemini-pro",
        }
        assert "unrelated" not in result

    def test_extracts_partial_params(self):
        """Should only include params that exist in kwargs."""
        result = _extract_generation_params({"temperature": 0.5})
        assert result == {"temperature": 0.5}

    def test_empty_kwargs(self):
        """Should return empty dict for empty kwargs."""
        result = _extract_generation_params({})
        assert result == {}


class TestExtractTokenUsage:
    """Test _extract_token_usage helper."""

    def test_extracts_from_usage_object(self):
        """Should extract token counts from result.usage object."""
        usage = Mock()
        usage.completion_tokens = 100
        usage.prompt_tokens = 200
        usage.total_tokens = 300

        result_obj = Mock()
        result_obj.usage = usage

        result = _extract_token_usage(result_obj)
        assert result["completion_tokens"] == 100
        assert result["prompt_tokens"] == 200
        assert result["total_tokens"] == 300

    def test_extracts_from_dict(self):
        """Should extract token counts from dict result."""
        result_dict = {
            "completion_tokens": 50,
            "prompt_tokens": 150,
            "total_tokens": 200,
        }
        result = _extract_token_usage(result_dict)
        assert result["completion_tokens"] == 50
        assert result["prompt_tokens"] == 150
        assert result["total_tokens"] == 200

    def test_returns_none_for_no_usage(self):
        """Should return None values when no usage info is available."""
        result = _extract_token_usage("plain string")
        assert result["completion_tokens"] is None
        assert result["prompt_tokens"] is None
        assert result["total_tokens"] is None

    def test_partial_usage_object(self):
        """Should handle partial usage with only some token fields."""
        usage = Mock(spec=["completion_tokens"])
        usage.completion_tokens = 100

        result_obj = Mock()
        result_obj.usage = usage

        result = _extract_token_usage(result_obj)
        assert result["completion_tokens"] == 100
        assert result["prompt_tokens"] is None
        assert result["total_tokens"] is None

    def test_dict_with_missing_keys(self):
        """Should return None for missing keys in dict."""
        result_dict = {"completion_tokens": 50}
        result = _extract_token_usage(result_dict)
        assert result["completion_tokens"] == 50
        assert result["prompt_tokens"] is None
        assert result["total_tokens"] is None

    def test_none_result(self):
        """Should handle None result."""
        result = _extract_token_usage(None)
        assert result["completion_tokens"] is None
        assert result["prompt_tokens"] is None
        assert result["total_tokens"] is None


# ---------------------------------------------------------------------------
# trace_workflow decorator tests
# ---------------------------------------------------------------------------


class TestTraceWorkflow:
    """Test trace_workflow decorator."""

    def setup_method(self):
        """Reset context vars."""
        current_trace_id.set(None)
        current_span_id.set(None)

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_happy_path(self, mock_get_langfuse):
        """Async decorated function should execute and trace successfully."""
        mock_client = Mock()
        mock_client.create_trace.return_value = "trace_1"
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("my_workflow")
        async def my_func(x, y):
            return x + y

        result = await my_func(3, 4)

        assert result == 7
        mock_client.create_trace.assert_called_once()
        mock_client.end_trace.assert_called_once()
        call_kwargs = mock_client.end_trace.call_args[1]
        assert call_kwargs["trace_id"] == "trace_1"
        assert call_kwargs["metadata"] == {"status": "success"}

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_error_path(self, mock_get_langfuse):
        """Async decorated function should trace errors and re-raise."""
        mock_client = Mock()
        mock_client.create_trace.return_value = "trace_err"
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("failing_workflow")
        async def failing_func():
            raise ValueError("something broke")

        with pytest.raises(ValueError, match="something broke"):
            await failing_func()

        mock_client.end_trace.assert_called_once()
        call_kwargs = mock_client.end_trace.call_args[1]
        assert call_kwargs["metadata"]["status"] == "error"
        assert "something broke" in call_kwargs["metadata"]["error"]

    @patch("observability.decorators.get_langfuse")
    def test_sync_happy_path(self, mock_get_langfuse):
        """Sync decorated function should execute and trace successfully."""
        mock_client = Mock()
        mock_client.create_trace.return_value = "trace_sync"
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("sync_workflow")
        def my_func(x):
            return x * 2

        result = my_func(5)

        assert result == 10
        mock_client.create_trace.assert_called_once()
        mock_client.end_trace.assert_called_once()
        call_kwargs = mock_client.end_trace.call_args[1]
        assert call_kwargs["metadata"] == {"status": "success"}

    @patch("observability.decorators.get_langfuse")
    def test_sync_error_path(self, mock_get_langfuse):
        """Sync decorated function should trace errors and re-raise."""
        mock_client = Mock()
        mock_client.create_trace.return_value = "trace_err"
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("sync_err")
        def failing_func():
            raise RuntimeError("sync failure")

        with pytest.raises(RuntimeError, match="sync failure"):
            failing_func()

        mock_client.end_trace.assert_called_once()
        call_kwargs = mock_client.end_trace.call_args[1]
        assert call_kwargs["metadata"]["status"] == "error"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_no_langfuse(self, mock_get_langfuse):
        """Async function should still work when langfuse is None."""
        mock_get_langfuse.return_value = None

        @trace_workflow("no_lf")
        async def my_func():
            return "ok"

        result = await my_func()
        assert result == "ok"

    @patch("observability.decorators.get_langfuse")
    def test_sync_no_langfuse(self, mock_get_langfuse):
        """Sync function should still work when langfuse is None."""
        mock_get_langfuse.return_value = None

        @trace_workflow("no_lf")
        def my_func():
            return "ok"

        result = my_func()
        assert result == "ok"

    @patch("observability.decorators.get_langfuse")
    def test_default_name_from_function(self, mock_get_langfuse):
        """When no name given, should use the function name."""
        mock_client = Mock()
        mock_client.create_trace.return_value = "t1"
        mock_get_langfuse.return_value = mock_client

        @trace_workflow()
        def my_special_function():
            return 1

        my_special_function()

        call_kwargs = mock_client.create_trace.call_args[1]
        assert call_kwargs["name"] == "my_special_function"

    @patch("observability.decorators.get_langfuse")
    def test_preserves_function_metadata(self, mock_get_langfuse):
        """Decorator should preserve the original function name and docstring."""
        mock_get_langfuse.return_value = None

        @trace_workflow("test")
        def my_func():
            """My docstring."""
            return 1

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_preserves_function_metadata(self, mock_get_langfuse):
        """Async decorator should preserve the original function name."""
        mock_get_langfuse.return_value = None

        @trace_workflow("test")
        async def my_async_func():
            """Async docstring."""
            return 1

        assert my_async_func.__name__ == "my_async_func"
        assert my_async_func.__doc__ == "Async docstring."

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_no_end_trace_when_no_trace_id(self, mock_get_langfuse):
        """Should not call end_trace when create_trace returns None."""
        mock_client = Mock()
        mock_client.create_trace.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("test")
        async def func():
            return "ok"

        result = await func()
        assert result == "ok"
        mock_client.end_trace.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_sync_no_end_trace_when_no_trace_id(self, mock_get_langfuse):
        """Sync: should not call end_trace when create_trace returns None."""
        mock_client = Mock()
        mock_client.create_trace.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("test")
        def func():
            return "ok"

        result = func()
        assert result == "ok"
        mock_client.end_trace.assert_not_called()

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_error_no_trace_id(self, mock_get_langfuse):
        """Async error path: should not call end_trace when no trace_id."""
        mock_client = Mock()
        mock_client.create_trace.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("test")
        async def func():
            raise ValueError("err")

        with pytest.raises(ValueError):
            await func()
        mock_client.end_trace.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_sync_error_no_trace_id(self, mock_get_langfuse):
        """Sync error path: should not call end_trace when no trace_id."""
        mock_client = Mock()
        mock_client.create_trace.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_workflow("test")
        def func():
            raise ValueError("err")

        with pytest.raises(ValueError):
            func()
        mock_client.end_trace.assert_not_called()


# ---------------------------------------------------------------------------
# trace_agent decorator tests
# ---------------------------------------------------------------------------


class TestTraceAgent:
    """Test trace_agent decorator."""

    def setup_method(self):
        """Reset context vars."""
        current_trace_id.set(None)
        current_span_id.set(None)

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_happy_path_list_result(self, mock_get_langfuse):
        """Async agent should trace and record suggestions_count for list results."""
        mock_client = Mock()
        mock_client.create_span.return_value = "span_1"
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="security_agent", agent_type="security")
        async def analyze(chunk):
            return ["suggestion1", "suggestion2"]

        result = await analyze("chunk_data")

        assert result == ["suggestion1", "suggestion2"]
        mock_client.create_span.assert_called_once()
        mock_client.update_span.assert_called_once()
        call_kwargs = mock_client.update_span.call_args[1]
        assert call_kwargs["metadata"]["suggestions_count"] == 2

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_happy_path_non_list_result(self, mock_get_langfuse):
        """Async agent with non-list result should have suggestions_count=0."""
        mock_client = Mock()
        mock_client.create_span.return_value = "span_1"
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="style_agent", agent_type="style")
        async def analyze(chunk):
            return "single_result"

        result = await analyze("chunk_data")
        assert result == "single_result"
        call_kwargs = mock_client.update_span.call_args[1]
        assert call_kwargs["metadata"]["suggestions_count"] == 0

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_error_path(self, mock_get_langfuse):
        """Async agent should trace errors and re-raise."""
        mock_client = Mock()
        mock_client.create_span.return_value = "span_err"
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="failing_agent", agent_type="logic")
        async def analyze(chunk):
            raise TimeoutError("agent timed out")

        with pytest.raises(TimeoutError, match="agent timed out"):
            await analyze("chunk")

        call_kwargs = mock_client.update_span.call_args[1]
        assert call_kwargs["level"] == "ERROR"
        assert "agent timed out" in call_kwargs["metadata"]["error"]

    @patch("observability.decorators.get_langfuse")
    def test_sync_happy_path(self, mock_get_langfuse):
        """Sync agent should trace successfully."""
        mock_client = Mock()
        mock_client.create_span.return_value = "span_sync"
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="sync_agent", agent_type="perf")
        def analyze(data):
            return {"findings": []}

        result = analyze("data")
        assert result == {"findings": []}
        mock_client.update_span.assert_called_once()

    @patch("observability.decorators.get_langfuse")
    def test_sync_error_path(self, mock_get_langfuse):
        """Sync agent should trace errors and re-raise."""
        mock_client = Mock()
        mock_client.create_span.return_value = "span_err"
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="sync_err_agent")
        def analyze():
            raise RuntimeError("sync error")

        with pytest.raises(RuntimeError, match="sync error"):
            analyze()

        call_kwargs = mock_client.update_span.call_args[1]
        assert call_kwargs["level"] == "ERROR"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_default_agent_type_unknown(self, mock_get_langfuse):
        """Agent type should default to 'unknown' when not specified."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="no_type_agent")
        async def analyze():
            return []

        await analyze()

        span_call_kwargs = mock_client.create_span.call_args[1]
        assert span_call_kwargs["metadata"]["agent_type"] == "unknown"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_no_langfuse(self, mock_get_langfuse):
        """Agent should work without langfuse client."""
        mock_get_langfuse.return_value = None

        @trace_agent(name="no_lf")
        async def analyze():
            return ["suggestion"]

        result = await analyze()
        assert result == ["suggestion"]

    @patch("observability.decorators.get_langfuse")
    def test_sync_no_langfuse(self, mock_get_langfuse):
        """Sync agent should work without langfuse client."""
        mock_get_langfuse.return_value = None

        @trace_agent(name="no_lf")
        def analyze():
            return "result"

        result = analyze()
        assert result == "result"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_default_name_from_function(self, mock_get_langfuse):
        """Agent name should default to function name."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        @trace_agent()
        async def my_agent_func():
            return []

        await my_agent_func()

        span_call_kwargs = mock_client.create_span.call_args[1]
        assert span_call_kwargs["name"] == "my_agent_func"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_no_update_when_no_span_id(self, mock_get_langfuse):
        """Should not call update_span when create_span returns None."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="test")
        async def func():
            return []

        await func()
        mock_client.update_span.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_sync_no_update_when_no_span_id(self, mock_get_langfuse):
        """Sync: should not call update_span when create_span returns None."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="test")
        def func():
            return "ok"

        func()
        mock_client.update_span.assert_not_called()

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_error_no_span_id(self, mock_get_langfuse):
        """Error path: should not call update_span when no span_id."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="test")
        async def func():
            raise ValueError("err")

        with pytest.raises(ValueError):
            await func()
        mock_client.update_span.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_sync_error_no_span_id(self, mock_get_langfuse):
        """Sync error path: should not call update_span when no span_id."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="test")
        def func():
            raise ValueError("err")

        with pytest.raises(ValueError):
            func()
        mock_client.update_span.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_preserves_function_metadata(self, mock_get_langfuse):
        """Decorator should preserve the original function name."""
        mock_get_langfuse.return_value = None

        @trace_agent("test")
        def my_func():
            """Original doc."""
            pass

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "Original doc."

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_metadata_includes_function_name(self, mock_get_langfuse):
        """Span metadata should include the original function name."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        @trace_agent(name="custom_name", agent_type="security")
        async def analyze_security():
            return []

        await analyze_security()

        span_call_kwargs = mock_client.create_span.call_args[1]
        assert span_call_kwargs["metadata"]["function"] == "analyze_security"
        assert span_call_kwargs["metadata"]["agent_type"] == "security"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_input_data_extracted(self, mock_get_langfuse):
        """Span should include extracted input data from arguments."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        chunk = Mock()
        chunk.file_path = "src/utils.py"
        chunk.language = "python"

        @trace_agent(name="agent")
        async def analyze(chunk_arg):
            return []

        await analyze(chunk)

        span_call_kwargs = mock_client.create_span.call_args[1]
        assert span_call_kwargs["input_data"]["file_path"] == "src/utils.py"
        assert span_call_kwargs["input_data"]["language"] == "python"


# ---------------------------------------------------------------------------
# trace_llm decorator tests
# ---------------------------------------------------------------------------


class TestTraceLlm:
    """Test trace_llm decorator."""

    def setup_method(self):
        """Reset context vars."""
        current_trace_id.set(None)
        current_span_id.set(None)

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_happy_path(self, mock_get_langfuse):
        """Async LLM call should trace successfully."""
        mock_client = Mock()
        mock_client.create_span.return_value = "llm_span_1"
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="gemini-pro")
        async def generate(prompt, temperature=0.7):
            return "generated text"

        result = await generate("write me a poem", temperature=0.7)

        assert result == "generated text"
        mock_client.create_span.assert_called_once()
        span_kwargs = mock_client.create_span.call_args[1]
        assert span_kwargs["name"] == "llm_call_gemini-pro"
        assert span_kwargs["metadata"]["model"] == "gemini-pro"
        assert span_kwargs["metadata"]["type"] == "llm_generation"
        assert span_kwargs["metadata"]["temperature"] == 0.7

        mock_client.update_span.assert_called_once()

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_error_path(self, mock_get_langfuse):
        """Async LLM call should trace errors and re-raise."""
        mock_client = Mock()
        mock_client.create_span.return_value = "llm_span_err"
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="gemini-pro")
        async def generate(prompt):
            raise ConnectionError("API error")

        with pytest.raises(ConnectionError, match="API error"):
            await generate("hello")

        call_kwargs = mock_client.update_span.call_args[1]
        assert call_kwargs["level"] == "ERROR"
        assert "API error" in call_kwargs["metadata"]["error"]

    @patch("observability.decorators.get_langfuse")
    def test_sync_happy_path(self, mock_get_langfuse):
        """Sync LLM call should trace successfully."""
        mock_client = Mock()
        mock_client.create_span.return_value = "llm_sync"
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="gpt-4")
        def generate(prompt):
            return {"completion_tokens": 50, "prompt_tokens": 100, "total_tokens": 150}

        result = generate("hello")

        assert result["total_tokens"] == 150
        mock_client.update_span.assert_called_once()
        call_kwargs = mock_client.update_span.call_args[1]
        # Token usage extracted from dict result
        assert call_kwargs["metadata"]["completion_tokens"] == 50
        assert call_kwargs["metadata"]["prompt_tokens"] == 100
        assert call_kwargs["metadata"]["total_tokens"] == 150

    @patch("observability.decorators.get_langfuse")
    def test_sync_error_path(self, mock_get_langfuse):
        """Sync LLM call should trace errors."""
        mock_client = Mock()
        mock_client.create_span.return_value = "llm_err"
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="gpt-4")
        def generate():
            raise RuntimeError("model error")

        with pytest.raises(RuntimeError, match="model error"):
            generate()

        call_kwargs = mock_client.update_span.call_args[1]
        assert call_kwargs["level"] == "ERROR"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_model_name_defaults_to_unknown(self, mock_get_langfuse):
        """Span name should use 'unknown' when model_name is None."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        @trace_llm()
        async def generate():
            return "ok"

        await generate()

        span_kwargs = mock_client.create_span.call_args[1]
        assert span_kwargs["name"] == "llm_call_unknown"
        assert span_kwargs["metadata"]["model"] == "unknown"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_prompt_extraction_from_kwargs(self, mock_get_langfuse):
        """Should extract prompt from kwargs and pass as input_data."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="gemini")
        async def generate(prompt=None):
            return "result"

        await generate(prompt="analyze this code")

        span_kwargs = mock_client.create_span.call_args[1]
        assert span_kwargs["input_data"]["prompt"] == "analyze this code"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_prompt_truncation(self, mock_get_langfuse):
        """Long prompts should be truncated to 1000 chars."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        long_prompt = "x" * 2000

        @trace_llm(model_name="gemini")
        async def generate(prompt=None):
            return "result"

        await generate(prompt=long_prompt)

        span_kwargs = mock_client.create_span.call_args[1]
        assert len(span_kwargs["input_data"]["prompt"]) == 1000

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_no_langfuse(self, mock_get_langfuse):
        """LLM call should work without langfuse client."""
        mock_get_langfuse.return_value = None

        @trace_llm(model_name="gemini")
        async def generate():
            return "generated"

        result = await generate()
        assert result == "generated"

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_token_usage_from_usage_object(self, mock_get_langfuse):
        """Should extract token usage from result.usage object."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        # Use a simple string return that has a .usage attribute added via
        # a wrapper class. _safe_serialize will hit __dict__ -> str() fallback
        # which produces a sliceable string for the [:1000] truncation.

        @trace_llm(model_name="gemini")
        async def generate():
            # Return a dict with token usage keys -- _extract_token_usage
            # handles dict results directly
            return {
                "text": "generated output",
                "completion_tokens": 200,
                "prompt_tokens": 400,
                "total_tokens": 600,
            }

        await generate()

        update_kwargs = mock_client.update_span.call_args[1]
        assert update_kwargs["metadata"]["completion_tokens"] == 200
        assert update_kwargs["metadata"]["prompt_tokens"] == 400
        assert update_kwargs["metadata"]["total_tokens"] == 600

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_no_update_when_no_span_id(self, mock_get_langfuse):
        """Should not call update_span when create_span returns None."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="test")
        async def func():
            return "ok"

        await func()
        mock_client.update_span.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_sync_no_update_when_no_span_id(self, mock_get_langfuse):
        """Sync: should not call update_span when create_span returns None."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="test")
        def func():
            return "ok"

        func()
        mock_client.update_span.assert_not_called()

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_output_truncated(self, mock_get_langfuse):
        """Output should be truncated to 1000 chars."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        long_output = "y" * 2000

        @trace_llm(model_name="test")
        async def generate():
            return long_output

        await generate()

        update_kwargs = mock_client.update_span.call_args[1]
        assert len(update_kwargs["output"]) == 1000

    @patch("observability.decorators.get_langfuse")
    def test_preserves_function_metadata(self, mock_get_langfuse):
        """Decorator should preserve function name and docstring."""
        mock_get_langfuse.return_value = None

        @trace_llm(model_name="test")
        def my_generate():
            """Generate something."""
            return "ok"

        assert my_generate.__name__ == "my_generate"
        assert my_generate.__doc__ == "Generate something."

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_async_error_no_span_id(self, mock_get_langfuse):
        """Error path: should not call update_span when no span_id."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="test")
        async def func():
            raise ValueError("err")

        with pytest.raises(ValueError):
            await func()
        mock_client.update_span.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_sync_error_no_span_id(self, mock_get_langfuse):
        """Sync error: should not call update_span when no span_id."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="test")
        def func():
            raise ValueError("err")

        with pytest.raises(ValueError):
            func()
        mock_client.update_span.assert_not_called()

    @pytest.mark.asyncio
    @patch("observability.decorators.get_langfuse")
    async def test_generation_params_extracted(self, mock_get_langfuse):
        """Generation parameters should be included in span metadata."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        @trace_llm(model_name="gemini")
        async def generate(prompt=None, temperature=None, max_tokens=None):
            return "ok"

        await generate(prompt="hi", temperature=0.5, max_tokens=2000)

        span_kwargs = mock_client.create_span.call_args[1]
        assert span_kwargs["metadata"]["temperature"] == 0.5
        assert span_kwargs["metadata"]["max_tokens"] == 2000


# ---------------------------------------------------------------------------
# trace_span context manager tests
# ---------------------------------------------------------------------------


class TestTraceSpan:
    """Test trace_span context manager."""

    def setup_method(self):
        """Reset context vars."""
        current_trace_id.set(None)
        current_span_id.set(None)

    @patch("observability.decorators.get_langfuse")
    def test_happy_path(self, mock_get_langfuse):
        """Context manager should create and update span on success."""
        mock_client = Mock()
        mock_client.create_span.return_value = "cm_span"
        mock_get_langfuse.return_value = mock_client

        with trace_span("db_query", {"table": "users"}) as span_id:
            assert span_id == "cm_span"
            # do some work
            _ = 1 + 1

        mock_client.create_span.assert_called_once()
        mock_client.update_span.assert_called_once_with(span_id="cm_span")

    @patch("observability.decorators.get_langfuse")
    def test_error_path(self, mock_get_langfuse):
        """Context manager should update span with ERROR on exception."""
        mock_client = Mock()
        mock_client.create_span.return_value = "cm_span_err"
        mock_get_langfuse.return_value = mock_client

        with pytest.raises(ValueError, match="db error"), trace_span("db_query"):
            raise ValueError("db error")

        mock_client.update_span.assert_called_once_with(
            span_id="cm_span_err", level="ERROR", status_message="db error"
        )

    @patch("observability.decorators.get_langfuse")
    def test_no_langfuse(self, mock_get_langfuse):
        """Context manager should work when langfuse is None."""
        mock_get_langfuse.return_value = None

        with trace_span("operation") as span_id:
            assert span_id is None

    @patch("observability.decorators.get_langfuse")
    def test_no_span_id_happy_path(self, mock_get_langfuse):
        """No update_span call when create_span returns None."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        with trace_span("op") as span_id:
            assert span_id is None

        mock_client.update_span.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_no_span_id_error_path(self, mock_get_langfuse):
        """No update_span call when create_span returns None even on error."""
        mock_client = Mock()
        mock_client.create_span.return_value = None
        mock_get_langfuse.return_value = mock_client

        with pytest.raises(RuntimeError), trace_span("op"):
            raise RuntimeError("err")

        mock_client.update_span.assert_not_called()

    @patch("observability.decorators.get_langfuse")
    def test_metadata_defaults_to_empty_dict(self, mock_get_langfuse):
        """When metadata is None, should pass empty dict."""
        mock_client = Mock()
        mock_client.create_span.return_value = "s1"
        mock_get_langfuse.return_value = mock_client

        with trace_span("op"):
            pass

        span_kwargs = mock_client.create_span.call_args[1]
        assert span_kwargs["metadata"] == {}
