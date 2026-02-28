"""Tests for observability langfuse_client module."""

import time
from unittest.mock import Mock, patch

from observability.langfuse_client import (
    LangFuseClient,
    current_span_id,
    current_trace_id,
    get_langfuse,
    init_langfuse,
)


class TestLangFuseClientInit:
    """Test LangFuseClient initialization."""

    def test_disabled_when_no_keys(self):
        """Client should be disabled when no API keys are provided."""
        client = LangFuseClient(public_key=None, secret_key=None, enabled=True)
        assert client.enabled is False

    def test_disabled_when_only_public_key(self):
        """Client should be disabled when only public key is provided."""
        client = LangFuseClient(public_key="pk-123", secret_key=None, enabled=True)
        assert client.enabled is False

    def test_disabled_when_only_secret_key(self):
        """Client should be disabled when only secret key is provided."""
        client = LangFuseClient(public_key=None, secret_key="sk-123", enabled=True)
        assert client.enabled is False

    def test_disabled_when_enabled_false(self):
        """Client should be disabled when enabled=False, even with keys."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=False)
        assert client.enabled is False

    def test_disabled_when_empty_public_key(self):
        """Client should be disabled when public key is empty string."""
        client = LangFuseClient(public_key="", secret_key="sk-123", enabled=True)
        assert client.enabled is False

    def test_stores_host(self):
        """Client should store custom host."""
        client = LangFuseClient(
            public_key=None, secret_key=None, host="https://custom.langfuse.com"
        )
        assert client.host == "https://custom.langfuse.com"

    def test_default_host(self):
        """Client should use default host when not specified."""
        client = LangFuseClient(public_key=None, secret_key=None)
        assert client.host == "https://cloud.langfuse.com"

    def test_internal_dicts_initialized_empty(self):
        """Client should initialize with empty internal dicts."""
        client = LangFuseClient(public_key=None, secret_key=None)
        assert client._traces == {}
        assert client._spans == {}
        assert client._langfuse is None

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_initialize_called_when_enabled(self, mock_init):
        """_initialize_langfuse should be called when enabled with valid keys."""
        LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_init.assert_called_once()

    @patch(
        "observability.langfuse_client.LangFuseClient._initialize_langfuse",
        side_effect=Exception("connection failed"),
    )
    def test_disabled_on_initialization_error(self, mock_init):
        """Client should be disabled when initialization raises an error."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        assert client.enabled is False


