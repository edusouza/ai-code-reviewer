"""Cloud Monitoring metrics integration."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    value: float
    timestamp: datetime
    labels: dict[str, str]
    metric_type: str  # gauge, counter, histogram


class CloudMetricsClient:
    """Client for Google Cloud Monitoring metrics."""

    def __init__(self, project_id: str | None = None, enabled: bool = True):
        """
        Initialize Cloud Monitoring client.

        Args:
            project_id: GCP project ID
            enabled: Whether metrics collection is enabled
        """
        self.project_id = project_id or settings.project_id
        self.enabled = enabled and bool(self.project_id)

        self._client = None
        self._metrics_buffer: list[MetricPoint] = []
        self._buffer_size = 100

        if self.enabled:
            try:
                self._initialize_client()
            except Exception as e:
                logger.error(f"Failed to initialize Cloud Monitoring: {e}")
                self.enabled = False

    def _initialize_client(self) -> None:
        """Initialize the Cloud Monitoring client."""
        try:
            from google.cloud.monitoring_v3 import MetricServiceClient

            self._client = MetricServiceClient()
            self._project_name = f"projects/{self.project_id}"
            logger.info("Cloud Monitoring client initialized")
        except ImportError:
            logger.warning("google-cloud-monitoring not installed, metrics disabled")
            self.enabled = False

    def record_gauge(
        self, metric_name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """
        Record a gauge metric (value at a point in time).

        Args:
            metric_name: Name of the metric
            value: Current value
            labels: Optional labels for the metric
        """
        if not self.enabled:
            return

        point = MetricPoint(
            name=metric_name,
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            metric_type="gauge",
        )
        self._add_to_buffer(point)

    def record_counter(
        self, metric_name: str, value: float = 1, labels: dict[str, str] | None = None
    ) -> None:
        """
        Record a counter metric (accumulating value).

        Args:
            metric_name: Name of the metric
            value: Increment value (default 1)
            labels: Optional labels for the metric
        """
        if not self.enabled:
            return

        point = MetricPoint(
            name=metric_name,
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            metric_type="counter",
        )
        self._add_to_buffer(point)

    def record_histogram(
        self, metric_name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """
        Record a histogram metric (distribution of values).

        Args:
            metric_name: Name of the metric
            value: Value to record
            labels: Optional labels for the metric
        """
        if not self.enabled:
            return

        point = MetricPoint(
            name=metric_name,
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            metric_type="histogram",
        )
        self._add_to_buffer(point)

    def record_timing(
        self, metric_name: str, duration_seconds: float, labels: dict[str, str] | None = None
    ) -> None:
        """
        Record a timing metric.

        Args:
            metric_name: Name of the metric
            duration_seconds: Duration in seconds
            labels: Optional labels
        """
        self.record_histogram(
            metric_name=f"{metric_name}_duration_seconds", value=duration_seconds, labels=labels
        )

    def _add_to_buffer(self, point: MetricPoint) -> None:
        """Add a metric point to the buffer."""
        self._metrics_buffer.append(point)

        if len(self._metrics_buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush all buffered metrics to Cloud Monitoring."""
        if not self.enabled or not self._metrics_buffer:
            return

        try:
            from google.cloud.monitoring_v3 import Point as MonitoringPoint
            from google.cloud.monitoring_v3 import TimeSeries

            # Group metrics by name and type
            grouped_metrics: dict[str, list[MetricPoint]] = {}
            for point in self._metrics_buffer:
                key = f"{point.metric_type}:{point.name}"
                if key not in grouped_metrics:
                    grouped_metrics[key] = []
                grouped_metrics[key].append(point)

            # Create time series for each group
            time_series_list = []
            for key, points in grouped_metrics.items():
                metric_type, metric_name = key.split(":", 1)

                # Build time series
                series = TimeSeries()
                series.metric.type = f"custom.googleapis.com/ai_reviewer/{metric_name}"
                series.resource.type = "generic_task"
                series.resource.labels["project_id"] = self.project_id
                series.resource.labels["location"] = "global"
                series.resource.labels["namespace"] = "ai-code-reviewer"
                series.resource.labels["job"] = "review-worker"

                # Add labels
                for point in points:
                    for label_key, label_value in point.labels.items():
                        series.metric.labels[label_key] = label_value

                # Add data points
                for point in points:
                    ts_point = MonitoringPoint()
                    ts_point.interval.end_time.seconds = int(point.timestamp.timestamp())
                    ts_point.interval.end_time.nanos = int(
                        (point.timestamp.timestamp() % 1) * 10**9
                    )

                    if metric_type == "counter":
                        ts_point.value.int64_value = int(point.value)
                    elif metric_type == "histogram":
                        ts_point.value.double_value = point.value
                    else:
                        ts_point.value.double_value = point.value

                    series.points.append(ts_point)

                time_series_list.append(series)

            # Send to Cloud Monitoring in batches
            batch_size = 200  # Cloud Monitoring limit
            if self._client is not None:
                for i in range(0, len(time_series_list), batch_size):
                    batch = time_series_list[i : i + batch_size]
                    self._client.create_time_series(name=self._project_name, time_series=batch)

            logger.debug(f"Flushed {len(self._metrics_buffer)} metrics to Cloud Monitoring")
            self._metrics_buffer.clear()

        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")

    def record_review_metrics(
        self,
        pr_event: Any,
        duration_seconds: float,
        suggestions_count: int,
        tokens_used: int,
        cost_usd: float,
        success: bool,
    ) -> None:
        """
        Record comprehensive review metrics.

        Args:
            pr_event: PR event data
            duration_seconds: Review duration
            suggestions_count: Number of suggestions generated
            tokens_used: Total tokens consumed
            cost_usd: Estimated cost in USD
            success: Whether the review succeeded
        """
        labels = {
            "provider": getattr(pr_event, "provider", "unknown"),
            "repo_owner": getattr(pr_event, "repo_owner", "unknown"),
            "status": "success" if success else "failed",
        }

        self.record_timing("review", duration_seconds, labels)
        self.record_gauge("review_suggestions_count", suggestions_count, labels)
        self.record_gauge("review_tokens_used", tokens_used, labels)
        self.record_gauge("review_cost_usd", cost_usd, labels)
        self.record_counter("reviews_total", 1, labels)

    def record_agent_metrics(
        self, agent_type: str, duration_seconds: float, suggestions_found: int, success: bool
    ) -> None:
        """
        Record agent execution metrics.

        Args:
            agent_type: Type of agent
            duration_seconds: Execution duration
            suggestions_found: Number of suggestions found
            success: Whether execution succeeded
        """
        labels = {"agent_type": agent_type, "status": "success" if success else "failed"}

        self.record_timing(f"agent_{agent_type}", duration_seconds, labels)
        self.record_gauge(f"agent_{agent_type}_suggestions", suggestions_found, labels)
        self.record_counter(f"agent_{agent_type}_runs", 1, labels)

    def record_llm_metrics(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_seconds: float,
        success: bool,
    ) -> None:
        """
        Record LLM call metrics.

        Args:
            model_name: Model used
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            duration_seconds: Call duration
            success: Whether call succeeded
        """
        labels = {"model": model_name, "status": "success" if success else "failed"}

        total_tokens = prompt_tokens + completion_tokens

        self.record_gauge("llm_prompt_tokens", prompt_tokens, labels)
        self.record_gauge("llm_completion_tokens", completion_tokens, labels)
        self.record_gauge("llm_total_tokens", total_tokens, labels)
        self.record_timing("llm_request", duration_seconds, labels)
        self.record_counter("llm_requests", 1, labels)

    def record_feedback_metrics(self, feedback_type: str, score: float, provider: str) -> None:
        """
        Record feedback metrics.

        Args:
            feedback_type: Type of feedback (positive, negative, neutral)
            score: Score value
            provider: Provider that received the feedback
        """
        labels = {"feedback_type": feedback_type, "provider": provider}

        self.record_gauge("feedback_score", score, labels)
        self.record_counter(f"feedback_{feedback_type}", 1, labels)


# Global client instance
_metrics_client: CloudMetricsClient | None = None


def init_metrics(project_id: str | None = None, enabled: bool = True) -> CloudMetricsClient:
    """
    Initialize the global metrics client.

    Args:
        project_id: GCP project ID
        enabled: Whether metrics are enabled

    Returns:
        CloudMetricsClient instance
    """
    global _metrics_client
    _metrics_client = CloudMetricsClient(project_id=project_id, enabled=enabled)
    return _metrics_client


def get_metrics_client() -> CloudMetricsClient | None:
    """Get the global metrics client instance."""
    return _metrics_client
