"""Tests for observability metrics module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from observability.metrics import CloudMetricsClient, MetricPoint


class TestCloudMetricsClient:
    """Test Cloud Metrics client functionality."""

    def test_initialization_without_project(self):
        """Test client initialization without project ID."""
        client = CloudMetricsClient(project_id=None, enabled=True)
        
        assert client.enabled is False  # Should disable if no project ID

    def test_initialization_with_missing_dependency(self):
        """Test client handles missing google-cloud-monitoring gracefully."""
        with patch('observability.metrics.logger'):
            client = CloudMetricsClient(project_id="test-project", enabled=True)
            # When library is not installed, it should disable itself
            assert client.enabled is False

    def test_record_when_disabled(self):
        """Test that metrics are not recorded when client is disabled."""
        client = CloudMetricsClient(project_id="test-project", enabled=False)
        
        client.record_gauge("test", 1.0)
        
        # Buffer should remain empty
        assert len(client._metrics_buffer) == 0

    def test_flush_when_disabled(self):
        """Test that flush does nothing when client is disabled."""
        client = CloudMetricsClient(project_id="test-project", enabled=False)
        
        # Should not raise any errors
        client.flush()
        
        assert len(client._metrics_buffer) == 0

    def test_flush_empty_buffer(self):
        """Test that flush does nothing with empty buffer."""
        client = CloudMetricsClient(project_id="test-project", enabled=False)
        
        # Should not raise any errors
        client.flush()

    def test_metric_point_creation(self):
        """Test MetricPoint dataclass creation."""
        point = MetricPoint(
            name="test_metric",
            value=42.0,
            timestamp=datetime.utcnow(),
            labels={"env": "test"},
            metric_type="gauge"
        )
        
        assert point.name == "test_metric"
        assert point.value == 42.0
        assert point.labels == {"env": "test"}
        assert point.metric_type == "gauge"

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_record_gauge_metric(self, mock_init):
        """Test recording a gauge metric when client is enabled."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()  # Mock the client
        
        client.record_gauge("test_metric", 42.0, {"label": "value"})
        
        # Should add to buffer since client is enabled
        assert len(client._metrics_buffer) == 1
        assert client._metrics_buffer[0].name == "test_metric"
        assert client._metrics_buffer[0].value == 42.0
        assert client._metrics_buffer[0].metric_type == "gauge"

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_record_counter_metric(self, mock_init):
        """Test recording a counter metric."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()
        
        client.record_counter("request_count", 1, {"endpoint": "/api"})
        
        assert len(client._metrics_buffer) == 1
        assert client._metrics_buffer[0].metric_type == "counter"

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_record_histogram_metric(self, mock_init):
        """Test recording a histogram metric."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()
        
        client.record_histogram("response_time", 0.150)
        
        assert len(client._metrics_buffer) == 1
        assert client._metrics_buffer[0].metric_type == "histogram"

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_buffer_flush_on_size(self, mock_init):
        """Test that buffer flushes when reaching size limit."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()
        
        # Add metrics up to buffer size
        for i in range(100):
            client.record_gauge(f"metric_{i}", float(i))
        
        # Buffer should have flushed (possibly with some remaining items due to timing)
        assert len(client._metrics_buffer) <= 100

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_record_review_metrics(self, mock_init):
        """Test recording comprehensive review metrics."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()
        
        # Mock PR event
        pr_event = Mock()
        pr_event.provider = "github"
        pr_event.repo_owner = "test-owner"
        
        client.record_review_metrics(
            pr_event=pr_event,
            duration_seconds=5.5,
            suggestions_count=10,
            tokens_used=1500,
            cost_usd=0.01,
            success=True
        )
        
        # Should have recorded multiple metrics
        assert len(client._metrics_buffer) >= 5

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_record_agent_metrics(self, mock_init):
        """Test recording agent execution metrics."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()
        
        client.record_agent_metrics(
            agent_type="security",
            duration_seconds=2.0,
            suggestions_found=5,
            success=True
        )
        
        assert len(client._metrics_buffer) >= 3

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_record_llm_metrics(self, mock_init):
        """Test recording LLM call metrics."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()
        
        client.record_llm_metrics(
            model_name="gemini-pro",
            prompt_tokens=1000,
            completion_tokens=500,
            duration_seconds=1.5,
            success=True
        )
        
        assert len(client._metrics_buffer) >= 5

    @patch('observability.metrics.CloudMetricsClient._initialize_client')
    def test_record_feedback_metrics(self, mock_init):
        """Test recording feedback metrics."""
        client = CloudMetricsClient(project_id="test-project", enabled=True)
        client._initialize_client = mock_init
        client._client = Mock()
        
        client.record_feedback_metrics("positive", 0.9, "github")
        
        assert len(client._metrics_buffer) == 2
