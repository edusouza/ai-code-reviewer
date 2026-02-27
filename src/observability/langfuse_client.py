"""LangFuse integration for observability and tracing."""

import logging
import time
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger(__name__)

# Context variables for tracking current trace/span
current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)
current_span_id: ContextVar[str | None] = ContextVar("current_span_id", default=None)


class LangFuseClient:
    """Client for LangFuse observability platform."""

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str = "https://cloud.langfuse.com",
        enabled: bool = True,
    ):
        """
        Initialize LangFuse client.

        Args:
            public_key: LangFuse public API key
            secret_key: LangFuse secret API key
            host: LangFuse host URL
            enabled: Whether tracing is enabled
        """
        self.enabled = enabled and bool(public_key and secret_key)
        self.host = host
        self.public_key = public_key
        self.secret_key = secret_key

        self._langfuse = None
        self._traces: dict[str, dict[str, Any]] = {}
        self._spans: dict[str, dict[str, Any]] = {}

        if self.enabled:
            try:
                self._initialize_langfuse()
            except Exception as e:
                logger.error(f"Failed to initialize LangFuse: {e}")
                self.enabled = False

    def _initialize_langfuse(self) -> None:
        """Initialize the LangFuse SDK."""
        try:
            from langfuse import Langfuse

            self._langfuse = Langfuse(
                public_key=self.public_key, secret_key=self.secret_key, host=self.host
            )
            logger.info("LangFuse client initialized successfully")
        except ImportError:
            logger.warning("langfuse package not installed, using mock client")
            self._langfuse = None

    def create_trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> str | None:
        """
        Create a new trace.

        Args:
            name: Trace name
            metadata: Additional metadata
            user_id: Optional user identifier
            session_id: Optional session identifier

        Returns:
            Trace ID if created, None otherwise
        """
        if not self.enabled:
            return None

        trace_id = f"trace_{int(time.time() * 1000)}_{hash(name) & 0xFFFF}"

        try:
            if self._langfuse:
                trace = self._langfuse.trace(
                    id=trace_id,
                    name=name,
                    metadata=metadata or {},
                    user_id=user_id,
                    session_id=session_id,
                )
                trace_id = trace.id

            self._traces[trace_id] = {
                "id": trace_id,
                "name": name,
                "metadata": metadata or {},
                "user_id": user_id,
                "session_id": session_id,
                "start_time": time.time(),
                "spans": [],
            }

            # Set as current trace
            current_trace_id.set(trace_id)

            logger.debug(f"Created trace: {trace_id} - {name}")
            return trace_id

        except Exception as e:
            logger.error(f"Failed to create trace: {e}")
            return None

    def create_span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        input_data: Any | None = None,
    ) -> str | None:
        """
        Create a new span within a trace.

        Args:
            name: Span name
            trace_id: Parent trace ID (uses current if not provided)
            parent_span_id: Parent span ID for nested spans
            metadata: Additional metadata
            input_data: Input data for the span

        Returns:
            Span ID if created, None otherwise
        """
        if not self.enabled:
            return None

        # Use current trace if not provided
        if trace_id is None:
            trace_id = current_trace_id.get()

        if trace_id is None:
            logger.warning("No trace ID available for span")
            return None

        span_id = f"span_{int(time.time() * 1000)}_{hash(name) & 0xFFFF}"

        try:
            if self._langfuse and trace_id in self._traces:
                span = self._langfuse.span(
                    trace_id=trace_id,
                    id=span_id,
                    name=name,
                    parent_observation_id=parent_span_id,
                    metadata=metadata or {},
                    input=input_data,
                )
                span_id = span.id

            self._spans[span_id] = {
                "id": span_id,
                "trace_id": trace_id,
                "name": name,
                "parent_span_id": parent_span_id,
                "metadata": metadata or {},
                "input": input_data,
                "start_time": time.time(),
                "status": "running",
            }

            if trace_id in self._traces:
                self._traces[trace_id]["spans"].append(span_id)

            # Set as current span
            current_span_id.set(span_id)

            logger.debug(f"Created span: {span_id} - {name}")
            return span_id

        except Exception as e:
            logger.error(f"Failed to create span: {e}")
            return None

    def update_span(
        self,
        span_id: str,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        level: str = "DEFAULT",
        status_message: str | None = None,
    ) -> None:
        """
        Update a span with output and completion status.

        Args:
            span_id: Span ID to update
            output: Output data
            metadata: Additional metadata to merge
            level: Log level (DEBUG, DEFAULT, WARNING, ERROR)
            status_message: Status message
        """
        if not self.enabled or span_id not in self._spans:
            return

        try:
            span = self._spans[span_id]
            span["output"] = output
            span["end_time"] = time.time()
            span["duration"] = span["end_time"] - span["start_time"]
            span["status"] = "completed"
            span["level"] = level
            span["status_message"] = status_message

            if metadata:
                span["metadata"].update(metadata)

            if self._langfuse:
                self._langfuse.update_span(
                    id=span_id,
                    trace_id=span["trace_id"],
                    output=output,
                    metadata=span["metadata"],
                    level=level,
                    status_message=status_message,
                )

            logger.debug(f"Updated span: {span_id} - duration: {span['duration']:.2f}s")

        except Exception as e:
            logger.error(f"Failed to update span: {e}")

    def end_trace(
        self,
        trace_id: str | None = None,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        End a trace and mark it complete.

        Args:
            trace_id: Trace ID to end (uses current if not provided)
            output: Final output data
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        if trace_id is None:
            trace_id = current_trace_id.get()

        if trace_id is None or trace_id not in self._traces:
            return

        try:
            trace = self._traces[trace_id]
            trace["end_time"] = time.time()
            trace["duration"] = trace["end_time"] - trace["start_time"]
            trace["output"] = output

            if metadata:
                trace["metadata"].update(metadata)

            if self._langfuse:
                self._langfuse.update_trace(id=trace_id, output=output, metadata=trace["metadata"])

            logger.debug(f"Ended trace: {trace_id} - duration: {trace['duration']:.2f}s")

            # Clear current trace
            current_trace_id.set(None)
            current_span_id.set(None)

        except Exception as e:
            logger.error(f"Failed to end trace: {e}")

    def score_trace(self, trace_id: str, name: str, value: float, comment: str | None = None) -> None:
        """
        Add a score to a trace.

        Args:
            trace_id: Trace ID to score
            name: Score name
            value: Score value (numeric)
            comment: Optional comment
        """
        if not self.enabled:
            return

        try:
            if self._langfuse:
                self._langfuse.score(trace_id=trace_id, name=name, value=value, comment=comment)

            if trace_id in self._traces:
                if "scores" not in self._traces[trace_id]:
                    self._traces[trace_id]["scores"] = []
                self._traces[trace_id]["scores"].append(
                    {"name": name, "value": value, "comment": comment}
                )

            logger.debug(f"Added score to trace {trace_id}: {name}={value}")

        except Exception as e:
            logger.error(f"Failed to score trace: {e}")

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Get trace data by ID."""
        return self._traces.get(trace_id)

    def get_span(self, span_id: str) -> dict[str, Any] | None:
        """Get span data by ID."""
        return self._spans.get(span_id)

    def flush(self) -> None:
        """Flush all pending traces and spans to LangFuse."""
        if self.enabled and self._langfuse:
            try:
                self._langfuse.flush()
                logger.debug("Flushed LangFuse traces")
            except Exception as e:
                logger.error(f"Failed to flush LangFuse: {e}")


# Global client instance
_langfuse_client: LangFuseClient | None = None


def init_langfuse(
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str = "https://cloud.langfuse.com",
    enabled: bool = True,
) -> LangFuseClient:
    """
    Initialize the global LangFuse client.

    Args:
        public_key: LangFuse public API key
        secret_key: LangFuse secret API key
        host: LangFuse host URL
        enabled: Whether tracing is enabled

    Returns:
        LangFuseClient instance
    """
    global _langfuse_client
    _langfuse_client = LangFuseClient(
        public_key=public_key, secret_key=secret_key, host=host, enabled=enabled
    )
    return _langfuse_client


def get_langfuse() -> LangFuseClient | None:
    """Get the global LangFuse client instance."""
    return _langfuse_client