class TestLangFuseClientInitializeLangfuse:
    """Test _initialize_langfuse method."""

    def test_langfuse_import_error_sets_langfuse_none(self):
        """When langfuse package is not installed, _langfuse should be None.

        Note: the code logs a warning but keeps enabled=True (falls back to
        local-only tracking without the SDK).
        """
        client = LangFuseClient(public_key=None, secret_key=None, enabled=False)
        client.enabled = True  # Override to test the method directly

        # Patch the import inside _initialize_langfuse to raise ImportError
        with patch("builtins.__import__", side_effect=ImportError("no langfuse")):
            client._initialize_langfuse()

        assert client._langfuse is None
        # The code keeps enabled=True -- it can still do local tracking
        assert client.enabled is True

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_successful_initialization_with_sdk(self, mock_init):
        """Client should try to initialize when both keys are provided."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_init.assert_called_once()
        assert client.enabled is True


class TestCreateTrace:
    """Test create_trace method."""

    def setup_method(self):
        """Reset context vars before each test."""
        current_trace_id.set(None)
        current_span_id.set(None)

    def test_returns_none_when_disabled(self):
        """create_trace should return None when client is disabled."""
        client = LangFuseClient(public_key=None, secret_key=None, enabled=False)
        result = client.create_trace(name="test_trace")
        assert result is None

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_creates_trace_with_no_langfuse_sdk(self, mock_init):
        """create_trace should work without the Langfuse SDK (local tracking)."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None  # No SDK

        trace_id = client.create_trace(name="test_trace", metadata={"key": "value"})

        assert trace_id is not None
        assert trace_id.startswith("trace_")
        assert trace_id in client._traces
        assert client._traces[trace_id]["name"] == "test_trace"
        assert client._traces[trace_id]["metadata"] == {"key": "value"}
        assert client._traces[trace_id]["spans"] == []
        assert "start_time" in client._traces[trace_id]

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_creates_trace_sets_context_var(self, mock_init):
        """create_trace should set the current_trace_id context variable."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="my_trace")

        assert current_trace_id.get() == trace_id

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_creates_trace_with_user_and_session(self, mock_init):
        """create_trace should store user_id and session_id."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(
            name="trace",
            user_id="user-42",
            session_id="session-99",
        )

        trace_data = client._traces[trace_id]
        assert trace_data["user_id"] == "user-42"
        assert trace_data["session_id"] == "session-99"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_creates_trace_with_langfuse_sdk(self, mock_init):
        """create_trace should use the Langfuse SDK when available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_trace = Mock()
        mock_trace.id = "sdk_trace_id_123"
        mock_langfuse.trace.return_value = mock_trace
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(
            name="my_trace",
            metadata={"key": "val"},
            user_id="u1",
            session_id="s1",
        )

        assert trace_id == "sdk_trace_id_123"
        mock_langfuse.trace.assert_called_once()
        call_kwargs = mock_langfuse.trace.call_args[1]
        assert call_kwargs["name"] == "my_trace"
        assert call_kwargs["metadata"] == {"key": "val"}
        assert call_kwargs["user_id"] == "u1"
        assert call_kwargs["session_id"] == "s1"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_creates_trace_default_metadata(self, mock_init):
        """create_trace with None metadata should default to empty dict."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        assert client._traces[trace_id]["metadata"] == {}

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_creates_trace_exception_returns_none(self, mock_init):
        """create_trace should return None when an internal exception occurs."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.side_effect = Exception("SDK error")
        client._langfuse = mock_langfuse

        result = client.create_trace(name="failing_trace")
        assert result is None


class TestCreateSpan:
    """Test create_span method."""

    def setup_method(self):
        """Reset context vars before each test."""
        current_trace_id.set(None)
        current_span_id.set(None)

    def test_returns_none_when_disabled(self):
        """create_span should return None when client is disabled."""
        client = LangFuseClient(public_key=None, secret_key=None, enabled=False)
        result = client.create_span(name="test_span")
        assert result is None

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_returns_none_when_no_trace_id(self, mock_init):
        """create_span should return None when no trace ID is available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        result = client.create_span(name="test_span")
        assert result is None

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_uses_current_trace_id_when_not_provided(self, mock_init):
        """create_span should use current_trace_id context var when trace_id is None."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        # First create a trace to set the context var
        trace_id = client.create_trace(name="parent_trace")

        span_id = client.create_span(name="child_span")

        assert span_id is not None
        assert client._spans[span_id]["trace_id"] == trace_id

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_creates_span_with_explicit_trace_id(self, mock_init):
        """create_span should use the explicit trace_id when provided."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        # Create trace first so it exists in _traces
        trace_id = client.create_trace(name="trace")

        span_id = client.create_span(
            name="span",
            trace_id=trace_id,
            metadata={"agent": "security"},
            input_data={"file": "main.py"},
        )

        assert span_id is not None
        span_data = client._spans[span_id]
        assert span_data["trace_id"] == trace_id
        assert span_data["metadata"] == {"agent": "security"}
        assert span_data["input"] == {"file": "main.py"}
        assert span_data["status"] == "running"
        assert span_data["name"] == "span"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_span_added_to_trace_spans_list(self, mock_init):
        """Created span should be added to the parent trace's spans list."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id)

        assert span_id in client._traces[trace_id]["spans"]

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_span_sets_current_span_id(self, mock_init):
        """create_span should set current_span_id context variable."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id)

        assert current_span_id.get() == span_id

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_span_with_parent_span_id(self, mock_init):
        """create_span should store parent_span_id for nested spans."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        parent_span_id = client.create_span(name="parent", trace_id=trace_id)
        child_span_id = client.create_span(
            name="child",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )

        assert client._spans[child_span_id]["parent_span_id"] == parent_span_id

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_span_with_langfuse_sdk(self, mock_init):
        """create_span should use the Langfuse SDK when available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_span = Mock()
        mock_span.id = "sdk_span_id_456"
        mock_langfuse.span.return_value = mock_span
        mock_langfuse.trace.return_value = Mock(id="sdk_trace_id")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="my_span", trace_id=trace_id, input_data={"x": 1})

        assert span_id == "sdk_span_id_456"
        mock_langfuse.span.assert_called_once()

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_span_exception_returns_none(self, mock_init):
        """create_span should return None on internal exception."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.return_value = Mock(id="t1")
        mock_langfuse.span.side_effect = Exception("SDK error")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")
        result = client.create_span(name="span", trace_id=trace_id)

        assert result is None

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_span_not_added_to_nonexistent_trace(self, mock_init):
        """create_span should not fail if trace_id is not in _traces dict."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        # Set trace_id in context var but don't create a trace in _traces
        current_trace_id.set("nonexistent_trace")
        span_id = client.create_span(name="orphan_span")

        assert span_id is not None
        # Span should exist in _spans but not be added to any trace's spans list
        assert client._spans[span_id]["trace_id"] == "nonexistent_trace"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_span_default_metadata(self, mock_init):
        """create_span with None metadata should default to empty dict."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id)

        assert client._spans[span_id]["metadata"] == {}


class TestUpdateSpan:
    """Test update_span method."""

    def setup_method(self):
        """Reset context vars before each test."""
        current_trace_id.set(None)
        current_span_id.set(None)

    def test_noop_when_disabled(self):
        """update_span should do nothing when client is disabled."""
        client = LangFuseClient(public_key=None, secret_key=None, enabled=False)
        # Should not raise
        client.update_span(span_id="nonexistent", output="data")

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_noop_when_span_not_found(self, mock_init):
        """update_span should do nothing when span_id is not in _spans."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None
        # Should not raise
        client.update_span(span_id="nonexistent", output="data")

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_updates_span_data(self, mock_init):
        """update_span should update span output, duration, status."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id)

        client.update_span(
            span_id=span_id,
            output={"result": "ok"},
            metadata={"duration_seconds": 1.5},
            level="WARNING",
            status_message="Completed with warnings",
        )

        span_data = client._spans[span_id]
        assert span_data["output"] == {"result": "ok"}
        assert span_data["status"] == "completed"
        assert span_data["level"] == "WARNING"
        assert span_data["status_message"] == "Completed with warnings"
        assert span_data["metadata"]["duration_seconds"] == 1.5
        assert "duration" in span_data
        assert span_data["duration"] >= 0

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_updates_span_merges_metadata(self, mock_init):
        """update_span should merge new metadata into existing metadata."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id, metadata={"agent": "security"})

        client.update_span(span_id=span_id, metadata={"status": "error", "error": "timeout"})

        span_data = client._spans[span_id]
        assert span_data["metadata"]["agent"] == "security"
        assert span_data["metadata"]["status"] == "error"
        assert span_data["metadata"]["error"] == "timeout"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_updates_span_no_metadata(self, mock_init):
        """update_span with no metadata should not overwrite existing metadata."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id, metadata={"original": True})

        client.update_span(span_id=span_id, output="result")

        assert client._spans[span_id]["metadata"] == {"original": True}

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_updates_span_with_langfuse_sdk(self, mock_init):
        """update_span should call Langfuse SDK update_span when available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.return_value = Mock(id="t1")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")

        # Manually add a span since SDK is mocked
        span_id = "manual_span"
        client._spans[span_id] = {
            "id": span_id,
            "trace_id": trace_id,
            "name": "test",
            "metadata": {},
            "start_time": time.time(),
            "status": "running",
        }

        client.update_span(span_id=span_id, output="data", level="ERROR")

        mock_langfuse.update_span.assert_called_once()
        call_kwargs = mock_langfuse.update_span.call_args[1]
        assert call_kwargs["id"] == span_id
        assert call_kwargs["output"] == "data"
        assert call_kwargs["level"] == "ERROR"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_updates_span_exception_handled(self, mock_init):
        """update_span should handle exceptions gracefully."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.return_value = Mock(id="t1")
        mock_langfuse.update_span.side_effect = Exception("update failed")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")
        client._spans["s1"] = {
            "id": "s1",
            "trace_id": trace_id,
            "metadata": {},
            "start_time": time.time(),
            "status": "running",
        }

        # Should not raise
        client.update_span(span_id="s1", output="data")


class TestEndTrace:
    """Test end_trace method."""

    def setup_method(self):
        """Reset context vars before each test."""
        current_trace_id.set(None)
        current_span_id.set(None)

    def test_noop_when_disabled(self):
        """end_trace should do nothing when client is disabled."""
        client = LangFuseClient(public_key=None, secret_key=None, enabled=False)
        client.end_trace(trace_id="t1", output="done")

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_noop_when_trace_not_found(self, mock_init):
        """end_trace should do nothing when trace_id is not in _traces."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None
        client.end_trace(trace_id="nonexistent")

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_uses_current_trace_id_when_not_provided(self, mock_init):
        """end_trace should use current_trace_id context var when trace_id is None."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        client.end_trace(output="result", metadata={"status": "success"})

        trace_data = client._traces[trace_id]
        assert trace_data["output"] == "result"
        assert trace_data["metadata"]["status"] == "success"
        assert "duration" in trace_data

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_end_trace_sets_duration(self, mock_init):
        """end_trace should calculate and set duration."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        client.end_trace(trace_id=trace_id)

        trace_data = client._traces[trace_id]
        assert "end_time" in trace_data
        assert "duration" in trace_data
        assert trace_data["duration"] >= 0

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_end_trace_clears_context_vars(self, mock_init):
        """end_trace should clear current_trace_id and current_span_id."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id)

        assert current_trace_id.get() == trace_id
        assert current_span_id.get() == span_id

        client.end_trace(trace_id=trace_id)

        assert current_trace_id.get() is None
        assert current_span_id.get() is None

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_end_trace_merges_metadata(self, mock_init):
        """end_trace should merge new metadata into existing metadata."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace", metadata={"function": "review"})
        client.end_trace(trace_id=trace_id, metadata={"status": "success"})

        trace_data = client._traces[trace_id]
        assert trace_data["metadata"]["function"] == "review"
        assert trace_data["metadata"]["status"] == "success"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_end_trace_no_metadata(self, mock_init):
        """end_trace with no metadata should not change existing metadata."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace", metadata={"original": True})
        client.end_trace(trace_id=trace_id, output="result")

        assert client._traces[trace_id]["metadata"] == {"original": True}

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_end_trace_with_langfuse_sdk(self, mock_init):
        """end_trace should call Langfuse SDK update_trace when available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.return_value = Mock(id="t1")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")
        client.end_trace(trace_id=trace_id, output="done")

        mock_langfuse.update_trace.assert_called_once()

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_end_trace_exception_handled(self, mock_init):
        """end_trace should handle exceptions gracefully."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.return_value = Mock(id="t1")
        mock_langfuse.update_trace.side_effect = Exception("update failed")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")
        # Should not raise
        client.end_trace(trace_id=trace_id)

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_end_trace_with_none_trace_id_and_no_context(self, mock_init):
        """end_trace with None trace_id and no context var should do nothing."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None
        # Should not raise
        client.end_trace()


