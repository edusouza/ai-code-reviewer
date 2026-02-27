"""Tests for cost tracker module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock

from cost.tracker import CostTracker, CostRecord, ModelPricing


class TestCostTracker:
    """Test cost tracker functionality."""

    def test_calculate_cost_gemini_pro(self):
        """Test cost calculation for Gemini Pro model."""
        tracker = CostTracker()
        
        cost = tracker.calculate_cost("gemini-pro", 1000, 500)
        
        # Expected: (1000/1000) * 0.00025 + (500/1000) * 0.0005 = 0.00025 + 0.00025 = 0.0005
        expected = 0.00025 + 0.00025
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_gemini_flash(self):
        """Test cost calculation for Gemini Flash model."""
        tracker = CostTracker()
        
        cost = tracker.calculate_cost("gemini-flash", 2000, 1000)
        
        # Expected: (2000/1000) * 0.0001 + (1000/1000) * 0.0002 = 0.0002 + 0.0002 = 0.0004
        expected = 0.0002 + 0.0002
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_gpt4(self):
        """Test cost calculation for GPT-4 model."""
        tracker = CostTracker()
        
        cost = tracker.calculate_cost("gpt-4", 1000, 500)
        
        # Expected: (1000/1000) * 0.03 + (500/1000) * 0.06 = 0.03 + 0.03 = 0.06
        expected = 0.03 + 0.03
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation falls back to Gemini Pro for unknown models."""
        tracker = CostTracker()
        
        cost = tracker.calculate_cost("unknown-model", 1000, 500)
        
        # Should use Gemini Pro pricing as default
        expected = 0.00025 + 0.00025
        assert cost == pytest.approx(expected, rel=1e-6)

    @pytest.mark.asyncio
    async def test_track_call(self):
        """Test tracking a single API call."""
        tracker = CostTracker()
        
        record = await tracker.track_call(
            model="gemini-pro",
            operation="analyze_code",
            prompt_tokens=1000,
            completion_tokens=500,
            pr_number=123,
            repo="test/repo",
            metadata={"agent": "security"}
        )
        
        assert isinstance(record, CostRecord)
        assert record.model == "gemini-pro"
        assert record.operation == "analyze_code"
        assert record.prompt_tokens == 1000
        assert record.completion_tokens == 500
        assert record.pr_number == 123
        assert record.repo == "test/repo"
        assert record.metadata["agent"] == "security"
        assert record.cost_usd > 0
        assert record.timestamp is not None

    @pytest.mark.asyncio
    async def test_track_review(self):
        """Test tracking a complete review."""
        tracker = CostTracker()
        
        record = await tracker.track_review(
            pr_number=456,
            repo="owner/repo",
            model="gemini-pro",
            total_prompt_tokens=5000,
            total_completion_tokens=2000,
            num_files=3,
            num_suggestions=10
        )
        
        assert isinstance(record, CostRecord)
        assert record.model == "gemini-pro"
        assert record.operation == "full_review"
        assert record.pr_number == 456
        assert record.repo == "owner/repo"
        assert record.metadata["num_files"] == 3
        assert record.metadata["num_suggestions"] == 10
        assert record.metadata["cost_per_file"] > 0
        assert record.metadata["cost_per_suggestion"] > 0

    @pytest.mark.asyncio
    async def test_get_pr_cost_found(self, mocker):
        """Test retrieving cost for a PR that exists."""
        # Mock Firestore
        mock_db = mocker.Mock()
        mock_doc = mocker.Mock()
        mock_doc.to_dict.return_value = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": "gemini-pro",
            "operation": "full_review",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "cost_usd": 0.001,
            "pr_number": 123,
            "repo": "test/repo",
            "metadata": {}
        }
        
        mock_query = mocker.Mock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = mocker.Mock()
        mock_collection.where.return_value = mock_collection
        mock_collection.limit.return_value = mock_query
        
        mock_db.collection.return_value = mock_collection
        
        tracker = CostTracker(firestore_db=mock_db)
        
        # Mock the async executor
        mocker.patch(
            'asyncio.get_event_loop',
            return_value=mocker.Mock(
                run_in_executor=lambda *args, **kwargs: [mock_doc]
            )
        )
        
        record = await tracker.get_pr_cost(123, "test/repo")
        
        assert record is not None
        assert record.pr_number == 123
        assert record.repo == "test/repo"

    @pytest.mark.asyncio
    async def test_get_pr_cost_not_found(self, mocker):
        """Test retrieving cost for a PR that doesn't exist."""
        mock_db = mocker.Mock()
        mock_collection = mocker.Mock()
        mock_collection.where.return_value = mock_collection
        mock_collection.limit.return_value = mocker.Mock(stream=lambda: [])
        mock_db.collection.return_value = mock_collection
        
        tracker = CostTracker(firestore_db=mock_db)
        
        # Mock the async executor to return empty list
        mocker.patch(
            'asyncio.get_event_loop',
            return_value=mocker.Mock(
                run_in_executor=lambda *args, **kwargs: []
            )
        )
        
        record = await tracker.get_pr_cost(999, "nonexistent/repo")
        
        assert record is None

    @pytest.mark.asyncio
    async def test_get_daily_cost(self, mocker):
        """Test getting total cost for a day."""
        mock_db = mocker.Mock()
        mock_doc1 = mocker.Mock()
        mock_doc1.to_dict.return_value = {"cost_usd": 0.5}
        mock_doc2 = mocker.Mock()
        mock_doc2.to_dict.return_value = {"cost_usd": 0.3}
        
        mock_collection = mocker.Mock()
        mock_collection.where.return_value = mock_collection
        mock_collection.stream.return_value = [mock_doc1, mock_doc2]
        mock_db.collection.return_value = mock_collection
        
        tracker = CostTracker(firestore_db=mock_db)
        
        # Mock the async executor
        mocker.patch(
            'asyncio.get_event_loop',
            return_value=mocker.Mock(
                run_in_executor=lambda *args, **kwargs: [mock_doc1, mock_doc2]
            )
        )
        
        cost = await tracker.get_daily_cost()
        
        assert cost == 0.8

    def test_model_pricing_values(self):
        """Test that model pricing values are reasonable."""
        assert ModelPricing.GEMINI_PRO.value < ModelPricing.GPT4.value
        assert ModelPricing.GEMINI_FLASH.value < ModelPricing.GEMINI_PRO.value
        assert ModelPricing.GPT35.value < ModelPricing.GPT4.value