class TestScoreTrace:
    """Test score_trace method."""

    def setup_method(self):
        """Reset context vars before each test."""
        current_trace_id.set(None)
        current_span_id.set(None)

    def test_noop_when_disabled(self):
        """score_trace should do nothing when client is disabled."""
        client = LangFuseClient(public_key=None, secret_key=None, enabled=False)
        client.score_trace(trace_id="t1", name="quality", value=0.9)

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_adds_score_to_trace(self, mock_init):
        """score_trace should add score to the trace's scores list."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        client.score_trace(
            trace_id=trace_id,
            name="quality",
            value=0.95,
            comment="Good review",
        )

        trace_data = client._traces[trace_id]
        assert "scores" in trace_data
        assert len(trace_data["scores"]) == 1
        assert trace_data["scores"][0]["name"] == "quality"
        assert trace_data["scores"][0]["value"] == 0.95
        assert trace_data["scores"][0]["comment"] == "Good review"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_adds_multiple_scores(self, mock_init):
        """score_trace should support adding multiple scores."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        client.score_trace(trace_id=trace_id, name="quality", value=0.9)
        client.score_trace(trace_id=trace_id, name="accuracy", value=0.8)

        assert len(client._traces[trace_id]["scores"]) == 2

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_score_nonexistent_trace_no_error(self, mock_init):
        """score_trace for a non-existent trace should not raise."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        # Should not raise
        client.score_trace(trace_id="nonexistent", name="quality", value=0.5)

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_score_with_langfuse_sdk(self, mock_init):
        """score_trace should call Langfuse SDK score when available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.return_value = Mock(id="t1")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")
        client.score_trace(trace_id=trace_id, name="quality", value=0.9, comment="Great")

        mock_langfuse.score.assert_called_once_with(
            trace_id=trace_id, name="quality", value=0.9, comment="Great"
        )

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_score_exception_handled(self, mock_init):
        """score_trace should handle exceptions gracefully."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.trace.return_value = Mock(id="t1")
        mock_langfuse.score.side_effect = Exception("score failed")
        client._langfuse = mock_langfuse

        trace_id = client.create_trace(name="trace")
        # Should not raise
        client.score_trace(trace_id=trace_id, name="quality", value=0.5)


class TestGetTraceAndSpan:
    """Test get_trace and get_span methods."""

    def setup_method(self):
        """Reset context vars before each test."""
        current_trace_id.set(None)
        current_span_id.set(None)

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_get_trace_returns_data(self, mock_init):
        """get_trace should return trace data for a valid trace_id."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        data = client.get_trace(trace_id)

        assert data is not None
        assert data["name"] == "trace"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_get_trace_returns_none_for_nonexistent(self, mock_init):
        """get_trace should return None for non-existent trace_id."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        assert client.get_trace("nonexistent") is None

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_get_span_returns_data(self, mock_init):
        """get_span should return span data for a valid span_id."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None

        trace_id = client.create_trace(name="trace")
        span_id = client.create_span(name="span", trace_id=trace_id)

        data = client.get_span(span_id)
        assert data is not None
        assert data["name"] == "span"

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_get_span_returns_none_for_nonexistent(self, mock_init):
        """get_span should return None for non-existent span_id."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        assert client.get_span("nonexistent") is None


class TestFlush:
    """Test flush method."""

    def test_noop_when_disabled(self):
        """flush should do nothing when client is disabled."""
        client = LangFuseClient(public_key=None, secret_key=None, enabled=False)
        # Should not raise
        client.flush()

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_noop_when_no_langfuse_sdk(self, mock_init):
        """flush should do nothing when SDK is not available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        client._langfuse = None
        # Should not raise
        client.flush()

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_calls_langfuse_flush(self, mock_init):
        """flush should call Langfuse SDK flush when available."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        client._langfuse = mock_langfuse

        client.flush()

        mock_langfuse.flush.assert_called_once()

    @patch("observability.langfuse_client.LangFuseClient._initialize_langfuse")
    def test_flush_exception_handled(self, mock_init):
        """flush should handle exceptions gracefully."""
        client = LangFuseClient(public_key="pk-123", secret_key="sk-123", enabled=True)
        mock_langfuse = Mock()
        mock_langfuse.flush.side_effect = Exception("flush failed")
        client._langfuse = mock_langfuse

        # Should not raise
        client.flush()


class TestModuleFunctions:
    """Test module-level functions init_langfuse and get_langfuse."""

    def test_init_langfuse_creates_client(self):
        """init_langfuse should create a global LangFuseClient."""
        import observability.langfuse_client as module

        old_client = module._langfuse_client
        try:
            client = init_langfuse(public_key=None, secret_key=None, enabled=False)
            assert isinstance(client, LangFuseClient)
            assert module._langfuse_client is client
        finally:
            module._langfuse_client = old_client

    def test_init_langfuse_returns_client(self):
        """init_langfuse should return the created client."""
        import observability.langfuse_client as module

        old_client = module._langfuse_client
        try:
            client = init_langfuse(enabled=False)
            assert client is get_langfuse()
        finally:
            module._langfuse_client = old_client

    def test_get_langfuse_returns_none_initially(self):
        """get_langfuse should return None if not initialized."""
        import observability.langfuse_client as module

        old_client = module._langfuse_client
        try:
            module._langfuse_client = None
            assert get_langfuse() is None
        finally:
            module._langfuse_client = old_client

    def test_init_langfuse_with_custom_params(self):
        """init_langfuse should pass parameters to the client."""
        import observability.langfuse_client as module

        old_client = module._langfuse_client
        try:
            client = init_langfuse(
                public_key=None,
                secret_key=None,
                host="https://custom.host.com",
                enabled=False,
            )
            assert client.host == "https://custom.host.com"
        finally:
            module._langfuse_client = old_client
